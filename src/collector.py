import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

from src.config import (
    MAX_SCRAPE_CHARS,
    MAX_SCRAPE_ARTICLES,
    SCRAPE_TIMEOUT,
    SCRAPE_WORKERS,
    RSS_FEEDS,
    DEDUP_SIMILARITY_THRESHOLD,
    LLM_PROVIDERS,
)

load_dotenv()

logger = logging.getLogger(__name__)


def _get_api_key(env_key):
    """从环境变量或 Streamlit secrets 中获取 API Key。"""
    val = os.getenv(env_key, "")
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(env_key, "")
    except Exception:
        return ""


class NewsCollector:

    def fetch_news(self, query="financial markets trends", count=10, sources=None,
                   time_range="24h", ai_search=False, **kwargs):
        """
        获取新闻。
        ai_search=True: 先用 Gemini Search Grounding 联网搜索，再用 RSS 补充
        ai_search=False: 纯 RSS（默认）
        """
        rss_items = self._fetch_rss(count, time_range)

        if not ai_search:
            return rss_items

        # AI 联网搜索 + RSS 合并去重
        ai_items = self._fetch_gemini_search(query, count, time_range)
        if not ai_items:
            return rss_items

        # AI 结果在前，RSS 补充在后，统一去重
        merged = ai_items + rss_items
        return self._dedup(merged, count)

    def _fetch_rss(self, count=10, time_range="24h"):
        """从多个 RSS 源聚合新闻，按时间过滤、去重后取 top N。"""
        import feedparser

        time_range_days = {"24h": 1, "week": 7, "month": 30}
        max_age = timedelta(days=time_range_days.get(time_range, 1))
        now = datetime.now(timezone.utc)

        all_items = []
        for feed_info in RSS_FEEDS:
            try:
                logger.info("Fetching RSS from: %s...", feed_info["source"])
                feed = feedparser.parse(feed_info["url"])
                for entry in feed.entries[:count]:
                    # 时间过滤
                    published_str = entry.get("published", "")
                    if published_str:
                        try:
                            pub_dt = parsedate_to_datetime(published_str)
                            if now - pub_dt > max_age:
                                continue
                        except Exception:
                            pass  # 解析失败则保留

                    all_items.append({
                        "title": entry.get("title", "No Title"),
                        "url": entry.get("link", ""),
                        "description": entry.get("summary", entry.get("title", "")),
                        "source": feed_info["source"],
                        "published_age": published_str or "Unknown",
                        "fetched_at": datetime.now().isoformat(),
                    })
                logger.info("  %s: %d articles", feed_info["source"], min(len(feed.entries), count))
            except Exception as e:
                logger.warning("  %s failed: %s", feed_info["source"], e)

        if not all_items:
            logger.warning("All RSS feeds failed. Using mock data.")
            return self._get_mock_data()

        result = self._dedup(all_items, count)
        logger.info("Successfully fetched %d unique articles from %d RSS sources.", len(result), len(RSS_FEEDS))
        return result

    @staticmethod
    def _dedup(items, count):
        """去重（URL + 标题模糊匹配）。"""
        seen_urls = set()
        seen_titles = []
        unique_items = []
        for item in items:
            url = item.get("url", "")
            if url and url in seen_urls:
                continue
            title = item["title"].strip().lower()
            is_dup = any(
                SequenceMatcher(None, title, t).ratio() >= DEDUP_SIMILARITY_THRESHOLD
                for t in seen_titles
            )
            if is_dup:
                continue
            if url:
                seen_urls.add(url)
            seen_titles.append(title)
            unique_items.append(item)
        return unique_items[:count]

    def _fetch_gemini_search(self, query, count, time_range):
        """用 Gemini Search Grounding 联网搜索最新金融新闻。"""
        import requests as http_requests

        api_key = _get_api_key("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set, skipping AI search.")
            return []

        cfg = LLM_PROVIDERS.get("gemini", {})
        base_url = cfg.get("base_url", "https://generativelanguage.googleapis.com/v1beta")
        model = cfg.get("model", "gemini-2.5-flash")
        url = f"{base_url}/models/{model}:generateContent?key={api_key}"

        time_desc = {"24h": "in the last 24 hours", "week": "this week", "month": "this month"}
        prompt = (
            f"Search for the latest {count} financial market news articles about: {query}\n"
            f"Time range: {time_desc.get(time_range, 'recent')}\n\n"
            f"For each article, output EXACTLY in this format (one article per block):\n"
            f"TITLE: <article title>\n"
            f"SOURCE: <news source name>\n"
            f"SUMMARY: <1-2 sentence summary>\n"
            f"---\n"
            f"Output {count} articles. Be factual and cite real news."
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
        }

        try:
            logger.info("Fetching news via Gemini Search Grounding...")
            resp = http_requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            text = data["candidates"][0]["content"]["parts"][0].get("text", "")
            grounding = data["candidates"][0].get("groundingMetadata", {})
            chunks = grounding.get("groundingChunks", [])

            # 解析结构化输出
            news_items = []
            blocks = text.split("---")
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                title = source = summary = ""
                for line in block.split("\n"):
                    line = line.strip()
                    if line.startswith("TITLE:"):
                        title = line[6:].strip()
                    elif line.startswith("SOURCE:"):
                        source = line[7:].strip()
                    elif line.startswith("SUMMARY:"):
                        summary = line[8:].strip()
                if title:
                    news_items.append({
                        "title": title,
                        "url": "",
                        "description": summary or title,
                        "source": f"🔍 {source}" if source else "🔍 Gemini Search",
                        "published_age": "Recent",
                        "fetched_at": datetime.now().isoformat(),
                    })

            # 用 grounding chunks 的 URL 补充
            for i, chunk in enumerate(chunks):
                web = chunk.get("web", {})
                if i < len(news_items) and web.get("uri"):
                    news_items[i]["url"] = web["uri"]

            logger.info("Gemini Search returned %d articles with %d grounding sources.", len(news_items), len(chunks))
            return news_items[:count]

        except Exception as e:
            logger.warning("Gemini Search failed: %s", e)
            return []

    def _get_mock_data(self):
        """兜底 mock 数据，用于测试流程。"""
        logger.info("Returning MOCK data.")
        return [
            {
                "title": "Mock: Tech Stocks Rally on AI Optimism",
                "url": "https://example.com/news1",
                "description": "Technology shares surged driven by strong earnings from major AI chipmakers.",
                "source": "MockNews",
                "published_age": "2 hours ago",
                "fetched_at": datetime.now().isoformat()
            },
            {
                "title": "Mock: Fed Signals Potential Rate Cut",
                "url": "https://example.com/news2",
                "description": "Federal Reserve officials hinted at a possible interest rate reduction later this year.",
                "source": "MockFinance",
                "published_age": "5 hours ago",
                "fetched_at": datetime.now().isoformat()
            }
        ]

    def scrape_content(self, url, timeout=SCRAPE_TIMEOUT):
        """使用 trafilatura 提取文章正文，失败则回退到 BeautifulSoup。"""
        # trafilatura 提取
        try:
            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=True,
                    favor_precision=True,
                )
                if text and len(text) > 100:
                    return text[:MAX_SCRAPE_CHARS]
        except Exception:
            pass

        # BeautifulSoup 回退
        try:
            import requests
            from bs4 import BeautifulSoup
            resp = requests.get(url, timeout=timeout, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()

            article = soup.find("article") or soup.find("main") or soup.find("body")
            if article:
                paragraphs = article.find_all("p")
                text = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
                if text:
                    return text[:MAX_SCRAPE_CHARS]
        except Exception:
            pass

        return ""

    def enrich_with_content(self, news_items, max_scrape=MAX_SCRAPE_ARTICLES):
        """为新闻列表并行抓取正文内容，添加 full_content 字段。"""
        to_scrape = [
            (i, item) for i, item in enumerate(news_items[:max_scrape])
            if item.get("url", "").startswith("http") and not item.get("full_content")
        ]
        total = len(to_scrape)
        logger.info("Scraping full article content (%d articles, %d workers)...", total, SCRAPE_WORKERS)

        def _scrape_one(idx_item):
            idx, item = idx_item
            content = self.scrape_content(item["url"])
            return idx, item, content

        with ThreadPoolExecutor(max_workers=SCRAPE_WORKERS) as executor:
            futures = {executor.submit(_scrape_one, pair): pair for pair in to_scrape}
            for future in as_completed(futures):
                idx, item, content = future.result()
                item["full_content"] = content
                if content:
                    logger.info("  [%d/%d] %d chars - %s", idx + 1, total, len(content), item.get("title", "")[:60])
                else:
                    logger.warning("  [%d/%d] no content - %s", idx + 1, total, item.get("title", "")[:60])

        # 确保未抓取的条目也有 full_content 字段
        for item in news_items:
            item.setdefault("full_content", "")

        return news_items

    def save_news(self, news_items, filename="data/raw_news.json"):
        """保存新闻数据到 JSON 文件。"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(news_items, f, indent=2, ensure_ascii=False)
        logger.info("Saved data to %s", filename)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    collector = NewsCollector()
    news = collector.fetch_news(query="latest stock market news", count=5)
    collector.save_news(news)
