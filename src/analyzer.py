from __future__ import annotations

import logging
import os
import re
from collections.abc import Generator
from datetime import datetime, timezone

import yfinance as yf

from src.config import (
    DEEP_LLM_PROVIDER,
    DEFAULT_LLM_PROVIDER,
    LLM_PROVIDERS,
    PREVIOUS_REPORT_MAX_AGE_HOURS,
    PREVIOUS_REPORT_MAX_CHARS,
    REPORT_SECTORS,
    SNAPSHOT_TICKERS,
    TIME_RANGE_PERIOD_MAP,
)
from src.utils import get_api_key, get_proxy, retry_api_call

logger = logging.getLogger(__name__)


class FinancialAnalyzer:
    def __init__(self, provider: str | None = None) -> None:
        self.provider = provider or DEFAULT_LLM_PROVIDER
        self._validate_provider()

    def _validate_provider(self) -> None:
        """校验所选 provider 是否有可用的 API Key。"""
        cfg = LLM_PROVIDERS.get(self.provider)
        if not cfg:
            raise ValueError(f"Unknown LLM provider: {self.provider}")
        api_key = get_api_key(cfg["env_key"])
        if not api_key:
            logger.warning("API key %s not set for provider %s", cfg["env_key"], self.provider)

    # ──────────────────── 辅助方法 ────────────────────

    def _build_news_context(self, news_items: list[dict]) -> str:
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
    def fetch_market_snapshot(time_range: str = "week") -> str:
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
            "You are an expert Wall Street Financial Analyst and Chief Investment Strategist with 20 years of experience at a top-tier investment bank. You produce institutional-grade research briefings known for their precision, depth, and actionable insights.",
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
        parts.append(f"{sec}{lang}")

        return "\n".join(parts)

    # ──────────────── LLM 后端调用 ────────────────

    def _call_llm(self, input_text: str, deep_analysis: bool = False) -> str:
        """
        路由 LLM 调用。
        Gemini 优先，若因地区限制失败则自动回退到智谱 GLM。
        """
        provider = DEEP_LLM_PROVIDER if deep_analysis else self.provider

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

    def _call_gemini(self, input_text: str, provider_key: str = "gemini") -> str:
        """调用 Google Gemini API，支持代理。"""
        import requests as http_requests

        cfg = LLM_PROVIDERS[provider_key]
        api_key = get_api_key(cfg["env_key"])
        model = os.getenv("GEMINI_MODEL", cfg["model"])
        url = f"{cfg['base_url']}/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": input_text}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192,
                "thinkingConfig": {
                    "thinkingBudget": 0,
                },
            },
        }
        proxies = get_proxy()
        resp = retry_api_call(lambda: http_requests.post(url, json=payload, timeout=180, proxies=proxies))
        if resp.status_code != 200:
            logger.error("Gemini API error %d: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return f"No response from {cfg['name']}."

    def _call_gemini_stream(self, input_text: str, provider_key: str = "gemini") -> Generator[str, None, None]:
        """调用 Google Gemini API 流式输出，逞块 yield 文本。"""
        import requests as http_requests

        cfg = LLM_PROVIDERS[provider_key]
        api_key = get_api_key(cfg["env_key"])
        model = os.getenv("GEMINI_MODEL", cfg["model"])
        url = f"{cfg['base_url']}/models/{model}:streamGenerateContent?alt=sse&key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": input_text}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192,
                "thinkingConfig": {
                    "thinkingBudget": 0,
                },
            },
        }
        proxies = get_proxy()
        import json as json_mod

        resp = http_requests.post(url, json=payload, timeout=180, proxies=proxies, stream=True)
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
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
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
        payload = {
            "model": cfg["model"],
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Wall Street Financial Analyst with 20 years of experience.",
                },
                {"role": "user", "content": input_text},
            ],
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        resp = retry_api_call(lambda: http_requests.post(url, json=payload, headers=headers, timeout=120))
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
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
        payload = {
            "model": cfg["model"],
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Wall Street Financial Analyst with 20 years of experience.",
                },
                {"role": "user", "content": input_text},
            ],
            "temperature": 0.7,
            "max_tokens": 4096,
            "stream": True,
        }
        resp = http_requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
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
        previous_report: str | None = None,
        deep_analysis: bool = False,
        time_range: str = "week",
        previous_report_meta: dict | None = None,
    ) -> str:
        """分析新闻并生成简报。"""
        if not news_items:
            return "No news to analyze."

        if previous_report_meta and not self._is_previous_report_valid(previous_report_meta):
            logger.info("Previous report is too old or metadata invalid, skipping comparison.")
            previous_report = None

        news_context = self._build_news_context(news_items)
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
            return self._call_llm(input_text, deep_analysis=deep_analysis)
        except Exception as e:
            return f"Analysis failed: {e}"

    def _call_llm_stream(self, input_text: str, deep_analysis: bool = False) -> Generator[str, None, None]:
        """
        流式路由 LLM 调用。
        Gemini 优先，若因地区限制失败则自动回退到智谱 GLM。
        """
        provider = DEEP_LLM_PROVIDER if deep_analysis else self.provider

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
        previous_report: str | None = None,
        deep_analysis: bool = False,
        on_status: object = None,
        time_range: str = "week",
        previous_report_meta: dict | None = None,
    ) -> Generator[str, None, None]:
        """分析新闻并生成简报（真正流式 yield 方式）。"""
        if not news_items:
            yield "No news to analyze."
            return

        if previous_report_meta and not self._is_previous_report_valid(previous_report_meta):
            logger.info("Previous report is too old or metadata invalid, skipping comparison.")
            previous_report = None

        news_context = self._build_news_context(news_items)

        if on_status:
            provider_key = DEEP_LLM_PROVIDER if deep_analysis else self.provider
            provider_name = LLM_PROVIDERS.get(provider_key, {}).get("name", provider_key)
            on_status(f"📊 Analyzing with {provider_name}...")

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
            yield from self._call_llm_stream(input_text, deep_analysis=deep_analysis)
        except Exception as e:
            yield f"Analysis failed: {e}"

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
