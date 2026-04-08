"""MarketSentimentAnalyzer 单元测试。"""

from src.sentiment import AssetSignal, MarketSentimentAnalyzer


def test_classify_score():
    assert MarketSentimentAnalyzer._classify_score(0.7) == "strong_bull"  # >= 0.6
    assert MarketSentimentAnalyzer._classify_score(0.3) == "bull"  # >= 0.2
    assert MarketSentimentAnalyzer._classify_score(0.0) == "neutral"
    assert MarketSentimentAnalyzer._classify_score(-0.3) == "bear"  # <= -0.2
    assert MarketSentimentAnalyzer._classify_score(-0.7) == "strong_bear"  # <= -0.6


def test_classify_vix():
    assert MarketSentimentAnalyzer._classify_vix(10) == "low"  # < 15
    assert MarketSentimentAnalyzer._classify_vix(16) == "normal"  # 15-20
    assert MarketSentimentAnalyzer._classify_vix(22) == "elevated"  # 20-25
    assert MarketSentimentAnalyzer._classify_vix(27) == "high"  # 25-30
    assert MarketSentimentAnalyzer._classify_vix(35) == "extreme"  # > 30


def test_compute_score_bullish():
    sig = AssetSignal(
        name="Test",
        ticker="TST",
        sector="equity",
        group="Test Group",
        price=100.0,
        change_1d_pct=2.0,
        change_5d_pct=4.0,
        change_20d_pct=8.0,
        above_ma20=True,
        volume_ratio=2.0,
    )
    score = MarketSentimentAnalyzer._compute_score(sig)
    assert score > 0, f"Expected positive score, got {score}"


def test_compute_score_bearish():
    sig = AssetSignal(
        name="Test",
        ticker="TST",
        sector="equity",
        group="Test Group",
        price=100.0,
        change_1d_pct=-3.0,
        change_5d_pct=-5.0,
        change_20d_pct=-10.0,
        above_ma20=False,
        volume_ratio=2.0,
    )
    score = MarketSentimentAnalyzer._compute_score(sig)
    assert score < 0, f"Expected negative score, got {score}"


def test_compute_score_vix_inverted():
    """VIX 应采用反向评分。"""
    sig = AssetSignal(
        name="VIX",
        ticker="^VIX",
        sector="volatility",
        group="Volatility",
        price=25.0,
        change_1d_pct=5.0,
        change_5d_pct=10.0,
        change_20d_pct=15.0,
        above_ma20=True,
        volume_ratio=1.0,
    )
    score = MarketSentimentAnalyzer._compute_score(sig)
    assert score < 0, f"VIX rising should produce negative score, got {score}"


def test_build_reason():
    sig = AssetSignal(
        name="SPY",
        ticker="SPY",
        sector="equity",
        group="Indices",
        price=500.0,
        change_1d_pct=1.5,
        change_5d_pct=3.0,
        change_20d_pct=5.0,
        above_ma20=True,
        volume_ratio=2.0,
    )
    reason = MarketSentimentAnalyzer._build_reason(sig)
    assert "1D" in reason
    assert "5D" in reason
    assert "above MA20" in reason
    assert "vol" in reason
