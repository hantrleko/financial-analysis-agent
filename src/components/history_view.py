"""
历史记录组件。
支持查看、搜索、删除、批量导出 ZIP、两期报告对比。
"""

import io
import os
import zipfile
import difflib

import streamlit as st

from src.i18n import t
from src.history import HistoryManager


def _export_runs_as_zip(hm: HistoryManager, run_ids: list[str]) -> bytes:
    """将指定 run_ids 的报告打包为 ZIP。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for run_id in run_ids:
            run_data = hm.load_run(run_id)
            if not run_data:
                continue
            prefix = f"reports/{run_id}"
            # report.md
            report = run_data.get("report", "")
            if report:
                zf.writestr(f"{prefix}/report.md", report)
            # metadata
            meta = run_data.get("metadata")
            if meta:
                import json
                zf.writestr(f"{prefix}/metadata.json", json.dumps(meta, indent=2, ensure_ascii=False))
            # PDF
            pdf_path = run_data.get("pdf_path")
            if pdf_path and os.path.exists(pdf_path):
                zf.write(pdf_path, f"{prefix}/briefing.pdf")
            # Audio
            audio_path = run_data.get("audio_path")
            if audio_path and os.path.exists(audio_path):
                zf.write(audio_path, f"{prefix}/briefing.mp3")
    return buf.getvalue()


def _render_diff(report_a: str, report_b: str, label_a: str, label_b: str):
    """渲染两份报告的对比视图。"""
    lines_a = report_a.splitlines()
    lines_b = report_b.splitlines()

    diff = difflib.unified_diff(lines_a, lines_b, fromfile=label_a, tofile=label_b, lineterm="")
    diff_lines = list(diff)

    if not diff_lines:
        st.info(t("no_diff"))
        return

    html_parts = []
    for line in diff_lines:
        if line.startswith("+++") or line.startswith("---"):
            html_parts.append(f'<div style="color:#94a3b8;font-weight:600;margin-top:8px;">{line}</div>')
        elif line.startswith("@@"):
            html_parts.append(f'<div style="color:#60a5fa;font-size:12px;margin:6px 0 2px 0;">{line}</div>')
        elif line.startswith("+"):
            html_parts.append(f'<div class="diff-added">{line}</div>')
        elif line.startswith("-"):
            html_parts.append(f'<div class="diff-removed">{line}</div>')
        else:
            html_parts.append(f'<div style="color:#94a3b8;padding:1px 12px;">{line}</div>')

    st.markdown(
        '<div style="font-family:monospace;font-size:13px;max-height:600px;overflow-y:auto;'
        'background:#0f172a;border-radius:8px;padding:16px;border:1px solid #334155;">'
        + "\n".join(html_parts)
        + '</div>',
        unsafe_allow_html=True,
    )


def render_history_tab(history_dir: str):
    """渲染完整的历史记录 Tab 内容。"""
    try:
        hm = HistoryManager(history_dir=history_dir)

        # -- 搜索栏 --
        hist_col1, hist_col2, hist_col3 = st.columns([2, 1, 1])
        with hist_col1:
            hist_keyword = st.text_input(
                t("search_keyword"), key="hist_keyword",
                placeholder=t("search_placeholder"),
            )
        with hist_col2:
            hist_date_from = st.date_input(t("date_from"), value=None, key="hist_date_from")
        with hist_col3:
            hist_date_to = st.date_input(t("date_to"), value=None, key="hist_date_to")

        if hist_keyword or hist_date_from or hist_date_to:
            date_from_str = hist_date_from.isoformat() if hist_date_from else None
            date_to_str = hist_date_to.isoformat() if hist_date_to else None
            runs = hm.search_runs(keyword=hist_keyword or None, date_from=date_from_str, date_to=date_to_str)
            st.caption(t("found_records", n=len(runs)))
        else:
            runs = hm.list_runs()

        if not runs:
            st.info(t("no_history"))
            return

        # -- 工具栏：导出 & 对比 --
        tool_col1, tool_col2, tool_col3 = st.columns([1, 1, 2])
        with tool_col1:
            all_run_ids = [r.get("run_id", "") for r in runs]
            zip_data = _export_runs_as_zip(hm, all_run_ids)
            st.download_button(
                label=t("export_zip"),
                data=zip_data,
                file_name="financial_reports_export.zip",
                mime="application/zip",
                use_container_width=True,
            )
        with tool_col2:
            show_compare = st.checkbox(t("compare_reports"), key="show_compare")

        # -- 报告对比 --
        if show_compare and len(runs) >= 2:
            st.markdown("---")
            compare_col1, compare_col2 = st.columns(2)
            run_labels = [f"{r.get('timestamp', 'N/A')[:19]} — {r.get('query', '')[:30]}" for r in runs]
            run_id_map = {label: r.get("run_id", "") for label, r in zip(run_labels, runs)}

            with compare_col1:
                label_a = st.selectbox(t("compare_left"), options=run_labels, index=0, key="compare_a")
            with compare_col2:
                default_b = min(1, len(run_labels) - 1)
                label_b = st.selectbox(t("compare_right"), options=run_labels, index=default_b, key="compare_b")

            if label_a and label_b and label_a != label_b:
                data_a = hm.load_run(run_id_map[label_a])
                data_b = hm.load_run(run_id_map[label_b])
                report_a = data_a.get("report", "") if data_a else ""
                report_b = data_b.get("report", "") if data_b else ""
                _render_diff(report_a, report_b, label_a, label_b)
            st.markdown("---")

        # -- 记录列表 --
        for run in runs:
            run_id = run.get("run_id", "unknown")
            col1, col2 = st.columns([5, 1])

            with col1:
                st.markdown(
                    f"**{run.get('timestamp', 'N/A')}** — "
                    f"{t('query_label')}: *{run.get('query', '')}* — "
                    f"{t('sources_label')}: {', '.join(run.get('sources', []))} — "
                    f"{t('articles_label')}: {run.get('num_articles', 0)}"
                )

            with col2:
                if st.button(t("delete"), key=f"del_{run_id}"):
                    hm.delete_run(run_id)
                    st.rerun()

            with st.expander(f"{t('view_details')} — {run_id}"):
                full_run = hm.load_run(run_id)
                if full_run:
                    st.markdown(full_run.get("report", t("no_report")))

                    audio = full_run.get("audio_path")
                    if audio and os.path.exists(audio):
                        st.audio(audio)

                    pdf = full_run.get("pdf_path")
                    if pdf and os.path.exists(pdf):
                        with open(pdf, "rb") as f:
                            st.download_button(
                                label=t("download_pdf"),
                                data=f,
                                file_name=f"briefing_{run_id}.pdf",
                                mime="application/pdf",
                                key=f"pdf_{run_id}",
                            )
                else:
                    st.warning(t("load_failed"))

            st.divider()

    except Exception as e:
        st.error(t("error_history", e=e))
