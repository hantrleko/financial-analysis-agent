import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.collector import NewsCollector
from src.analyzer import FinancialAnalyzer
from src.media_gen import MediaGenerator
from src.history import HistoryManager

VERSION = "v1.3"

HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")


def main():
    print(f"🏦 Starting Financial Analysis System ({VERSION})...")

    # 配置
    language = "en"       # 可修改为 "zh"
    deep_analysis = True  # 是否启用深度分析

    # 1. Collect News
    collector = NewsCollector()
    query = "latest financial news market trends"
    print(f"\n[1/5] Collecting news for: {query}")

    news_items = collector.fetch_news(query=query, count=5)

    if not news_items:
        print("No news found. Exiting.")
        return

    # Save raw data
    collector.save_news(news_items, "data/daily_news.json")

    print(f"Collected {len(news_items)} items.")
    for i, item in enumerate(news_items, 1):
        print(f"{i}. {item.get('title', 'No Title')} ({item.get('source', 'Unknown')})")

    # 2. Scrape full content (deep mode)
    if deep_analysis:
        print(f"\n[2/5] Scraping full article content...")
        collector.enrich_with_content(news_items)
        scraped = sum(1 for it in news_items if it.get("full_content"))
        print(f"Scraped full content for {scraped}/{len(news_items)} articles.")
    else:
        print(f"\n[2/5] Skipping article scraping (deep analysis off).")

    # 3. Load previous report for comparison
    previous_report = None
    if deep_analysis:
        hm = HistoryManager(history_dir=HISTORY_DIR)
        prev_runs = hm.list_runs()
        if prev_runs:
            prev_data = hm.load_run(prev_runs[0]["run_id"])
            if prev_data and prev_data.get("report"):
                previous_report = prev_data["report"]
                print(f"[Context] Loaded previous report ({len(previous_report)} chars) for trend comparison.")

    # 4. Analysis
    print(f"\n[3/5] Analyzing news with Gemini (language={language}, deep={deep_analysis})...")
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
        print(f"Analysis failed: {e}")
        return

    # 5. Media Gen
    print("\n[4/5] Generating media...")
    media_gen = MediaGenerator()
    try:
        audio_file = media_gen.generate_audio(
            analysis_report, "data/daily_briefing.mp3",
            language=language,
        )
        if audio_file:
            print(f"Audio generated: {audio_file}")
        else:
            print("Audio generation skipped (check API Key).")
    except Exception as e:
        print(f"Audio generation failed: {e}")

    # 6. PDF Export
    print("\n[5/5] Exporting PDF...")
    try:
        pdf_title = "金融分析简报" if language == "zh" else "Financial Analysis Briefing"
        pdf_file = media_gen.generate_pdf(
            analysis_report, "data/daily_briefing.pdf",
            language=language, title=pdf_title,
        )
        if pdf_file:
            print(f"PDF generated: {pdf_file}")
    except Exception as e:
        print(f"PDF generation failed: {e}")

    print("\n✅ Workflow Complete!")


if __name__ == "__main__":
    main()
