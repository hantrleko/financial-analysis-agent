"""
集中管理所有 CSS 样式。
通过 inject_styles() 注入到 Streamlit 页面。
"""

import streamlit as st

APP_CSS = """
<style>
/* ── 全局字体 & 平滑 ── */
html, body, [class*="st-"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* ── 侧边栏美化 ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f1724 0%, #1a2332 100%);
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label {
    color: #c8d6e5 !important;
}

/* ── 侧边栏底部版本信息 ── */
.sidebar-footer {
    position: fixed;
    bottom: 0;
    width: inherit;
    padding: 12px 16px;
    border-top: 1px solid #334155;
    background: linear-gradient(180deg, rgba(15,23,36,0.9) 0%, #0f1724 100%);
    backdrop-filter: blur(8px);
    z-index: 999;
}
.sidebar-footer .footer-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11px;
    color: #64748b;
}
.sidebar-footer .footer-content a {
    color: #60a5fa;
    text-decoration: none;
    transition: color 0.2s;
}
.sidebar-footer .footer-content a:hover {
    color: #93c5fd;
}
.sidebar-footer .footer-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 10px;
    background: rgba(34,197,94,0.15);
    color: #22c55e;
    font-weight: 600;
}

/* ── Metric 卡片 ── */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.3);
}
div[data-testid="stMetric"] label {
    color: #cbd5e1 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 22px !important;
    font-weight: 700 !important;
}

/* ── Tab 样式 ── */
button[data-baseweb="tab"] {
    font-size: 15px !important;
    font-weight: 600 !important;
    padding: 10px 20px !important;
    transition: all 0.2s ease;
}
button[data-baseweb="tab"]:hover {
    background: rgba(59,130,246,0.08) !important;
}

/* ── Expander 美化 ── */
details[data-testid="stExpander"] {
    border: 1px solid #334155 !important;
    border-radius: 10px !important;
    margin-bottom: 8px;
    transition: border-color 0.2s ease;
}
details[data-testid="stExpander"]:hover {
    border-color: #475569 !important;
}

/* ── 按钮美化 ── */
.stButton > button[kind="primary"],
section[data-testid="stSidebar"] .stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s ease;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59,130,246,0.3);
}

/* ── 资产卡片 ── */
.asset-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
    transition: border-color 0.2s ease, transform 0.2s ease;
}
.asset-card:hover {
    border-color: #60a5fa;
    transform: translateX(2px);
}
.asset-card .asset-name {
    font-weight: 700;
    font-size: 15px;
    margin-bottom: 4px;
}
.asset-card .asset-meta {
    color: #cbd5e1;
    font-size: 13px;
    line-height: 1.6;
}
.asset-card .asset-reason {
    color: #94a3b8;
    font-size: 12px;
    font-style: italic;
    margin-top: 4px;
}
.positive { color: #22c55e; }
.negative { color: #ef4444; }

/* ── 情绪条 ── */
.sentiment-bar {
    display: flex;
    height: 32px;
    border-radius: 8px;
    overflow: hidden;
    margin: 12px 0 24px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.sentiment-bar > div {
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 13px;
    font-weight: 600;
    min-width: 50px;
    transition: width 0.6s ease;
}

/* ── 分隔线 ── */
hr {
    border-color: #1e293b !important;
}

/* ── 数据表格 + 斑马纹 ── */
.stDataFrame {
    border-radius: 8px;
    overflow: hidden;
}
.stDataFrame tbody tr:nth-child(even) {
    background: rgba(51, 65, 85, 0.25);
}
.stDataFrame tbody tr:hover {
    background: rgba(59, 130, 246, 0.12);
}

/* ── 进度步骤条 ── */
.progress-steps {
    display: flex;
    gap: 8px;
    margin: 10px 0 18px 0;
    flex-wrap: wrap;
}
.progress-step {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
    background: #1e293b;
    border: 1px solid #334155;
    color: #94a3b8;
    transition: all 0.3s ease;
}
.progress-step.active {
    background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
    border-color: #60a5fa;
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(59,130,246,0.3);
    animation: pulse-glow 2s infinite;
}
.progress-step.done {
    background: linear-gradient(135deg, #065f46 0%, #059669 100%);
    border-color: #34d399;
    color: #ffffff;
}

@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 2px 8px rgba(59,130,246,0.3); }
    50% { box-shadow: 0 2px 16px rgba(59,130,246,0.5); }
}

/* ── 对比视图 ── */
.diff-added {
    background: rgba(34, 197, 94, 0.15);
    border-left: 3px solid #22c55e;
    padding: 4px 12px;
    margin: 2px 0;
    border-radius: 4px;
}
.diff-removed {
    background: rgba(239, 68, 68, 0.15);
    border-left: 3px solid #ef4444;
    padding: 4px 12px;
    margin: 2px 0;
    border-radius: 4px;
}

/* ── 主题切换动画 ── */
* {
    transition: background-color 0.3s ease, color 0.2s ease, border-color 0.3s ease;
}

/* ── 骨架屏加载动画 ── */
@keyframes skeleton-shimmer {
    0% { background-position: -200px 0; }
    100% { background-position: calc(200px + 100%) 0; }
}
.skeleton-line {
    height: 14px;
    border-radius: 6px;
    background: linear-gradient(90deg, #1e293b 0%, #334155 50%, #1e293b 100%);
    background-size: 200px 100%;
    animation: skeleton-shimmer 1.5s ease-in-out infinite;
    margin-bottom: 10px;
}
.skeleton-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
}
.skeleton-card .skeleton-line:first-child { width: 60%; height: 18px; }
.skeleton-card .skeleton-line:nth-child(2) { width: 90%; }
.skeleton-card .skeleton-line:nth-child(3) { width: 75%; }

/* ── Dashboard 概览卡片 ── */
.overview-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 20px 24px;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.overview-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    border-radius: 14px 14px 0 0;
}
.overview-card.card-blue::before { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
.overview-card.card-green::before { background: linear-gradient(90deg, #22c55e, #4ade80); }
.overview-card.card-amber::before { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.overview-card.card-red::before { background: linear-gradient(90deg, #ef4444, #f87171); }
.overview-card.card-purple::before { background: linear-gradient(90deg, #8b5cf6, #a78bfa); }

.overview-card:hover {
    border-color: #475569;
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
.overview-card .card-icon {
    font-size: 28px;
    margin-bottom: 8px;
}
.overview-card .card-value {
    font-size: 24px;
    font-weight: 800;
    color: #e2e8f0;
    margin-bottom: 2px;
}
.overview-card .card-label {
    font-size: 12px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 500;
}

/* ── 市场快照迷你组件 ── */
.market-ticker {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 8px 0;
}
.market-ticker .tick-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    background: rgba(30,41,59,0.8);
    border: 1px solid #334155;
    white-space: nowrap;
}
.market-ticker .tick-item.up {
    color: #22c55e;
    border-color: rgba(34,197,94,0.3);
}
.market-ticker .tick-item.down {
    color: #ef4444;
    border-color: rgba(239,68,68,0.3);
}
.market-ticker .tick-item .tick-name {
    color: #94a3b8;
    font-weight: 500;
    font-size: 10px;
}

/* ── 滚动到顶部按钮 ── */
.scroll-top-btn {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: linear-gradient(135deg, #3b82f6, #2563eb);
    color: white;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    box-shadow: 0 4px 12px rgba(59,130,246,0.4);
    z-index: 9999;
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.3s ease;
}
.scroll-top-btn.visible {
    opacity: 1;
    transform: translateY(0);
}
.scroll-top-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(59,130,246,0.5);
}

/* ── 状态徽标 ── */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}
.status-badge.online {
    background: rgba(34,197,94,0.15);
    color: #22c55e;
}
.status-badge.offline {
    background: rgba(239,68,68,0.15);
    color: #ef4444;
}
.status-badge .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    display: inline-block;
}
.status-badge.online .dot { background: #22c55e; }
.status-badge.offline .dot { background: #ef4444; }

/* ═══════════════ 报纸版面 ═══════════════ */
.newspaper {
    background: #fdf6e3;
    color: #1a1a1a;
    font-family: "Georgia", "Noto Serif SC", "Source Han Serif SC", "SimSun", serif;
    padding: 40px 48px;
    border: 2px solid #8b7355;
    border-radius: 4px;
    box-shadow: 4px 4px 20px rgba(0,0,0,0.25);
    max-width: 1100px;
    margin: 20px auto;
}

/* 报头 */
.np-masthead {
    text-align: center;
    border-bottom: 4px double #1a1a1a;
    padding-bottom: 12px;
    margin-bottom: 4px;
}
.np-masthead-title {
    font-size: 36px;
    font-weight: 900;
    letter-spacing: 5px;
    text-transform: uppercase;
    color: #1a1a1a;
    margin: 0;
    line-height: 1.1;
    font-family: "Times New Roman", "Noto Serif SC", serif;
}
.np-masthead-sub {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid #1a1a1a;
    border-bottom: 1px solid #1a1a1a;
    padding: 5px 0;
    margin-top: 6px;
    font-size: 11px;
    color: #555;
    letter-spacing: 1px;
}

/* 头条 */
.np-headline {
    font-size: 28px;
    font-weight: 900;
    line-height: 1.2;
    text-align: center;
    margin: 20px 0 6px 0;
    color: #1a1a1a;
    font-family: "Times New Roman", "Noto Serif SC", serif;
}
.np-subheadline {
    text-align: center;
    font-size: 15px;
    font-style: italic;
    color: #555;
    margin-bottom: 18px;
    padding-bottom: 14px;
    border-bottom: 1px solid #ccc;
}

/* 多栏布局 */
.np-columns {
    column-count: 2;
    column-gap: 36px;
    column-rule: 1px solid #ccc;
    text-align: justify;
    hyphens: auto;
}

/* 文章区块 */
.np-section {
    break-inside: avoid-column;
    -webkit-column-break-inside: avoid;
    display: inline-block;
    width: 100%;
    margin-bottom: 20px;
}
.np-section-title {
    font-size: 17px;
    font-weight: 800;
    border-bottom: 2px solid #1a1a1a;
    padding-bottom: 4px;
    margin-bottom: 8px;
    color: #1a1a1a;
    font-family: "Times New Roman", "Noto Serif SC", serif;
}
.np-body {
    font-size: 14px;
    line-height: 1.75;
    color: #2a2a2a;
}
.np-body p {
    text-indent: 2em;
    margin: 0 0 8px 0;
}
.np-body ul, .np-body ol {
    text-indent: 0;
    padding-left: 1.5em;
    margin: 6px 0 10px 0;
}
.np-body li {
    margin-bottom: 4px;
}
.np-body h3 {
    font-size: 15px;
    font-weight: 800;
    color: #1a1a1a;
    margin: 14px 0 6px 0;
    font-family: "Times New Roman", "Noto Serif SC", serif;
    border-left: 3px solid #8b7355;
    padding-left: 8px;
}

/* 引用框 */
.np-pullquote {
    break-inside: avoid;
    border-left: 4px solid #8b7355;
    border-right: 4px solid #8b7355;
    padding: 14px 18px;
    margin: 16px 0;
    font-size: 15px;
    font-style: italic;
    color: #333;
    text-align: center;
    background: rgba(139,115,85,0.06);
    line-height: 1.5;
}

/* 分隔符 */
.np-divider {
    border: none;
    border-top: 1px solid #ccc;
    margin: 16px 0;
}
.np-heavy-divider {
    border: none;
    border-top: 3px double #1a1a1a;
    margin: 20px 0;
}

/* 页脚 */
.np-footer {
    border-top: 2px solid #1a1a1a;
    margin-top: 24px;
    padding-top: 10px;
    text-align: center;
    font-size: 10px;
    color: #888;
    letter-spacing: 0.5px;
}

/* ═══════════════ 移动端适配 ═══════════════ */
@media (max-width: 768px) {
    .newspaper { padding: 20px 16px; }
    .np-columns { column-count: 1 !important; }
    .np-masthead-title { font-size: 24px !important; letter-spacing: 2px !important; }
    .np-headline { font-size: 22px !important; }

    div[data-testid="stMetric"] {
        padding: 12px 14px;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 18px !important;
    }

    .asset-card {
        padding: 10px 14px;
    }
    .asset-card .asset-name {
        font-size: 14px;
    }
    .asset-card .asset-meta {
        font-size: 12px;
    }

    .sentiment-bar > div {
        font-size: 11px;
        min-width: 40px;
    }

    button[data-baseweb="tab"] {
        font-size: 13px !important;
        padding: 8px 12px !important;
    }

    .progress-steps {
        flex-direction: column;
        gap: 4px;
    }
    .progress-step {
        font-size: 12px;
        padding: 5px 10px;
    }

    .overview-card .card-value {
        font-size: 20px;
    }

    .sidebar-footer {
        position: relative;
        margin-top: 20px;
    }

    .market-ticker .tick-item {
        font-size: 10px;
        padding: 2px 6px;
    }
}

@media (max-width: 480px) {
    .np-masthead-title { font-size: 18px !important; letter-spacing: 1px !important; }
    .np-headline { font-size: 18px !important; }
    .np-masthead-sub { flex-direction: column; gap: 2px; }
}

/* ── 打印优化 ── */
@media print {
    .newspaper {
        box-shadow: none;
        border: 1px solid #ccc;
    }
    .sidebar-footer,
    .scroll-top-btn,
    .stButton,
    section[data-testid="stSidebar"] {
        display: none !important;
    }
}
</style>
"""

# 骨架屏 HTML 模板
SKELETON_CARDS_HTML = """
<div class="skeleton-card">
    <div class="skeleton-line"></div>
    <div class="skeleton-line"></div>
    <div class="skeleton-line"></div>
</div>
<div class="skeleton-card">
    <div class="skeleton-line"></div>
    <div class="skeleton-line"></div>
    <div class="skeleton-line"></div>
</div>
"""


def inject_styles():
    """将全局 CSS 注入 Streamlit 页面。"""
    st.markdown(APP_CSS, unsafe_allow_html=True)


def render_skeleton(count: int = 2) -> str:
    """生成骨架屏加载占位 HTML。"""
    card = (
        '<div class="skeleton-card">'
        '<div class="skeleton-line"></div>'
        '<div class="skeleton-line"></div>'
        '<div class="skeleton-line"></div>'
        "</div>"
    )
    return card * count


def render_sidebar_footer(version: str) -> str:
    """渲染侧边栏底部版本信息 HTML。"""
    return (
        '<div class="sidebar-footer">'
        '<div class="footer-content">'
        f'<span class="footer-badge">v{version}</span>'
        "<span>AI-Powered Financial Intelligence</span>"
        "</div>"
        "</div>"
    )
