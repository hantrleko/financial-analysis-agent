"""Pipeline 模块单元测试。"""

from src.pipeline import PipelineConfig


def test_pipeline_config_defaults():
    config = PipelineConfig()
    assert config.query == "latest financial news market trends"
    assert config.num_articles == 5
    assert config.language == "en"
    assert config.deep_analysis is True
    assert config.data_dir == "data"


def test_pipeline_config_custom():
    config = PipelineConfig(
        query="中国市场",
        language="zh",
        num_articles=10,
        deep_analysis=False,
    )
    assert config.query == "中国市场"
    assert config.language == "zh"
    assert config.num_articles == 10
    assert config.deep_analysis is False
