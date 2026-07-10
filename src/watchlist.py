"""
自选清单 (Watchlist) 管理模块。

以本地 JSON 文件持久化用户自定义标的列表，并提供：
- 增删标的（含去重、规范化）
- 批量拉取实时报价 + 技术信号摘要

设计为纯逻辑层，不依赖 streamlit，便于单元测试。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)

DEFAULT_WATCHLIST = ["AAPL", "MSFT", "SPY", "BTC-USD"]


@dataclass
class Quote:
    ticker: str
    name: str = ""
    price: float | None = None
    change_pct: float | None = None
    rsi: float | None = None
    tech_score: float = 0.0
    signal: str = "neutral"
    ok: bool = False


class WatchlistManager:
    """管理自选标的的持久化与报价拉取。"""

    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    # ──────────────── 持久化 ────────────────

    def load(self) -> list[str]:
        if not os.path.exists(self.path):
            return list(DEFAULT_WATCHLIST)
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            tickers = data.get("tickers", []) if isinstance(data, dict) else data
            return [str(t).strip().upper() for t in tickers if str(t).strip()]
        except Exception:
            logger.exception("Failed to load watchlist, returning defaults")
            return list(DEFAULT_WATCHLIST)

    def save(self, tickers: list[str]) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"tickers": tickers}, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("Failed to save watchlist")

    @staticmethod
    def normalize(ticker: str) -> str:
        return str(ticker or "").strip().upper()

    def add(self, ticker: str) -> tuple[bool, list[str]]:
        """添加标的。返回 (是否新增, 最新列表)。"""
        ticker = self.normalize(ticker)
        tickers = self.load()
        if not ticker:
            return False, tickers
        if ticker in tickers:
            return False, tickers
        tickers.append(ticker)
        self.save(tickers)
        return True, tickers

    def remove(self, ticker: str) -> list[str]:
        ticker = self.normalize(ticker)
        tickers = [t for t in self.load() if t != ticker]
        self.save(tickers)
        return tickers

    # ──────────────── 报价 ────────────────

    def fetch_quotes(self, tickers: list[str] | None = None) -> list[Quote]:
        """批量拉取报价与技术信号。网络失败时返回 ok=False 的占位。"""
        import pandas as pd
        import yfinance as yf

        from src.indicators import analyze_indicators
        from src.indicators import rsi as rsi_calc

        tickers = tickers if tickers is not None else self.load()
        if not tickers:
            return []

        quotes: list[Quote] = []
        try:
            data = yf.download(tickers, period="3mo", progress=False, group_by="ticker")
        except Exception:
            logger.exception("Failed to download watchlist quotes")
            return [Quote(ticker=t) for t in tickers]

        for tk in tickers:
            q = Quote(ticker=tk, name=tk)
            try:
                # Handle both single- and multi-ticker frame shapes
                if isinstance(data.columns, pd.MultiIndex):
                    if tk in data.columns.get_level_values(0):
                        sub = data[tk]
                    else:
                        quotes.append(q)
                        continue
                else:
                    sub = data

                close = sub["Close"].dropna()
                if len(close) < 2:
                    quotes.append(q)
                    continue

                q.price = float(close.iloc[-1])
                q.change_pct = float((close.iloc[-1] / close.iloc[-2] - 1) * 100)
                r = rsi_calc(close).dropna()
                q.rsi = float(r.iloc[-1]) if not r.empty else None

                snap = analyze_indicators(sub if "Open" in sub.columns else pd.DataFrame({"Close": close}))
                q.tech_score = snap.tech_score
                q.signal = _score_to_signal(snap.tech_score)
                q.ok = True
            except Exception:
                logger.debug("Failed to compute quote for %s", tk, exc_info=True)
            quotes.append(q)

        return quotes


def _score_to_signal(score: float) -> str:
    if score >= 0.5:
        return "strong_bull"
    if score >= 0.2:
        return "bull"
    if score <= -0.5:
        return "strong_bear"
    if score <= -0.2:
        return "bear"
    return "neutral"


def quote_to_dict(q: Quote) -> dict:
    return asdict(q)
