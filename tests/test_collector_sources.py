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
