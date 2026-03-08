import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

YOU_API_KEY = os.getenv("YOU_API_KEY")


class NewsCollector:
    # 支持的新闻源列表
    AVAILABLE_SOURCES = [
        "Bloomberg", "Reuters", "AP News", "Yahoo Finance",
        "CNBC", "Financial Times", "Wall Street Journal"
    ]

    # 新闻源到域名的映射
    _SOURCE_DOMAINS = {
        "Bloomberg": "bloomberg.com",
        "Reuters": "reuters.com",
        "AP News": "apnews.com",
        "Yahoo Finance": "finance.yahoo.com",
        "CNBC": "cnbc.com",
        "Financial Times": "ft.com",
        "Wall Street Journal": "wsj.com",
    }

    # 时间范围关键词映射
    _TIME_RANGE_KEYWORDS = {
        "24h": "past 24 hours",
        "week": "past week",
        "month": "past month",
    }

    def __init__(self):
        self.api_key = YOU_API_KEY

    def fetch_news(self, query="financial markets trends", count=10, sources=None, time_range="24h"):
        """
        使用 youdotcom SDK 获取新闻，失败则回退到 RSS。
        支持通过 sources 指定新闻来源，通过 time_range 限定时间范围。
        """
        if not self.api_key:
            print("Warning: YOU_API_KEY not found. Falling back to RSS.")
            return self._fetch_rss(count)

        try:
            from youdotcom import You

            # 构建带 site: 限定的查询
            final_query = query
            if sources:
                site_parts = []
                for src in sources:
                    domain = self._SOURCE_DOMAINS.get(src)
                    if domain:
                        site_parts.append(f"site:{domain}")
                if site_parts:
                    final_query = f"{query} {' OR '.join(site_parts)}"

            # 追加时间范围关键词
            time_keyword = self._TIME_RANGE_KEYWORDS.get(time_range)
            if time_keyword:
                final_query = f"{final_query} {time_keyword}"

            print(f"Fetching news via You.com SDK for: '{final_query}'...")
            with You(self.api_key) as you:
                res = you.search.unified(query=final_query)

            news_items = []
            if res.results and res.results.web:
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
                        "fetched_at": datetime.now().isoformat()
                    })

            print(f"Successfully fetched {len(news_items)} articles via You.com.")
            return news_items if news_items else self._fetch_rss(count)

        except Exception as e:
            print(f"Error fetching from You.com: {e}")
            print("Falling back to RSS feeds...")
            return self._fetch_rss(count)

    # 多源 RSS 列表
    _RSS_FEEDS = [
        {"url": "https://finance.yahoo.com/news/rssindex", "source": "Yahoo Finance"},
        {"url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en", "source": "Google News (Business)"},
        {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "source": "CNBC"},
        {"url": "https://feeds.reuters.com/reuters/businessNews", "source": "Reuters"},
        {"url": "https://feeds.bloomberg.com/markets/news.rss", "source": "Bloomberg"},
    ]

    def _fetch_rss(self, count=10):
        """从多个 RSS 源聚合新闻，按时间排序后取 top N。"""
        import feedparser

        all_items = []
        for feed_info in self._RSS_FEEDS:
            try:
                print(f"Fetching RSS from: {feed_info['source']}...")
                feed = feedparser.parse(feed_info["url"])
                for entry in feed.entries[:count]:
                    all_items.append({
                        "title": entry.get("title", "No Title"),
                        "url": entry.get("link", ""),
                        "description": entry.get("summary", entry.get("title", "")),
                        "source": feed_info["source"],
                        "published_age": entry.get("published", "Unknown"),
                        "fetched_at": datetime.now().isoformat(),
                    })
                print(f"  ✓ {feed_info['source']}: {min(len(feed.entries), count)} articles")
            except Exception as e:
                print(f"  ✗ {feed_info['source']}: {e}")

        if not all_items:
            print("All RSS feeds failed. Using mock data.")
            return self._get_mock_data()

        # 去重（按 title）
        seen_titles = set()
        unique_items = []
        for item in all_items:
            title_key = item["title"].strip().lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_items.append(item)

        result = unique_items[:count]
        print(f"Successfully fetched {len(result)} unique articles from {len(self._RSS_FEEDS)} RSS sources.")
        return result

    def _get_mock_data(self):
        """兜底 mock 数据，用于测试流程。"""
        print("Returning MOCK data.")
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

    def scrape_content(self, url, timeout=10):
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
                    return text[:4000]
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
                    return text[:4000]
        except Exception:
            pass

        return ""

    def enrich_with_content(self, news_items, max_scrape=10):
        """为新闻列表批量抓取正文内容，添加 full_content 字段。"""
        total = min(len(news_items), max_scrape)
        print(f"\nScraping full article content ({total} articles)...")
        for i, item in enumerate(news_items[:max_scrape]):
            url = item.get("url", "")
            if url and url.startswith("http"):
                content = self.scrape_content(url)
                item["full_content"] = content
                if content:
                    print(f"  ✓ [{i+1}/{total}] {len(content)} chars — {item.get('title', '')[:60]}")
                else:
                    print(f"  ✗ [{i+1}/{total}] no content — {item.get('title', '')[:60]}")
            else:
                item["full_content"] = ""
        return news_items

    def save_news(self, news_items, filename="data/raw_news.json"):
        """保存新闻数据到 JSON 文件。"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(news_items, f, indent=2, ensure_ascii=False)
        print(f"Saved data to {filename}")


if __name__ == "__main__":
    collector = NewsCollector()
    news = collector.fetch_news(query="latest stock market news", count=5)
    collector.save_news(news)
