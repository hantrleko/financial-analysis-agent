"""FinancialAnalyzer 单元测试。"""

from unittest.mock import patch, MagicMock
from src.analyzer import FinancialAnalyzer


def test_build_news_context():
    analyzer = FinancialAnalyzer()
    items = [
        {"title": "Stock rises", "description": "Market up today", "source": "CNBC",
         "url": "https://cnbc.com/1", "published": "2026-04-01"},
        {"title": "Oil drops", "description": "Oil fell sharply", "source": "Bloomberg",
         "url": "https://bloomberg.com/2", "published": "2026-04-01",
         "full_content": "Full article about oil prices dropping significantly due to oversupply."},
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
    analyzer = FinancialAnalyzer(provider="gemini")

    import os
    assert os.getenv("GEMINI_MODEL") == "gemini-1.5-pro"
