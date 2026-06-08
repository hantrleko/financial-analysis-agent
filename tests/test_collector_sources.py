from src.collector import NewsCollector


def test_source_matches_supports_suffix():
    assert NewsCollector._source_matches("CNBC (Markets)", {"CNBC"})
    assert NewsCollector._source_matches("Bloomberg", {"Bloomberg"})
    assert not NewsCollector._source_matches("MarketWatch", {"CNBC"})


def test_fetch_news_passes_sources_to_rss(monkeypatch):
    collector = NewsCollector()
    captured = {}

    def fake_fetch_rss(*, count, time_range, sources):
        captured["sources"] = sources
        return []

    monkeypatch.setattr(collector, "_fetch_rss", fake_fetch_rss)
    monkeypatch.setattr(collector, "_fetch_google_news_rss", lambda *args, **kwargs: [])
    monkeypatch.setattr(collector, "_dedup", lambda items, count: items[:count])

    collector.fetch_news(
        query="test",
        count=5,
        sources=["CNBC", "Bloomberg"],
        time_range="24h",
        ai_search=False,
    )

    assert captured["sources"] == ["CNBC", "Bloomberg"]


def test_dedup_skips_empty_titles_and_url_fragments():
    items = [
        {"title": "", "url": "https://example.com/empty"},
        {"title": "Market Rally", "url": "https://example.com/a#section"},
        {"title": "Different title", "url": "https://example.com/a"},
        {"title": "Market Rally!", "url": "https://example.com/b"},
    ]

    result = NewsCollector._dedup(items, count=10)

    assert [item["title"] for item in result] == ["Market Rally"]


def test_enrich_with_content_continues_after_scrape_error(monkeypatch):
    collector = NewsCollector()
    news_items = [
        {"title": "Bad", "url": "https://example.com/bad"},
        {"title": "Good", "url": "https://example.com/good"},
        {"title": "No URL", "url": ""},
    ]

    def fake_scrape(url):
        if url.endswith("bad"):
            raise RuntimeError("boom")
        return "full article text"

    monkeypatch.setattr(collector, "scrape_content", fake_scrape)

    enriched = collector.enrich_with_content(news_items, max_scrape=3)

    assert enriched[0]["full_content"] == ""
    assert enriched[1]["full_content"] == "full article text"
    assert enriched[2]["full_content"] == ""
