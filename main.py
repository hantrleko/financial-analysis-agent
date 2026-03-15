import os
import sys
import logging

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.collector import NewsCollector
from src.analyzer import FinancialAnalyzer
from src.media_gen import MediaGenerator
from src.history import HistoryManager
from src.config import VERSION

logger = logging.getLogger(__name__)

HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    logger.info(f"🏦 Starting Financial Analysis System ({VERSION})...")

    # 配置
    language = "en"       # 可修改为 "zh"
    deep_analysis = True  # 是否启用深度分析

    # 1. Collect News
    collector = NewsCollector()
    query = "latest financial news market trends"
    logger.info(f"[1/5] Collecting news for: {query}")

    news_items = collector.fetch_news(query=query, count=5)

    if not news_items:
        logger.info("No news found. Exiting.")
        return

    # Save raw data
    collector.save_news(news_items, "data/daily_news.json")

    logger.info(f"Collected {len(news_items)} items.")
    for i, item in enumerate(news_items, 1):
        logger.info(f"{i}. {item.get('title', 'No Title')} ({item.get('source', 'Unknown')})")

    # 2. Scrape full content (deep mode)
    if deep_analysis:
        logger.info("[2/5] Scraping full article content...")
        collector.enrich_with_content(news_items)
        scraped = sum(1 for it in news_items if it.get("full_content"))
        logger.info(f"Scraped full content for {scraped}/{len(news_items)} articles.")
    else:
        logger.info("[2/5] Skipping article scraping (deep analysis off).")

    # 3. Load previous report for comparison
    previous_report = None
    if deep_analysis:
        hm = HistoryManager(history_dir=HISTORY_DIR)
        prev_runs = hm.list_runs()
        if prev_runs:
            prev_data = hm.load_run(prev_runs[0]["run_id"])
            if prev_data and prev_data.get("report"):
                previous_report = prev_data["report"]
                logger.info(f"[Context] Loaded previous report ({len(previous_report)} chars) for trend comparison.")

    # 4. Analysis
    logger.info(f"[3/5] Analyzing news with You.com AI (language={language}, deep={deep_analysis})...")
    analysis_report = ""
    try:
        analyzer = FinancialAnalyzer()
        analysis_report = analyzer.analyze_news(
            news_items,
            language=language,
            deep_analysis=deep_analysis,
            previous_report=previous_report,
        )
        print("\n--- Analysis Report ---\n")
        print(analysis_report)
        print("\n-----------------------\n")

        # Save Report
        analyzer.save_analysis(analysis_report, "data/daily_report.md")

    except Exception as e:
        logger.info(f"Analysis failed: {e}")
        return

    # 5. Media Gen
    logger.info("[4/5] Generating media...")
    media_gen = MediaGenerator()
    try:
        audio_file = media_gen.generate_audio(
            analysis_report, "data/daily_briefing.mp3",
            language=language,
        )
        if audio_file:
            logger.info(f"Audio generated: {audio_file}")
        else:
            logger.info("Audio generation skipped (check API Key).")
    except Exception as e:
        logger.info(f"Audio generation failed: {e}")

    # 6. PDF Export
    logger.info("[5/5] Exporting PDF...")
    try:
        pdf_title = "金融分析简报" if language == "zh" else "Financial Analysis Briefing"
        pdf_file = media_gen.generate_pdf(
            analysis_report, "data/daily_briefing.pdf",
            language=language, title=pdf_title,
        )
        if pdf_file:
            logger.info(f"PDF generated: {pdf_file}")
    except Exception as e:
        logger.info(f"PDF generation failed: {e}")

    logger.info("✅ Workflow Complete!")


if __name__ == "__main__":
    main()
