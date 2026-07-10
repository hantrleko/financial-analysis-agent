"""技术指标模块单元测试。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators import (
    IndicatorSnapshot,
    analyze_indicators,
    atr,
    bollinger_bands,
    ema,
    macd,
    rsi,
    score_from_close,
    sma,
    stochastic,
)


def _make_ohlcv(prices: list[float]) -> pd.DataFrame:
    close = pd.Series(prices, dtype=float)
    high = close * 1.01
    low = close * 0.99
    open_ = close.shift(1).fillna(close.iloc[0])
    vol = pd.Series([1000] * len(prices), dtype=float)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol})


def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    result = sma(s, 2)
    assert result.iloc[-1] == 4.5  # (4+5)/2


def test_ema_basic():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    result = ema(s, 3)
    assert len(result) == 5
    assert result.iloc[-1] > result.iloc[0]


def test_rsi_all_gains_is_100():
    s = pd.Series(range(1, 40), dtype=float)  # strictly increasing
    r = rsi(s)
    assert r.dropna().iloc[-1] > 90  # near 100


def test_rsi_all_losses_is_low():
    s = pd.Series(range(40, 1, -1), dtype=float)  # strictly decreasing
    r = rsi(s)
    assert r.dropna().iloc[-1] < 10


def test_rsi_range_bounded():
    rng = np.random.default_rng(42)
    s = pd.Series(100 + rng.standard_normal(100).cumsum())
    r = rsi(s).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_rsi_short_series_returns_nan():
    s = pd.Series([1.0])
    r = rsi(s)
    assert len(r) == 1


def test_macd_columns():
    s = pd.Series(100 + np.arange(60), dtype=float)
    m = macd(s)
    assert set(m.columns) == {"macd", "signal", "hist"}
    assert len(m) == 60


def test_bollinger_bands_ordering():
    s = pd.Series(100 + np.random.default_rng(1).standard_normal(50).cumsum())
    bb = bollinger_bands(s)
    valid = bb.dropna()
    assert (valid["upper"] >= valid["mid"]).all()
    assert (valid["mid"] >= valid["lower"]).all()


def test_atr_non_negative():
    df = _make_ohlcv(list(100 + np.random.default_rng(2).standard_normal(50).cumsum()))
    a = atr(df["High"], df["Low"], df["Close"]).dropna()
    assert (a >= 0).all()


def test_stochastic_bounded():
    df = _make_ohlcv(list(100 + np.random.default_rng(3).standard_normal(50).cumsum()))
    st = stochastic(df["High"], df["Low"], df["Close"]).dropna()
    assert (st["k"] >= 0).all() and (st["k"] <= 100).all()


def test_analyze_indicators_returns_snapshot():
    df = _make_ohlcv(list(100 + np.arange(60, dtype=float)))
    snap = analyze_indicators(df)
    assert isinstance(snap, IndicatorSnapshot)
    assert snap.rsi is not None
    assert -1.0 <= snap.tech_score <= 1.0


def test_analyze_indicators_empty():
    snap = analyze_indicators(pd.DataFrame())
    assert snap.tech_score == 0.0
    assert snap.rsi is None


def test_overbought_uptrend_flags_mean_reversion():
    # A near-vertical uptrend is overbought → RSI/Stochastic warn (score can dip negative),
    # but trend signals (MACD, SMA cross) stay bullish.
    df = _make_ohlcv(list(np.linspace(100, 200, 80)))
    snap = analyze_indicators(df)
    assert "MACD bullish" in snap.signals
    assert any("SMA20 > SMA50" in s for s in snap.signals)
    assert snap.rsi is not None and snap.rsi > 60


def test_score_from_close():
    close = pd.Series(np.linspace(100, 150, 60))
    score = score_from_close(close)
    assert -1.0 <= score <= 1.0


def test_score_from_close_short():
    assert score_from_close(pd.Series([100.0])) == 0.0
