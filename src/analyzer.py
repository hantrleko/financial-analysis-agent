import logging
import os
import re
from datetime import datetime, timezone

import yfinance as yf
from dotenv import load_dotenv
from youdotcom import You
from youdotcom.models import (
    ExpressAgentRunsRequest,
    AdvancedAgentRunsRequest,
    ResearchTool,
    SearchEffort,
    ReportVerbosity,
)

from src.config import (
    REPORT_SECTORS, SNAPSHOT_TICKERS, PREVIOUS_REPORT_MAX_CHARS,
    TIME_RANGE_PERIOD_MAP, PREVIOUS_REPORT_MAX_AGE_HOURS,
)

load_dotenv()

logger = logging.getLogger(__name__)

YOU_API_KEY = os.getenv("YOU_API_KEY")


class FinancialAnalyzer:
    def __init__(self):
        if not YOU_API_KEY:
            raise ValueError("YOU_API_KEY not found in .env")

        self.client = You(YOU_API_KEY)

    # ──────────────────── 辅助方法 ────────────────────

    def _build_news_context(self, news_items):
        """构建新闻上下文，优先使用全文内容。"""
        parts = []
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
    def fetch_market_snapshot(time_range="week"):
        """从 yfinance 批量拉取关键资产实时行情快照。"""
        tickers_list = list(SNAPSHOT_TICKERS.values())
        name_by_ticker = {v: k for k, v in SNAPSHOT_TICKERS.items()}
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
    def _lang_instruction(language):
        return (
            "Write the entire briefing in Chinese (中文)." if language == "zh"
            else "Write the entire briefing in English."
        )

    @staticmethod
    def _sector_instruction(sectors):
        if not sectors:
            return ""
        sector_display = {v: k for k, v in REPORT_SECTORS.items()}
        sector_list = ", ".join(sector_display.get(s, s) for s in sectors)
        return (
            f"\nOrganize your analysis by the following sectors, using each as a main heading: {sector_list}. "
            "For each sector, analyze the relevant news items. Skip a sector if no relevant news is found.\n"
        )

    def _briefing_structure(self, briefing_length):
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
            return """Produce a comprehensive Daily Financial Briefing in ~800 words.
The briefing should have the following sections:
1. 🚨 **Market Sentinel**: In-depth analysis of the single most important trend or risk factor.
2. 📈 **Key Drivers**: Detailed explanation of 3-5 main stories driving the market, with data points.
3. 🏭 **Sector Spotlight**: Highlight 2-3 sectors most affected and why.
4. 🌍 **Macro & Geopolitical Context**: Broader economic or geopolitical factors at play.
5. 💡 **Actionable Insights**: 2-3 concrete suggestions for investors (both conservative and aggressive).
6. ⚠️ **Risks to Watch**: Key downside risks or upcoming catalysts.
7. 🔮 **Outlook**: Prediction for the next 24-48 hours with reasoning.
Format the output in clean Markdown.
Keep it professional, data-driven, yet engaging. Provide depth and nuance."""

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
    def _is_previous_report_valid(prev_metadata):
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
    def _summarize_previous_report(report, max_chars=PREVIOUS_REPORT_MAX_CHARS):
        """提取上期报告的关键结论部分。"""
        sections = []
        for marker in ["Market Sentinel", "Outlook", "Key Drivers", "Actionable",
                        "市场哨兵", "展望", "关键驱动", "可操作", "风险", "宏观"]:
            pattern = re.compile(
                rf"(#+\s*.*?{re.escape(marker)}.*?\n)"  # heading line
                rf"(.*?)(?=\n#+\s|\Z)",                  # body until next heading or end
                re.DOTALL,
            )
            match = pattern.search(report)
            if match:
                sections.append(match.group(0).strip())

        if sections:
            return "\n\n".join(sections)[:max_chars]
        return report[:max_chars]

    # ──────────────── 构建 Agent Input ────────────────

    def _build_input(self, news_context, briefing_length, language, sectors,
                     market_snapshot=None, previous_report=None):
        """构建传入 You.com Agent 的 input 文本。"""
        structure = self._briefing_structure(briefing_length)
        lang = self._lang_instruction(language)
        sec = self._sector_instruction(sectors)

        parts = [
            "You are an expert Wall Street Financial Analyst with 20 years of experience.",
            f"\n## Collected News Articles\n{news_context}",
        ]

        if market_snapshot:
            parts.append(f"\n## Current Market Data (Real-time)\n{market_snapshot}")

        if previous_report:
            summary = self._summarize_previous_report(previous_report)
            parts.append(f"\n## Previous Report (for trend comparison)\n{summary}")

        parts.append(f"\n## Your Task\nBased on ALL the above intelligence and data, {structure}")

        parts.append("\n## Critical Requirements")
        parts.append("- Reference SPECIFIC data points and numbers from the provided news articles")
        parts.append("- Cross-reference news narratives with actual market data — note any contradictions")
        if previous_report:
            parts.append("- Compare with the previous report: highlight what has changed, what trends are continuing, and any reversals")
        parts.append("- Provide concrete price levels, percentages, and metrics wherever possible")
        parts.append("- Distinguish between confirmed facts and market speculation")
        parts.append(f"{sec}{lang}")

        return "\n".join(parts)

    # ──────────────── 提取报告文本 ────────────────

    @staticmethod
    def _extract_report(response):
        """从 Agent 响应中提取报告文本。"""
        if not response or not response.output:
            return "No response from AI agent."

        for item in response.output:
            if hasattr(item, 'text') and item.text:
                return item.text

        return "No report content in response."

    # ──────────────── 公共 API ────────────────

    def analyze_news(self, news_items, briefing_length="medium", language="en",
                     sectors=None, previous_report=None, deep_analysis=False,
                     time_range="week", previous_report_meta=None):
        """
        分析新闻并生成简报。
        deep_analysis=True 时使用 Advanced Agent + ResearchTool 进行深度分析。
        """
        if not news_items:
            return "No news to analyze."

        # 校验上期报告有效性
        if previous_report_meta and not self._is_previous_report_valid(previous_report_meta):
            logger.info("Previous report is too old or metadata invalid, skipping comparison.")
            previous_report = None

        news_context = self._build_news_context(news_items)

        if not deep_analysis:
            # 轻量模式：Express Agent（快速）+ 市场数据
            snapshot = self.fetch_market_snapshot(time_range=time_range)
            input_text = self._build_input(
                news_context=news_context,
                briefing_length=briefing_length,
                language=language,
                sectors=sectors,
                market_snapshot=snapshot,
                previous_report=previous_report,
            )
            try:
                response = self.client.agents.runs.create(
                    request=ExpressAgentRunsRequest(input=input_text),
                )
                return self._extract_report(response)
            except Exception as e:
                return f"Analysis failed: {e}"

        # ── 深度分析模式：Advanced Agent + ResearchTool ──
        logger.info("Analyzing %d articles (deep analysis)...", len(news_items))

        # 拉取实时市场数据
        logger.info("Fetching real-time market snapshot...")
        snapshot = self.fetch_market_snapshot(time_range=time_range)

        input_text = self._build_input(
            news_context=news_context,
            briefing_length=briefing_length,
            language=language,
            sectors=sectors,
            market_snapshot=snapshot,
            previous_report=previous_report,
        )

        logger.info("Synthesizing report with Advanced Agent + Research...")
        try:
            response = self.client.agents.runs.create(
                request=AdvancedAgentRunsRequest(
                    input=input_text,
                    tools=[
                        ResearchTool(
                            search_effort=SearchEffort.HIGH,
                            report_verbosity=ReportVerbosity.HIGH,
                        ),
                    ],
                ),
            )
            return self._extract_report(response)
        except Exception as e:
            return f"Analysis failed: {e}"

    def analyze_news_stream(self, news_items, briefing_length="medium", language="en",
                            sectors=None, previous_report=None, deep_analysis=False,
                            on_status=None, time_range="week", previous_report_meta=None):
        """
        分析新闻并生成简报（yield 方式）。
        You.com Agent API 不支持逐 token 流式，一次性返回完整结果。
        """
        if not news_items:
            yield "No news to analyze."
            return

        # 校验上期报告有效性
        if previous_report_meta and not self._is_previous_report_valid(previous_report_meta):
            logger.info("Previous report is too old or metadata invalid, skipping comparison.")
            previous_report = None

        news_context = self._build_news_context(news_items)

        if not deep_analysis:
            # 轻量模式 + 市场数据
            if on_status:
                on_status("🔍 Analyzing with Express Agent...")
            snapshot = self.fetch_market_snapshot(time_range=time_range)
            input_text = self._build_input(
                news_context=news_context,
                briefing_length=briefing_length,
                language=language,
                sectors=sectors,
                market_snapshot=snapshot,
                previous_report=previous_report,
            )
            try:
                response = self.client.agents.runs.create(
                    request=ExpressAgentRunsRequest(input=input_text),
                )
                yield self._extract_report(response)
            except Exception as e:
                yield f"Analysis failed: {e}"
            return

        # ── 深度分析模式 ──

        # 市场数据
        if on_status:
            on_status("📊 Fetching real-time market data...")
        snapshot = self.fetch_market_snapshot(time_range=time_range)

        input_text = self._build_input(
            news_context=news_context,
            briefing_length=briefing_length,
            language=language,
            sectors=sectors,
            market_snapshot=snapshot,
            previous_report=previous_report,
        )

        # Advanced Agent + Research
        if on_status:
            on_status("🔬 Deep analysis in progress (Advanced Agent + Research)...")
        try:
            response = self.client.agents.runs.create(
                request=AdvancedAgentRunsRequest(
                    input=input_text,
                    tools=[
                        ResearchTool(
                            search_effort=SearchEffort.HIGH,
                            report_verbosity=ReportVerbosity.HIGH,
                        ),
                    ],
                ),
            )
            yield self._extract_report(response)
        except Exception as e:
            yield f"Analysis failed: {e}"

    def save_analysis(self, analysis_text, filename="data/daily_report.md"):
        """保存分析报告到 Markdown 文件。"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(analysis_text)
        logger.info("Saved analysis to %s", filename)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analyzer = FinancialAnalyzer()
    mock_news = [
        {"title": "Tech Stocks Rally", "source": "Bloomberg",
         "description": "AI hype continues to drive Nasdaq.", "published_age": "1h"},
        {"title": "Fed Rates Hold Steady", "source": "Reuters",
         "description": "Powell signals no cuts yet.", "published_age": "2h"}
    ]
    # 测试轻量模式
    logger.info("=== Light Mode ===")
    logger.info(analyzer.analyze_news(mock_news))
    # 测试深度模式
    logger.info("=== Deep Mode ===")
    logger.info(analyzer.analyze_news(mock_news, deep_analysis=True))
