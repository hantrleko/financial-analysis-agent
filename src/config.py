"""
集中管理项目配置常量。
所有可调参数统一在此维护，各模块通过 from src.config import ... 引用。
"""

VERSION = "v1.4"

# ──────────────────── 抓取参数 ────────────────────
MAX_SCRAPE_CHARS = 4000       # 每篇文章最大抓取字符数
MAX_SCRAPE_ARTICLES = 10      # 单次最多抓取文章数
SCRAPE_TIMEOUT = 10           # 抓取超时（秒）
SCRAPE_WORKERS = 5            # 并行抓取线程数

# ──────────────────── 新闻源 ────────────────────
AVAILABLE_SOURCES = [
    "Bloomberg", "Reuters", "AP News", "Yahoo Finance",
    "CNBC", "Financial Times", "Wall Street Journal",
]

SOURCE_DOMAINS = {
    "Bloomberg": "bloomberg.com",
    "Reuters": "reuters.com",
    "AP News": "apnews.com",
    "Yahoo Finance": "finance.yahoo.com",
    "CNBC": "cnbc.com",
    "Financial Times": "ft.com",
    "Wall Street Journal": "wsj.com",
}

RSS_FEEDS = [
    {"url": "https://finance.yahoo.com/news/rssindex", "source": "Yahoo Finance"},
    {"url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en", "source": "Google News (Business)"},
    {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "source": "CNBC"},
    {"url": "https://feeds.reuters.com/reuters/businessNews", "source": "Reuters"},
    {"url": "https://feeds.bloomberg.com/markets/news.rss", "source": "Bloomberg"},
]

# ──────────────────── 报告板块 ────────────────────
REPORT_SECTORS = {
    "宏观经济 Macro": "macro",
    "股票个股 Stocks": "stocks",
    "大宗商品 Commodities": "commodities",
    "虚拟货币 Crypto": "crypto",
    "外汇 Forex": "forex",
    "债券固收 Bonds": "bonds",
}

# ──────────────────── 市场快照 ────────────────────
SNAPSHOT_TICKERS = {
    "S&P 500 (SPY)": "SPY",
    "Nasdaq 100 (QQQ)": "QQQ",
    "Dow Jones (DIA)": "DIA",
    "Gold": "GC=F",
    "Crude Oil (WTI)": "CL=F",
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    "US 10Y Yield": "^TNX",
    "VIX": "^VIX",
}

# ──────────────────── 上期报告注入 ────────────────────
PREVIOUS_REPORT_MAX_CHARS = 2000   # 注入上期报告的最大字符数
