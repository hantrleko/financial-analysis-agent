"""
市场情绪仪表盘组件。
将情绪分析数据渲染为可视化仪表盘，含仪表盘图、雷达图、热力图。
"""

from __future__ import annotations

import html as html_mod
from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from src.i18n import sig_label, t, vix_label
from src.sentiment import SIGNAL_EMOJI, MarketSentimentAnalyzer, SentimentReport


@st.cache_data(ttl=300, show_spinner=False)
def _cached_sentiment() -> SentimentReport:
    return MarketSentimentAnalyzer.analyze()


# -- Mini visualisations for metric cards --------------------------


def _sentiment_gauge(score: float) -> go.Figure:
    """Create a half-gauge chart for overall sentiment score (-1 to +1)."""
    color = "#22c55e" if score >= 0.2 else "#ef4444" if score <= -0.2 else "#64748b"
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "", "font": {"size": 28, "color": "#e2e8f0"}},
            gauge={
                "axis": {
                    "range": [-1, 1],
                    "tickwidth": 1,
                    "tickcolor": "#475569",
                    "tickfont": {"color": "#94a3b8", "size": 10},
                },
                "bar": {"color": color, "thickness": 0.6},
                "bgcolor": "#1e293b",
                "borderwidth": 0,
                "steps": [
                    {"range": [-1, -0.2], "color": "rgba(239,68,68,0.15)"},
                    {"range": [-0.2, 0.2], "color": "rgba(100,116,139,0.15)"},
                    {"range": [0.2, 1], "color": "rgba(34,197,94,0.15)"},
                ],
            },
        )
    )
    fig.update_layout(
        height=180,
        margin=dict(l=20, r=20, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e2e8f0"},
    )
    return fig


# -- Radar chart for sector strength --------------------------------


def _sector_radar(sentiment: SentimentReport) -> go.Figure:
    """Radar chart showing multi-dimensional sector strength comparison."""
    sector_names: list[str] = []
    sector_scores: list[float] = []
    for name, sec in sentiment.sectors.items():
        short = name.split(" ")[0] if " " in name else name[:12]
        sector_names.append(short)
        sector_scores.append(sec.avg_score)

    if not sector_names:
        fig = go.Figure()
        fig.update_layout(height=300, template="plotly_dark", title=t("sector_breakdown"))
        return fig

    # Close the polygon
    sector_names_closed = sector_names + [sector_names[0]]
    sector_scores_closed = sector_scores + [sector_scores[0]]

    fig = go.Figure(
        go.Scatterpolar(
            r=sector_scores_closed,
            theta=sector_names_closed,
            fill="toself",
            fillcolor="rgba(59,130,246,0.15)",
            line=dict(color="#3b82f6", width=2),
            marker=dict(size=6, color="#60a5fa"),
        )
    )
    fig.update_layout(
        polar=dict(
            bgcolor="#0f172a",
            radialaxis=dict(
                range=[-1, 1], showticklabels=True, tickfont=dict(size=9, color="#64748b"), gridcolor="#1e293b"
            ),
            angularaxis=dict(tickfont=dict(size=10, color="#cbd5e1"), gridcolor="#1e293b"),
        ),
        height=380,
        margin=dict(l=60, r=60, t=40, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        title=dict(text=t("sector_breakdown") + " Radar", font=dict(color="#e2e8f0", size=14)),
    )
    return fig


def _sector_heatmap(sentiment: SentimentReport) -> go.Figure:
    """Heatmap of sector sentiment scores grouped by region/type."""
    names: list[str] = []
    scores: list[float] = []
    for name, sec in sentiment.sectors.items():
        names.append(name)
        scores.append(round(sec.avg_score, 2))

    if not names:
        fig = go.Figure()
        fig.update_layout(height=200, template="plotly_dark")
        return fig

    fig = go.Figure(
        go.Heatmap(
            z=[scores],
            x=names,
            y=["Sentiment"],
            colorscale=[
                [0.0, "#dc2626"],
                [0.3, "#ef4444"],
                [0.45, "#64748b"],
                [0.55, "#64748b"],
                [0.7, "#22c55e"],
                [1.0, "#16a34a"],
            ],
            zmin=-1,
            zmax=1,
            text=[[f"{s:+.2f}" for s in scores]],
            texttemplate="%{text}",
            textfont={"size": 11, "color": "#e2e8f0"},
            hovertemplate="%{x}<br>Score: %{z:+.2f}<extra></extra>",
            colorbar=dict(
                title="Score",
                titlefont=dict(color="#94a3b8"),
                tickfont=dict(color="#94a3b8"),
            ),
        )
    )
    fig.update_layout(
        height=160,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0f172a",
        xaxis=dict(tickfont=dict(size=9, color="#94a3b8"), tickangle=-45),
        yaxis=dict(showticklabels=False),
        title=dict(text="Sector Sentiment Heatmap", font=dict(color="#e2e8f0", size=14)),
    )
    return fig


# -- Asset card rendering -------------------------------------------


def render_asset_card(a) -> str:
    """Render an AssetSignal as a styled HTML card with XSS-safe escaping."""
    emoji = SIGNAL_EMOJI.get(a.signal, "")
    label = sig_label(a.signal)
    day_cls = "positive" if a.change_1d_pct >= 0 else "negative"
    week_cls = "positive" if a.change_5d_pct >= 0 else "negative"
    name_esc = html_mod.escape(a.name)
    reason_esc = html_mod.escape(a.reason)
    return (
        f'<div class="asset-card">'
        f'<div class="asset-name">{emoji} {name_esc} &mdash; {label} '
        f'<span style="float:right;font-size:14px;">score '
        f"<code>{a.score:+.2f}</code></span></div>"
        f'<div class="asset-meta">'
        f"{t('col_price')}: <b>{a.price:.2f}</b> &nbsp;|&nbsp; "
        f'1D: <span class="{day_cls}"><b>{a.change_1d_pct:+.1f}%</b></span> '
        f"&nbsp;|&nbsp; "
        f'5D: <span class="{week_cls}"><b>{a.change_5d_pct:+.1f}%</b></span>'
        f"</div>"
        f'<div class="asset-reason">{reason_esc}</div>'
        f"</div>"
    )


def render_sentiment_tab() -> None:
    """Render the full Market Sentiment tab."""
    st.subheader(t("sentiment_title"))
    st.caption(t("sentiment_caption"))

    # Manual refresh button + last-updated timestamp
    ctrl_col1, ctrl_col2 = st.columns([1, 3])
    with ctrl_col1:
        refresh_clicked = st.button(t("refresh_data"), key="refresh_sentiment", use_container_width=True)
    with ctrl_col2:
        last_ts = st.session_state.get("sentiment_last_updated")
        if last_ts:
            st.caption(t("last_updated", time=last_ts))

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

    # -- Top overview: Gauge + Bull/Bear counts + VIX indicator --
    gauge_col, stats_col, vix_col = st.columns([2, 1, 1])

    with gauge_col:
        st.plotly_chart(_sentiment_gauge(sentiment.overall_score), use_container_width=True, key="gauge_chart")

    with stats_col:
        st.metric(t("bullish"), sentiment.bull_count)
        st.metric(t("bearish"), sentiment.bear_count)

    with vix_col:
        _vix_lbl = vix_label(sentiment.vix_level)
        st.metric("VIX", f"{sentiment.vix_value:.1f}", _vix_lbl)

    # -- Bull / Bear proportion bar --
    total = sentiment.bull_count + sentiment.bear_count + sentiment.neutral_count
    if total > 0:
        bull_pct = sentiment.bull_count / total * 100
        bear_pct = sentiment.bear_count / total * 100
        neutral_pct = sentiment.neutral_count / total * 100
        st.markdown(
            f'<div class="sentiment-bar">'
            f'<div style="width:{bull_pct}%; background:linear-gradient(90deg,#16a34a,#22c55e);">'
            f"{bull_pct:.0f}% {t('bull_label')}</div>"
            f'<div style="width:{neutral_pct}%; background:linear-gradient(90deg,#4b5563,#6b7280);">'
            f"{neutral_pct:.0f}% {t('neutral_label')}</div>"
            f'<div style="width:{bear_pct}%; background:linear-gradient(90deg,#ef4444,#dc2626);">'
            f"{bear_pct:.0f}% {t('bear_label')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # -- Sector Radar + Heatmap --
    st.markdown("---")
    radar_col, heat_col = st.columns(2)
    with radar_col:
        st.plotly_chart(_sector_radar(sentiment), use_container_width=True, key="radar_chart")
    with heat_col:
        st.plotly_chart(_sector_heatmap(sentiment), use_container_width=True, key="heatmap_chart")

    # -- Opportunities & Risks --
    st.markdown("---")
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

    # -- Sector details --
    st.markdown("---")
    st.subheader(t("sector_breakdown"))
    for group_name, sector in sentiment.sectors.items():
        sector_emoji = SIGNAL_EMOJI.get(sector.signal, "")
        sector_label_text = sig_label(sector.signal)
        with st.expander(
            f"{sector_emoji} **{group_name}** &mdash; {sector_label_text} "
            f"({t('col_score')}: {sector.avg_score:+.2f} | "
            f"Bull {sector.bull_count} Neutral {sector.neutral_count} Bear {sector.bear_count})",
            expanded=False,
        ):
            if sector.assets:
                rows: list[dict[str, str]] = []
                for a in sorted(sector.assets, key=lambda x: x.score, reverse=True):
                    rows.append(
                        {
                            t("col_signal"): f"{SIGNAL_EMOJI.get(a.signal, '')} {sig_label(a.signal)}",
                            t("col_asset"): a.name,
                            t("col_price"): f"{a.price:.2f}",
                            "1D %": f"{a.change_1d_pct:+.1f}%",
                            "5D %": f"{a.change_5d_pct:+.1f}%",
                            "20D %": f"{a.change_20d_pct:+.1f}%",
                            t("col_ma20"): t("col_above") if a.above_ma20 else t("col_below"),
                            t("col_vol_ratio"): f"{a.volume_ratio:.1f}x",
                            t("col_score"): f"{a.score:+.2f}",
                            t("col_reason"): a.reason,
                        }
                    )
                st.dataframe(rows, use_container_width=True, hide_index=True)
