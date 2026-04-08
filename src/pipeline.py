"""
分析流水线：统一 CLI 和 Web UI 的核心分析流程。
消除 main.py 和 app.py 之间的逻辑重复。
"""

import logging
import os
from dataclasses import dataclass, field

from src.analyzer import FinancialAnalyzer
from src.collector import NewsCollector
from src.history import HistoryManager
from src.media_gen import MediaGenerator

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """分析流水线配置。"""

    query: str = "latest financial news market trends"
    num_articles: int = 5
    sources: list = field(default_factory=list)
    time_range: str = "week"
    briefing_length: str = "medium"
    language: str = "en"
    deep_analysis: bool = True
    ai_search: bool = False
    scrape_content: bool = True
    generate_audio: bool = True
    generate_pdf: bool = True
    tts_engine: str = "elevenlabs"
    voice_name: str | None = None
    llm_provider: str | None = None
    sectors: list | None = None
    data_dir: str = "data"
    history_dir: str = "history"


@dataclass
class PipelineResult:
    """分析流水线结果。"""

    news_items: list = field(default_factory=list)
    report: str = ""
    audio_path: str | None = None
    pdf_path: str | None = None
    run_id: str = ""
    error: str | None = None


def run_pipeline(config: PipelineConfig, on_status=None) -> PipelineResult:
    """
    执行完整的分析流水线。
    on_status: 可选回调函数，接收状态消息字符串。
    返回 PipelineResult。
    """
    result = PipelineResult()

    def _status(msg):
        logger.info(msg)
        if on_status:
            on_status(msg)

    try:
        os.makedirs(config.data_dir, exist_ok=True)

        # 1. 采集新闻
        _status(f"[1/5] Collecting news for: {config.query}")
        collector = NewsCollector()
        news_items = collector.fetch_news(
            query=config.query,
            count=config.num_articles,
            sources=config.sources or None,
            time_range=config.time_range,
            ai_search=config.deep_analysis and config.ai_search,
        )

        if not news_items:
            result.error = "No news articles found."
            return result

        result.news_items = news_items
        collector.save_news(news_items, os.path.join(config.data_dir, "daily_news.json"))
        _status(f"Collected {len(news_items)} articles.")

        # 2. 抓取全文（深度分析模式）
        if config.deep_analysis and config.scrape_content:
            _status("[2/5] Scraping full article content...")
            collector.enrich_with_content(news_items)
            scraped = sum(1 for it in news_items if it.get("full_content"))
            _status(f"Scraped full content for {scraped}/{len(news_items)} articles.")
        else:
            _status("[2/5] Skipping article scraping.")

        # 3. 加载上期报告
        previous_report = None
        previous_report_meta = None
        hm = HistoryManager(history_dir=config.history_dir)
        prev_runs = hm.list_runs()
        if prev_runs:
            prev_data = hm.load_run(prev_runs[0]["run_id"])
            if prev_data and prev_data.get("report"):
                previous_report = prev_data["report"]
                previous_report_meta = prev_data.get("metadata")
                _status(f"Loaded previous report ({len(previous_report)} chars) for comparison.")

        # 4. AI 分析
        _status("[3/5] Analyzing news...")
        analyzer = FinancialAnalyzer(provider=config.llm_provider)
        report = analyzer.analyze_news(
            news_items,
            briefing_length=config.briefing_length,
            language=config.language,
            sectors=config.sectors,
            deep_analysis=config.deep_analysis,
            previous_report=previous_report,
            previous_report_meta=previous_report_meta,
            time_range=config.time_range,
        )
        result.report = report

        # 保存报告
        report_path = os.path.join(config.data_dir, "daily_report.md")
        analyzer.save_analysis(report, report_path)

        # 5. 媒体生成
        media_gen = MediaGenerator()

        if config.generate_audio:
            _status("[4/5] Generating audio...")
            try:
                audio_path = media_gen.generate_audio(
                    report,
                    output_file=os.path.join(config.data_dir, "daily_briefing.mp3"),
                    language=config.language,
                    voice_name=config.voice_name,
                    tts_engine=config.tts_engine,
                )
                result.audio_path = audio_path
            except Exception as e:
                logger.warning("Audio generation failed: %s", e)
        else:
            _status("[4/5] Skipping audio generation.")

        if config.generate_pdf:
            _status("[5/5] Exporting PDF...")
            try:
                pdf_title = "金融分析简报" if config.language == "zh" else "Financial Analysis Briefing"
                pdf_path = media_gen.generate_pdf(
                    report,
                    output_file=os.path.join(config.data_dir, "daily_briefing.pdf"),
                    language=config.language,
                    title=pdf_title,
                )
                result.pdf_path = pdf_path
            except Exception as e:
                logger.warning("PDF generation failed: %s", e)
        else:
            _status("[5/5] Skipping PDF export.")

        # 6. 保存到历史记录
        hm_save = HistoryManager(history_dir=config.history_dir)
        result.run_id = hm_save.save_run(
            news_items=news_items,
            report=report,
            query=config.query,
            sources=config.sources,
            time_range=config.time_range,
            briefing_length=config.briefing_length,
            audio_file=result.audio_path,
            pdf_file=result.pdf_path,
        )

        _status(f"Analysis complete! Run saved as {result.run_id}")

    except Exception as e:
        logger.exception("Pipeline failed")
        result.error = str(e)

    return result
