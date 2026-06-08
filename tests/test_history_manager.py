import json
from datetime import datetime as real_datetime

from src.history import HistoryManager


def test_generate_run_id_handles_collisions(tmp_path, monkeypatch):
    hm = HistoryManager(history_dir=str(tmp_path))

    class FixedDateTime:
        @classmethod
        def now(cls):
            return real_datetime(2026, 3, 18, 12, 0, 0, 123456)

    import src.history as history_module

    monkeypatch.setattr(history_module, "datetime", FixedDateTime)

    existing = tmp_path / "20260318_120000_123456"
    existing.mkdir()

    run_id = hm._generate_run_id()
    assert run_id == "20260318_120000_123456_1"


def test_save_and_load_run_roundtrip(tmp_path):
    hm = HistoryManager(history_dir=str(tmp_path))
    run_id = hm.save_run(
        news_items=[{"title": "A", "url": "https://example.com"}],
        report="# Report",
        query="market",
        sources=["CNBC"],
        time_range="24h",
        briefing_length="short",
    )

    loaded = hm.load_run(run_id)
    assert loaded is not None
    assert loaded["report"] == "# Report"
    assert loaded["news"][0]["title"] == "A"

    meta = json.loads((tmp_path / run_id / "metadata.json").read_text(encoding="utf-8"))
    assert meta["query"] == "market"
    assert meta["num_articles"] == 1


def test_list_runs_skips_corrupted_metadata(tmp_path):
    hm = HistoryManager(history_dir=str(tmp_path))
    valid_run_id = hm.save_run(news_items=[], report="# Valid", query="valid")

    bad_dir = tmp_path / "bad_run"
    bad_dir.mkdir()
    (bad_dir / "metadata.json").write_text("{bad json", encoding="utf-8")

    runs = hm.list_runs()
    assert [r["run_id"] for r in runs] == [valid_run_id]


def test_load_run_returns_partial_data_when_json_is_corrupted(tmp_path):
    hm = HistoryManager(history_dir=str(tmp_path))
    run_dir = tmp_path / "manual_run"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text("{bad json", encoding="utf-8")
    (run_dir / "news.json").write_text("{bad json", encoding="utf-8")
    (run_dir / "report.md").write_text("# Still readable", encoding="utf-8")

    loaded = hm.load_run("manual_run")
    assert loaded is not None
    assert loaded["run_id"] == "manual_run"
    assert loaded["report"] == "# Still readable"
    assert "metadata" not in loaded
    assert "news" not in loaded
