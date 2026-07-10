"""
自选清单 Tab 组件。
展示用户自定义标的的实时报价、涨跌、RSI 与技术信号，支持增删与刷新。
"""

from __future__ import annotations

import os
from datetime import datetime

import streamlit as st

from src.i18n import t
from src.sentiment import SIGNAL_EMOJI
from src.watchlist import WatchlistManager


@st.cache_data(ttl=180, show_spinner=False)
def _cached_quotes(path: str, tickers_tuple: tuple[str, ...]):
    wm = WatchlistManager(path)
    return [q for q in wm.fetch_quotes(list(tickers_tuple))]


def render_watchlist_tab(base_dir: str) -> None:
    """渲染自选清单 Tab。"""
    st.subheader(t("watchlist_title"))
    st.caption(t("watchlist_caption"))

    wl_path = os.path.join(base_dir, "data", "watchlist.json")
    wm = WatchlistManager(wl_path)
    tickers = wm.load()

    # ---- Add ticker row ----
    add_col, btn_col, refresh_col = st.columns([3, 1, 1])
    with add_col:
        new_ticker = st.text_input(
            t("watchlist_add"), key="watchlist_input", label_visibility="collapsed", placeholder=t("watchlist_add")
        )
    with btn_col:
        add_clicked = st.button(t("watchlist_add_btn"), use_container_width=True, key="watchlist_add_btn")
    with refresh_col:
        refresh_clicked = st.button(t("watchlist_refresh"), use_container_width=True, key="watchlist_refresh_btn")

    if add_clicked and new_ticker.strip():
        norm = WatchlistManager.normalize(new_ticker)
        if norm in tickers:
            st.warning(t("watchlist_exists", ticker=norm))
        else:
            added, tickers = wm.add(norm)
            if added:
                _cached_quotes.clear()
                st.success(t("watchlist_added", ticker=norm))
                st.rerun()

    if refresh_clicked:
        _cached_quotes.clear()
        st.session_state["watchlist_last_updated"] = datetime.now().strftime("%H:%M:%S")
        st.rerun()

    last_ts = st.session_state.get("watchlist_last_updated")
    if last_ts:
        st.caption(t("last_updated", time=last_ts))

    if not tickers:
        st.info(t("watchlist_empty"))
        return

    with st.spinner(t("watchlist_loading")):
        quotes = _cached_quotes(wl_path, tuple(tickers))

    # ---- Metric cards row ----
    valid = [q for q in quotes if q.ok]
    if valid:
        cols = st.columns(min(len(valid), 5))
        for i, q in enumerate(valid[:5]):
            with cols[i]:
                st.metric(
                    q.ticker,
                    f"{q.price:.2f}" if q.price is not None else "—",
                    delta=f"{q.change_pct:+.2f}%" if q.change_pct is not None else None,
                )

    # ---- Detailed table with remove buttons ----
    st.markdown("---")
    header = st.columns([2, 1.2, 1.2, 1, 1.6, 0.8])
    header[0].markdown(f"**{t('watchlist_col_ticker')}**")
    header[1].markdown(f"**{t('watchlist_col_price')}**")
    header[2].markdown(f"**{t('watchlist_col_change')}**")
    header[3].markdown(f"**{t('watchlist_col_rsi')}**")
    header[4].markdown(f"**{t('watchlist_col_signal')}**")
    header[5].markdown("")

    from src.i18n import sig_label

    for q in quotes:
        row = st.columns([2, 1.2, 1.2, 1, 1.6, 0.8])
        row[0].markdown(f"**{q.ticker}**")
        if q.ok:
            row[1].markdown(f"{q.price:.2f}" if q.price is not None else "—")
            if q.change_pct is not None:
                color = "#22c55e" if q.change_pct >= 0 else "#ef4444"
                row[2].markdown(
                    f"<span style='color:{color}'>{q.change_pct:+.2f}%</span>", unsafe_allow_html=True
                )
            else:
                row[2].markdown("—")
            row[3].markdown(f"{q.rsi:.0f}" if q.rsi is not None else "—")
            emoji = SIGNAL_EMOJI.get(q.signal, "⚪")
            row[4].markdown(f"{emoji} {sig_label(q.signal)} ({q.tech_score:+.2f})")
        else:
            row[1].markdown("—")
            row[2].markdown(f"<span style='color:#f59e0b'>{t('watchlist_invalid', ticker=q.ticker)}</span>",
                            unsafe_allow_html=True)
            row[3].markdown("—")
            row[4].markdown("—")
        if row[5].button(t("watchlist_remove"), key=f"wl_rm_{q.ticker}"):
            wm.remove(q.ticker)
            _cached_quotes.clear()
            st.rerun()
