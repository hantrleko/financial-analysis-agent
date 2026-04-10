"""FinancialAnalyzer 单元测试。"""

from src.analyzer import FinancialAnalyzer


def test_build_news_context():
    analyzer = FinancialAnalyzer()
    items = [
        {
            "title": "Stock rises",
            "description": "Market up today",
            "source": "CNBC",
            "url": "https://cnbc.com/1",
            "published": "2026-04-01",
        },
        {
            "title": "Oil drops",
            "description": "Oil fell sharply",
            "source": "Bloomberg",
            "url": "https://bloomberg.com/2",
            "published": "2026-04-01",
            "full_content": "Full article about oil prices dropping significantly due to oversupply.",
        },
    ]
    ctx = analyzer._build_news_context(items)
    assert "Stock rises" in ctx
    assert "Oil drops" in ctx
    assert "Full article about oil" in ctx


def test_call_llm_fallback(monkeypatch):
    """Gemini 地区限制时应回退到 ZhiPu GLM。"""
    analyzer = FinancialAnalyzer(provider="gemini")

    def fake_gemini(self, text, provider_key="gemini"):
        raise Exception("FAILED_PRECONDITION: region not supported")

    def fake_zhipu(self, text, provider_key="zhipu"):
        return "ZhiPu response"

    monkeypatch.setattr(FinancialAnalyzer, "_call_gemini", fake_gemini)
    monkeypatch.setattr(FinancialAnalyzer, "_call_openai_compat", fake_zhipu)

    result = analyzer._call_llm("test input")
    assert result == "ZhiPu response"


def test_analyze_news_empty():
    analyzer = FinancialAnalyzer()
    result = analyzer.analyze_news([])
    assert result == "No news to analyze."


def test_analyze_news_stream_empty():
    analyzer = FinancialAnalyzer()
    chunks = list(analyzer.analyze_news_stream([]))
    assert chunks == ["No news to analyze."]


def test_gemini_model_env_override(monkeypatch):
    """GEMINI_MODEL 环境变量应覆盖默认模型。"""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")
    _analyzer = FinancialAnalyzer(provider="gemini")  # noqa: F841 — ensures init reads env

    import os

    assert os.getenv("GEMINI_MODEL") == "gemini-1.5-pro"


def test_extract_gemini_text_filters_thoughts():
    """_extract_gemini_text should skip thought parts and only return answer text."""
    data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Let me think about this...", "thought": True},
                        {"text": "Here is the actual answer."},
                        {"text": " And more content.", "thought": False},
                    ]
                }
            }
        ]
    }
    result = FinancialAnalyzer._extract_gemini_text(data)
    assert "Let me think" not in result
    assert "Here is the actual answer." in result
    assert "And more content." in result


def test_extract_gemini_text_no_parts():
    """_extract_gemini_text should return fallback when no valid parts."""
    data = {"candidates": [{"content": {"parts": [{"text": "only thought", "thought": True}]}}]}
    result = FinancialAnalyzer._extract_gemini_text(data, "TestModel")
    assert result == "No response from TestModel."


def test_gemini_generation_config_dynamic_thinking():
    """Default thinkingBudget=-1 should not include thinkingConfig."""
    analyzer = FinancialAnalyzer(briefing_length="detailed")
    config = analyzer._gemini_generation_config()
    assert "thinkingConfig" not in config
    assert config["maxOutputTokens"] == 16384


def test_gemini_generation_config_explicit_budget(monkeypatch):
    """Explicit thinkingBudget via env should be set in config."""
    monkeypatch.setenv("GEMINI_THINKING_BUDGET", "4096")
    analyzer = FinancialAnalyzer(briefing_length="short")
    config = analyzer._gemini_generation_config()
    assert config["thinkingConfig"]["thinkingBudget"] == 4096
    assert config["maxOutputTokens"] == 2048


def test_gemini_generation_config_disabled_thinking(monkeypatch):
    """thinkingBudget=0 should explicitly disable thinking."""
    monkeypatch.setenv("GEMINI_THINKING_BUDGET", "0")
    analyzer = FinancialAnalyzer(briefing_length="medium")
    config = analyzer._gemini_generation_config()
    assert config["thinkingConfig"]["thinkingBudget"] == 0
    assert config["maxOutputTokens"] == 4096
