"""历史记录 CSV 导出测试。"""

from __future__ import annotations

from src.components.history_view import _export_runs_as_csv


def test_export_csv_basic():
    runs = [
        {
            "run_id": "20240101_120000",
            "timestamp": "2024-01-01T12:00:00",
            "query": "market trends",
            "sources": ["CNBC", "Bloomberg"],
            "num_articles": 5,
            "time_range": "24h",
            "briefing_length": "medium",
        }
    ]
    data = _export_runs_as_csv(runs)
    text = data.decode("utf-8-sig")
    assert "run_id" in text
    assert "market trends" in text
    assert "CNBC; Bloomberg" in text
    assert "20240101_120000" in text


def test_export_csv_empty():
    data = _export_runs_as_csv([])
    text = data.decode("utf-8-sig")
    # header row only
    assert "run_id" in text
    assert text.strip().count("\n") == 0


def test_export_csv_missing_fields():
    runs = [{"run_id": "x", "query": "q"}]
    data = _export_runs_as_csv(runs)
    text = data.decode("utf-8-sig")
    assert "x" in text
