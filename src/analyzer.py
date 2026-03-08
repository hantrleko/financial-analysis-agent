import os
import yfinance as yf
from google import genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

REPORT_SECTORS = {
    "宏观经济 Macro": "macro",
    "股票个股 Stocks": "stocks",
    "大宗商品 Commodities": "commodities",
    "虚拟货币 Crypto": "crypto",
    "外汇 Forex": "forex",
    "债券固收 Bonds": "bonds",
}

SECTOR_KEYWORDS = {
    "macro": "macroeconomics GDP inflation interest rates central bank monetary policy",
    "stocks": "stock market equities earnings S&P 500 Nasdaq individual stocks",
    "commodities": "commodities gold oil silver copper natural gas",
    "crypto": "cryptocurrency bitcoin ethereum blockchain crypto market",
    "forex": "foreign exchange forex currency USD EUR JPY",
    "bonds": "bonds treasury yields fixed income credit spread",
}

# 市场快照使用的关键指标
_SNAPSHOT_TICKERS = {
    "S&P 500 (SPY)": "SPY",
    "Nasdaq 100 (QQQ)": "QQQ",
    "Dow Jones (DIA)": "DIA",
    "Gold": "GC=F",
    "Crude Oil (WTI)": "CL=F",
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    "US 10Y Yield": "^TNX",
    "VIX": "^VIX",
}


class FinancialAnalyzer:
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in .env")

        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model_name = "gemini-2.5-flash"

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
    def fetch_market_snapshot():
        """从 yfinance 拉取关键资产实时行情快照。"""
        lines = []
        for name, ticker in _SNAPSHOT_TICKERS.items():
            try:
                hist = yf.Ticker(ticker).history(period="5d")
                if hist.empty:
                    continue
                current = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[0]
                change_pct = (current - prev) / prev * 100
                lines.append(f"  {name}: {current:.2f} ({change_pct:+.2f}% 5d)")
            except Exception:
                pass
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

    # ──────────────── Round 1: 事实提取 ────────────────

    def _extract_facts(self, news_context, language="en"):
        """Round 1: 从新闻中提取结构化关键事实和数据点。"""
        lang = self._lang_instruction(language)
        prompt = f"""You are a senior financial research analyst. Carefully read each article below and extract:

1. **Key Facts & Data Points**: Specific numbers, percentages, dollar amounts, dates
2. **Main Entities**: Companies, people, institutions mentioned and their roles
3. **Market Signals**: Bullish or bearish implications, direction indicators
4. **Cross-article Connections**: Note if multiple articles relate to the same theme

Be thorough and precise. Extract ALL relevant data points — these will be used for deeper analysis.
{lang}

News Articles:
{news_context}"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            return response.text
        except Exception as e:
            print(f"Round 1 fact extraction failed: {e}")
            return ""

    # ──────────────── Round 2: 最终分析 ────────────────

    def _build_final_prompt(self, facts_summary, market_snapshot,
                            previous_report, briefing_length, language, sectors):
        """构建注入了所有上下文的最终分析 prompt。"""
        structure = self._briefing_structure(briefing_length)
        lang = self._lang_instruction(language)
        sec = self._sector_instruction(sectors)

        # 组装上下文块
        context_blocks = []

        context_blocks.append(f"""## Extracted Intelligence from Today's News
{facts_summary}""")

        context_blocks.append(f"""## Current Market Data (Real-time)
{market_snapshot}""")

        if previous_report:
            context_blocks.append(f"""## Previous Report (for trend comparison)
{previous_report[:1500]}""")

        all_context = "\n\n".join(context_blocks)

        prompt = f"""You are an expert Wall Street Financial Analyst with 20 years of experience.

You have access to the following research materials:

{all_context}

## Your Task
Based on ALL the above intelligence and data, {structure}

## Critical Requirements
- Reference SPECIFIC data points and numbers from the extracted intelligence
- Cross-reference news narratives with actual market data — note any contradictions
- {"Compare with the previous report: highlight what has changed, what trends are continuing, and any reversals" if previous_report else ""}
- Provide concrete price levels, percentages, and metrics wherever possible
- Distinguish between confirmed facts and market speculation
{sec}{lang}"""

        return prompt

    # ──────────────── 公共 API ────────────────

    def analyze_news(self, news_items, briefing_length="medium", language="en",
                     sectors=None, previous_report=None, deep_analysis=False):
        """
        分析新闻并生成简报。
        deep_analysis=True 时启用多轮分析 + 市场数据注入。
        """
        if not news_items:
            return "No news to analyze."

        news_context = self._build_news_context(news_items)

        if not deep_analysis:
            # 轻量模式：保持原有单次调用行为
            structure = self._briefing_structure(briefing_length)
            lang = self._lang_instruction(language)
            sec = self._sector_instruction(sectors)
            prompt = f"""You are an expert Wall Street Financial Analyst.
{structure}
{sec}{lang}

News Data:
{news_context}"""
            try:
                response = self.client.models.generate_content(
                    model=self.model_name, contents=prompt)
                return response.text
            except Exception as e:
                return f"Analysis failed: {e}"

        # ── 深度分析模式 ──
        print(f"[Deep Analysis] Analyzing {len(news_items)} articles...")

        # Round 1: 提取事实
        print("[Round 1/2] Extracting key facts and data points...")
        facts = self._extract_facts(news_context, language)

        # 拉取实时市场数据
        print("[Market Data] Fetching real-time market snapshot...")
        snapshot = self.fetch_market_snapshot()

        # Round 2: 综合分析
        print("[Round 2/2] Synthesizing final report...")
        prompt = self._build_final_prompt(
            facts_summary=facts or news_context,
            market_snapshot=snapshot,
            previous_report=previous_report,
            briefing_length=briefing_length,
            language=language,
            sectors=sectors,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt)
            return response.text
        except Exception as e:
            return f"Analysis failed: {e}"

    def analyze_news_stream(self, news_items, briefing_length="medium", language="en",
                            sectors=None, previous_report=None, deep_analysis=False,
                            on_status=None):
        """
        流式版本：逐块 yield 分析结果。
        on_status: 可选回调函数，用于在 UI 中显示当前阶段。
        """
        if not news_items:
            yield "No news to analyze."
            return

        news_context = self._build_news_context(news_items)

        if not deep_analysis:
            # 轻量模式
            structure = self._briefing_structure(briefing_length)
            lang = self._lang_instruction(language)
            sec = self._sector_instruction(sectors)
            prompt = f"""You are an expert Wall Street Financial Analyst.
{structure}
{sec}{lang}

News Data:
{news_context}"""
            try:
                response = self.client.models.generate_content_stream(
                    model=self.model_name, contents=prompt)
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
            except Exception as e:
                yield f"Analysis failed: {e}"
            return

        # ── 深度分析模式 ──

        # Round 1: 提取事实（非流式）
        if on_status:
            on_status("🔬 [Round 1/2] Extracting key facts and data points...")
        facts = self._extract_facts(news_context, language)

        # 市场数据
        if on_status:
            on_status("📊 Fetching real-time market data...")
        snapshot = self.fetch_market_snapshot()

        # Round 2: 综合分析（流式输出）
        if on_status:
            on_status("📝 [Round 2/2] Synthesizing final report...")
        prompt = self._build_final_prompt(
            facts_summary=facts or news_context,
            market_snapshot=snapshot,
            previous_report=previous_report,
            briefing_length=briefing_length,
            language=language,
            sectors=sectors,
        )

        try:
            response = self.client.models.generate_content_stream(
                model=self.model_name, contents=prompt)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"Analysis failed: {e}"

    def save_analysis(self, analysis_text, filename="data/daily_report.md"):
        """保存分析报告到 Markdown 文件。"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(analysis_text)
        print(f"Saved analysis to {filename}")


if __name__ == "__main__":
    analyzer = FinancialAnalyzer()
    mock_news = [
        {"title": "Tech Stocks Rally", "source": "Bloomberg",
         "description": "AI hype continues to drive Nasdaq.", "published_age": "1h"},
        {"title": "Fed Rates Hold Steady", "source": "Reuters",
         "description": "Powell signals no cuts yet.", "published_age": "2h"}
    ]
    # 测试轻量模式
    print("=== Light Mode ===")
    print(analyzer.analyze_news(mock_news))
    # 测试深度模式
    print("\n=== Deep Mode ===")
    print(analyzer.analyze_news(mock_news, deep_analysis=True))
