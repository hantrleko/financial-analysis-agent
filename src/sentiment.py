"""
市场情绪分析模块。
从 yfinance 拉取多维度市场数据，计算各资产/板块的多空信号，
输出综合情绪评分、机会与风险识别。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf

from src.config import SENTIMENT_ASSETS, SENTIMENT_THRESHOLDS, VIX_LEVELS

logger = logging.getLogger(__name__)


# ──────────────────── 数据结构 ────────────────────


@dataclass
class AssetSignal:
    """单个资产的情绪信号。"""

    name: str
    ticker: str
    sector: str
    group: str
    price: float = 0.0
    change_1d_pct: float = 0.0
    change_5d_pct: float = 0.0
    change_20d_pct: float = 0.0
    above_ma20: bool = False  # 价格在 20 日均线之上
    volume_ratio: float = 1.0  # 当日成交量 / 20 日均量
    score: float = 0.0  # 综合情绪分 (-1 ~ +1)
    signal: str = "neutral"  # strong_bull / bull / neutral / bear / strong_bear
    reason: str = ""


@dataclass
class SectorSummary:
    """板块/类别的聚合情绪。"""

    name: str
    avg_score: float = 0.0
    signal: str = "neutral"
    bull_count: int = 0
    bear_count: int = 0
    neutral_count: int = 0
    assets: list[AssetSignal] = field(default_factory=list)


@dataclass
class SentimentReport:
    """完整的市场情绪报告。"""

    overall_score: float = 0.0  # 整体情绪分 (-1 ~ +1)
    overall_signal: str = "neutral"
    bull_count: int = 0
    bear_count: int = 0
    neutral_count: int = 0
    vix_value: float = 0.0
    vix_level: str = "normal"  # low / normal / elevated / high / extreme
    sectors: dict[str, SectorSummary] = field(default_factory=dict)
    opportunities: list[AssetSignal] = field(default_factory=list)
    risks: list[AssetSignal] = field(default_factory=list)
    all_assets: list[AssetSignal] = field(default_factory=list)
    timestamp: str = ""


# ──────────────────── 核心计算 ────────────────────


class MarketSentimentAnalyzer:
    @staticmethod
    def analyze() -> SentimentReport:
        """执行完整的市场情绪分析，返回 SentimentReport。"""
        from datetime import datetime

        report = SentimentReport(timestamp=datetime.now().isoformat())

        # 1. 收集所有 ticker
        all_tickers = []
        ticker_meta = {}  # ticker -> (name, sector, group)
        for group_name, assets in SENTIMENT_ASSETS.items():
            for asset_name, info in assets.items():
                t = info["ticker"]
                all_tickers.append(t)
                ticker_meta[t] = (asset_name, info["sector"], group_name)

        # 2. 批量下载 1 个月数据（足够计算 20 日均线）
        logger.info("Fetching market data for %d assets...", len(all_tickers))
        try:
            data = yf.download(all_tickers, period="1mo", progress=False)
        except Exception:
            logger.exception("Failed to download market data for sentiment analysis")
            return report

        if data.empty:
            logger.warning("No market data returned for sentiment analysis")
            return report

        close = data["Close"]
        volume = data.get("Volume")

        # 3. 逐资产计算信号
        asset_signals = []
        for ticker, (name, sector, group) in ticker_meta.items():
            sig = MarketSentimentAnalyzer._compute_asset_signal(
                name,
                ticker,
                sector,
                group,
                close,
                volume,
            )
            if sig:
                asset_signals.append(sig)

        report.all_assets = asset_signals

        # 4. VIX 解读
        vix_sig = next((s for s in asset_signals if s.ticker == "^VIX"), None)
        if vix_sig:
            report.vix_value = vix_sig.price
            report.vix_level = MarketSentimentAnalyzer._classify_vix(vix_sig.price)

        # 5. 按板块聚合
        groups = {}
        for sig in asset_signals:
            if sig.group not in groups:
                groups[sig.group] = SectorSummary(name=sig.group)
            groups[sig.group].assets.append(sig)

        for grp in groups.values():
            scores = [a.score for a in grp.assets]
            grp.avg_score = sum(scores) / len(scores) if scores else 0.0
            grp.signal = MarketSentimentAnalyzer._classify_score(grp.avg_score)
            grp.bull_count = sum(1 for a in grp.assets if a.score > SENTIMENT_THRESHOLDS["bull"])
            grp.bear_count = sum(1 for a in grp.assets if a.score < SENTIMENT_THRESHOLDS["bear"])
            grp.neutral_count = len(grp.assets) - grp.bull_count - grp.bear_count

        report.sectors = groups

        # 6. 整体情绪（排除 VIX，VIX 反向指标单独处理）
        non_vix = [s for s in asset_signals if s.sector != "volatility"]
        if non_vix:
            report.overall_score = sum(s.score for s in non_vix) / len(non_vix)
            # VIX 调整：高 VIX 压低整体情绪
            if report.vix_level == "high":
                report.overall_score -= 0.1
            elif report.vix_level == "extreme":
                report.overall_score -= 0.2
            elif report.vix_level == "low":
                report.overall_score += 0.05
            report.overall_score = max(-1.0, min(1.0, report.overall_score))

        report.overall_signal = MarketSentimentAnalyzer._classify_score(report.overall_score)
        report.bull_count = sum(1 for s in non_vix if s.score > SENTIMENT_THRESHOLDS["bull"])
        report.bear_count = sum(1 for s in non_vix if s.score < SENTIMENT_THRESHOLDS["bear"])
        report.neutral_count = len(non_vix) - report.bull_count - report.bear_count

        # 7. 识别机会与风险
        report.opportunities = sorted(
            [s for s in non_vix if s.score >= SENTIMENT_THRESHOLDS["bull"]],
            key=lambda x: x.score,
            reverse=True,
        )
        report.risks = sorted(
            [s for s in non_vix if s.score <= SENTIMENT_THRESHOLDS["bear"]],
            key=lambda x: x.score,
        )

        logger.info(
            "Sentiment analysis complete: overall=%.2f (%s), bull=%d, bear=%d, neutral=%d",
            report.overall_score,
            report.overall_signal,
            report.bull_count,
            report.bear_count,
            report.neutral_count,
        )
        return report

    @staticmethod
    def _compute_asset_signal(
        name: str,
        ticker: str,
        sector: str,
        group: str,
        close_df: pd.DataFrame | pd.Series,
        volume_df: pd.DataFrame | pd.Series | None,
    ) -> AssetSignal | None:
        """计算单个资产的多空信号。"""
        try:
            # 处理 MultiIndex 或单列
            if isinstance(close_df, pd.DataFrame) and ticker in close_df.columns:
                series = close_df[ticker].dropna()
            elif isinstance(close_df, pd.Series):
                series = close_df.dropna()
            else:
                return None

            if len(series) < 2:
                return None

            sig = AssetSignal(name=name, ticker=ticker, sector=sector, group=group)
            sig.price = float(series.iloc[-1])

            # 涨跌幅
            if len(series) >= 2:
                sig.change_1d_pct = (series.iloc[-1] / series.iloc[-2] - 1) * 100
            if len(series) >= 5:
                sig.change_5d_pct = (series.iloc[-1] / series.iloc[-5] - 1) * 100
            if len(series) >= 20:
                sig.change_20d_pct = (series.iloc[-1] / series.iloc[-20] - 1) * 100

            # 20 日均线
            if len(series) >= 20:
                ma20 = series.rolling(20).mean().iloc[-1]
                sig.above_ma20 = sig.price > ma20

            # 成交量比率
            if volume_df is not None:
                try:
                    if isinstance(volume_df, pd.DataFrame) and ticker in volume_df.columns:
                        vol_series = volume_df[ticker].dropna()
                    elif isinstance(volume_df, pd.Series):
                        vol_series = volume_df.dropna()
                    else:
                        vol_series = None

                    if vol_series is not None and len(vol_series) >= 20:
                        avg_vol = vol_series.rolling(20).mean().iloc[-1]
                        if avg_vol > 0:
                            sig.volume_ratio = float(vol_series.iloc[-1] / avg_vol)
                except Exception:
                    pass

            # 综合评分 (-1 ~ +1)
            sig.score = MarketSentimentAnalyzer._compute_score(sig)
            sig.signal = MarketSentimentAnalyzer._classify_score(sig.score)
            sig.reason = MarketSentimentAnalyzer._build_reason(sig)

            return sig

        except Exception:
            logger.debug("Failed to compute signal for %s (%s)", name, ticker, exc_info=True)
            return None

    @staticmethod
    def _compute_score(sig: AssetSignal) -> float:
        """
        多因子评分模型：
        - 日涨跌 (权重 30%)
        - 5 日动量 (权重 25%)
        - 20 日趋势 (权重 20%)
        - 均线位置 (权重 15%)
        - 放量程度 (权重 10%)

        VIX 特殊处理：反向评分（VIX 上涨 = 市场恐惧 = 看空）
        """
        is_vix = sig.sector == "volatility"

        # 日涨跌 → 映射到 [-1, 1]，±3% 饱和
        day_score = max(-1.0, min(1.0, sig.change_1d_pct / 3.0))
        if is_vix:
            day_score = -day_score

        # 5 日动量 → ±5% 饱和
        week_score = max(-1.0, min(1.0, sig.change_5d_pct / 5.0))
        if is_vix:
            week_score = -week_score

        # 20 日趋势 → ±10% 饱和
        month_score = max(-1.0, min(1.0, sig.change_20d_pct / 10.0))
        if is_vix:
            month_score = -month_score

        # 均线位置
        ma_score = 0.5 if sig.above_ma20 else -0.5
        if is_vix:
            ma_score = -ma_score

        # 放量信号：量比 > 1.5 放大趋势方向
        vol_score = 0.0
        if sig.volume_ratio > 1.5:
            vol_score = 0.5 if day_score > 0 else -0.5
        elif sig.volume_ratio < 0.5:
            vol_score = -0.2  # 缩量，趋势减弱

        total = day_score * 0.30 + week_score * 0.25 + month_score * 0.20 + ma_score * 0.15 + vol_score * 0.10
        return max(-1.0, min(1.0, total))

    @staticmethod
    def _classify_score(score: float) -> str:
        if score >= SENTIMENT_THRESHOLDS["strong_bull"]:
            return "strong_bull"
        elif score >= SENTIMENT_THRESHOLDS["bull"]:
            return "bull"
        elif score <= SENTIMENT_THRESHOLDS["strong_bear"]:
            return "strong_bear"
        elif score <= SENTIMENT_THRESHOLDS["bear"]:
            return "bear"
        return "neutral"

    @staticmethod
    def _classify_vix(value: float) -> str:
        if value < VIX_LEVELS["low"]:
            return "low"
        elif value < VIX_LEVELS["normal"]:
            return "normal"
        elif value < VIX_LEVELS["elevated"]:
            return "elevated"
        elif value < VIX_LEVELS["high"]:
            return "high"
        return "extreme"

    @staticmethod
    def _build_reason(sig: AssetSignal) -> str:
        """生成简短的信号解释。"""
        parts = []
        if abs(sig.change_1d_pct) >= 0.5:
            direction = "↑" if sig.change_1d_pct > 0 else "↓"
            parts.append(f"1D {direction}{abs(sig.change_1d_pct):.1f}%")
        if abs(sig.change_5d_pct) >= 1.0:
            direction = "↑" if sig.change_5d_pct > 0 else "↓"
            parts.append(f"5D {direction}{abs(sig.change_5d_pct):.1f}%")
        if sig.above_ma20:
            parts.append("above MA20")
        else:
            parts.append("below MA20")
        if sig.volume_ratio > 1.5:
            parts.append(f"vol {sig.volume_ratio:.1f}x")
        return " | ".join(parts) if parts else "low volatility"


# ──────────────────── 辅助：信号转 emoji ────────────────────

SIGNAL_EMOJI = {
    "strong_bull": "🟢🟢",
    "bull": "🟢",
    "neutral": "⚪",
    "bear": "🔴",
    "strong_bear": "🔴🔴",
}

SIGNAL_LABEL = {
    "en": {
        "strong_bull": "Strong Bull",
        "bull": "Bullish",
        "neutral": "Neutral",
        "bear": "Bearish",
        "strong_bear": "Strong Bear",
    },
    "zh": {
        "strong_bull": "强看多",
        "bull": "看多",
        "neutral": "中性",
        "bear": "看空",
        "strong_bear": "强看空",
    },
}

VIX_EMOJI = {
    "en": {
        "low": "😎 Greed (Low Vol)",
        "normal": "😐 Normal",
        "elevated": "😟 Caution",
        "high": "😰 Fear",
        "extreme": "🚨 Extreme Fear",
    },
    "zh": {
        "low": "😎 贪婪（低波动）",
        "normal": "😐 正常",
        "elevated": "😟 警惕",
        "high": "😰 恐惧",
        "extreme": "🚨 极度恐惧",
    },
}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    analyzer = MarketSentimentAnalyzer()
    result = analyzer.analyze()
    logger.info("Overall: %+.2f (%s)", result.overall_score, result.overall_signal)
    logger.info("VIX: %.1f (%s)", result.vix_value, result.vix_level)
    logger.info("Bull: %d  Bear: %d  Neutral: %d", result.bull_count, result.bear_count, result.neutral_count)
    logger.info("--- Opportunities ---")
    for a in result.opportunities:
        logger.info("  %s: %+.2f (%s)", a.name, a.score, a.reason)
    logger.info("--- Risks ---")
    for a in result.risks:
        logger.info("  %s: %+.2f (%s)", a.name, a.score, a.reason)
