"""
市场情绪仪表盘组件。
将情绪分析数据渲染为可视化仪表盘。
"""

from datetime import datetime

import streamlit as st

from src.i18n import t, sig_label, vix_label
from src.sentiment import MarketSentimentAnalyzer, SIGNAL_EMOJI


@st.cache_data(ttl=300, show_spinner=False)
def _cached_sentiment():
    return MarketSentimentAnalyzer.analyze()


def render_asset_card(a):
    """将 AssetSignal 渲染为美化的卡片 HTML。"""
    emoji = SIGNAL_EMOJI.get(a.signal, "⚪")
    label = sig_label(a.signal)
    day_cls = "positive" if a.change_1d_pct >= 0 else "negative"
    week_cls = "positive" if a.change_5d_pct >= 0 else "negative"
    return (
        f'<div class="asset-card">'
        f'<div class="asset-name">{emoji} {a.name} — {label} <span style="float:right;font-size:14px;">score <code>{a.score:+.2f}</code></span></div>'
        f'<div class="asset-meta">'
        f'{t("col_price")}: <b>{a.price:.2f}</b> &nbsp;|&nbsp; '
        f'1D: <span class="{day_cls}"><b>{a.change_1d_pct:+.1f}%</b></span> &nbsp;|&nbsp; '
        f'5D: <span class="{week_cls}"><b>{a.change_5d_pct:+.1f}%</b></span>'
        f'</div>'
        f'<div class="asset-reason">{a.reason}</div>'
        f'</div>'
    )


def render_sentiment_tab():
    """渲染完整的市场情绪 Tab 内容。"""
    st.subheader(t("sentiment_title"))
    st.caption(t("sentiment_caption"))

    # 手动刷新按钮 + 上次更新时间
    ctrl_col1, ctrl_col2 = st.columns([1, 3])
    with ctrl_col1:
        refresh_clicked = st.button(t("refresh_data"), key="refresh_sentiment", use_container_width=True)
    with ctrl_col2:
        last_ts = st.session_state.get("sentiment_last_updated")
        if last_ts:
            st.caption(t("last_updated", time=last_ts))

    # 只在点击刷新或已有缓存时加载
    if refresh_clicked:
        _cached_sentiment.clear()
        st.session_state["sentiment_loaded"] = True
        st.session_state["sentiment_last_updated"] = datetime.now().strftime("%H:%M:%S")
        st.rerun()

    if not st.session_state.get("sentiment_loaded", False):
        st.info(t("click_refresh"))
        return

    with st.spinner(t("analyzing_sentiment")):
        sentiment = _cached_sentiment()

    if not sentiment.all_assets:
        st.warning(t("sentiment_unavailable"))
        return

    # -- 顶部总览指标 --
    overview_cols = st.columns(4)
    with overview_cols[0]:
        _sig_emoji = SIGNAL_EMOJI.get(sentiment.overall_signal, "⚪")
        _sig_label = sig_label(sentiment.overall_signal)
        st.metric(
            t("overall_sentiment"),
            f"{_sig_emoji} {_sig_label}",
            f"{sentiment.overall_score:+.2f}",
        )
    with overview_cols[1]:
        st.metric(t("bullish"), sentiment.bull_count)
    with overview_cols[2]:
        st.metric(t("bearish"), sentiment.bear_count)
    with overview_cols[3]:
        _vix_label = vix_label(sentiment.vix_level)
        st.metric("VIX", f"{sentiment.vix_value:.1f}", _vix_label)

    # -- 多空比例条 --
    total = sentiment.bull_count + sentiment.bear_count + sentiment.neutral_count
    if total > 0:
        bull_pct = sentiment.bull_count / total * 100
        bear_pct = sentiment.bear_count / total * 100
        neutral_pct = sentiment.neutral_count / total * 100
        st.markdown(
            f'<div class="sentiment-bar">'
            f'<div style="width:{bull_pct}%; background:linear-gradient(90deg,#16a34a,#22c55e);">'
            f'{bull_pct:.0f}% {t("bull_label")}</div>'
            f'<div style="width:{neutral_pct}%; background:linear-gradient(90deg,#4b5563,#6b7280);">'
            f'{neutral_pct:.0f}% {t("neutral_label")}</div>'
            f'<div style="width:{bear_pct}%; background:linear-gradient(90deg,#ef4444,#dc2626);">'
            f'{bear_pct:.0f}% {t("bear_label")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # -- 机会 & 风险 双栏 --
    opp_col, risk_col = st.columns(2)

    with opp_col:
        st.markdown(t("opportunities"))
        if sentiment.opportunities:
            cards_html = "".join(render_asset_card(a) for a in sentiment.opportunities)
            st.markdown(cards_html, unsafe_allow_html=True)
        else:
            st.info(t("no_opportunities"))

    with risk_col:
        st.markdown(t("risks_title"))
        if sentiment.risks:
            cards_html = "".join(render_asset_card(a) for a in sentiment.risks)
            st.markdown(cards_html, unsafe_allow_html=True)
        else:
            st.info(t("no_risks"))

    # -- 各板块详情 --
    st.markdown("---")
    st.subheader(t("sector_breakdown"))
    for group_name, sector in sentiment.sectors.items():
        sector_emoji = SIGNAL_EMOJI.get(sector.signal, "⚪")
        sector_label_text = sig_label(sector.signal)
        with st.expander(
            f"{sector_emoji} **{group_name}** — {sector_label_text} "
            f"({t('col_score')}: {sector.avg_score:+.2f} | 🟢{sector.bull_count} ⚪{sector.neutral_count} 🔴{sector.bear_count})",
            expanded=False,
        ):
            if sector.assets:
                rows = []
                for a in sorted(sector.assets, key=lambda x: x.score, reverse=True):
                    rows.append({
                        t("col_signal"): f"{SIGNAL_EMOJI.get(a.signal, '⚪')} {sig_label(a.signal)}",
                        t("col_asset"): a.name,
                        t("col_price"): f"{a.price:.2f}",
                        "1D %": f"{a.change_1d_pct:+.1f}%",
                        "5D %": f"{a.change_5d_pct:+.1f}%",
                        "20D %": f"{a.change_20d_pct:+.1f}%",
                        t("col_ma20"): t("col_above") if a.above_ma20 else t("col_below"),
                        t("col_vol_ratio"): f"{a.volume_ratio:.1f}x",
                        t("col_score"): f"{a.score:+.2f}",
                        t("col_reason"): a.reason,
                    })
                st.dataframe(rows, use_container_width=True, hide_index=True)
