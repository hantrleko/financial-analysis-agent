import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from src.analyzer import FinancialAnalyzer
from src.collector import NewsCollector
from src.components.charts_view import render_charts_tab
from src.components.history_view import render_history_tab
from src.components.newspaper_view import render_newspaper
from src.components.sentiment_dashboard import render_sentiment_tab
from src.config import (
    AVAILABLE_SOURCES,
    DEFAULT_LLM_PROVIDER,
    LLM_PROVIDERS,
    REPORT_SECTORS,
    VERSION,
)
from src.history import HistoryManager
from src.i18n import t
from src.media_gen import EDGE_VOICE_PRESETS, TTS_ENGINES, VOICE_PRESETS, MediaGenerator
from src.styles import inject_styles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_DIR = os.path.join(BASE_DIR, "history")

st.set_page_config(
    page_title="Financial Analysis System",
    page_icon="\U0001f3e6",
    layout="wide",
)

inject_styles()

if "language" not in st.session_state:
    st.session_state["language"] = "en"

_lang_label = st.sidebar.selectbox(
    "\U0001f310 Language / \u8bed\u8a00",
    options=["English", "\u4e2d\u6587"],
    index=0 if st.session_state["language"] == "en" else 1,
    key="_lang_select",
)
_selected_lang = "zh" if _lang_label == "\u4e2d\u6587" else "en"
if _selected_lang != st.session_state["language"]:
    st.session_state["language"] = _selected_lang
    st.rerun()

language = st.session_state["language"]

st.sidebar.divider()

ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "")

if ACCESS_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title(t("app_title"))
        pwd = st.text_input(t("password_prompt"), type="password")
        if pwd:
            if pwd == ACCESS_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error(t("wrong_password"))
        st.stop()

st.title(t("app_title"))
st.caption(f"Version {VERSION}")

st.sidebar.header(t("sidebar_controls"))

PRESETS = {
    t("preset_quick"): {
        "num_articles": 3,
        "briefing_length": "short",
        "deep_analysis": False,
        "ai_search": False,
        "scrape_content": False,
        "newspaper_mode": False,
        "generate_audio": False,
        "generate_pdf": False,
        "query": t("search_query_default"),
        "sources": AVAILABLE_SOURCES,
    },
    t("preset_deep"): {
        "num_articles": 10,
        "briefing_length": "detailed",
        "deep_analysis": True,
        "ai_search": True,
        "scrape_content": True,
        "newspaper_mode": True,
        "generate_audio": True,
        "generate_pdf": True,
        "query": t("search_query_default"),
        "sources": AVAILABLE_SOURCES,
    },
    t("preset_china"): {
        "num_articles": 8,
        "briefing_length": "detailed",
        "deep_analysis": True,
        "ai_search": True,
        "scrape_content": True,
        "newspaper_mode": False,
        "generate_audio": True,
        "generate_pdf": True,
        "query": "A\u80a1 \u6caa\u6df1 \u5e02\u573a\u52a8\u6001" if language == "zh" else "China A-share market trends",
        "sources": ["Sina Finance", "Cls.cn", "Eastmoney", "Bloomberg", "Reuters"],
    },
    t("preset_custom"): None,
}

selected_preset = st.sidebar.radio(
    t("preset_label"),
    options=list(PRESETS.keys()),
    index=len(PRESETS) - 1,
    horizontal=True,
)

preset_cfg = PRESETS[selected_preset]
is_preset = preset_cfg is not None

with st.sidebar.expander(t("basic_settings"), expanded=True):
    st.subheader(t("llm_engine"))

    _llm_options = {cfg["name"]: key for key, cfg in LLM_PROVIDERS.items()}
    _llm_default_name = LLM_PROVIDERS[DEFAULT_LLM_PROVIDER]["name"]
    _llm_selected_name = st.selectbox(
        t("llm_provider"),
        options=list(_llm_options.keys()),
        index=list(_llm_options.keys()).index(_llm_default_name),
        help=t("llm_provider_help"),
    )
    llm_provider = _llm_options[_llm_selected_name]

    _gemini_model_choices = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ]
    _default_gemini_model = os.getenv("GEMINI_MODEL", _gemini_model_choices[0])
    _gemini_model_idx = _gemini_model_choices.index(_default_gemini_model) if _default_gemini_model in _gemini_model_choices else 0
    _selected_gemini_model = st.selectbox(
        t("gemini_model"),
        options=_gemini_model_choices,
        index=_gemini_model_idx,
        help=t("gemini_model_help"),
    )
    os.environ["GEMINI_MODEL"] = _selected_gemini_model

    query = st.text_input(
        t("search_query"),
        value=preset_cfg["query"] if is_preset else t("search_query_default"),
    )

    sources = st.multiselect(
        t("news_sources"),
        options=AVAILABLE_SOURCES,
        default=preset_cfg["sources"] if is_preset else AVAILABLE_SOURCES,
    )

    TIME_RANGE_OPTIONS = {
        t("time_24h"): "24h",
        t("time_week"): "week",
        t("time_month"): "month",
    }
    time_range_label = st.selectbox(
        t("time_range"),
        options=list(TIME_RANGE_OPTIONS.keys()),
    )
    time_range = TIME_RANGE_OPTIONS[time_range_label]

    num_articles = st.slider(
        t("num_articles"),
        min_value=1,
        max_value=20,
        value=preset_cfg["num_articles"] if is_preset else 5,
    )

    BRIEFING_LENGTH_OPTIONS = {
        t("length_short"): "short",
        t("length_medium"): "medium",
        t("length_detailed"): "detailed",
    }
    _briefing_default = preset_cfg["briefing_length"] if is_preset else "medium"
    _briefing_keys = list(BRIEFING_LENGTH_OPTIONS.keys())
    _briefing_vals = list(BRIEFING_LENGTH_OPTIONS.values())
    _briefing_idx = _briefing_vals.index(_briefing_default) if _briefing_default in _briefing_vals else 1
    briefing_label = st.selectbox(
        t("briefing_length"),
        options=_briefing_keys,
        index=_briefing_idx,
    )
    briefing_length = BRIEFING_LENGTH_OPTIONS[briefing_label]

with st.sidebar.expander(t("advanced_settings"), expanded=False):
    st.subheader(t("report_sectors"))
    selected_sectors = st.multiselect(
        t("organize_sectors"),
        options=list(REPORT_SECTORS.keys()),
        help=t("organize_sectors_help"),
    )
    sector_values = [REPORT_SECTORS[s] for s in selected_sectors] if selected_sectors else None

    st.subheader(t("audio_export"))

    generate_audio = st.checkbox(
        t("generate_audio"),
        value=preset_cfg["generate_audio"] if is_preset else True,
    )

    tts_engine_label = st.selectbox(
        t("tts_engine"),
        options=list(TTS_ENGINES.keys()),
        index=1 if language == "zh" else 0,
        disabled=not generate_audio,
        help=t("tts_engine_help"),
    )
    tts_engine = TTS_ENGINES[tts_engine_label]

    if tts_engine == "edge_tts":
        voice_options = list(EDGE_VOICE_PRESETS.get(language, EDGE_VOICE_PRESETS["en"]).keys())
    else:
        voice_options = list(VOICE_PRESETS.get(language, VOICE_PRESETS["en"]).keys())
    voice_name = st.selectbox(
        t("voice"),
        options=voice_options,
        disabled=not generate_audio,
    )

    generate_pdf = st.checkbox(
        t("export_pdf"),
        value=preset_cfg["generate_pdf"] if is_preset else True,
    )

    st.subheader(t("deep_analysis"))
    deep_analysis = st.checkbox(
        t("enable_deep"),
        value=preset_cfg["deep_analysis"] if is_preset else True,
        help=t("enable_deep_help"),
    )
    ai_search = st.checkbox(
        t("ai_search"),
        value=preset_cfg["ai_search"] if is_preset else True,
        disabled=not deep_analysis,
        help=t("ai_search_help"),
    )
    scrape_content = st.checkbox(
        t("scrape_articles"),
        value=preset_cfg["scrape_content"] if is_preset else True,
        disabled=not deep_analysis,
        help=t("scrape_articles_help"),
    )
    newspaper_mode = st.checkbox(
        t("newspaper_mode"),
        value=preset_cfg["newspaper_mode"] if is_preset else False,
        disabled=not deep_analysis,
        help=t("newspaper_mode_help"),
    )
    _theme_options = {t("theme_classic"): "classic", t("theme_modern"): "modern"}
    _theme_label = st.selectbox(
        t("newspaper_theme"),
        options=list(_theme_options.keys()),
        index=0,
        disabled=not (deep_analysis and newspaper_mode),
    )
    newspaper_theme = _theme_options[_theme_label]

run_clicked = st.sidebar.button(t("run_analysis"), use_container_width=True, type="primary")

st.sidebar.divider()


@st.dialog(t("update_log"), width="large")
def _show_changelog():
    _changelog_path = os.path.join(BASE_DIR, "CHANGELOG.md")
    if os.path.exists(_changelog_path):
        with open(_changelog_path, "r", encoding="utf-8") as _f:
            st.markdown(_f.read())
    else:
        st.info(t("no_changelog"))


if st.sidebar.button(t("update_log"), use_container_width=True):
    _show_changelog()


ANALYSIS_STEPS = [
    ("step_collect", "\U0001f4e5"),
    ("step_scrape", "\U0001f4c4"),
    ("step_analyze", "\U0001f916"),
    ("step_media", "\U0001f3ac"),
    ("step_save", "\U0001f4be"),
]


def render_progress(current_step: int, progress_bar, step_label):
    pct = int((current_step / len(ANALYSIS_STEPS)) * 100)
    progress_bar.progress(pct)
    step_key, step_icon = ANALYSIS_STEPS[min(current_step, len(ANALYSIS_STEPS) - 1)]
    step_label.markdown(f"{step_icon} **{t(step_key)}**")


def render_step_pills(current_step: int):
    parts = []
    for i, (key, icon) in enumerate(ANALYSIS_STEPS):
        if i < current_step:
            cls = "done"
        elif i == current_step:
            cls = "active"
        else:
            cls = ""
        parts.append(f'<div class="progress-step {cls}">{icon} {t(key)}</div>')
    return '<div class="progress-steps">' + "".join(parts) + '</div>'


def _sentiment_tag(title: str) -> str:
    """Simple keyword-based sentiment tag for a news title."""
    title_lower = title.lower()
    pos_kw = ["surge", "jump", "rally", "gain", "rise", "soar", "record", "boom",
              "涨", "大涨", "飙升", "反弹", "突破", "创新高", "利好"]
    neg_kw = ["crash", "plunge", "drop", "fall", "decline", "slump", "fear", "risk",
              "跌", "大跌", "暴跌", "下跌", "崩", "风险", "利空"]
    if any(k in title_lower for k in pos_kw):
        return t("sentiment_positive")
    if any(k in title_lower for k in neg_kw):
        return t("sentiment_negative")
    return t("sentiment_neutral_tag")


def _render_news_list(news_items: list, show_full_content: bool = False) -> None:
    """Render news items with sentiment tags and optional source grouping."""
    _group_options = {t("group_none"): "none", t("group_source"): "source"}
    _grp_label = st.selectbox(t("news_group_by"), options=list(_group_options.keys()),
                              index=0, key="news_group_select")
    group_mode = _group_options[_grp_label]

    if group_mode == "source":
        from collections import defaultdict
        groups: dict[str, list] = defaultdict(list)
        for item in news_items:
            groups[item.get("source", "Unknown")].append(item)
        for source, items in groups.items():
            st.markdown(f"**{source}** ({len(items)})")
            for item in items:
                tag = _sentiment_tag(item.get("title", ""))
                desc = item.get("description", "")
                full = item.get("full_content", "") if show_full_content else ""
                extra = f"\n\n\U0001f4c4 _{t('chars_scraped', n=len(full))}_" if full else ""
                st.markdown(f"{tag} **{item.get('title', 'No Title')}**")
                st.caption(f"{desc}{extra}")
            st.divider()
    else:
        for item in news_items:
            tag = _sentiment_tag(item.get("title", ""))
            desc = item.get("description", "")
            full = item.get("full_content", "") if show_full_content else ""
            extra = f"\n\n\U0001f4c4 _{t('chars_scraped', n=len(full))}_" if full else ""
            st.markdown(
                f"{tag} **{item.get('title', 'No Title')}** "
                f"\u2014 *{item.get('source', 'Unknown')}*"
            )
            st.caption(f"{desc}{extra}")
            st.divider()


def display_result(news_items, report, audio_path=None, pdf_path=None,
                   use_newspaper=False, newspaper_theme="classic"):
    with st.expander(t("collected_news", count=len(news_items)), expanded=False):
        _render_news_list(news_items)

    st.subheader(t("analysis_report"))
    if use_newspaper:
        st.markdown(render_newspaper(report, theme_name=newspaper_theme),
                    unsafe_allow_html=True)
    else:
        st.markdown(report)

    if audio_path and os.path.exists(audio_path):
        st.subheader(t("audio_briefing"))
        st.audio(audio_path)

    if pdf_path and os.path.exists(pdf_path):
        st.subheader(t("pdf_briefing"))
        with open(pdf_path, "rb") as f:
            st.download_button(
                label=t("download_pdf"),
                data=f,
                file_name="daily_briefing.pdf",
                mime="application/pdf",
            )


tab_analysis, tab_sentiment, tab_charts, tab_history = st.tabs([
    t("tab_analysis"), t("tab_sentiment"), t("tab_charts"), t("tab_history"),
])

with tab_analysis:
    if run_clicked:
        try:
            os.makedirs(DATA_DIR, exist_ok=True)

            progress_bar = st.progress(0)
            step_label = st.empty()
            step_pills = st.empty()

            render_progress(0, progress_bar, step_label)
            step_pills.markdown(render_step_pills(0), unsafe_allow_html=True)

            collector = NewsCollector()
            news_items = collector.fetch_news(
                query=query,
                count=num_articles,
                sources=sources,
                time_range=time_range,
                ai_search=deep_analysis and ai_search,
            )

            if not news_items:
                progress_bar.empty()
                step_label.empty()
                step_pills.empty()
                st.warning(t("no_news"))
            else:
                render_progress(1, progress_bar, step_label)
                step_pills.markdown(render_step_pills(1), unsafe_allow_html=True)

                if deep_analysis and scrape_content:
                    collector.enrich_with_content(news_items)
                    scraped = sum(1 for it in news_items if it.get("full_content"))
                    st.caption(t("scraped_count", scraped=scraped, total=len(news_items)))

                with st.expander(t("collected_news", count=len(news_items)), expanded=False):
                    _render_news_list(news_items, show_full_content=True)

                previous_report = None
                previous_report_meta = None
                hm_prev = HistoryManager(history_dir=HISTORY_DIR)
                prev_runs = hm_prev.list_runs()
                if prev_runs:
                    prev_data = hm_prev.load_run(prev_runs[0]["run_id"])
                    if prev_data and prev_data.get("report"):
                        previous_report = prev_data["report"]
                        previous_report_meta = prev_data.get("metadata")

                render_progress(2, progress_bar, step_label)
                step_pills.markdown(render_step_pills(2), unsafe_allow_html=True)

                st.subheader(t("analysis_report"))
                analyzer = FinancialAnalyzer(provider=llm_provider)

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
                    time_range=time_range,
                    previous_report_meta=previous_report_meta,
                )
                for chunk in stream:
                    report_chunks.append(chunk)
                    report_container.markdown("".join(report_chunks))

                status_placeholder.empty()
                report = "".join(report_chunks)

                if newspaper_mode and deep_analysis:
                    report_container.empty()
                    report_container.markdown(
                        render_newspaper(report, theme_name=newspaper_theme),
                        unsafe_allow_html=True,
                    )

                report_path = os.path.join(DATA_DIR, "daily_report.md")
                analyzer.save_analysis(report, report_path)

                render_progress(3, progress_bar, step_label)
                step_pills.markdown(render_step_pills(3), unsafe_allow_html=True)

                audio_path = None
                pdf_path = None
                media_gen = MediaGenerator()

                if generate_audio:
                    audio_path = media_gen.generate_audio(
                        report,
                        output_file=os.path.join(DATA_DIR, "daily_briefing.mp3"),
                        language=language,
                        voice_name=voice_name,
                        tts_engine=tts_engine,
                    )
                    if audio_path and os.path.exists(audio_path):
                        st.subheader(t("audio_briefing"))
                        st.audio(audio_path)

                if generate_pdf:
                    pdf_title = "\u91d1\u878d\u5206\u6790\u7b80\u62a5" if language == "zh" else "Financial Analysis Briefing"
                    pdf_path = media_gen.generate_pdf(
                        report,
                        output_file=os.path.join(DATA_DIR, "daily_briefing.pdf"),
                        language=language,
                        title=pdf_title,
                    )
                    if pdf_path and os.path.exists(pdf_path):
                        st.subheader(t("pdf_briefing"))
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                label=t("download_pdf"),
                                data=f,
                                file_name="daily_briefing.pdf",
                                mime="application/pdf",
                            )

                render_progress(4, progress_bar, step_label)
                step_pills.markdown(render_step_pills(4), unsafe_allow_html=True)

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

                progress_bar.progress(100)
                step_pills.markdown(render_step_pills(5), unsafe_allow_html=True)
                step_label.empty()
                st.success(t("analysis_complete", run_id=run_id))

                st.session_state["last_result"] = {
                    "news_items": news_items,
                    "report": report,
                    "audio_path": audio_path,
                    "pdf_path": pdf_path,
                    "run_id": run_id,
                    "newspaper_mode": newspaper_mode and deep_analysis,
                    "newspaper_theme": newspaper_theme,
                }

        except Exception as e:
            st.error(t("error_occurred", e=e))

    elif "last_result" in st.session_state:
        result = st.session_state["last_result"]
        st.info(t("cached_result", run_id=result["run_id"]))
        display_result(
            result["news_items"],
            result["report"],
            result.get("audio_path"),
            result.get("pdf_path"),
            use_newspaper=result.get("newspaper_mode", False),
            newspaper_theme=result.get("newspaper_theme", "classic"),
        )

with tab_sentiment:
    render_sentiment_tab()

with tab_charts:
    render_charts_tab()

with tab_history:
    render_history_tab(HISTORY_DIR)
