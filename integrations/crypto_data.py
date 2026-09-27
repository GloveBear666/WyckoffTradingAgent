"""Public CCXT data, isolated from all paid equity providers and trading APIs."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

import ccxt
import pandas as pd

EXCHANGES = ("okx", "binance", "bybit")
TIMEFRAMES = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}


class CryptoDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class CryptoQuery:
    exchange: str = "okx"
    symbol: str = "BTC/USDT"
    market: str = "spot"
    timeframe: str = "1d"
    limit: int = 320

    def __post_init__(self):
        if self.exchange not in EXCHANGES or self.market not in {"spot", "swap"}:
            raise ValueError("请选择支持的交易所及 spot / swap 市场")
        if self.timeframe not in TIMEFRAMES or not 100 <= self.limit <= 500:
            raise ValueError("周期须为 15m / 1h / 4h / 1d，K 线数量须为 100–500")
        symbol = self.symbol.strip().upper()
        if self.market == "swap" and ":" not in symbol and "/" in symbol:
            symbol += ":" + symbol.split("/")[1]
        if len(symbol) > 50 or "/" not in symbol:
            raise ValueError("请使用交易对格式，例如 BTC/USDT")
        object.__setattr__(self, "symbol", symbol)


class CryptoDataSource:
    def __init__(self):
        self._clients: dict = {}
        self._cache: dict = {}
        self._lock = threading.Lock()

    def fetch(self, query: CryptoQuery) -> tuple[pd.DataFrame, dict]:
        # Reuse instances so CCXT's limiter covers successive requests as well.
        with self._lock:
            cached = self._cache.get(query)
            if cached and time.monotonic() - cached[0] < 30:
                return cached[1].copy(), dict(cached[2])
            try:
                client = self._client(query)
                market = client.market(query.symbol)
                _validate_market(market, query)
                rows = _fetch_pages(client, query)
                frame = normalize_candles(rows, query, client.milliseconds())
                meta = _metadata(client, query, market, frame)
            except ccxt.BaseError as exc:
                raise CryptoDataError(
                    f"{query.exchange} 公开行情不可用（{type(exc).__name__}），请稍后重试或切换交易所"
                ) from exc
            if len(self._cache) >= 64:
                self._cache.pop(next(iter(self._cache)))
            self._cache[query] = (time.monotonic(), frame, meta)
            return frame.copy(), dict(meta)

    def _client(self, query: CryptoQuery):
        key = (query.exchange, query.market)
        if key not in self._clients:
            client = getattr(ccxt, query.exchange)(
                {"enableRateLimit": True, "timeout": 15000, "options": {"defaultType": query.market}}
            )
            client.load_markets()
            self._clients[key] = client
        return self._clients[key]


def _validate_market(market: dict, query: CryptoQuery):
    if not market.get(query.market) or market.get("active") is False:
        raise CryptoDataError("交易对不存在、已停用或市场类型不匹配")
    if query.market == "swap" and not market.get("linear"):
        raise CryptoDataError("当前仅支持线性永续合约，请选择 BTC/USDT:USDT 等交易对")


def _fetch_pages(client, query: CryptoQuery) -> list:
    if not client.has.get("fetchOHLCV") or query.timeframe not in client.timeframes:
        raise CryptoDataError("该交易所不支持所选 K 线周期")
    step = TIMEFRAMES[query.timeframe] * 1000
    now = client.milliseconds()
    since = now // step * step - query.limit * step
    rows = []
    for _ in range(8):
        batch = client.fetch_ohlcv(query.symbol, query.timeframe, since=since, limit=min(query.limit + 1, 200))
        if not batch:
            break
        rows.extend(batch)
        next_since = max(int(row[0]) for row in batch) + step
        if next_since <= since or next_since >= now:
            break
        since = next_since
    return rows


def normalize_candles(rows: list, query: CryptoQuery, now_ms: int) -> pd.DataFrame:
    if not rows or any(len(row) != 6 for row in rows):
        raise CryptoDataError("交易所返回了空行情或无效 K 线")
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if not df.map(lambda x: pd.notna(x) and math.isfinite(x)).all().all():
        raise CryptoDataError("K 线包含缺失或非有限数值")
    df = df.drop_duplicates("timestamp", keep="last").sort_values("timestamp")
    step = TIMEFRAMES[query.timeframe] * 1000
    df = df[df.timestamp + step <= now_ms].tail(query.limit).reset_index(drop=True)
    if len(df) < 100:
        raise CryptoDataError(f"只有 {len(df)} 根已收盘 K 线，至少需要 100 根")
    prices = df[["open", "high", "low", "close"]]
    if (prices <= 0).any().any() or (df.volume < 0).any():
        raise CryptoDataError("K 线价格或成交量无效")
    if (df.high < prices.max(axis=1)).any() or (df.low > prices.min(axis=1)).any():
        raise CryptoDataError("K 线最高/最低价格关系无效")
    if (df.timestamp % step != 0).any() or (df.timestamp.diff().dropna() != step).any():
        raise CryptoDataError("K 线时间未对齐或存在缺口；请切换交易对/周期后重试")
    if now_ms - int(df.timestamp.iloc[-1]) >= 3 * step:
        raise CryptoDataError("交易所 K 线已过期，停止生成分析")
    df["date"] = pd.to_datetime(df.timestamp, unit="ms", utc=True)
    df["pct_chg"] = df.close.pct_change().fillna(0) * 100
    return df


def _metadata(client, query: CryptoQuery, market: dict, frame: pd.DataFrame) -> dict:
    meta = {
        "source": f"ccxt:{query.exchange}",
        "exchange": query.exchange,
        "market": query.market,
        "symbol": query.symbol,
        "timeframe": query.timeframe,
        "bars": len(frame),
        "timezone": "UTC",
        "closed_candles_only": True,
        "last_candle_at": frame.date.iloc[-1].isoformat(),
        "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "base": market["base"],
        "quote": market["quote"],
        "volume_unit": "exchange_native",
        "contract_size": market.get("contractSize"),
        "warnings": [],
    }
    if query.market == "swap":
        meta["derivatives"] = _derivatives(client, query.symbol)
    if len(frame) < query.limit:
        meta["warnings"].append(f"请求 {query.limit} 根，仅返回 {len(frame)} 根已收盘 K 线")
    return meta


def _derivatives(client, symbol: str) -> dict:
    result = {}
    fields = {
        "funding": (
            "fetchFundingRate",
            "fetch_funding_rate",
            ("fundingRate", "fundingTimestamp", "nextFundingTimestamp", "interval"),
        ),
        "open_interest": (
            "fetchOpenInterest",
            "fetch_open_interest",
            ("openInterestAmount", "openInterestValue", "timestamp"),
        ),
    }
    for key, (capability, method, columns) in fields.items():
        if not client.has.get(capability):
            result[key] = {"status": "unsupported"}
            continue
        try:
            raw = getattr(client, method)(symbol)
            values = {field: raw.get(field) for field in columns}
            result[key] = {"status": "ok" if any(v is not None for v in values.values()) else "unavailable", **values}
        except ccxt.BaseError:
            result[key] = {"status": "unavailable"}
    return result
