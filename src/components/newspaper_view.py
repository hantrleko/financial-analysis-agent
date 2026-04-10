"""
报纸版面渲染组件。
将 Markdown 分析报告转换为经典报纸版面 HTML。
支持多主题（经典 classic / 现代 modern）。
"""

from __future__ import annotations

import re
from datetime import datetime

import streamlit as st

from src.config import VERSION
from src.i18n import t
from src.newspaper import inline_markdown

# ---- Theme definitions ------------------------------------------------

NEWSPAPER_THEMES: dict[str, dict[str, str]] = {
    "classic": {
        "bg": "#fdf6e3",
        "fg": "#1a1a1a",
        "accent": "#8b7355",
        "font": '"Georgia", "Noto Serif SC", "Source Han Serif SC", "SimSun", serif',
        "heading_font": '"Times New Roman", "Noto Serif SC", serif',
        "border": "#8b7355",
        "sub_color": "#555",
        "body_color": "#2a2a2a",
        "footer_color": "#888",
    },
    "modern": {
        "bg": "#ffffff",
        "fg": "#111827",
        "accent": "#2563eb",
        "font": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif',
        "heading_font": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        "border": "#d1d5db",
        "sub_color": "#6b7280",
        "body_color": "#374151",
        "footer_color": "#9ca3af",
    },
    "dark": {
        "bg": "#0f172a",
        "fg": "#e2e8f0",
        "accent": "#3b82f6",
        "font": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif',
        "heading_font": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        "border": "#334155",
        "sub_color": "#94a3b8",
        "body_color": "#cbd5e1",
        "footer_color": "#64748b",
    },
}


def _inline_md(text: str) -> str:
    """处理行内 Markdown 格式。"""
    return inline_markdown(text)


def _strip_emoji(text: str) -> str:
    """去除 Emoji 前缀，用于报纸正式排版。"""
    return re.sub(r"^[\U0001f300-\U0001fAFF\u2600-\u27BF\u2700-\u27BF]+\s*", "", text).strip()


def _md_to_html_body(text):
    """将 Markdown 正文段落转换为 HTML。"""
    html_parts = []
    lines = text.strip().split("\n")
    in_list = False
    list_type = None

    def _close_list():
        nonlocal in_list, list_type
        if in_list:
            html_parts.append(f"</{list_type}>")
            in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            _close_list()
            continue

        # ### 子标题
        h3_match = re.match(r"^###\s+(.+)", stripped)
        if h3_match:
            _close_list()
            html_parts.append(f"<h3>{_inline_md(h3_match.group(1))}</h3>")
            continue

        # 无序列表
        if stripped.startswith(("- ", "* ")):
            if not in_list or list_type != "ul":
                _close_list()
                html_parts.append("<ul>")
                in_list = True
                list_type = "ul"
            html_parts.append(f"<li>{_inline_md(stripped[2:])}</li>")
            continue

        # 有序列表
        m = re.match(r"^(\d+)\.\s(.*)", stripped)
        if m:
            if not in_list or list_type != "ol":
                _close_list()
                html_parts.append("<ol>")
                in_list = True
                list_type = "ol"
            html_parts.append(f"<li>{_inline_md(m.group(2))}</li>")
            continue

        # 引用
        if stripped.startswith("> "):
            _close_list()
            html_parts.append(f'<div class="np-pullquote">{_inline_md(stripped[2:])}</div>')
            continue

        # 分隔线
        if stripped.startswith("---") or stripped.startswith("***"):
            _close_list()
            html_parts.append('<hr class="np-divider">')
            continue

        # 纯粗体行当作小标题（如 **Summary:** 或 **Risk Alert**）
        bold_line = re.match(r"^\*\*(.+?)\*\*[：:]*\s*$", stripped)
        if bold_line:
            _close_list()
            html_parts.append(f"<h3>{bold_line.group(1)}</h3>")
            continue

        # 普通段落
        _close_list()
        html_parts.append(f"<p>{_inline_md(stripped)}</p>")

    _close_list()
    return "\n".join(html_parts)


def render_newspaper(report_md: str, theme_name: str = "classic") -> str:
    """
    将 Markdown 分析报告解析为报纸版面 HTML。
    支持多主题: classic (经典报纸) / modern (现代简洁)。
    """
    language = st.session_state.get("language", "en")
    theme = NEWSPAPER_THEMES.get(theme_name, NEWSPAPER_THEMES["classic"])

    # 按 ## 分割为 sections（不匹配 ###）
    parts = re.split(r"^##(?!#)\s+", report_md, flags=re.MULTILINE)

    headline = ""
    subheadline = ""
    sections = []

    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue

        if i == 0:
            # ## 之前的内容（可能有 # 大标题）
            m = re.match(r"^#\s+(.+)", part)
            if m:
                headline = _strip_emoji(m.group(1).strip())
                rest = part[m.end() :].strip()
                if rest:
                    sections.append({"title": "", "body": rest})
            elif part:
                sections.append({"title": "", "body": part})
            continue

        # 提取标题行（第一行）
        lines = part.split("\n", 1)
        section_title = _strip_emoji(lines[0].strip())
        section_body = lines[1].strip() if len(lines) > 1 else ""

        if i == 1 and not headline:
            # 第一个 ## section -> headline + subheadline
            headline = section_title
            # 取正文第一句作为副标题
            first_para = section_body.split("\n\n")[0] if section_body else ""
            first_sentence = re.split(r"[.!?。！？]", first_para)
            if first_sentence and first_sentence[0].strip():
                subheadline = _inline_md(first_sentence[0].strip().lstrip("- *"))

        if section_body:
            sections.append({"title": section_title, "body": section_body})

    if not headline:
        headline = t("newspaper_masthead")

    # 构建 HTML
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y") if language == "en" else now.strftime("%Y年%m月%d日 %A")
    edition = t("newspaper_edition")
    vol_no = f"Vol. {now.strftime('%Y')} No. {now.strftime('%j')}"

    # Theme-specific inline overrides (applied via style= on .newspaper div)
    theme_style = (
        f"background:{theme['bg']};color:{theme['fg']};font-family:{theme['font']};border-color:{theme['border']};"
    )
    heading_style = f"font-family:{theme['heading_font']};color:{theme['fg']};"

    html = f'''<div class="newspaper" style="{theme_style}">
<!-- masthead -->
<div class="np-masthead">
    <div class="np-masthead-title" style="{heading_style}">{t("newspaper_masthead")}</div>
    <div class="np-masthead-sub" style="color:{theme["sub_color"]};">
        <span>{date_str}</span>
        <span>{edition}</span>
        <span>{vol_no}</span>
    </div>
</div>

<!-- headline -->
<div class="np-headline" style="{heading_style}">{_inline_md(headline)}</div>
'''
    if subheadline:
        html += f'<div class="np-subheadline">{subheadline}</div>\n'
    else:
        html += '<div class="np-subheadline">&nbsp;</div>\n'

    html += '<hr class="np-heavy-divider">\n'

    # 版面分布：长报告分两段双栏，短报告单段双栏
    if len(sections) >= 4:
        mid = (len(sections) + 1) // 2
        groups = [sections[:mid], sections[mid:]]
    else:
        groups = [sections]

    for gi, group in enumerate(groups):
        if gi > 0:
            html += '<hr class="np-heavy-divider">\n'
        html += '<div class="np-columns">\n'
        for sec in group:
            html += '<div class="np-section">\n'
            if sec["title"]:
                html += f'<div class="np-section-title">{_inline_md(sec["title"])}</div>\n'
            html += f'<div class="np-body">{_md_to_html_body(sec["body"])}</div>\n'
            html += "</div>\n"
        html += "</div>\n"

    # 页脚
    html += f"""
<div class="np-footer">
    {t("newspaper_disclaimer")}<br>
    &copy; {now.strftime("%Y")} Financial Analysis System {VERSION}
</div>
</div>"""

    return html
