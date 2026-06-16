"""Deterministic news intelligence layer for richer financial briefings.

This module extracts lightweight signals from collected news before the LLM
runs. The output is intentionally transparent and dependency-free so it can be
used both in prompts and in the Streamlit UI without extra API calls.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

CATEGORY_KEYWORDS = {
    "macro": [
        "fed",
        "federal reserve",
        "rate",
        "inflation",
        "cpi",
        "pce",
        "jobs",
        "payroll",
        "gdp",
        "央行",
        "美联储",
        "利率",
        "通胀",
        "就业",
        "经济",
    ],
    "stocks": [
        "stock",
        "equity",
        "nasdaq",
        "s&p",
        "dow",
        "earnings",
        "shares",
        "ipo",
        "股票",
        "A股",
        "港股",
        "财报",
        "上市",
    ],
    "commodities": [
        "oil",
        "crude",
        "gold",
        "copper",
        "commodity",
        "opec",
        "原油",
        "黄金",
        "铜",
        "大宗商品",
    ],
    "crypto": ["bitcoin", "btc", "ethereum", "eth", "crypto", "token", "比特币", "以太坊", "加密"],
    "forex": ["dollar", "yen", "euro", "yuan", "fx", "currency", "美元", "日元", "欧元", "人民币", "外汇"],
    "bonds": ["treasury", "yield", "bond", "debt", "credit", "国债", "收益率", "债券", "信用"],
}

POSITIVE_KEYWORDS = [
    "surge",
    "jump",
    "rally",
    "gain",
    "rise",
    "soar",
    "record",
    "beat",
    "upgrade",
    "optimism",
    "涨",
    "大涨",
    "反弹",
    "突破",
    "创新高",
    "利好",
]
NEGATIVE_KEYWORDS = [
    "crash",
    "plunge",
    "drop",
    "fall",
    "decline",
    "slump",
    "miss",
    "downgrade",
    "risk",
    "fear",
    "warning",
    "跌",
    "大跌",
    "暴跌",
    "下跌",
    "风险",
    "利空",
]
URGENCY_KEYWORDS = [
    "breaking",
    "urgent",
    "unexpected",
    "surprise",
    "shock",
    "crisis",
    "default",
    "war",
    "tariff",
    "sanction",
    "突发",
    "紧急",
    "意外",
    "危机",
    "违约",
    "战争",
    "关税",
    "制裁",
]

CATEGORY_ASSET_WATCHLIST = {
    "macro": ["US Treasuries / TLT", "US Dollar / DXY", "S&P 500 / SPY", "Gold / GLD"],
    "stocks": ["S&P 500 / SPY", "Nasdaq 100 / QQQ", "Dow Jones / DIA"],
    "commodities": ["Crude Oil / CL", "Gold / GLD", "Copper / HG"],
    "crypto": ["Bitcoin / BTC-USD", "Ethereum / ETH-USD", "Coinbase / COIN"],
    "forex": ["US Dollar / DXY", "EUR/USD", "USD/JPY", "USD/CNH"],
    "bonds": ["US Treasuries / TLT", "10Y Yield / ^TNX", "High Yield Credit / HYG"],
    "other": ["S&P 500 / SPY"],
}

CATEGORY_ASSET_WATCHLIST_CHINA = {
    "macro": ["上证综合 / 000001.SS", "国债国债 / 10Y (10年期国债)", "人民币汇率 / FXCNH"],
    "stocks": ["上证指数 / 000001.SS", "沪深300 / 000300.SS", "创业板指 / 399006.SZ", "上证50 / 000016.SS"],
    "commodities": ["贵金属 / 黄金", "有色金属 / 铜", "原油 / 布伦特"],
    "crypto": ["比特币 / BTC-USD"],
    "forex": ["人民币 / USD/CNH", "人民币离岸 / CNH"],
    "bonds": ["国债 / 10Y (10年期国债)", "政策利率 / 货币", "信用利差 / 信用债"],
    "other": ["上证指数 / 000001.SS"],
}

ASSET_KEYWORDS_CN = {
    "上证综合 / 000001.SS": ["上证", "上证指数", "上证综指", "000001"],
    "国债国债 / 10Y (10年期国债)": ["国债", "10年", "10y", "债息", "债券收益率"],
    "人民币汇率 / FXCNH": ["人民币", "cnh", "美元人民币", "usd/cnh", "汇率"],
    "上证指数 / 000001.SS": ["上证指数", "上证", "上证综指", "000001.ss"],
    "沪深300 / 000300.SS": ["沪深300", "000300"],
    "创业板指 / 399006.SZ": ["创业板", "399006", "创业板指"],
    "上证50 / 000016.SS": ["上证50", "上证 50", "000016"],
    "贵金属 / 黄金": ["黄金", "gold", "贵金属", "金价"],
    "有色金属 / 铜": ["铜", "copper", "有色"],
    "原油 / 布伦特": ["原油", "石油", "brent", "油价"],
    "比特币 / BTC-USD": ["比特币", "bitcoin", "btc", "crypto", "加密"],
    "人民币 / USD/CNH": ["人民币", "人民币兑美元", "美元人民币", "usd/cnh", "cnh"],
    "人民币离岸 / CNH": ["离岸人民币", "cnh", "人民币"],
    "国债 / 10Y (10年期国债)": ["债券", "国债", "10y", "十年期"],
    "政策利率 / 货币": ["利率", "政策利率", "降准", "降息", "加息"],
    "信用利差 / 信用债": ["信用债", "信用利差", "cds", "债券风险"],
}

CHINA_SCOPE_KEYWORDS = [
    "a股",
    "沪深",
    "上证",
    "深证",
    "创业板",
    "中国",
    "china",
    "a-share",
    "a share",
]

ASSET_KEYWORDS = {
    "US Treasuries / TLT": ["treasury", "yield", "bond", "debt", "国债", "收益率", "债券"],
    "10Y Yield / ^TNX": ["10-year", "10 year", "10y", "yield", "收益率"],
    "High Yield Credit / HYG": ["credit", "default", "debt", "信用", "违约"],
    "US Dollar / DXY": ["dollar", "dxy", "美元"],
    "EUR/USD": ["euro", "eur", "欧元"],
    "USD/JPY": ["yen", "jpy", "日元"],
    "USD/CNH": ["yuan", "renminbi", "cnh", "人民币", "离岸人民币"],
    "S&P 500 / SPY": ["s&p", "sp500", "s&p 500", "stock", "equity", "stocks", "股票", "美股"],
    "Nasdaq 100 / QQQ": ["nasdaq", "tech", "ai", "semiconductor", "科技", "芯片", "人工智能"],
    "Dow Jones / DIA": ["dow", "industrial", "道指"],
    "Crude Oil / CL": ["oil", "crude", "opec", "原油", "石油"],
    "Gold / GLD": ["gold", "bullion", "黄金"],
    "Copper / HG": ["copper", "铜"],
    "Bitcoin / BTC-USD": ["bitcoin", "btc", "比特币"],
    "Ethereum / ETH-USD": ["ethereum", "eth", "以太坊"],
    "Coinbase / COIN": ["coinbase", "coin", "crypto exchange", "加密交易所"],
}

TIME_HORIZON_KEYWORDS = {
    "intraday": ["breaking", "urgent", "today", "now", "24 hours", "intraday", "突发", "紧急", "今日", "今天", "盘中"],
    "near_term": ["this week", "week", "upcoming", "next", "meeting", "deadline", "本周", "近期", "下周", "会议"],
    "medium_term": ["month", "quarter", "guidance", "outlook", "policy path", "月", "季度", "财报季", "展望", "路径"],
}

CATEGORY_LABELS = {
    "en": {
        "macro": "Macro",
        "stocks": "Stocks",
        "commodities": "Commodities",
        "crypto": "Crypto",
        "forex": "Forex",
        "bonds": "Bonds",
        "other": "Other",
    },
    "zh": {
        "macro": "宏观",
        "stocks": "股票",
        "commodities": "大宗商品",
        "crypto": "加密资产",
        "forex": "外汇",
        "bonds": "债券",
        "other": "其他",
    },
}

TONE_LABELS = {
    "en": {"positive": "Positive", "negative": "Negative", "neutral": "Neutral"},
    "zh": {"positive": "正面", "negative": "负面", "neutral": "中性"},
}

MARKET_REGIME_LABELS = {
    "en": {
        "risk_on": "Risk-on watch",
        "risk_off": "Risk-off watch",
        "two_way": "Two-way volatility",
        "event_driven": "Event-driven watch",
        "neutral": "Neutral / wait-and-see",
    },
    "zh": {
        "risk_on": "风险偏好观察",
        "risk_off": "避险观察",
        "two_way": "双向波动",
        "event_driven": "事件驱动观察",
        "neutral": "中性 / 观望",
    },
}

DIVERSITY_LABELS = {
    "en": {
        "broad": "Broad coverage",
        "balanced": "Balanced coverage",
        "concentrated": "Concentrated coverage",
        "single_source": "Single-source coverage",
    },
    "zh": {
        "broad": "覆盖面广",
        "balanced": "覆盖均衡",
        "concentrated": "来源集中",
        "single_source": "单一来源",
    },
}

CONVICTION_LABELS = {
    "en": {
        "high": "High conviction",
        "moderate": "Moderate conviction",
        "low": "Low conviction",
    },
    "zh": {
        "high": "高置信度",
        "moderate": "中等置信度",
        "low": "低置信度",
    },
}

TENSION_LABELS = {
    "en": {
        "directional": "Directional narrative",
        "mixed": "Mixed but tilted",
        "conflicted": "Conflicting signals",
        "low_signal": "Low signal density",
    },
    "zh": {
        "directional": "方向明确",
        "mixed": "多空混合但有倾向",
        "conflicted": "信号冲突",
        "low_signal": "信号密度偏低",
    },
}

HORIZON_LABELS = {
    "en": {
        "intraday": "Intraday / 24h",
        "near_term": "Near-term / 1w",
        "medium_term": "Medium-term / 1m+",
    },
    "zh": {
        "intraday": "盘中 / 24小时",
        "near_term": "短期 / 一周",
        "medium_term": "中期 / 一月以上",
    },
}

HORIZON_PRIORITY = {
    "intraday": 3,
    "near_term": 2,
    "medium_term": 1,
}


@dataclass
class NewsSignal:
    """Signal extracted from a single news item."""

    title: str
    source: str = "Unknown"
    category: str = "other"
    tone: str = "neutral"
    urgency: int = 0
    reason: str = ""
    asset_impacts: list[str] = field(default_factory=list)
    time_horizon: str = "near_term"


@dataclass
class NewsIntelligence:
    """Aggregated intelligence generated from collected news."""

    signals: list[NewsSignal] = field(default_factory=list)
    category_counts: Counter = field(default_factory=Counter)
    tone_counts: Counter = field(default_factory=Counter)
    top_sources: Counter = field(default_factory=Counter)
    asset_counts: Counter = field(default_factory=Counter)
    horizon_counts: Counter = field(default_factory=Counter)

    @property
    def dominant_category(self) -> str:
        if not self.category_counts:
            return "other"
        classified_counts = Counter({k: v for k, v in self.category_counts.items() if k != "other"})
        if classified_counts:
            return classified_counts.most_common(1)[0][0]
        return "other"

    @property
    def dominant_tone(self) -> str:
        if not self.tone_counts:
            return "neutral"
        return self.tone_counts.most_common(1)[0][0]

    @property
    def high_urgency(self) -> list[NewsSignal]:
        return sorted([s for s in self.signals if s.urgency > 0], key=lambda s: s.urgency, reverse=True)

    @property
    def total_articles(self) -> int:
        return sum(self.top_sources.values())

    @property
    def source_diversity_score(self) -> float:
        if not self.total_articles:
            return 0.0
        return min(1.0, len(self.top_sources) / self.total_articles)

    @property
    def source_diversity_key(self) -> str:
        if len(self.top_sources) <= 1:
            return "single_source"
        if self.source_diversity_score >= 0.75:
            return "broad"
        if self.source_diversity_score >= 0.45:
            return "balanced"
        return "concentrated"

    @property
    def market_regime_key(self) -> str:
        positive = self.tone_counts.get("positive", 0)
        negative = self.tone_counts.get("negative", 0)
        urgent_negative = any(signal.urgency > 0 and signal.tone == "negative" for signal in self.signals)
        if negative > positive and (urgent_negative or self.high_urgency):
            return "risk_off"
        if positive > negative and not urgent_negative:
            return "risk_on"
        if positive and negative:
            return "two_way"
        if self.high_urgency:
            return "event_driven"
        return "neutral"

    @property
    def primary_assets(self) -> list[str]:
        return [asset for asset, _count in self.asset_counts.most_common(5)]

    @property
    def dominant_category_share(self) -> float:
        if not self.total_articles:
            return 0.0
        return self.category_counts.get(self.dominant_category, 0) / self.total_articles

    @property
    def tone_alignment_share(self) -> float:
        if not self.total_articles:
            return 0.0
        directional_count = max(self.tone_counts.get("positive", 0), self.tone_counts.get("negative", 0))
        return directional_count / self.total_articles

    @property
    def urgent_share(self) -> float:
        if not self.total_articles:
            return 0.0
        return len(self.high_urgency) / self.total_articles

    @property
    def asset_focus_share(self) -> float:
        if not self.total_articles or not self.asset_counts:
            return 0.0
        return self.asset_counts.most_common(1)[0][1] / self.total_articles

    @property
    def conviction_score(self) -> int:
        if not self.total_articles:
            return 0
        source_breadth = self.source_diversity_score if len(self.top_sources) > 1 else 0.0
        theme_strength = 0.0 if self.dominant_category == "other" else self.dominant_category_share
        urgent_strength = min(1.0, self.urgent_share * 2)
        score = round(
            100
            * (
                0.25 * source_breadth
                + 0.25 * theme_strength
                + 0.20 * self.tone_alignment_share
                + 0.15 * urgent_strength
                + 0.15 * self.asset_focus_share
            )
        )
        return max(0, min(100, score))

    @property
    def conviction_key(self) -> str:
        if self.conviction_score >= 75:
            return "high"
        if self.conviction_score >= 50:
            return "moderate"
        return "low"

    @property
    def narrative_tension_key(self) -> str:
        positive = self.tone_counts.get("positive", 0)
        negative = self.tone_counts.get("negative", 0)
        if positive and negative:
            conflict_ratio = min(positive, negative) / max(positive, negative)
            return "conflicted" if conflict_ratio >= 0.75 else "mixed"
        if self.tone_alignment_share >= 0.5:
            return "directional"
        return "low_signal"

    @property
    def dominant_horizon(self) -> str:
        urgent_counts = Counter(signal.time_horizon for signal in self.high_urgency)
        if urgent_counts:
            return max(
                urgent_counts.items(),
                key=lambda item: (item[1], HORIZON_PRIORITY.get(item[0], 0)),
            )[0]
        if not self.horizon_counts:
            return "near_term"
        return max(
            self.horizon_counts.items(),
            key=lambda item: (item[1], HORIZON_PRIORITY.get(item[0], 0)),
        )[0]


def classify_category(text: str) -> str:
    """Classify a news item into a broad market category."""
    text_lower = text.lower()
    scores = {
        category: sum(1 for keyword in keywords if keyword.lower() in text_lower)
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    category, score = max(scores.items(), key=lambda item: item[1])
    return category if score > 0 else "other"


def classify_tone(text: str) -> str:
    """Classify basic market tone from keyword evidence."""
    text_lower = text.lower()
    pos = sum(1 for keyword in POSITIVE_KEYWORDS if keyword.lower() in text_lower)
    neg = sum(1 for keyword in NEGATIVE_KEYWORDS if keyword.lower() in text_lower)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def urgency_score(text: str) -> int:
    """Return a simple urgency score based on catalyst/risk keywords."""
    text_lower = text.lower()
    return sum(1 for keyword in URGENCY_KEYWORDS if keyword.lower() in text_lower)


def _is_china_scope(text: str) -> bool:
    """判断文本是否偏向 A 股/中国市场。"""
    normalized = (text or "").lower()
    return any(keyword.lower() in normalized for keyword in CHINA_SCOPE_KEYWORDS)


def infer_asset_impacts(
    text: str,
    category: str,
    max_assets: int = 5,
    asset_keyword_map: dict[str, list[str]] | None = None,
    category_watchlist: dict[str, list[str]] | None = None,
) -> list[str]:
    """Infer a compact asset watchlist affected by a news item."""
    text_lower = text.lower()
    impacts: list[str] = []
    keyword_map = asset_keyword_map or ASSET_KEYWORDS
    watchlist_map = category_watchlist or CATEGORY_ASSET_WATCHLIST

    for asset, keywords in keyword_map.items():
        if any(keyword.lower() in text_lower for keyword in keywords):
            impacts.append(asset)

    for asset in watchlist_map.get(category, watchlist_map.get("other", [])):
        if asset not in impacts:
            impacts.append(asset)

    return impacts[:max_assets]


def infer_time_horizon(text: str) -> str:
    """Infer the most relevant validation horizon for a news item."""
    text_lower = text.lower()
    for horizon in ("intraday", "near_term", "medium_term"):
        if any(keyword.lower() in text_lower for keyword in TIME_HORIZON_KEYWORDS[horizon]):
            return horizon
    return "near_term"


def build_news_intelligence(
    news_items: list[dict],
    max_signals: int = 8,
    market_scope: str = "auto",
    query: str | None = None,
) -> NewsIntelligence:
    """Build deterministic intelligence signals from collected news items."""
    item_text = " ".join(str(item.get("title", "")) for item in news_items)
    scope = market_scope
    if scope == "auto":
        scope = "china_a_share" if _is_china_scope(f"{query or ''} {item_text}") else "global"
    asset_map = ASSET_KEYWORDS_CN if scope == "china_a_share" else ASSET_KEYWORDS
    watchlist_map = CATEGORY_ASSET_WATCHLIST_CHINA if scope == "china_a_share" else CATEGORY_ASSET_WATCHLIST

    signals: list[NewsSignal] = []
    for item in news_items:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        description = str(item.get("description") or item.get("full_content") or "")
        source = str(item.get("source") or "Unknown")
        text = f"{title}\n{description}"
        category = classify_category(text)
        tone = classify_tone(text)
        urgency = urgency_score(text)
        asset_impacts = infer_asset_impacts(
            text=text,
            category=category,
            max_assets=5,
            asset_keyword_map=asset_map,
            category_watchlist=watchlist_map,
        )
        time_horizon = infer_time_horizon(text)
        reason_bits = []
        if category != "other":
            reason_bits.append(category)
        if tone != "neutral":
            reason_bits.append(tone)
        if urgency:
            reason_bits.append(f"urgency={urgency}")
        signals.append(
            NewsSignal(
                title=title,
                source=source,
                category=category,
                tone=tone,
                urgency=urgency,
                reason=", ".join(reason_bits) or "baseline coverage",
                asset_impacts=asset_impacts,
                time_horizon=time_horizon,
            )
        )

    category_counts = Counter(signal.category for signal in signals)
    tone_counts = Counter(signal.tone for signal in signals)
    top_sources = Counter(signal.source for signal in signals)
    asset_counts = Counter(asset for signal in signals for asset in signal.asset_impacts)
    horizon_counts = Counter(signal.time_horizon for signal in signals)
    ranked = sorted(signals, key=lambda s: (s.urgency, s.tone != "neutral", s.category != "other"), reverse=True)
    return NewsIntelligence(
        signals=ranked[:max_signals],
        category_counts=category_counts,
        tone_counts=tone_counts,
        top_sources=top_sources,
        asset_counts=asset_counts,
        horizon_counts=horizon_counts,
    )


def _scenario_playbook_lines(intelligence: NewsIntelligence, language: str) -> list[str]:
    labels = CATEGORY_LABELS.get(language, CATEGORY_LABELS["en"])
    tone_labels = TONE_LABELS.get(language, TONE_LABELS["en"])
    horizon_labels = HORIZON_LABELS.get(language, HORIZON_LABELS["en"])
    dominant = labels.get(intelligence.dominant_category, intelligence.dominant_category)
    tone = tone_labels.get(intelligence.dominant_tone, intelligence.dominant_tone)
    horizon = horizon_labels.get(intelligence.dominant_horizon, intelligence.dominant_horizon)

    primary_asset = intelligence.primary_assets[0] if intelligence.primary_assets else None

    if language == "zh":
        asset_note = f"，优先观察 **{primary_asset}**" if primary_asset else ""
        return [
            f"- 基准情景：**{dominant}** 仍是主线，当前新闻基调偏 **{tone}**{asset_note}，验证窗口为 **{horizon}**。",
            "- 乐观情景：正面催化剂从单点扩散到多来源、多资产，且高优先级风险信号降温。",
            "- 悲观情景：高优先级催化剂升级，或负面叙事从主要来源扩散到更广新闻面。",
            f"- 需要验证：关注 **{dominant}** 新闻是否延续、来源覆盖是否扩大，以及紧迫信号是否跨资产传导。",
        ]

    asset_note = f", with **{primary_asset}** as the first asset to validate" if primary_asset else ""
    return [
        f"- Base case: **{dominant}** remains the main driver with a **{tone}** news tone{asset_note}; validation window: **{horizon}**.",
        "- Bull case: Positive catalysts broaden across sources and assets while high-priority risk signals fade.",
        "- Bear case: High-priority catalysts intensify or negative narratives spread beyond the leading sources.",
        f"- Confirmation watch: Track **{dominant}** follow-through, source breadth, and whether urgent items become cross-asset.",
    ]


def _narrative_monitor_lines(intelligence: NewsIntelligence, language: str) -> list[str]:
    conviction_labels = CONVICTION_LABELS.get(language, CONVICTION_LABELS["en"])
    tension_labels = TENSION_LABELS.get(language, TENSION_LABELS["en"])
    conviction = conviction_labels.get(intelligence.conviction_key, intelligence.conviction_key)
    tension = tension_labels.get(intelligence.narrative_tension_key, intelligence.narrative_tension_key)
    dominant_share = f"{intelligence.dominant_category_share:.0%}"
    tone_share = f"{intelligence.tone_alignment_share:.0%}"

    if language == "zh":
        return [
            f"- 叙事置信度：**{conviction} ({intelligence.conviction_score}/100)**，衡量来源广度、主题集中度、语气一致性、紧迫性和资产聚焦度。",
            f"- 叙事张力：**{tension}**；主导主题占比 **{dominant_share}**，方向性语气占比 **{tone_share}**。",
            "- 使用方式：高置信度适合作为报告主线；信号冲突时应降低仓位假设并强调等待确认。",
        ]

    return [
        f"- Narrative conviction: **{conviction} ({intelligence.conviction_score}/100)** across source breadth, theme focus, tone alignment, urgency, and asset focus.",
        f"- Narrative tension: **{tension}**; dominant theme share is **{dominant_share}** and directional tone share is **{tone_share}**.",
        "- How to use it: high conviction can anchor the report thesis; conflicting signals should reduce position-size assumptions and emphasize confirmation.",
    ]


def _decision_checklist_lines(intelligence: NewsIntelligence, language: str) -> list[str]:
    horizon_labels = HORIZON_LABELS.get(language, HORIZON_LABELS["en"])
    regime_labels = MARKET_REGIME_LABELS.get(language, MARKET_REGIME_LABELS["en"])
    horizon = horizon_labels.get(intelligence.dominant_horizon, intelligence.dominant_horizon)
    regime = regime_labels.get(intelligence.market_regime_key, intelligence.market_regime_key)
    assets = ", ".join(intelligence.primary_assets[:3]) or "N/A"

    if language == "zh":
        return [
            f"- 验证窗口：**{horizon}**；优先围绕 **{regime}** 假设跟踪价格反应。",
            f"- 重点资产：{assets}。若这些资产与新闻方向同向确认，提升信号权重。",
            "- 升级条件：多来源继续跟进、资产反应扩大、且高优先级催化剂数量上升。",
            "- 降级条件：主要来源停止跟进、资产价格反向运行，或后续新闻证伪初始叙事。",
        ]

    return [
        f"- Validation window: **{horizon}**; monitor price action against the **{regime}** hypothesis first.",
        f"- Priority assets: {assets}. Upgrade confidence if they confirm the news direction.",
        "- Upgrade trigger: broader source follow-through, wider asset confirmation, and rising high-priority catalysts.",
        "- Downgrade trigger: source follow-through fades, assets move against the narrative, or later reports invalidate it.",
    ]


def render_news_intelligence_markdown(
    news_items: list[dict],
    language: str = "en",
    max_signals: int = 8,
    market_scope: str = "auto",
    query: str | None = None,
) -> str:
    """Render a concise market-intelligence dashboard in Markdown."""
    intelligence = build_news_intelligence(
        news_items,
        max_signals=max_signals,
        market_scope=market_scope,
        query=query,
    )
    labels = CATEGORY_LABELS.get(language, CATEGORY_LABELS["en"])
    tone_labels = TONE_LABELS.get(language, TONE_LABELS["en"])
    regime_labels = MARKET_REGIME_LABELS.get(language, MARKET_REGIME_LABELS["en"])
    diversity_labels = DIVERSITY_LABELS.get(language, DIVERSITY_LABELS["en"])
    horizon_labels = HORIZON_LABELS.get(language, HORIZON_LABELS["en"])
    conviction_labels = CONVICTION_LABELS.get(language, CONVICTION_LABELS["en"])
    tension_labels = TENSION_LABELS.get(language, TENSION_LABELS["en"])
    if not intelligence.signals:
        return ""

    if language == "zh":
        title = "## 新闻智能信号图谱"
        category_line = "- 主导主题"
        tone_line = "- 新闻基调"
        regime_line = "- 市场状态"
        diversity_line = "- 来源覆盖"
        source_line = "- 主要来源"
        asset_line = "- 资产影响雷达"
        horizon_line = "- 验证窗口"
        conviction_line = "- 叙事置信度"
        tension_line = "- 叙事张力"
        urgency_title = "### 高优先级催化剂"
        asset_title = "### 资产影响雷达"
        narrative_title = "### 叙事置信度监控"
        checklist_title = "### 决策检查清单"
        signal_title = "### 代表性信号"
        playbook_title = "### 情景推演与验证清单"
        no_urgency = "- 暂无明显高紧迫性催化剂。"
        no_assets = "- 暂无可映射的重点资产。"
        asset_signal_suffix = "条信号"
    else:
        title = "## News Intelligence Signal Map"
        category_line = "- Dominant theme"
        tone_line = "- News tone"
        regime_line = "- Market regime"
        diversity_line = "- Coverage diversity"
        source_line = "- Leading sources"
        asset_line = "- Asset impact radar"
        horizon_line = "- Validation horizon"
        conviction_line = "- Narrative conviction"
        tension_line = "- Narrative tension"
        urgency_title = "### High-Priority Catalysts"
        asset_title = "### Asset Impact Radar"
        narrative_title = "### Narrative Conviction Monitor"
        checklist_title = "### Decision Checklist"
        signal_title = "### Representative Signals"
        playbook_title = "### Scenario Playbook"
        no_urgency = "- No high-urgency catalyst detected."
        no_assets = "- No mapped asset focus detected."
        asset_signal_suffix = "signal(s)"

    top_sources = ", ".join(f"{source} ({count})" for source, count in intelligence.top_sources.most_common(3))
    top_assets = ", ".join(f"{asset} ({count})" for asset, count in intelligence.asset_counts.most_common(3))
    lines = [
        title,
        f"{category_line}: **{labels.get(intelligence.dominant_category, intelligence.dominant_category)}**",
        f"{tone_line}: **{tone_labels.get(intelligence.dominant_tone, intelligence.dominant_tone)}**",
        f"{regime_line}: **{regime_labels.get(intelligence.market_regime_key, intelligence.market_regime_key)}**",
        f"{diversity_line}: **{diversity_labels.get(intelligence.source_diversity_key, intelligence.source_diversity_key)}** "
        f"({intelligence.source_diversity_score:.0%})",
        f"{source_line}: {top_sources or 'N/A'}",
        f"{asset_line}: {top_assets or 'N/A'}",
        f"{horizon_line}: **{horizon_labels.get(intelligence.dominant_horizon, intelligence.dominant_horizon)}**",
        f"{conviction_line}: **{conviction_labels.get(intelligence.conviction_key, intelligence.conviction_key)}** "
        f"({intelligence.conviction_score}/100)",
        f"{tension_line}: **{tension_labels.get(intelligence.narrative_tension_key, intelligence.narrative_tension_key)}**",
        "",
        urgency_title,
    ]

    urgent = intelligence.high_urgency[:3]
    if urgent:
        for signal in urgent:
            lines.append(
                f"- [{labels.get(signal.category, signal.category)} | "
                f"{tone_labels.get(signal.tone, signal.tone)}] {signal.title} — {signal.source}"
            )
    else:
        lines.append(no_urgency)

    lines.extend(["", asset_title])
    if intelligence.asset_counts:
        for asset, count in intelligence.asset_counts.most_common(5):
            lines.append(f"- {asset}: {count} {asset_signal_suffix}")
    else:
        lines.append(no_assets)

    lines.extend(["", narrative_title, *_narrative_monitor_lines(intelligence, language)])
    lines.extend(["", checklist_title, *_decision_checklist_lines(intelligence, language)])

    lines.extend(["", signal_title])
    for signal in intelligence.signals[:5]:
        lines.append(
            f"- [{labels.get(signal.category, signal.category)} | "
            f"{tone_labels.get(signal.tone, signal.tone)} | "
            f"{horizon_labels.get(signal.time_horizon, signal.time_horizon)} | urgency {signal.urgency}] "
            f"{signal.title} — {signal.source}"
        )

    lines.extend(["", playbook_title, *_scenario_playbook_lines(intelligence, language)])

    return "\n".join(lines)
