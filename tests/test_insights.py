from src.insights import (
    build_news_intelligence,
    classify_category,
    classify_tone,
    infer_asset_impacts,
    infer_time_horizon,
    render_news_intelligence_markdown,
    urgency_score,
)


def test_classify_category_detects_macro_and_crypto():
    assert classify_category("Fed rate decision and CPI inflation") == "macro"
    assert classify_category("Bitcoin and Ethereum crypto rally") == "crypto"


def test_classify_tone_positive_negative_neutral():
    assert classify_tone("Stocks rally and shares surge") == "positive"
    assert classify_tone("Oil prices plunge on demand risk") == "negative"
    assert classify_tone("Company announces board meeting") == "neutral"


def test_urgency_score_detects_catalysts():
    assert urgency_score("Breaking: unexpected tariff shock") >= 3


def test_infer_asset_impacts_maps_macro_and_oil_news():
    macro_assets = infer_asset_impacts("Fed rate surprise lifts the dollar and treasury yields", "macro")
    oil_assets = infer_asset_impacts("OPEC crude oil supply shock", "commodities")

    assert "US Treasuries / TLT" in macro_assets
    assert "US Dollar / DXY" in macro_assets
    assert "Crude Oil / CL" in oil_assets


def test_infer_time_horizon_detects_validation_windows():
    assert infer_time_horizon("Breaking news today: urgent Fed decision") == "intraday"
    assert infer_time_horizon("Upcoming policy meeting this week") == "near_term"
    assert infer_time_horizon("Quarter guidance and medium-term outlook") == "medium_term"


def test_build_news_intelligence_ranks_urgent_items():
    items = [
        {"title": "Company board meeting", "source": "A"},
        {"title": "Breaking Fed rate shock hits stocks", "description": "Nasdaq shares plunge", "source": "B"},
    ]

    intelligence = build_news_intelligence(items)

    assert intelligence.dominant_category in {"macro", "stocks"}
    assert intelligence.market_regime_key == "risk_off"
    assert intelligence.source_diversity_key == "broad"
    assert intelligence.dominant_horizon == "intraday"
    assert intelligence.conviction_score >= 50
    assert intelligence.conviction_key in {"moderate", "high"}
    assert intelligence.narrative_tension_key == "directional"
    assert "S&P 500 / SPY" in intelligence.primary_assets
    assert intelligence.signals[0].source == "B"
    assert intelligence.signals[0].urgency > 0


def test_build_news_intelligence_detects_conflicting_narratives():
    items = [
        {"title": "Fed rate outlook lifts stocks", "description": "S&P shares rally", "source": "A"},
        {"title": "Fed inflation warning hits stocks", "description": "Nasdaq shares plunge", "source": "B"},
    ]

    intelligence = build_news_intelligence(items)

    assert intelligence.narrative_tension_key == "conflicted"
    assert intelligence.tone_alignment_share == 0.5
    assert intelligence.conviction_score > 0


def test_render_news_intelligence_markdown_bilingual():
    items = [
        {"title": "Fed rate surprise lifts dollar", "source": "Reuters"},
        {"title": "比特币 大涨 创新高", "source": "Sina"},
    ]

    en = render_news_intelligence_markdown(items, language="en")
    zh = render_news_intelligence_markdown(items, language="zh")

    assert "News Intelligence Signal Map" in en
    assert "Dominant theme" in en
    assert "Market regime" in en
    assert "Asset Impact Radar" in en
    assert "Validation horizon" in en
    assert "Narrative conviction" in en
    assert "Narrative Conviction Monitor" in en
    assert "Decision Checklist" in en
    assert "Scenario Playbook" in en
    assert "新闻智能信号图谱" in zh
    assert "主导主题" in zh
    assert "市场状态" in zh
    assert "资产影响雷达" in zh
    assert "验证窗口" in zh
    assert "叙事置信度" in zh
    assert "叙事置信度监控" in zh
    assert "决策检查清单" in zh
    assert "情景推演与验证清单" in zh
