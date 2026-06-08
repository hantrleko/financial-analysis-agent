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


@dataclass
class NewsSignal:
    """Signal extracted from a single news item."""

    title: str
    source: str = "Unknown"
    category: str = "other"
    tone: str = "neutral"
    urgency: int = 0
    reason: str = ""


@dataclass
class NewsIntelligence:
    """Aggregated intelligence generated from collected news."""

    signals: list[NewsSignal] = field(default_factory=list)
    category_counts: Counter = field(default_factory=Counter)
    tone_counts: Counter = field(default_factory=Counter)
    top_sources: Counter = field(default_factory=Counter)

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


def build_news_intelligence(news_items: list[dict], max_signals: int = 8) -> NewsIntelligence:
    """Build deterministic intelligence signals from collected news items."""
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
            )
        )

    category_counts = Counter(signal.category for signal in signals)
    tone_counts = Counter(signal.tone for signal in signals)
    top_sources = Counter(signal.source for signal in signals)
    ranked = sorted(signals, key=lambda s: (s.urgency, s.tone != "neutral", s.category != "other"), reverse=True)
    return NewsIntelligence(
        signals=ranked[:max_signals],
        category_counts=category_counts,
        tone_counts=tone_counts,
        top_sources=top_sources,
    )


def render_news_intelligence_markdown(news_items: list[dict], language: str = "en", max_signals: int = 8) -> str:
    """Render a concise market-intelligence dashboard in Markdown."""
    intelligence = build_news_intelligence(news_items, max_signals=max_signals)
    labels = CATEGORY_LABELS.get(language, CATEGORY_LABELS["en"])
    if not intelligence.signals:
        return ""

    if language == "zh":
        title = "## 新闻智能信号图谱"
        category_line = "- 主导主题"
        tone_line = "- 新闻基调"
        source_line = "- 主要来源"
        urgency_title = "### 高优先级催化剂"
        signal_title = "### 代表性信号"
        no_urgency = "- 暂无明显高紧迫性催化剂。"
    else:
        title = "## News Intelligence Signal Map"
        category_line = "- Dominant theme"
        tone_line = "- News tone"
        source_line = "- Leading sources"
        urgency_title = "### High-Priority Catalysts"
        signal_title = "### Representative Signals"
        no_urgency = "- No high-urgency catalyst detected."

    top_sources = ", ".join(f"{source} ({count})" for source, count in intelligence.top_sources.most_common(3))
    lines = [
        title,
        f"{category_line}: **{labels.get(intelligence.dominant_category, intelligence.dominant_category)}**",
        f"{tone_line}: **{intelligence.dominant_tone}**",
        f"{source_line}: {top_sources or 'N/A'}",
        "",
        urgency_title,
    ]

    urgent = intelligence.high_urgency[:3]
    if urgent:
        for signal in urgent:
            lines.append(
                f"- [{labels.get(signal.category, signal.category)} | {signal.tone}] {signal.title} — {signal.source}"
            )
    else:
        lines.append(no_urgency)

    lines.extend(["", signal_title])
    for signal in intelligence.signals[:5]:
        lines.append(
            f"- [{labels.get(signal.category, signal.category)} | {signal.tone} | urgency {signal.urgency}] "
            f"{signal.title} — {signal.source}"
        )

    return "\n".join(lines)
