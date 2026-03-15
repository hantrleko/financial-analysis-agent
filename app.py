import os
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

# 项目根目录加入 sys.path，以便导入 src 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from src.config import VERSION, AVAILABLE_SOURCES, REPORT_SECTORS
from src.collector import NewsCollector
from src.analyzer import FinancialAnalyzer
from src.media_gen import MediaGenerator, VOICE_PRESETS, EDGE_VOICE_PRESETS, TTS_ENGINES
from src.history import HistoryManager
from src.visualizer import ASSET_GROUPS, create_asset_dashboard

# 基础路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_DIR = os.path.join(BASE_DIR, "history")

# 时间范围映射
TIME_RANGE_OPTIONS = {
    "Past 24 Hours": "24h",
    "Past Week": "week",
    "Past Month": "month",
}

# 简报长度映射
BRIEFING_LENGTH_OPTIONS = {
    "Short (~200 words)": "short",
    "Medium (~400 words)": "medium",
    "Detailed (~800 words)": "detailed",
}

LANGUAGE_OPTIONS = {
    "English": "en",
    "中文": "zh",
}

# ──────────────────────────── 页面配置 ────────────────────────────
st.set_page_config(
    page_title="Financial Analysis System",
    page_icon="🏦",
    layout="wide",
)

# ──────────────────────────── 访问密码 ────────────────────────────
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "")

if ACCESS_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🏦 Automated Financial Analysis System")
        pwd = st.text_input("🔒 Please enter access password", type="password")
        if pwd:
            if pwd == ACCESS_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Wrong password.")
        st.stop()

st.title("🏦 Automated Financial Analysis System")
st.caption(f"Version {VERSION}")

# ──────────────────────────── 侧边栏 ────────────────────────────
st.sidebar.header("⚙️ Controls")

query = st.sidebar.text_input(
    "Search Query",
    value="latest financial news market trends",
)

sources = st.sidebar.multiselect(
    "News Sources",
    options=AVAILABLE_SOURCES,
    default=AVAILABLE_SOURCES,
)

time_range_label = st.sidebar.selectbox(
    "Time Range",
    options=list(TIME_RANGE_OPTIONS.keys()),
)
time_range = TIME_RANGE_OPTIONS[time_range_label]

num_articles = st.sidebar.slider(
    "Number of Articles",
    min_value=1,
    max_value=20,
    value=5,
)

briefing_label = st.sidebar.selectbox(
    "Briefing Length",
    options=list(BRIEFING_LENGTH_OPTIONS.keys()),
)
briefing_length = BRIEFING_LENGTH_OPTIONS[briefing_label]

language_label = st.sidebar.selectbox(
    "Output Language",
    options=list(LANGUAGE_OPTIONS.keys()),
)
language = LANGUAGE_OPTIONS[language_label]

# 板块选择
st.sidebar.divider()
st.sidebar.subheader("📂 Report Sectors")
selected_sectors = st.sidebar.multiselect(
    "Organize by Sectors (optional)",
    options=list(REPORT_SECTORS.keys()),
    help="选择后报告将按板块分类组织；不选则使用默认格式",
)
sector_values = [REPORT_SECTORS[s] for s in selected_sectors] if selected_sectors else None

# 语音设置
st.sidebar.divider()
st.sidebar.subheader("🔊 Audio & Export")

generate_audio = st.sidebar.checkbox("Generate Audio", value=True)

tts_engine_label = st.sidebar.selectbox(
    "TTS Engine",
    options=list(TTS_ENGINES.keys()),
    index=1 if language == "zh" else 0,
    disabled=not generate_audio,
    help="中文推荐使用 Edge TTS，免费且语音自然",
)
tts_engine = TTS_ENGINES[tts_engine_label]

# 根据引擎选择语音列表
if tts_engine == "edge_tts":
    voice_options = list(EDGE_VOICE_PRESETS.get(language, EDGE_VOICE_PRESETS["en"]).keys())
else:
    voice_options = list(VOICE_PRESETS.get(language, VOICE_PRESETS["en"]).keys())
voice_name = st.sidebar.selectbox(
    "Voice",
    options=voice_options,
    disabled=not generate_audio,
)

generate_pdf = st.sidebar.checkbox("Export PDF", value=True)

# 深度分析设置
st.sidebar.divider()
st.sidebar.subheader("🔬 Deep Analysis")
deep_analysis = st.sidebar.checkbox(
    "Enable Deep Analysis",
    value=True,
    help="开启后将：1) 抓取文章全文 2) 注入实时市场数据 3) Advanced Agent + Research 深度分析 4) 对比上期报告。耗时更长但深度显著提升。",
)
scrape_content = st.sidebar.checkbox(
    "Scrape Full Articles",
    value=True,
    disabled=not deep_analysis,
    help="抓取新闻原文正文，为分析提供更丰富的上下文",
)

run_clicked = st.sidebar.button("🚀 Run Analysis")

# 更新日志弹窗
st.sidebar.divider()

@st.dialog("📋 Update Log", width="large")
def _show_changelog():
    _changelog_path = os.path.join(BASE_DIR, "CHANGELOG.md")
    if os.path.exists(_changelog_path):
        with open(_changelog_path, "r", encoding="utf-8") as _f:
            st.markdown(_f.read())
    else:
        st.info("No changelog found.")

if st.sidebar.button("📋 Update Log"):
    _show_changelog()

# ──────────────────────────── 公共展示函数 ────────────────────────────
def display_result(news_items, report, audio_path=None, pdf_path=None):
    """统一展示分析结果（避免运行/缓存两处重复代码）。"""
    with st.expander(
        f"📰 Collected News ({len(news_items)} articles)", expanded=False
    ):
        for item in news_items:
            st.markdown(
                f"**{item.get('title', 'No Title')}** "
                f"— *{item.get('source', 'Unknown')}*"
            )
            st.caption(item.get("description", ""))
            st.divider()

    st.subheader("📝 Analysis Report")
    st.markdown(report)

    if audio_path and os.path.exists(audio_path):
        st.subheader("🔊 Audio Briefing")
        st.audio(audio_path)

    if pdf_path and os.path.exists(pdf_path):
        st.subheader("📄 PDF Briefing")
        with open(pdf_path, "rb") as f:
            st.download_button(
                label="⬇️ Download PDF",
                data=f,
                file_name="daily_briefing.pdf",
                mime="application/pdf",
            )


# ──────────────────────────── yfinance 缓存 ────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def cached_asset_dashboard(groups_tuple, period):
    """缓存 yfinance 数据 5 分钟，避免重复拉取。"""
    return create_asset_dashboard(list(groups_tuple), period=period)


# ──────────────────────────── 主区域 ────────────────────────────
tab_analysis, tab_charts, tab_history = st.tabs(["📊 Analysis", "📈 Market Charts", "📜 History"])

# ─────────────── Analysis Tab ───────────────
with tab_analysis:
    if run_clicked:
        try:
            os.makedirs(DATA_DIR, exist_ok=True)

            # 1. 采集新闻
            with st.spinner("Collecting news..."):
                collector = NewsCollector()
                news_items = collector.fetch_news(
                    query=query,
                    count=num_articles,
                    sources=sources,
                    time_range=time_range,
                )

            if not news_items:
                st.warning("No news articles found. Try a different query.")
            else:
                # 1b. 抓取全文（深度分析模式）
                if deep_analysis and scrape_content:
                    with st.spinner("Scraping full article content..."):
                        collector.enrich_with_content(news_items)
                    scraped = sum(1 for it in news_items if it.get("full_content"))
                    st.caption(f"📄 Scraped full content for {scraped}/{len(news_items)} articles")

                # 展示采集结果
                with st.expander(
                    f"📰 Collected News ({len(news_items)} articles)", expanded=False
                ):
                    for item in news_items:
                        st.markdown(
                            f"**{item.get('title', 'No Title')}** "
                            f"— *{item.get('source', 'Unknown')}*"
                        )
                        desc = item.get("description", "")
                        full = item.get("full_content", "")
                        if full:
                            st.caption(f"{desc}\n\n📄 _{len(full)} chars of full content scraped_")
                        else:
                            st.caption(desc)
                        st.divider()

                # 1c. 加载上期报告（深度分析模式）
                previous_report = None
                if deep_analysis:
                    hm_prev = HistoryManager(history_dir=HISTORY_DIR)
                    prev_runs = hm_prev.list_runs()
                    if prev_runs:
                        prev_data = hm_prev.load_run(prev_runs[0]["run_id"])
                        if prev_data and prev_data.get("report"):
                            previous_report = prev_data["report"]

                # 2. You.com AI 分析
                st.subheader("📝 Analysis Report")
                analyzer = FinancialAnalyzer()

                # 深度模式下显示进度
                status_placeholder = st.empty()
                def on_status(msg):
                    status_placeholder.info(msg)

                report_container = st.empty()
                report_chunks = []

                stream = analyzer.analyze_news_stream(
                    news_items,
                    briefing_length=briefing_length,
                    language=language,
                    sectors=sector_values,
                    previous_report=previous_report,
                    deep_analysis=deep_analysis,
                    on_status=on_status if deep_analysis else None,
                )
                for chunk in stream:
                    report_chunks.append(chunk)
                    report_container.markdown("".join(report_chunks))

                status_placeholder.empty()
                report = "".join(report_chunks)

                # 保存报告到 data/
                report_path = os.path.join(DATA_DIR, "daily_report.md")
                analyzer.save_analysis(report, report_path)

                audio_path = None
                pdf_path = None
                media_gen = MediaGenerator()

                # 3. 音频
                if generate_audio:
                    with st.spinner("Generating audio..."):
                        audio_path = media_gen.generate_audio(
                            report,
                            output_file=os.path.join(DATA_DIR, "daily_briefing.mp3"),
                            language=language,
                            voice_name=voice_name,
                            tts_engine=tts_engine,
                        )
                    if audio_path and os.path.exists(audio_path):
                        st.subheader("🔊 Audio Briefing")
                        st.audio(audio_path)

                # 4. PDF 导出
                if generate_pdf:
                    with st.spinner("Generating PDF..."):
                        pdf_title = "金融分析简报" if language == "zh" else "Financial Analysis Briefing"
                        pdf_path = media_gen.generate_pdf(
                            report,
                            output_file=os.path.join(DATA_DIR, "daily_briefing.pdf"),
                            language=language,
                            title=pdf_title,
                        )
                    if pdf_path and os.path.exists(pdf_path):
                        st.subheader("📄 PDF Briefing")
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                label="⬇️ Download PDF",
                                data=f,
                                file_name="daily_briefing.pdf",
                                mime="application/pdf",
                            )

                # 5. 保存到历史记录
                with st.spinner("Saving to history..."):
                    hm = HistoryManager(history_dir=HISTORY_DIR)
                    run_id = hm.save_run(
                        news_items=news_items,
                        report=report,
                        query=query,
                        sources=sources,
                        time_range=time_range,
                        briefing_length=briefing_length,
                        audio_file=audio_path,
                        pdf_file=pdf_path,
                    )

                st.success(f"✅ Analysis complete! Run saved as **{run_id}**")

                # 缓存到 session_state 以持久化
                st.session_state["last_result"] = {
                    "news_items": news_items,
                    "report": report,
                    "audio_path": audio_path,
                    "pdf_path": pdf_path,
                    "run_id": run_id,
                }

        except Exception as e:
            st.error(f"An error occurred: {e}")

    # 如果之前有结果，展示缓存内容（非按钮触发时）
    elif "last_result" in st.session_state:
        result = st.session_state["last_result"]
        st.info(f"Showing cached result from run **{result['run_id']}**")
        display_result(
            result["news_items"],
            result["report"],
            result.get("audio_path"),
            result.get("pdf_path"),
        )

# ─────────────── Charts Tab ───────────────
CHART_PERIOD_OPTIONS = {
    "1 Week": "5d",
    "1 Month": "1mo",
    "3 Months": "3mo",
    "6 Months": "6mo",
    "1 Year": "1y",
}

with tab_charts:
    st.subheader("📈 Asset Price Trends")
    st.caption("Select asset groups and time range to view price movements (normalized as % change).")

    chart_col1, chart_col2 = st.columns([3, 1])
    with chart_col1:
        chart_groups = st.multiselect(
            "Asset Groups",
            options=list(ASSET_GROUPS.keys()),
            default=list(ASSET_GROUPS.keys())[:3],
            key="chart_groups",
        )
    with chart_col2:
        chart_period_label = st.selectbox(
            "Period",
            options=list(CHART_PERIOD_OPTIONS.keys()),
            index=1,
            key="chart_period",
        )
    chart_period = CHART_PERIOD_OPTIONS[chart_period_label]

    if chart_groups:
        with st.spinner("Loading market data..."):
            figures = cached_asset_dashboard(tuple(chart_groups), chart_period)
        for group_name, fig in figures.items():
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Please select at least one asset group.")

# ─────────────── History Tab ───────────────
with tab_history:
    try:
        hm = HistoryManager(history_dir=HISTORY_DIR)

        # Search controls
        hist_col1, hist_col2, hist_col3 = st.columns([2, 1, 1])
        with hist_col1:
            hist_keyword = st.text_input("🔍 Search keyword", key="hist_keyword", placeholder="Search in query or report...")
        with hist_col2:
            hist_date_from = st.date_input("From", value=None, key="hist_date_from")
        with hist_col3:
            hist_date_to = st.date_input("To", value=None, key="hist_date_to")

        # Use search_runs if filters are active, otherwise list_runs
        if hist_keyword or hist_date_from or hist_date_to:
            date_from_str = hist_date_from.isoformat() if hist_date_from else None
            date_to_str = hist_date_to.isoformat() if hist_date_to else None
            runs = hm.search_runs(keyword=hist_keyword or None, date_from=date_from_str, date_to=date_to_str)
            st.caption(f"Found {len(runs)} matching records")
        else:
            runs = hm.list_runs()

        if not runs:
            st.info("No history yet. Run an analysis to get started!")
        else:
            for run in runs:
                run_id = run.get("run_id", "unknown")
                col1, col2 = st.columns([5, 1])

                with col1:
                    st.markdown(
                        f"**{run.get('timestamp', 'N/A')}** — "
                        f"Query: *{run.get('query', '')}* — "
                        f"Sources: {', '.join(run.get('sources', []))} — "
                        f"Articles: {run.get('num_articles', 0)}"
                    )

                with col2:
                    if st.button("🗑️ Delete", key=f"del_{run_id}"):
                        hm.delete_run(run_id)
                        st.rerun()

                with st.expander(f"View details — {run_id}"):
                    full_run = hm.load_run(run_id)
                    if full_run:
                        st.markdown(full_run.get("report", "*No report available*"))

                        audio = full_run.get("audio_path")
                        if audio and os.path.exists(audio):
                            st.audio(audio)

                        pdf = full_run.get("pdf_path")
                        if pdf and os.path.exists(pdf):
                            with open(pdf, "rb") as f:
                                st.download_button(
                                    label="⬇️ Download PDF",
                                    data=f,
                                    file_name=f"briefing_{run_id}.pdf",
                                    mime="application/pdf",
                                    key=f"pdf_{run_id}",
                                )
                    else:
                        st.warning("Could not load run details.")

                st.divider()

    except Exception as e:
        st.error(f"Error loading history: {e}")
