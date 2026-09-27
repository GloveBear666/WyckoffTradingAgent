"""Crypto observations using the existing price/volume structure engine."""

from dataclasses import asdict

from core.price_targets import calc_atr
from core.wyckoff_engine import FunnelConfig
from core.wyckoff_structure import detect_structure_triggers
from integrations.crypto_data import CryptoDataSource, CryptoQuery


def analyze_crypto(source: CryptoDataSource, query: CryptoQuery) -> dict:
    frame, metadata = source.fetch(query)
    structure = detect_structure_triggers([query.symbol], {query.symbol: frame}, FunnelConfig())
    trading_range = structure.trading_ranges.get(query.symbol)
    signals = [key.upper() for key, hits in structure.triggers.items() if hits]
    close = frame.close
    result = {
        "metadata": metadata,
        "latest_close": float(close.iloc[-1]),
        "change_pct": float(frame.pct_chg.iloc[-1]),
        "ma20": float(close.tail(20).mean()),
        "ma50": float(close.tail(50).mean()),
        "ma200": float(close.tail(200).mean()) if len(frame) >= 200 else None,
        "atr14": calc_atr(frame.high, frame.low, close),
        "signals": signals,
        "stage": structure.stage_map.get(query.symbol, "未识别出有效交易区间"),
        "trading_range": asdict(trading_range) if trading_range else None,
        "mode": "observation_only",
        "note": "沿用原项目结构算法；参数尚未经过加密市场回测。均线/ATR 窗口单位为所选周期的 K 线根数。",
        "candles": [
            {
                "time": int(row.timestamp / 1000),
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
            }
            for row in frame.itertuples()
        ],
    }
    result["summary"] = (
        f"{query.symbol} · {query.exchange} · {query.market} · {query.timeframe}\n"
        f"最新收盘 {result['latest_close']:.10g} {metadata['quote']}，本根变化 {result['change_pct']:+.2f}%。\n"
        f"结构：{result['stage']}；信号：{', '.join(signals) or '未触发'}。\n"
        f"已检查 {len(frame)} 根已收盘 K 线，截至 {metadata['last_candle_at']}。\n{result['note']}"
    )
    return result
