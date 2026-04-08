"""
行情图表组件。
渲染资产价格走势图表，支持手动刷新。
"""

from datetime import datetime

import streamlit as st

from src.i18n import t
from src.visualizer import ASSET_GROUPS, create_asset_dashboard


@st.cache_data(ttl=300, show_spinner=False)
def _cached_asset_dashboard(groups_tuple, period):
    return create_asset_dashboard(list(groups_tuple), period=period)


CHART_PERIOD_OPTIONS_KEYS = [
    "period_1w", "period_1m", "period_3m", "period_6m", "period_1y",
]
CHART_PERIOD_VALUES = ["5d", "1mo", "3mo", "6mo", "1y"]


def render_charts_tab():
    """渲染完整的行情图表 Tab 内容。"""
    st.subheader(t("charts_title"))
    st.caption(t("charts_caption"))

    chart_col1, chart_col2 = st.columns([3, 1])
    with chart_col1:
        chart_groups = st.multiselect(
            t("asset_groups"),
            options=list(ASSET_GROUPS.keys()),
            default=list(ASSET_GROUPS.keys())[:3],
            key="chart_groups",
        )
    with chart_col2:
        period_labels = [t(k) for k in CHART_PERIOD_OPTIONS_KEYS]
        chart_period_label = st.selectbox(
            t("period"),
            options=period_labels,
            index=1,
            key="chart_period",
        )
    chart_period = CHART_PERIOD_VALUES[period_labels.index(chart_period_label)]

    # 手动刷新按钮
    ctrl_col1, ctrl_col2 = st.columns([1, 3])
    with ctrl_col1:
        refresh_clicked = st.button(t("refresh_data"), key="refresh_charts", use_container_width=True)
    with ctrl_col2:
        last_ts = st.session_state.get("charts_last_updated")
        if last_ts:
            st.caption(t("last_updated", time=last_ts))

    if refresh_clicked:
        _cached_asset_dashboard.clear()
        st.session_state["charts_loaded"] = True
        st.session_state["charts_last_updated"] = datetime.now().strftime("%H:%M:%S")
        st.rerun()

    if not st.session_state.get("charts_loaded", False):
        st.info(t("click_refresh_charts"))
        return

    if chart_groups:
        with st.spinner(t("loading_market")):
            figures = _cached_asset_dashboard(tuple(chart_groups), chart_period)
        for group_name, fig in figures.items():
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(t("select_group"))
