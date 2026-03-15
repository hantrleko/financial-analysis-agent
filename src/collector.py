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
    SOURCE_DOMAINS,
    DEDUP_SIMILARITY_THRESHOLD,
)

load_dotenv()

logger = logging.getLogger(__name__)

YOU_API_KEY = os.getenv("YOU_API_KEY")


class NewsCollector:
    # time_range → Freshness 映射
    _FRESHNESS_MAP = {
        "24h": "DAY",
        "week": "WEEK",
        "month": "MONTH",
    }

    def __init__(self):
        self.api_key = YOU_API_KEY

    def fetch_news(self, query="financial markets trends", count=10, sources=None, time_range="24h"):
        """
        使用 youdotcom SDK 获取新闻，失败则回退到 RSS。
        支持通过 sources 指定新闻来源，通过 time_range 限定时间范围。
        """
        if not self.api_key:
            logger.warning("YOU_API_KEY not found. Falling back to RSS.")
            return self._fetch_rss(count, time_range)

        try:
            from youdotcom import You
            from youdotcom.models import Freshness

            # 构建带 site: 限定的查询
            final_query = query
            if sources:
                site_parts = []
                for src in sources:
                    domain = SOURCE_DOMAINS.get(src)
                    if domain:
                        site_parts.append(f"site:{domain}")
                if site_parts:
                    final_query = f"{query} {' OR '.join(site_parts)}"

            # 通过 Freshness 枚举设定时间范围
            freshness_key = self._FRESHNESS_MAP.get(time_range)
            freshness_value = getattr(Freshness, freshness_key, None) if freshness_key else None

            logger.info("Fetching news via You.com SDK for: '%s' (freshness=%s)...", final_query, freshness_key)
            with You(self.api_key) as you:
                res = you.search.unified(query=final_query, freshness=freshness_value)

            news_items = []

            # 优先使用 news 结果
            if res.results and res.results.news:
                for item in res.results.news[:count]:
                    news_items.append({
                        "title": item.title,
                        "url": item.url,
                        "description": item.description or item.title,
                        "source": "You.com (News)",
                        "published_age": str(item.page_age) if item.page_age else "Recent",
                        "thumbnail_url": item.thumbnail_url or "",
                        "full_content": item.contents or "",
                        "fetched_at": datetime.now().isoformat(),
                    })

            # 回退到 web 结果
            if not news_items and res.results and res.results.web:
                for item in res.results.web[:count]:
                    snippet = ""
                    if item.snippets:
                        snippet = item.snippets[0]

                    news_items.append({
                        "title": item.title,
                        "url": item.url,
                        "description": snippet or item.title,
                        "source": "You.com",
                        "published_age": "Recent",
                        "fetched_at": datetime.now().isoformat(),
                    })

            logger.info("Successfully fetched %d articles via You.com.", len(news_items))
            return news_items if news_items else self._fetch_rss(count, time_range)

        except Exception as e:
            logger.error("Error fetching from You.com: %s", e)
            logger.warning("Falling back to RSS feeds...")
            return self._fetch_rss(count, time_range)

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

        # 去重（URL + 标题模糊匹配）
        seen_urls = set()
        seen_titles = []
        unique_items = []
        for item in all_items:
            url = item["url"]
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

        result = unique_items[:count]
        logger.info("Successfully fetched %d unique articles from %d RSS sources.", len(result), len(RSS_FEEDS))
        return result

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
