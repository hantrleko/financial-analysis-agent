"""Visualizer 单元测试。"""

import pandas as pd
from src.visualizer import create_price_chart, ASSET_GROUPS


def test_create_price_chart_empty():
    fig = create_price_chart(pd.DataFrame())
    assert fig is not None
    assert fig.layout.title.text == "暂无数据"


def test_create_price_chart_with_data():
    dates = pd.date_range("2026-01-01", periods=5)
    df = pd.DataFrame({
        "SPY": [400, 405, 410, 408, 412],
        "QQQ": [300, 305, 302, 310, 315],
    }, index=dates)
    fig = create_price_chart(df, title="Test")
    assert fig is not None
    assert len(fig.data) == 2
    assert fig.layout.title.text == "Test"


def test_asset_groups_has_entries():
    assert len(ASSET_GROUPS) >= 5
    for group_name, assets in ASSET_GROUPS.items():
        assert len(assets) >= 1
        for asset in assets:
            assert "ticker" in asset
            assert "name" in asset
