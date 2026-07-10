"""
行情图表组件。
渲染资产价格走势图表，支持手动刷新。
新增：K线图模式、相关性矩阵、自定义日期范围。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st

from src.i18n import t
from src.indicators import analyze_indicators
from src.visualizer import (
    ASSET_GROUPS,
    create_asset_dashboard,
    create_correlation_matrix,
    create_technical_chart,
    fetch_ohlcv_data,
)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_asset_dashboard(
    groups_tuple: tuple[str, ...],
    period: str,
    chart_type: str = "line",
    start: str | None = None,
    end: str | None = None,
) -> dict:
    return create_asset_dashboard(
        list(groups_tuple),
        period=period,
        chart_type=chart_type,
        start=start,
        end=end,
    )


@st.cache_data(ttl=300, show_spinner=False)
def _cached_correlation_matrix(
    tickers_tuple: tuple[str, ...],
    names_tuple: tuple[str, ...],
    period: str = "3mo",
):
    return create_correlation_matrix(list(tickers_tuple), list(names_tuple), period=period)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_ohlcv(ticker: str, period: str):
    return fetch_ohlcv_data(ticker, period=period)


CHART_PERIOD_OPTIONS_KEYS = [
    "period_1w",
    "period_1m",
    "period_3m",
    "period_6m",
    "period_1y",
]
CHART_PERIOD_VALUES = ["5d", "1mo", "3mo", "6mo", "1y"]


def render_charts_tab() -> None:
    """渲染完整的行情图表 Tab 内容。"""
    st.subheader(t("charts_title"))
    st.caption(t("charts_caption"))

    # ---- Controls row ----
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        chart_groups = st.multiselect(
            t("asset_groups"),
            options=list(ASSET_GROUPS.keys()),
            default=list(ASSET_GROUPS.keys())[:3],
            key="chart_groups",
        )
    with c2:
        period_labels = [t(k) for k in CHART_PERIOD_OPTIONS_KEYS]
        chart_period_label = st.selectbox(
            t("period"),
            options=period_labels,
            index=1,
            key="chart_period",
        )
        chart_period = CHART_PERIOD_VALUES[period_labels.index(chart_period_label)]
    with c3:
        _type_options = {
            t("chart_line"): "line",
            t("chart_candlestick"): "candlestick",
            t("chart_technical"): "technical",
        }
        _type_label = st.selectbox(
            t("chart_type"),
            options=list(_type_options.keys()),
            index=0,
            key="chart_type_select",
        )
        chart_type = _type_options[_type_label]

    # Custom date range (optional)
    use_custom = st.checkbox(t("custom_date_range"), key="use_custom_date")
    custom_start: str | None = None
    custom_end: str | None = None
    if use_custom:
        d1, d2 = st.columns(2)
        with d1:
            _start = st.date_input(t("date_start"), value=datetime.now() - timedelta(days=90), key="chart_date_start")
        with d2:
            _end = st.date_input(t("date_end"), value=datetime.now(), key="chart_date_end")
        custom_start = _start.isoformat() if _start else None
        custom_end = _end.isoformat() if _end else None

    # 手动刷新按钮 + 自动刷新 toggle
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 1, 2])
    with ctrl_col1:
        refresh_clicked = st.button(t("refresh_data"), key="refresh_charts", use_container_width=True)
    with ctrl_col2:
        auto_refresh = st.checkbox(t("auto_refresh"), key="charts_auto_refresh", value=False)
    with ctrl_col3:
        last_ts = st.session_state.get("charts_last_updated")
        if last_ts:
            st.caption(t("last_updated", time=last_ts))

    if refresh_clicked:
        _cached_asset_dashboard.clear()
        _cached_correlation_matrix.clear()
        st.session_state["charts_loaded"] = True
        st.session_state["charts_last_updated"] = datetime.now().strftime("%H:%M:%S")
        st.rerun()

    # Auto-refresh timer
    if auto_refresh and st.session_state.get("charts_loaded", False):
        import time as _time

        _interval_mins = 5
        _last_auto = st.session_state.get("charts_last_auto_ts", 0)
        _now = _time.time()
        if _now - _last_auto > _interval_mins * 60:
            st.session_state["charts_last_auto_ts"] = _now
            _cached_asset_dashboard.clear()
            _cached_correlation_matrix.clear()
            st.session_state["charts_last_updated"] = datetime.now().strftime("%H:%M:%S")

    if not st.session_state.get("charts_loaded", False):
        st.info(t("click_refresh_charts"))
        return

    # ---- Technical analysis mode: single-asset multi-panel chart ----
    if chart_type == "technical":
        _render_technical_panel(chart_groups, chart_period)
        return

    if chart_groups:
        with st.spinner(t("loading_market")):
            figures = _cached_asset_dashboard(
                tuple(chart_groups),
                chart_period,
                chart_type,
                start=custom_start,
                end=custom_end,
            )
        for _group_name, fig in figures.items():
            st.plotly_chart(fig, use_container_width=True)

        # ---- Correlation matrix ----
        show_corr = st.checkbox(t("chart_correlation"), key="show_corr")
        if show_corr:
            all_tickers: list[str] = []
            all_names: list[str] = []
            for gn in chart_groups:
                assets = ASSET_GROUPS.get(gn, [])
                for a in assets:
                    if a["ticker"] not in all_tickers:
                        all_tickers.append(a["ticker"])
                        all_names.append(a["name"])
            if len(all_tickers) >= 2:
                with st.spinner(t("loading_market")):
                    corr_fig = _cached_correlation_matrix(
                        tuple(all_tickers),
                        tuple(all_names),
                        period="3mo",
                    )
                st.plotly_chart(corr_fig, use_container_width=True)
    else:
        st.info(t("select_group"))


def _render_technical_panel(chart_groups: list[str], chart_period: str) -> None:
    """渲染单资产多面板技术分析视图。"""
    st.markdown(f"### {t('tech_indicators')}")

    # Build asset options from selected groups (fall back to all groups)
    options: dict[str, str] = {}
    groups_to_use = chart_groups or list(ASSET_GROUPS.keys())
    for gn in groups_to_use:
        for a in ASSET_GROUPS.get(gn, []):
            options[f"{a['name']} ({a['ticker']})"] = a["ticker"]

    if not options:
        st.info(t("select_group"))
        return

    col_a, col_b, col_c, col_d = st.columns([3, 1, 1, 1])
    with col_a:
        asset_label = st.selectbox(t("tech_pick_asset"), options=list(options.keys()), key="tech_asset")
    with col_b:
        show_bb = st.checkbox(t("tech_show_bollinger"), value=True, key="tech_bb")
    with col_c:
        show_rsi = st.checkbox(t("tech_show_rsi"), value=True, key="tech_rsi")
    with col_d:
        show_macd = st.checkbox(t("tech_show_macd"), value=True, key="tech_macd")

    ticker = options[asset_label]
    # Use a longer period for meaningful indicators
    tech_period = "6mo" if chart_period in ("5d", "1mo", "3mo") else chart_period

    with st.spinner(t("loading_market")):
        ohlcv = _cached_ohlcv(ticker, tech_period)

    if ohlcv is None or ohlcv.empty:
        st.warning(t("watchlist_invalid", ticker=ticker))
        return

    fig = create_technical_chart(
        ohlcv,
        title=asset_label,
        show_bollinger=show_bb,
        show_rsi=show_rsi,
        show_macd=show_macd,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Indicator summary table + technical score
    snap = analyze_indicators(ohlcv)
    st.markdown(f"#### {t('tech_summary')}")
    score_cls = "🟢" if snap.tech_score >= 0.2 else "🔴" if snap.tech_score <= -0.2 else "⚪"
    st.metric(t("tech_score_label"), f"{score_cls} {snap.tech_score:+.2f}")

    rows = []

    def _fmt(v, suffix=""):
        return f"{v:.2f}{suffix}" if v is not None else "—"

    rows.append({t("watchlist_col_ticker"): "RSI(14)", t("tech_signal_col"): _fmt(snap.rsi)})
    rows.append({t("watchlist_col_ticker"): "MACD Hist", t("tech_signal_col"): _fmt(snap.macd_hist)})
    rows.append({t("watchlist_col_ticker"): "Bollinger %B", t("tech_signal_col"): _fmt(snap.bb_pctb)})
    rows.append({t("watchlist_col_ticker"): "Stochastic %K", t("tech_signal_col"): _fmt(snap.stoch_k)})
    rows.append({t("watchlist_col_ticker"): "ATR %", t("tech_signal_col"): _fmt(snap.atr_pct, "%")})
    rows.append({t("watchlist_col_ticker"): "SMA20", t("tech_signal_col"): _fmt(snap.sma20)})
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if snap.signals:
        st.markdown("  ".join(f"`{s}`" for s in snap.signals))
    else:
        st.caption(t("tech_no_signal"))
