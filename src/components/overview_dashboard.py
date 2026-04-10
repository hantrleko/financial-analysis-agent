"""
Dashboard 概览组件。
提供全局市场概览、最近分析摘要、系统状态信息。
"""

from __future__ import annotations

import html as html_mod
import logging

import streamlit as st

from src.config import AVAILABLE_SOURCES, VERSION
from src.history import HistoryManager
from src.i18n import t
from src.styles import render_skeleton

logger = logging.getLogger(__name__)


def _fetch_market_pulse() -> list[dict]:
    """获取关键市场指标快照。返回 [{name, price, change_pct}] 列表。"""
    try:
        import yfinance as yf

        key_tickers = {
            "S&P 500": "SPY",
            "Nasdaq": "QQQ",
            "Gold": "GC=F",
            "BTC": "BTC-USD",
            "VIX": "^VIX",
            "EUR/USD": "EURUSD=X",
        }
        tickers_list = list(key_tickers.values())
        data = yf.download(tickers_list, period="5d", progress=False)

        if data.empty:
            return []

        close = data["Close"]
        results = []
        for name, ticker in key_tickers.items():
            try:
                series = close[ticker].dropna()
                if len(series) < 2:
                    continue
                current = float(series.iloc[-1])
                prev = float(series.iloc[-2])
                change_pct = (current - prev) / prev * 100
                results.append({"name": name, "price": current, "change_pct": change_pct})
            except Exception:
                pass

        return results
    except Exception as e:
        logger.warning("Failed to fetch market pulse: %s", e)
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _cached_market_pulse() -> list[dict]:
    return _fetch_market_pulse()


def _render_market_ticker(pulse_data: list[dict]) -> str:
    """渲染市场快照迷你组件 HTML。"""
    items = []
    for item in pulse_data:
        direction = "up" if item["change_pct"] >= 0 else "down"
        arrow = "+" if item["change_pct"] >= 0 else ""
        name_esc = html_mod.escape(item["name"])
        items.append(
            f'<div class="tick-item {direction}">'
            f'<span class="tick-name">{name_esc}</span> '
            f"{item['price']:.2f} "
            f"<b>{arrow}{item['change_pct']:.1f}%</b>"
            f"</div>"
        )
    return '<div class="market-ticker">' + "".join(items) + "</div>"


def _render_overview_card(icon: str, value: str, label: str, color_cls: str = "card-blue") -> str:
    """渲染概览卡片 HTML。"""
    return (
        f'<div class="overview-card {color_cls}">'
        f'<div class="card-icon">{icon}</div>'
        f'<div class="card-value">{html_mod.escape(str(value))}</div>'
        f'<div class="card-label">{html_mod.escape(label)}</div>'
        f"</div>"
    )


def render_overview_tab(history_dir: str) -> None:
    """渲染概览 Tab 内容。"""
    st.subheader(t("overview_title"))
    st.caption(t("overview_caption"))

    # ---- 概览卡片 row ----
    hm = HistoryManager(history_dir=history_dir)
    runs = hm.list_runs()
    total_runs = len(runs)
    last_run_time = runs[0].get("timestamp", "N/A")[:16] if runs else "N/A"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            _render_overview_card("📊", str(total_runs), t("overview_total_runs"), "card-blue"),
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            _render_overview_card("🕐", last_run_time, t("overview_last_run"), "card-green"),
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            _render_overview_card("📡", str(len(AVAILABLE_SOURCES)), t("overview_sources_count"), "card-amber"),
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            _render_overview_card("🤖", VERSION, "System Version", "card-purple"),
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ---- 市场脉搏 ----
    st.markdown(f"### {t('overview_market_pulse')}")

    pulse_placeholder = st.empty()
    pulse_placeholder.markdown(render_skeleton(1), unsafe_allow_html=True)

    pulse_data = _cached_market_pulse()
    if pulse_data:
        pulse_placeholder.markdown(_render_market_ticker(pulse_data), unsafe_allow_html=True)

        # Metric cards for key indicators
        mcols = st.columns(len(pulse_data))
        for i, item in enumerate(pulse_data):
            with mcols[i]:
                delta_str = f"{item['change_pct']:+.2f}%"
                st.metric(
                    item["name"],
                    f"{item['price']:.2f}",
                    delta=delta_str,
                    delta_color="normal" if item["name"] != "VIX" else "inverse",
                )
    else:
        pulse_placeholder.info(t("market_snapshot_error"))

    st.markdown("---")

    # ---- 最近分析 ----
    st.markdown(f"### {t('overview_recent_analyses')}")

    if runs:
        for run in runs[:5]:
            run_time = run.get("timestamp", "N/A")[:19]
            query = run.get("query", "")[:50]
            n_articles = run.get("num_articles", 0)
            has_audio = "🔊" if run.get("has_audio") else ""
            has_pdf = "📄" if run.get("has_pdf") else ""

            st.markdown(f"**{run_time}** — _{query}_ — {n_articles} articles {has_audio} {has_pdf}")
    else:
        st.info(t("overview_no_analyses"))

    # ---- 快速开始提示 ----
    if not runs:
        st.markdown("---")
        st.markdown(f"### {t('overview_quick_start')}")
        st.info(t("overview_quick_start_hint"))
