from unittest.mock import MagicMock

import pytest

pytest.importorskip("ccxt")
from agents.crypto_tools import analyze_crypto
from core.wyckoff_engine import FunnelConfig
from core.wyckoff_structure import detect_structure_triggers
from integrations.crypto_data import (
    CryptoDataError,
    CryptoDataSource,
    CryptoQuery,
    _derivatives,
    _fetch_pages,
    _validate_market,
    normalize_candles,
)

STEP = 86400000
NOW = 1700000000000 // STEP * STEP


def candles(count=321):
    return [[NOW - (320 - i) * STEP, 10, 12, 9, 11, 100 + i] for i in range(count)]


def test_normalize_closed_utc_sorted_deduped_and_decimal_prices():
    rows = candles()
    rows[0][1:5] = [0.000001, 0.000002, 0.0000009, 0.0000011]
    frame = normalize_candles(list(reversed(rows)) + [rows[0]], CryptoQuery(), NOW + 1000)
    assert len(frame) == 320
    assert frame.timestamp.is_monotonic_increasing
    assert frame.open.iloc[0] == 0.000001
    assert str(frame.date.dt.tz) == "UTC"
    assert frame.timestamp.iloc[-1] == NOW - STEP


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -1])
def test_invalid_price_fails_closed(bad):
    rows = candles()
    rows[100][4] = bad
    with pytest.raises(CryptoDataError):
        normalize_candles(rows, CryptoQuery(), NOW + 1000)


def test_gaps_stale_short_and_impossible_prices_fail():
    for rows in [candles()[::2], candles()[:100], candles()[-20:]]:
        with pytest.raises(CryptoDataError):
            normalize_candles(rows, CryptoQuery(), NOW + 1000)
    rows = candles()
    rows[50][2] = 8
    with pytest.raises(CryptoDataError):
        normalize_candles(rows, CryptoQuery(), NOW)


def test_swap_symbol_and_market_validation():
    query = CryptoQuery(symbol="eth/usdt", market="swap")
    assert query.symbol == "ETH/USDT:USDT"
    for market in [{"spot": True}, {"swap": True, "linear": False}, {"swap": True, "linear": True, "active": False}]:
        with pytest.raises(CryptoDataError):
            _validate_market(market, query)
    _validate_market({"swap": True, "linear": True, "active": True}, query)
    with pytest.raises(ValueError):
        CryptoQuery(exchange="arbitrary-url")


def test_pagination_moves_forward_and_stops_without_progress():
    client = MagicMock(has={"fetchOHLCV": True}, timeframes={"1d": "1d"})
    client.milliseconds.return_value = NOW + 1000
    rows = candles()
    client.fetch_ohlcv.side_effect = [rows[:200], rows[200:]]
    assert len(_fetch_pages(client, CryptoQuery())) == 321
    assert client.fetch_ohlcv.call_args_list[1].kwargs["since"] == rows[200][0]
    client.fetch_ohlcv.side_effect = None
    client.fetch_ohlcv.return_value = rows[:200]
    client.fetch_ohlcv.reset_mock()
    _fetch_pages(client, CryptoQuery())
    assert client.fetch_ohlcv.call_count == 2


def test_cache_reuses_exchange_without_paid_fallback(monkeypatch):
    source = CryptoDataSource()
    client = MagicMock(has={"fetchOHLCV": True}, timeframes={"1d": "1d"})
    client.market.return_value = {"spot": True, "base": "BTC", "quote": "USDT"}
    client.milliseconds.return_value = NOW + 1000
    client.fetch_ohlcv.return_value = candles()
    monkeypatch.setattr(source, "_client", lambda query: client)
    first, meta = source.fetch(CryptoQuery())
    first.loc[0, "close"] = 999
    second, _ = source.fetch(CryptoQuery())
    assert second.close.iloc[0] != 999
    assert client.fetch_ohlcv.call_count == 1
    assert meta["source"] == "ccxt:okx"


def test_derivative_missing_values_are_not_zero():
    client = MagicMock(has={"fetchFundingRate": False, "fetchOpenInterest": True})
    client.fetch_open_interest.return_value = {"openInterestAmount": None}
    result = _derivatives(client, "BTC/USDT:USDT")
    assert result["funding"] == {"status": "unsupported"}
    assert result["open_interest"]["status"] == "unavailable"
    assert result["open_interest"]["openInterestAmount"] is None


def test_analysis_uses_existing_structure_engine():
    frame = normalize_candles(candles(), CryptoQuery(), NOW + 1000)
    metadata = {"quote": "USDT", "last_candle_at": frame.date.iloc[-1].isoformat()}
    source = MagicMock()
    source.fetch.return_value = frame, metadata
    result = analyze_crypto(source, CryptoQuery())
    expected = detect_structure_triggers(["BTC/USDT"], {"BTC/USDT": frame}, FunnelConfig())
    assert result["signals"] == [key.upper() for key, hits in expected.triggers.items() if hits]
    assert result["mode"] == "observation_only"
    assert len(result["candles"]) == 320
    assert result["latest_close"] == 11
