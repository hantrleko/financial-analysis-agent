from __future__ import annotations

import logging
import os
import re
from collections import Counter
from collections.abc import Generator
from datetime import datetime, timezone

import yfinance as yf

from src.config import (
    CHINA_FOCUS_SOURCES,
    DEEP_LLM_PROVIDER,
    DEFAULT_LLM_PROVIDER,
    GEMINI_MAX_OUTPUT_TOKENS,
    GEMINI_THINKING_BUDGET,
    LLM_PROVIDERS,
    OPENAI_COMPAT_MAX_TOKENS,
    PREVIOUS_REPORT_MAX_AGE_HOURS,
    PREVIOUS_REPORT_MAX_CHARS,
    REPORT_SECTORS,
    SNAPSHOT_TICKERS,
    SNAPSHOT_TICKERS_CHINA,
    TIME_RANGE_PERIOD_MAP,
)
from src.insights import render_news_intelligence_markdown
from src.utils import get_api_key, get_proxy, retry_api_call

logger = logging.getLogger(__name__)

# Gemini systemInstruction — 分离系统角色指令，提高模型对输出要求的遵从度
GEMINI_SYSTEM_INSTRUCTION = (
    "You are an expert Wall Street Financial Analyst and Chief Investment Strategist "
    "with 20 years of experience at a top-tier investment bank. "
    "You produce institutional-grade research briefings known for their precision, depth, and actionable insights. "
    "CRITICAL: You MUST follow the output length and section requirements specified in the user's task. "
    "Never truncate, abbreviate, or produce placeholder content. "
    "If asked for a detailed report, produce a FULL detailed report with all sections completed in depth."
)

_RULE_POSITIVE_KEYWORDS = [
    "beat",
    "beats",
    "surge",
    "rally",
    "growth",
    "upgrade",
    "positive",
    "strong",
    "outperform",
    "gain",
    "record",
    "rebound",
    "上涨",
    "上升",
    "利好",
    "创新高",
    "突破",
]

_RULE_NEGATIVE_KEYWORDS = [
    "miss",
    "missed",
    "downgrade",
    "decline",
    "plunge",
    "crash",
    "fall",
    "weak",
    "loss",
    "risk",
    "concern",
    "pressure",
    "drop",
    "下跌",
    "暴跌",
    "下滑",
    "利空",
    "亏损",
]

_RULE_SECTOR_KEYWORDS = {
    "macro": ["inflation", "fed", "rates", "interest", "gdp", "unemployment", "央行", "利率", "货币", "cpi", "pmi", "就业"],
    "stocks": ["earnings", "revenue", "profit", "ai", "股市", "财报", "个股", "股票", "downgrade", "upgrade"],
    "commodities": ["oil", "gold", "commodity", "crude", "铜", "大宗商品", "金", "油", "铜", "原油"],
    "crypto": ["bitcoin", "btc", "ether", "crypto", "etf", "staked", "比特币", "加密"],
    "forex": ["dollar", "eur", "usd", "yen", "exchange rate", "forex", "人民币", "外汇", "汇率", "美元", "欧元", "日元"],
    "bonds": ["yield", "treasury", "bond", "credit", "spreads", "债券", "利率债", "收益率", "收益", "信用"],
}


class FinancialAnalyzer:
    def __init__(self, provider: str | None = None, briefing_length: str = "medium") -> None:
        self.provider = provider or DEFAULT_LLM_PROVIDER
        self.briefing_length = briefing_length
        self._validate_provider()

    def _validate_provider(self) -> None:
        """校验所选 provider 是否有可用的 API Key。"""
        cfg = LLM_PROVIDERS.get(self.provider)
        if not cfg:
            raise ValueError(f"Unknown LLM provider: {self.provider}")
        env_key = cfg.get("env_key", "")
        if not env_key:
            return
        api_key = get_api_key(env_key)
        if not api_key:
            logger.warning("API key %s not set for provider %s", cfg["env_key"], self.provider)

    # ──────────────────── 辅助方法 ────────────────────

    @staticmethod
    def _query_has_chinese_finance_signal(query: str | None) -> bool:
        if not query:
            return False
        text = query.lower()
        keywords = [
            "a股",
            "a-share",
            "a share",
            "china",
            "china a-share",
            "沪深",
            "上证",
            "深证",
            "中国",
            "中国股市",
            "财经",
            "股",
            "基金",
            "债券",
            "港股",
            "港股通",
        ]
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _is_mock_item(item: dict[str, object]) -> bool:
        return "mock" in str(item.get("source", "")).lower()

    def _detect_market_scope(self, query: str | None, news_items: list[dict]) -> str:
        if self._query_has_chinese_finance_signal(query):
            return "china_a_share"
        for item in news_items:
            source = str(item.get("source", "")).strip()
            if source in CHINA_FOCUS_SOURCES:
                return "china_a_share"
        return "global"

    @staticmethod
    def _snapshot_tickers_for_scope(scope: str) -> list[str]:
        if scope == "china_a_share":
            return list(SNAPSHOT_TICKERS_CHINA.values())
        return list(SNAPSHOT_TICKERS.values())

    def _build_news_context(
        self, news_items: list[dict], language: str = "en", query: str | None = None
    ) -> str:
        """构建新闻上下文，优先使用全文内容，并注入确定性新闻信号。"""
        market_scope = self._detect_market_scope(query=query, news_items=news_items)
        parts = []
        intelligence = render_news_intelligence_markdown(
            news_items, language=language, market_scope=market_scope
        )
        if intelligence:
            parts.append(f"{intelligence}\n")

        for i, item in enumerate(news_items, 1):
            part = f"\n--- Article {i} ---\n"
            part += f"Title: {item.get('title')} ({item.get('source')})\n"
            part += f"Date: {item.get('published_age')}\n"
            full = item.get("full_content", "")
            if full:
                part += f"Full Content:\n{full}\n"
            else:
                part += f"Summary: {item.get('description')}\n"
            parts.append(part)
        return "".join(parts)

    @staticmethod
    def fetch_market_snapshot(time_range: str = "week", tickers: list[str] | None = None) -> str:
        """从 yfinance 批量拉取关键资产实时行情快照。"""
        ticker_map = {**SNAPSHOT_TICKERS, **SNAPSHOT_TICKERS_CHINA}
        if tickers is not None:
            ticker_map = {name: code for name, code in ticker_map.items() if code in tickers}
            if not ticker_map:
                ticker_map = SNAPSHOT_TICKERS
            tickers_list = tickers
        else:
            tickers_list = list(SNAPSHOT_TICKERS.values())
        name_by_ticker = {v: k for k, v in ticker_map.items()}
        period = TIME_RANGE_PERIOD_MAP.get(time_range, "5d")

        try:
            data = yf.download(tickers_list, period=period, progress=False)
        except Exception:
            logger.exception("Failed to download market data")
            return "Market data temporarily unavailable."

        if data.empty:
            return "Market data temporarily unavailable."

        lines = []
        close = data["Close"]
        for ticker in tickers_list:
            try:
                series = close[ticker].dropna()
                if series.empty:
                    continue
                current = series.iloc[-1]
                prev = series.iloc[0]
                change_pct = (current - prev) / prev * 100
                name = name_by_ticker[ticker]
                lines.append(f"  {name}: {current:.2f} ({change_pct:+.2f}% 5d)")
            except Exception:
                logger.debug("Skipping ticker %s", ticker, exc_info=True)
        return "\n".join(lines) if lines else "Market data temporarily unavailable."

    @staticmethod
    def _lang_instruction(language: str) -> str:
        return (
            "Write the entire briefing in Chinese (中文)."
            if language == "zh"
            else "Write the entire briefing in English."
        )

    @staticmethod
    def _sector_instruction(sectors: list[str] | None) -> str:
        if not sectors:
            return ""
        sector_display = {v: k for k, v in REPORT_SECTORS.items()}
        sector_list = ", ".join(sector_display.get(s, s) for s in sectors)
        return (
            f"\nOrganize your analysis by the following sectors, using each as a main heading: {sector_list}. "
            "For each sector, analyze the relevant news items. Skip a sector if no relevant news is found.\n"
        )

    def _briefing_structure(self, briefing_length: str) -> str:
        """返回不同长度对应的报告结构要求。"""
        if briefing_length == "short":
            return """Produce a very concise Daily Financial Briefing in ~200 words.
Use bullet points for clarity. Cover:
- 🚨 Top risk/trend
- 📈 Key drivers (2-3 bullets)
- 💡 One actionable insight
- 🔮 Outlook (1 sentence)
Format in clean Markdown. Be brief and data-driven."""

        elif briefing_length == "detailed":
            return """Produce a comprehensive, institutional-grade Daily Financial Briefing.
MINIMUM LENGTH REQUIREMENT: The briefing MUST be at least 800 words. Aim for 800-1200 words.
Each section below MUST contain multiple detailed paragraphs with specific data points, analysis, and context.
Do NOT produce bullet-point-only output — use full prose paragraphs with supporting evidence.

The briefing MUST include ALL of the following sections (do not skip any):
1. 🚨 **Market Sentinel** (150+ words): In-depth analysis of the single most important trend or risk factor.
   Include specific price levels, percentage moves, and historical context.
2. 📈 **Key Drivers** (200+ words): Detailed explanation of 3-5 main stories driving the market.
   Each driver should include concrete data points, quotes from sources, and cause-effect analysis.
3. 🏭 **Sector Spotlight** (100+ words): Highlight 2-3 sectors most affected, with specific stock/ETF moves.
4. 🌍 **Macro & Geopolitical Context** (100+ words): Broader economic or geopolitical factors at play.
   Include relevant economic indicators, policy decisions, and global developments.
5. 💡 **Actionable Insights** (100+ words): 2-3 concrete suggestions for investors (both conservative and aggressive).
   Include specific entry/exit levels, position sizing guidance, and risk management.
6. ⚠️ **Risks to Watch** (80+ words): Key downside risks or upcoming catalysts with probability assessments.
7. 🔮 **Outlook** (80+ words): Prediction for the next 24-48 hours with detailed reasoning and scenarios.

Format the output in clean Markdown with proper headings.
Keep it professional, data-driven, yet engaging. Provide depth and nuance.
IMPORTANT: Do NOT truncate or abbreviate. Each section must be substantive and complete."""

        else:  # medium
            return """Produce a concise, high-impact Daily Financial Briefing in ~400 words.
The briefing should have the following sections:
1. 🚨 **Market Sentinel**: The single most important trend or risk factor right now.
2. 📈 **Key Drivers**: Briefly explain 2-3 main stories driving the market.
3. 💡 **Actionable Insight**: One concrete suggestion for investors (conservative or aggressive).
4. 🔮 **Outlook**: A 1-sentence prediction for the next 24 hours.
Format the output in clean Markdown.
Keep it professional, data-driven, yet engaging."""

    # ──────────────── 上期报告摘要 ────────────────

    @staticmethod
    def _is_previous_report_valid(prev_metadata: dict) -> bool:
        """校验上期报告是否在有效时间范围内。"""
        try:
            ts = prev_metadata.get("timestamp", "")
            report_time = datetime.fromisoformat(ts)
            if report_time.tzinfo is None:
                report_time = report_time.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - report_time).total_seconds() / 3600
            return age_hours <= PREVIOUS_REPORT_MAX_AGE_HOURS
        except Exception:
            return False

    @staticmethod
    def _summarize_previous_report(report: str, max_chars: int = PREVIOUS_REPORT_MAX_CHARS) -> str:
        """提取上期报告的关键结论部分。"""
        sections = []
        for marker in [
            "Market Sentinel",
            "Outlook",
            "Key Drivers",
            "Actionable",
            "市场哨兵",
            "展望",
            "关键驱动",
            "可操作",
            "风险",
            "宏观",
        ]:
            pattern = re.compile(
                rf"(#+\s*.*?{re.escape(marker)}.*?\n)"  # heading line
                rf"(.*?)(?=\n#+\s|\Z)",  # body until next heading or end
                re.DOTALL,
            )
            match = pattern.search(report)
            if match:
                sections.append(match.group(0).strip())

        if sections:
            return "\n\n".join(sections)[:max_chars]
        return report[:max_chars]

    @staticmethod
    def _safe_lower(value: str) -> str:
        return (value or "").lower()

    @staticmethod
    def _count_hits(value: str, keywords: list[str]) -> int:
        lowered = FinancialAnalyzer._safe_lower(value)
        return sum(lowered.count(keyword.lower()) for keyword in keywords)

    @staticmethod
    def _chunk_text(value: str, chunk_size: int = 900):
        for i in range(0, len(value), chunk_size):
            yield value[i : i + chunk_size]

    @staticmethod
    def _label_for_score(score: float, language: str = "en") -> str:
        if score >= 0.5:
            return "偏多" if language == "zh" else "bullish"
        if score <= -0.5:
            return "偏空" if language == "zh" else "bearish"
        return "中性" if language == "zh" else "neutral"

    def _provider_key_available(self, provider_key: str) -> bool:
        cfg = LLM_PROVIDERS.get(provider_key)
        if not cfg:
            return False
        if provider_key == "rule_based":
            return True
        env_key = cfg.get("env_key", "")
        if not env_key:
            return False
        return bool(get_api_key(env_key))

    @staticmethod
    def _normalize_text_block(item: dict) -> str:
        return " ".join(filter(None, [item.get("title", ""), item.get("description", ""), item.get("full_content", "")]))

    @staticmethod
    def _parse_snapshot(snapshot: str) -> list[tuple[str, float]]:
        if not snapshot:
            return []
        movers: list[tuple[str, float]] = []
        pattern = re.compile(r":\s*[-+]?\d+(?:\.\d+)?\s*\(([-+]?\d+(?:\.\d+)?)%")
        for line in snapshot.splitlines():
            try:
                match = pattern.search(line)
                if not match:
                    continue
                name = line.split(":")[0].strip(" -*")
                delta = float(match.group(1))
                movers.append((name, delta))
            except Exception:
                continue
        return movers

    def _provider_display_name(self, provider_key: str) -> str:
        return LLM_PROVIDERS.get(provider_key, {}).get("name", provider_key)

    def _engine_markdown_header(self, provider_key: str, language: str = "en", fallback: bool = False) -> str:
        engine_name = self._provider_display_name(provider_key)
        if language == "zh":
            suffix = "（回退引擎）" if fallback else "（已激活）"
            return f"## 执行引擎：{engine_name}{suffix}\n\n"
        suffix = " (Fallback Engine)" if fallback else " (Active)"
        return f"## Execution Engine: {engine_name}{suffix}\n\n"

    @staticmethod
    def _effective_provider(provider: str, deep_analysis: bool) -> str:
        if deep_analysis and provider != "rule_based":
            return DEEP_LLM_PROVIDER
        return provider

    def _analyze_news_signal(self, news_items: list[dict], language: str) -> tuple[list[dict], Counter]:
        article_scores = []
        sector_hits = Counter()
        for item in news_items:
            text = self._normalize_text_block(item)
            pos = self._count_hits(text, _RULE_POSITIVE_KEYWORDS)
            neg = self._count_hits(text, _RULE_NEGATIVE_KEYWORDS)
            score = pos - neg
            if score > 0:
                emotion = "bullish"
            elif score < 0:
                emotion = "bearish"
            else:
                emotion = "neutral"

            sector_marks = {}
            for sector, kws in _RULE_SECTOR_KEYWORDS.items():
                s = self._count_hits(text, kws)
                if s > 0:
                    sector_marks[sector] = s
                    sector_hits[sector] += s

            sector = sorted(sector_marks.items(), key=lambda it: it[1], reverse=True)[0][0] if sector_marks else "macro"
            article_scores.append(
                {
                    "title": item.get("title", "Untitled") or "Untitled",
                    "source": item.get("source", "Unknown"),
                    "score": score,
                    "emotion": emotion,
                    "emotion_label": self._label_for_score(score, language=language),
                    "sector": sector,
                }
            )

        article_scores.sort(key=lambda it: abs(it["score"]), reverse=True)
        return article_scores, sector_hits

    def _build_rule_based_report(
        self,
        news_items: list[dict],
        briefing_length: str,
        language: str,
        market_scope: str = "global",
        sectors: list[str] | None = None,
        snapshot: str | None = None,
        previous_report: str | None = None,
        time_range: str = "week",
    ) -> str:
        signals, sector_hits = self._analyze_news_signal(news_items, language)
        if sectors:
            wanted = set(sectors)
            signals = [s for s in signals if s["sector"] in wanted]
            sector_hits = Counter(item["sector"] for item in signals)

        article_count = len(signals)
        movers = self._parse_snapshot(snapshot or "")
        movers_top = sorted(movers, key=lambda it: abs(it[1]), reverse=True)[:3]
        bull_count = sum(1 for item in signals if item["emotion"] == "bullish")
        bear_count = sum(1 for item in signals if item["emotion"] == "bearish")
        sentiment_index = round((bull_count - bear_count) / article_count, 2) if article_count else 0.0

        top_sector = sector_hits.most_common(1)[0][0] if sector_hits else "macro"
        snapshot_label_zh = "3) A股快照（近5日）" if market_scope == "china_a_share" else "3) 市场快照（近5日）"
        snapshot_label_en = "3) A-share Snapshot (5-day proxy)" if market_scope == "china_a_share" else "3) Market Snapshot (5-day proxy)"
        is_mock_data = any(self._is_mock_item(item) for item in news_items)
        low_sample = article_count < 3

        title_zh = "# 金融市场简报（规则模式）"
        title_en = "# Financial Briefing (Rule-based)"
        title = title_zh if language == "zh" else title_en
        detail_note = (
            "说明：本模式为纯规则化模板，不调用外部模型。\n\n"
            if language == "zh"
            else "Note: this is deterministic rule-based output without external model calls.\n\n"
        )

        if language == "zh":
            lines = [
                title,
                detail_note,
            ]
            if is_mock_data:
                lines.extend(
                    [
                        "## ⚠️ 数据提示",
                        "当前结果主要依赖兜底样本（含 mock 来源），仅用于演示流程，不代表真实市场观点。",
                        "建议补充可抓取到的来源后再做交易性决策。",
                    ]
                )
            if low_sample:
                lines.extend(
                    [
                        "## 7) 样本有效性说明",
                        "⚠️ 当前样本量较少（少于3条），结论仅做趋势框架参考，不应单独作为交易信号。"
                        if article_count > 0
                        else "⚠️ 本次未抓取到有效样本，当前输出为基于历史信息的保守提示。",
                        "可观测变量较少时，先观察后续 2-3 条新闻是否同步，降低误判概率。",
                    ]
                )

            lines.extend(
                [
                "## 1) 情绪与主题聚合",
                f"- 文章样本数：{article_count}",
                f"- 多头：{bull_count}，空头：{bear_count}，中性：{article_count - bull_count - bear_count}",
                f"- 综合情绪指数：`(多头-空头)/样本数 = ({bull_count}-{bear_count})/{article_count} = {sentiment_index}`",
                f"- 情绪标签：**{self._label_for_score(sentiment_index, 'zh')}**",
                f"- 主题主导：**{top_sector}**",
                    "\n## 2) 关键新闻链条",
                ]
            )
            for idx, item in enumerate(signals[:3], start=1):
                lines.append(f"{idx}. [{item['source']}] {item['title']}（{item['emotion_label']}，评分{item['score']}）")
        else:
            lines = [
                title,
                detail_note,
            ]
            if is_mock_data:
                lines.extend(
                    [
                        "## ⚠️ Data Quality Notice",
                        "Current result is mainly driven by fallback/mock items and should be treated as a workflow demo, not investable output.",
                        "Use only when real feed data is unavailable.",
                    ]
                )
            if low_sample:
                lines.extend(
                    [
                        "## 7) Sample Quality Note",
                        "⚠️ Sample size is small (fewer than 3 items). This should be treated as directional context only.",
                        "Avoid turning this into direct action signals until 2–3 follow-up items align.",
                    ]
                )

            lines.extend(
                [
                "## 1) Sentiment and Theme Aggregation",
                f"- Sample size: {article_count}",
                f"- Bullish: {bull_count}, Bearish: {bear_count}, Neutral: {article_count - bull_count - bear_count}",
                f"- Sentiment index: `(bullish - bearish)/count = ({bull_count}-{bear_count})/{article_count} = {sentiment_index}`",
                f"- Sentiment label: **{self._label_for_score(sentiment_index, 'en')}**",
                f"- Dominant theme: **{top_sector}**",
                    "\n## 2) Key News Chains",
                ]
            )
            for idx, item in enumerate(signals[:3], start=1):
                lines.append(f"{idx}. [{item['source']}] {item['title']} (score {item['score']}, {item['emotion_label']})")

        if language == "zh":
            lines.extend(["", f"## {snapshot_label_zh}"])
            if movers_top:
                for name, delta in movers_top:
                    direction = "上行" if delta >= 0 else "下行"
                    lines.append(f"- {name}：{direction}{delta:+.2f}%")
            else:
                lines.append("- 快照暂不可用（后备模式已继续输出）")
        else:
            lines.extend(["", f"## {snapshot_label_en}"])
            if movers_top:
                for name, delta in movers_top:
                    direction = "up" if delta >= 0 else "down"
                    lines.append(f"- {name}: {direction} {delta:+.2f}%")
            else:
                lines.append("- Snapshot unavailable; rule mode continues with available textual signals.")

        if language == "zh":
            lines.extend(
                [
                    "\n## 4) 可执行建议",
                    "- 优先级 A：先做风控，再做观点；先控风险再博主观方向。",
                    "- 优先级 B：任何新闻结论先用“数据放大率”验证，避免单稿噪音。",
                    "- 优先级 C：若连续两次情绪指数反向，才调整核心仓位。",
                ]
            )
        else:
            lines.extend(
                [
                    "\n## 4) Action Checklist",
                    "- Priority A: prioritize risk control before directional positioning.",
                    "- Priority B: only validate via data amplification before converting narrative to action.",
                    "- Priority C: adjust core allocation only after two consecutive opposite sentiment checks.",
                ]
            )

        if previous_report:
            prev_excerpt = self._summarize_previous_report(previous_report, max_chars=320)
            if language == "zh":
                lines.extend(
                    [
                        "\n## 5) 与上期对比（摘要）",
                        f"- 样本对比：当前 {article_count} 篇；上期摘要 {len(previous_report)} 字。",
                        f"- 上期摘要：{prev_excerpt}",
                    ]
                )
            else:
                lines.extend(
                    [
                        "\n## 5) Prior Report Diff (summary)",
                        f"- Sample compare: current {article_count} items vs prior summary length {len(previous_report)} chars.",
                        f"- Prior excerpt: {prev_excerpt}",
                    ]
                )

        if briefing_length == "detailed":
            if language == "zh":
                lines.extend(
                    [
                        "\n## 6) 规则因果链解释（可复核）",
                        "- 规则：`情绪强度 × 快照动量`，若二者同向则提高优先级，否则降权。",
                        f"- 计算示例：`{sentiment_index}` × `{movers_top[0][1] if movers_top else 0:.2f}%` = "
                        f"`{sentiment_index * (movers_top[0][1] if movers_top else 0):.2f}`",
                        "- 只要快照与新闻方向出现背离，则等待下一轮样本再下决策。",
                        "- 结论：本报告仅作为研究型市场框架，不构成投资建议。",
                    ]
                )
            else:
                lines.extend(
                    [
                        "\n## 6) Rule-based causal logic",
                        "- Rule: `sentiment intensity × snapshot momentum`; same direction raises confidence, opposite weakens it.",
                        f"- Example: `{sentiment_index}` × `{movers_top[0][1] if movers_top else 0:.2f}%` = "
                        f"`{sentiment_index * (movers_top[0][1] if movers_top else 0):.2f}`",
                        "- Do not change positioning if narrative and snapshot direction diverge.",
                        "- This report is for research use only, not investment advice.",
                    ]
                )

        return "\n".join(lines)

    # ──────────────── 构建 Agent Input ────────────────

    def _build_input(
        self,
        news_context: str,
        briefing_length: str,
        language: str,
        sectors: list[str] | None,
        market_snapshot: str | None = None,
        previous_report: str | None = None,
    ) -> str:
        """构建传入 LLM 的 input 文本。"""
        structure = self._briefing_structure(briefing_length)
        lang = self._lang_instruction(language)
        sec = self._sector_instruction(sectors)

        parts = [
            f"\n## Collected News Articles\n{news_context}",
        ]

        if market_snapshot:
            parts.append(f"\n## Current Market Data (Real-time)\n{market_snapshot}")

        if previous_report:
            summary = self._summarize_previous_report(previous_report)
            parts.append(f"\n## Previous Report (for trend comparison)\n{summary}")

        parts.append(f"\n## Your Task\nBased on ALL the above intelligence and data, {structure}")

        parts.append("\n## Critical Requirements")
        parts.append("- Reference SPECIFIC data points, numbers, and percentages from the provided news articles")
        parts.append(
            "- Cross-reference news narratives with actual market data — explicitly note any contradictions or confirmations"
        )
        parts.append("- Identify cause-and-effect chains: what is driving what, and what are the second-order effects")
        if previous_report:
            parts.append(
                "- Compare with the previous report: highlight what has changed, what trends are continuing, and any reversals"
            )
        parts.append(
            "- Provide concrete price levels, support/resistance levels, percentages, and metrics wherever possible"
        )
        parts.append("- Distinguish between confirmed facts and market speculation — label speculation clearly")
        parts.append("- Prioritize information by market impact: lead with what matters most to investors")
        parts.append(
            "- Use the News Intelligence Signal Map, Asset Impact Radar, Narrative Conviction Monitor, Decision Checklist, "
            "and Scenario Playbook to frame the dominant theme, market regime, affected instruments, validation horizon, "
            "narrative confidence, and what evidence would confirm or invalidate the base case"
        )
        parts.append(f"{sec}{lang}")

        return "\n".join(parts)

    # ──────────────── LLM 后端调用 ────────────────

    def _call_llm(self, input_text: str, deep_analysis: bool = False) -> str:
        """
        路由 LLM 调用。
        Gemini 优先，若因地区限制失败则自动回退到智谱 GLM。
        """
        provider = self._effective_provider(self.provider, deep_analysis)

        if provider.startswith("gemini"):
            try:
                return self._call_gemini(input_text, provider)
            except Exception as e:
                if "location" in str(e).lower() or "FAILED_PRECONDITION" in str(e):
                    logger.warning("Gemini unavailable (region restriction), falling back to ZhiPu GLM...")
                    return self._call_openai_compat(input_text, "zhipu")
                raise
        else:
            return self._call_openai_compat(input_text, provider)

    def _gemini_generation_config(self) -> dict:
        """构建 Gemini generationConfig，根据报告长度动态调整 token 上限和思考预算。"""
        max_tokens = GEMINI_MAX_OUTPUT_TOKENS.get(self.briefing_length, 8192)
        thinking_budget = int(os.getenv("GEMINI_THINKING_BUDGET", str(GEMINI_THINKING_BUDGET)))
        config: dict = {
            "temperature": 0.7,
            "maxOutputTokens": max_tokens,
        }
        # thinkingBudget: -1 表示动态（默认），0 表示关闭
        if thinking_budget == -1:
            # 不传 thinkingConfig，使用 Gemini 默认的动态思考
            pass
        else:
            config["thinkingConfig"] = {"thinkingBudget": thinking_budget}
        return config

    @staticmethod
    def _extract_gemini_text(data: dict, provider_name: str = "Gemini") -> str:
        """从 Gemini 响应中提取非 thought 的 text 部分。检查 finishReason 并记录截断警告。"""
        try:
            candidate = data["candidates"][0]
            # 检查 finishReason — 可能是 MAX_TOKENS / SAFETY / RECITATION 等
            finish_reason = candidate.get("finishReason", "")
            if finish_reason and finish_reason not in ("STOP", "END_TURN"):
                logger.warning(
                    "Gemini response truncated: finishReason=%s (model may have hit token limit)",
                    finish_reason,
                )

            parts = candidate["content"]["parts"]
            text_parts = []
            for part in parts:
                # 过滤掉 thought summary 部分（thought == true）
                if part.get("thought", False):
                    continue
                text = part.get("text", "")
                if text:
                    text_parts.append(text)
            if text_parts:
                return "".join(text_parts)
            return f"No response from {provider_name}."
        except (KeyError, IndexError):
            return f"No response from {provider_name}."

    def _call_gemini(self, input_text: str, provider_key: str = "gemini") -> str:
        """调用 Google Gemini API，支持代理。使用 systemInstruction 分离角色指令。"""
        import requests as http_requests

        cfg = LLM_PROVIDERS[provider_key]
        api_key = get_api_key(cfg["env_key"])
        model = os.getenv("GEMINI_MODEL", cfg["model"])
        url = f"{cfg['base_url']}/models/{model}:generateContent"
        headers = {"x-goog-api-key": api_key}
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": GEMINI_SYSTEM_INSTRUCTION,
                    }
                ]
            },
            "contents": [{"parts": [{"text": input_text}]}],
            "generationConfig": self._gemini_generation_config(),
        }
        proxies = get_proxy()
        resp = retry_api_call(
            lambda: http_requests.post(url, headers=headers, json=payload, timeout=300, proxies=proxies)
        )
        if resp.status_code != 200:
            logger.error("Gemini API error %d: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        data = resp.json()
        return self._extract_gemini_text(data, cfg["name"])

    def _call_gemini_stream(self, input_text: str, provider_key: str = "gemini") -> Generator[str, None, None]:
        """调用 Google Gemini API 流式输出，逐块 yield 文本。自动过滤 thought 部分，检查 finishReason。"""
        import requests as http_requests

        cfg = LLM_PROVIDERS[provider_key]
        api_key = get_api_key(cfg["env_key"])
        model = os.getenv("GEMINI_MODEL", cfg["model"])
        url = f"{cfg['base_url']}/models/{model}:streamGenerateContent?alt=sse"
        headers = {"x-goog-api-key": api_key}
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": GEMINI_SYSTEM_INSTRUCTION,
                    }
                ]
            },
            "contents": [{"parts": [{"text": input_text}]}],
            "generationConfig": self._gemini_generation_config(),
        }
        proxies = get_proxy()
        import json as json_mod

        resp = http_requests.post(url, headers=headers, json=payload, timeout=300, proxies=proxies, stream=True)
        if resp.status_code != 200:
            logger.error("Gemini Stream API error %d: %s", resp.status_code, resp.text[:500])
            resp.raise_for_status()

        # Force UTF-8 decoding — requests defaults to ISO-8859-1 for
        # text/* content types when the server omits charset, which
        # garbles Chinese characters.
        resp.encoding = "utf-8"

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            # SSE format: "data: {...}"
            if line.startswith("data: "):
                json_str = line[6:]
                try:
                    chunk_data = json_mod.loads(json_str)
                    candidates = chunk_data.get("candidates", [])
                    if candidates:
                        # 检查 finishReason
                        finish_reason = candidates[0].get("finishReason", "")
                        if finish_reason and finish_reason not in ("STOP", "END_TURN", ""):
                            logger.warning(
                                "Gemini stream truncated: finishReason=%s",
                                finish_reason,
                            )
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            # 跳过 thought summary 部分
                            if part.get("thought", False):
                                continue
                            text = part.get("text", "")
                            if text:
                                yield text
                except (json_mod.JSONDecodeError, KeyError, IndexError):
                    continue

    def _call_openai_compat(self, input_text: str, provider_key: str) -> str:
        """调用 OpenAI 兼容接口（智谱 GLM 等）。"""
        import requests as http_requests

        cfg = LLM_PROVIDERS[provider_key]
        api_key = get_api_key(cfg["env_key"])
        url = f"{cfg['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        max_tokens = OPENAI_COMPAT_MAX_TOKENS.get(self.briefing_length, 4096)
        payload = {
            "model": cfg["model"],
            "messages": [
                {
                    "role": "system",
                    "content": GEMINI_SYSTEM_INSTRUCTION,
                },
                {"role": "user", "content": input_text},
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }
        resp = retry_api_call(lambda: http_requests.post(url, json=payload, headers=headers, timeout=180))
        resp.raise_for_status()
        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
            finish = data["choices"][0].get("finish_reason", "")
            if finish and finish != "stop":
                logger.warning("OpenAI-compat response truncated: finish_reason=%s", finish)
            return content
        except (KeyError, IndexError):
            return f"No response from {cfg['name']}."

    def _call_openai_compat_stream(self, input_text: str, provider_key: str) -> Generator[str, None, None]:
        """调用 OpenAI 兼容接口流式输出（智谱 GLM 等）。"""
        import json as json_mod

        import requests as http_requests

        cfg = LLM_PROVIDERS[provider_key]
        api_key = get_api_key(cfg["env_key"])
        url = f"{cfg['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        max_tokens = OPENAI_COMPAT_MAX_TOKENS.get(self.briefing_length, 4096)
        payload = {
            "model": cfg["model"],
            "messages": [
                {
                    "role": "system",
                    "content": GEMINI_SYSTEM_INSTRUCTION,
                },
                {"role": "user", "content": input_text},
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "stream": True,
        }
        resp = http_requests.post(url, json=payload, headers=headers, timeout=180, stream=True)
        resp.raise_for_status()

        # Force UTF-8 decoding for Chinese content support.
        resp.encoding = "utf-8"

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                json_str = line[6:]
                if json_str.strip() == "[DONE]":
                    break
                try:
                    chunk_data = json_mod.loads(json_str)
                    delta = chunk_data["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json_mod.JSONDecodeError, KeyError, IndexError):
                    continue

    # ──────────────── 公共 API ────────────────

    def analyze_news(
        self,
        news_items: list[dict],
        briefing_length: str = "medium",
        language: str = "en",
        sectors: list[str] | None = None,
        query: str | None = None,
        previous_report: str | None = None,
        deep_analysis: bool = False,
        time_range: str = "week",
        previous_report_meta: dict | None = None,
    ) -> str:
        """分析新闻并生成简报。"""
        self.briefing_length = briefing_length
        if not news_items:
            return "No news to analyze."

        if previous_report_meta and not self._is_previous_report_valid(previous_report_meta):
            logger.info("Previous report is too old or metadata invalid, skipping comparison.")
            previous_report = None

        market_scope = self._detect_market_scope(query=query, news_items=news_items)
        tickers = self._snapshot_tickers_for_scope(market_scope)
        snapshot = self.fetch_market_snapshot(time_range=time_range, tickers=tickers)
        news_context = self._build_news_context(news_items, language=language, query=query)
        input_text = self._build_input(
            news_context=news_context,
            briefing_length=briefing_length,
            language=language,
            sectors=sectors,
            market_snapshot=snapshot,
            previous_report=previous_report,
        )

        provider = self._effective_provider(self.provider, deep_analysis)
        if provider == "rule_based":
            rule_report = self._build_rule_based_report(
                news_items=news_items,
                briefing_length=briefing_length,
                language=language,
                market_scope=market_scope,
                sectors=sectors,
                snapshot=snapshot,
                previous_report=previous_report,
                time_range=time_range,
            )
            return self._engine_markdown_header("rule_based", language=language, fallback=False) + rule_report

        if not self._provider_key_available(provider):
            rule_report = self._build_rule_based_report(
                news_items=news_items,
                briefing_length=briefing_length,
                language=language,
                market_scope=market_scope,
                sectors=sectors,
                snapshot=snapshot,
                previous_report=previous_report,
                time_range=time_range,
            )
            return self._engine_markdown_header("rule_based", language=language, fallback=False) + rule_report

        try:
            report = self._call_llm(input_text, deep_analysis=deep_analysis)
            return self._engine_markdown_header(provider, language=language, fallback=False) + report
        except Exception as e:
            logger.warning("LLM analysis failed: %s. Falling back to rule-based report.", e)
            fallback_report = self._build_rule_based_report(
                news_items=news_items,
                briefing_length=briefing_length,
                language=language,
                market_scope=market_scope,
                sectors=sectors,
                snapshot=snapshot,
                previous_report=previous_report,
                time_range=time_range,
            )
            return self._engine_markdown_header("rule_based", language=language, fallback=True) + fallback_report

    def _call_llm_stream(self, input_text: str, deep_analysis: bool = False) -> Generator[str, None, None]:
        """
        流式路由 LLM 调用。
        Gemini 优先，若因地区限制失败则自动回退到智谱 GLM。
        """
        provider = self._effective_provider(self.provider, deep_analysis)

        if provider.startswith("gemini"):
            try:
                yield from self._call_gemini_stream(input_text, provider)
                return
            except Exception as e:
                if "location" in str(e).lower() or "FAILED_PRECONDITION" in str(e):
                    logger.warning("Gemini streaming unavailable (region restriction), falling back to ZhiPu GLM...")
                    yield from self._call_openai_compat_stream(input_text, "zhipu")
                    return
                raise
        else:
            yield from self._call_openai_compat_stream(input_text, provider)

    def analyze_news_stream(
        self,
        news_items: list[dict],
        briefing_length: str = "medium",
        language: str = "en",
        sectors: list[str] | None = None,
        query: str | None = None,
        previous_report: str | None = None,
        deep_analysis: bool = False,
        on_status: object = None,
        time_range: str = "week",
        previous_report_meta: dict | None = None,
    ) -> Generator[str, None, None]:
        """分析新闻并生成简报（真正流式 yield 方式）。"""
        self.briefing_length = briefing_length
        if not news_items:
            yield "No news to analyze."
            return

        if previous_report_meta and not self._is_previous_report_valid(previous_report_meta):
            logger.info("Previous report is too old or metadata invalid, skipping comparison.")
            previous_report = None

        market_scope = self._detect_market_scope(query=query, news_items=news_items)
        tickers = self._snapshot_tickers_for_scope(market_scope)
        provider = self._effective_provider(self.provider, deep_analysis)
        news_context = self._build_news_context(news_items, language=language, query=query)

        if on_status:
            provider_key = provider
            provider_name = LLM_PROVIDERS.get(provider_key, {}).get("name", provider_key)
            on_status(f"📊 Analyzing with {provider_name}...")

        snapshot = self.fetch_market_snapshot(time_range=time_range, tickers=tickers)
        input_text = self._build_input(
            news_context=news_context,
            briefing_length=briefing_length,
            language=language,
            sectors=sectors,
            market_snapshot=snapshot,
            previous_report=previous_report,
        )

        if provider == "rule_based":
            if on_status:
                on_status("📊 Analyzing with Rule-based engine..." if language == "en" else "📊 使用规则引擎分析中...")
            yield self._engine_markdown_header("rule_based", language=language, fallback=False)
            for chunk in self._chunk_text(
                self._build_rule_based_report(
                    news_items=news_items,
                    briefing_length=briefing_length,
                    language=language,
                    market_scope=market_scope,
                    sectors=sectors,
                    snapshot=snapshot,
                    previous_report=previous_report,
                    time_range=time_range,
                )
            ):
                yield chunk
            return

        if not self._provider_key_available(provider):
            if on_status:
                on_status("📊 Analyzing with Rule-based engine..." if language == "en" else "📊 使用规则引擎分析中...")
            yield self._engine_markdown_header("rule_based", language=language, fallback=False)
            for chunk in self._chunk_text(
                self._build_rule_based_report(
                    news_items=news_items,
                    briefing_length=briefing_length,
                    language=language,
                    market_scope=market_scope,
                    sectors=sectors,
                    snapshot=snapshot,
                    previous_report=previous_report,
                    time_range=time_range,
                )
            ):
                yield chunk
            return

        try:
            yield self._engine_markdown_header(provider, language=language, fallback=False)
            yield from self._call_llm_stream(input_text, deep_analysis=deep_analysis)
        except Exception as e:
            logger.warning("LLM streaming failed: %s. Falling back to rule-based report.", e)
            if on_status:
                on_status("📊 Falling back to rule-based engine..." if language == "en" else "📊 回退到规则引擎...")
            yield self._engine_markdown_header("rule_based", language=language, fallback=True)
            for chunk in self._chunk_text(
                self._build_rule_based_report(
                    news_items=news_items,
                    briefing_length=briefing_length,
                    language=language,
                    market_scope=market_scope,
                    sectors=sectors,
                    snapshot=snapshot,
                    previous_report=previous_report,
                    time_range=time_range,
                )
            ):
                yield chunk

    def save_analysis(self, analysis_text: str, filename: str = "data/daily_report.md") -> None:
        """保存分析报告到 Markdown 文件。"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(analysis_text)
        logger.info("Saved analysis to %s", filename)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analyzer = FinancialAnalyzer()
    mock_news = [
        {
            "title": "Tech Stocks Rally",
            "source": "Bloomberg",
            "description": "AI hype continues to drive Nasdaq.",
            "published_age": "1h",
        },
        {
            "title": "Fed Rates Hold Steady",
            "source": "Reuters",
            "description": "Powell signals no cuts yet.",
            "published_age": "2h",
        },
    ]
    logger.info("=== Using provider: %s ===", analyzer.provider)
    logger.info(analyzer.analyze_news(mock_news))
