"""
技术指标计算模块 (Technical Indicators).

提供纯函数式的技术指标计算，不依赖网络请求，便于测试与复用：
- SMA / EMA（均线）
- RSI（相对强弱指数）
- MACD（指数平滑异同移动平均）
- Bollinger Bands（布林带）
- ATR（平均真实波幅）
- Stochastic Oscillator（KD 随机指标）

以及一个综合的 `analyze_indicators`，将上述指标汇总为可解读的信号字典，
可被情绪评分模型、图表叠加、报告生成等模块复用。

所有函数对输入长度不足的情况都做了防御性处理，返回 NaN / None 而非抛错。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ──────────────────── 基础指标 ────────────────────


def sma(series: pd.Series, window: int) -> pd.Series:
    """简单移动平均 Simple Moving Average。"""
    return series.rolling(window=window, min_periods=1).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """指数移动平均 Exponential Moving Average。"""
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    相对强弱指数 RSI（0-100）。

    使用 Wilder 平滑法。数据不足时返回 NaN 序列。
    """
    if series is None or len(series) < 2:
        return pd.Series([np.nan] * (len(series) if series is not None else 0), index=getattr(series, "index", None))

    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # 当 avg_loss 为 0（全涨）时 RSI = 100；当 avg_gain 为 0（全跌）时 RSI = 0。
    out = out.where(avg_loss != 0.0, 100.0)
    out = out.where(avg_gain != 0.0, out.where(avg_loss == 0.0, 0.0) if (avg_loss == 0.0).any() else out)
    return out


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """
    MACD 指标。返回含 macd / signal / hist 三列的 DataFrame。
    """
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def bollinger_bands(
    series: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """
    布林带。返回含 mid / upper / lower / pctb / bandwidth 列的 DataFrame。
    pctb = %B 指标（价格在带内相对位置，0=下轨，1=上轨）。
    """
    mid = series.rolling(window=window, min_periods=1).mean()
    std = series.rolling(window=window, min_periods=1).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    span = (upper - lower).replace(0.0, np.nan)
    pctb = (series - lower) / span
    bandwidth = span / mid.replace(0.0, np.nan)
    return pd.DataFrame(
        {"mid": mid, "upper": upper, "lower": lower, "pctb": pctb, "bandwidth": bandwidth}
    )


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """平均真实波幅 Average True Range，衡量波动性。"""
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=1).mean()


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> pd.DataFrame:
    """随机指标 KD。返回含 k / d 列的 DataFrame（0-100）。"""
    lowest = low.rolling(window=k_period, min_periods=1).min()
    highest = high.rolling(window=k_period, min_periods=1).max()
    span = (highest - lowest).replace(0.0, np.nan)
    k = 100.0 * (close - lowest) / span
    d = k.rolling(window=d_period, min_periods=1).mean()
    return pd.DataFrame({"k": k, "d": d})


# ──────────────────── 综合信号 ────────────────────


@dataclass
class IndicatorSnapshot:
    """某一时点各技术指标的最新读数与解读。"""

    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    bb_pctb: float | None = None
    bb_bandwidth: float | None = None
    stoch_k: float | None = None
    stoch_d: float | None = None
    atr_pct: float | None = None  # ATR 占价格百分比
    sma20: float | None = None
    sma50: float | None = None
    # 归一化到 [-1, 1] 的技术面综合分
    tech_score: float = 0.0
    signals: list[str] = field(default_factory=list)


def _last_valid(series: pd.Series) -> float | None:
    """取序列最后一个非 NaN 值。"""
    if series is None or len(series) == 0:
        return None
    s = series.dropna()
    if s.empty:
        return None
    return float(s.iloc[-1])


def _rsi_score(value: float | None) -> tuple[float, str | None]:
    if value is None:
        return 0.0, None
    if value >= 70:
        return -0.6, f"RSI {value:.0f} overbought"
    if value <= 30:
        return 0.6, f"RSI {value:.0f} oversold"
    # 50 为中枢，映射到 [-0.4, 0.4]
    return max(-0.4, min(0.4, (value - 50) / 50.0 * 0.8)), None


def _macd_score(hist: float | None) -> tuple[float, str | None]:
    if hist is None:
        return 0.0, None
    if hist > 0:
        return 0.4, "MACD bullish"
    if hist < 0:
        return -0.4, "MACD bearish"
    return 0.0, None


def _bb_score(pctb: float | None) -> tuple[float, str | None]:
    if pctb is None:
        return 0.0, None
    if pctb >= 1.0:
        return -0.5, "Above upper Bollinger band"
    if pctb <= 0.0:
        return 0.5, "Below lower Bollinger band"
    # pctb 0.5 中枢
    return max(-0.3, min(0.3, (0.5 - pctb) * 0.6)), None


def _stoch_score(k: float | None) -> tuple[float, str | None]:
    if k is None:
        return 0.0, None
    if k >= 80:
        return -0.4, f"Stochastic {k:.0f} overbought"
    if k <= 20:
        return 0.4, f"Stochastic {k:.0f} oversold"
    return 0.0, None


def _ma_cross_score(sma20: float | None, sma50: float | None) -> tuple[float, str | None]:
    if sma20 is None or sma50 is None:
        return 0.0, None
    if sma20 > sma50:
        return 0.3, "SMA20 > SMA50 (uptrend)"
    if sma20 < sma50:
        return -0.3, "SMA20 < SMA50 (downtrend)"
    return 0.0, None


def analyze_indicators(ohlcv: pd.DataFrame) -> IndicatorSnapshot:
    """
    从 OHLCV DataFrame 计算所有指标，汇总为 IndicatorSnapshot。

    要求包含 'Close' 列；'High'/'Low' 缺失时相关指标跳过。
    """
    snap = IndicatorSnapshot()
    if ohlcv is None or ohlcv.empty or "Close" not in ohlcv.columns:
        return snap

    close = ohlcv["Close"].astype(float)
    high = ohlcv["High"].astype(float) if "High" in ohlcv.columns else close
    low = ohlcv["Low"].astype(float) if "Low" in ohlcv.columns else close

    snap.rsi = _last_valid(rsi(close))
    macd_df = macd(close)
    snap.macd = _last_valid(macd_df["macd"])
    snap.macd_signal = _last_valid(macd_df["signal"])
    snap.macd_hist = _last_valid(macd_df["hist"])

    bb = bollinger_bands(close)
    snap.bb_pctb = _last_valid(bb["pctb"])
    snap.bb_bandwidth = _last_valid(bb["bandwidth"])

    st_df = stochastic(high, low, close)
    snap.stoch_k = _last_valid(st_df["k"])
    snap.stoch_d = _last_valid(st_df["d"])

    atr_val = _last_valid(atr(high, low, close))
    last_price = _last_valid(close)
    if atr_val is not None and last_price:
        snap.atr_pct = atr_val / last_price * 100.0

    snap.sma20 = _last_valid(sma(close, 20))
    snap.sma50 = _last_valid(sma(close, 50)) if len(close) >= 2 else None

    # 综合评分：加权平均各子分
    weighted = [
        (_rsi_score(snap.rsi), 0.25),
        (_macd_score(snap.macd_hist), 0.25),
        (_bb_score(snap.bb_pctb), 0.20),
        (_stoch_score(snap.stoch_k), 0.15),
        (_ma_cross_score(snap.sma20, snap.sma50), 0.15),
    ]
    total = 0.0
    for (score, note), weight in weighted:
        total += score * weight
        if note:
            snap.signals.append(note)
    snap.tech_score = max(-1.0, min(1.0, total))
    return snap


def score_from_close(close: pd.Series) -> float:
    """便捷函数：仅有收盘价序列时估算技术面综合分 [-1, 1]。"""
    if close is None or len(close) < 2:
        return 0.0
    df = pd.DataFrame({"Close": close.astype(float)})
    return analyze_indicators(df).tech_score
