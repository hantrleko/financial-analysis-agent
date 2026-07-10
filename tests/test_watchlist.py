"""自选清单模块单元测试（不含网络调用）。"""

from __future__ import annotations

import os

from src.watchlist import DEFAULT_WATCHLIST, Quote, WatchlistManager, _score_to_signal, quote_to_dict


def test_load_defaults_when_missing(tmp_path):
    wm = WatchlistManager(os.path.join(tmp_path, "wl.json"))
    assert wm.load() == list(DEFAULT_WATCHLIST)


def test_add_and_persist(tmp_path):
    path = os.path.join(tmp_path, "wl.json")
    wm = WatchlistManager(path)
    added, tickers = wm.add("nvda")
    assert added is True
    assert "NVDA" in tickers
    # New instance should load persisted data
    wm2 = WatchlistManager(path)
    assert "NVDA" in wm2.load()


def test_add_duplicate_noop(tmp_path):
    wm = WatchlistManager(os.path.join(tmp_path, "wl.json"))
    wm.add("AAPL")
    added, tickers = wm.add("aapl")
    assert added is False
    assert tickers.count("AAPL") == 1


def test_add_empty_noop(tmp_path):
    wm = WatchlistManager(os.path.join(tmp_path, "wl.json"))
    added, _ = wm.add("   ")
    assert added is False


def test_remove(tmp_path):
    wm = WatchlistManager(os.path.join(tmp_path, "wl.json"))
    wm.add("TSLA")
    tickers = wm.remove("tsla")
    assert "TSLA" not in tickers


def test_normalize():
    assert WatchlistManager.normalize("  aapl ") == "AAPL"
    assert WatchlistManager.normalize(None) == ""


def test_score_to_signal():
    assert _score_to_signal(0.7) == "strong_bull"
    assert _score_to_signal(0.3) == "bull"
    assert _score_to_signal(0.0) == "neutral"
    assert _score_to_signal(-0.3) == "bear"
    assert _score_to_signal(-0.7) == "strong_bear"


def test_quote_to_dict():
    q = Quote(ticker="AAPL", price=100.0, ok=True)
    d = quote_to_dict(q)
    assert d["ticker"] == "AAPL"
    assert d["price"] == 100.0
    assert d["ok"] is True


def test_corrupt_file_falls_back(tmp_path):
    path = os.path.join(tmp_path, "wl.json")
    with open(path, "w") as f:
        f.write("{not valid json")
    wm = WatchlistManager(path)
    assert wm.load() == list(DEFAULT_WATCHLIST)
