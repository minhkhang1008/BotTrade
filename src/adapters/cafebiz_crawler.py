"""
CafeBiz RSS Crawler - Fetches market-relevant news from CafeBiz RSS feeds
and extracts full article content for AI analysis.
"""
import time
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("crawler")

# Market-relevant RSS feeds only
RSS_FEEDS = {
    "vi-mo": "https://cafebiz.vn/rss/vi-mo.rss",
    "chinh-sach": "https://cafebiz.vn/rss/chinh-sach.rss",
    "kinh-doanh": "https://cafebiz.vn/rss/cau-chuyen-kinh-doanh.rss",
    "bat-dong-san": "https://cafebiz.vn/rss/bat-dong-san.rss",
    "ngan-hang": "https://cafebiz.vn/rss/ngan-hang-tai-chinh.rss",
    "chung-khoan": "https://cafebiz.vn/rss/chung-khoan.rss",
    "san-xuat": "https://cafebiz.vn/rss/san-xuat.rss",
    "dau-tu": "https://cafebiz.vn/rss/dau-tu.rss",
}

# Max characters of article content to send to AI (controls token usage)
MAX_ARTICLE_CHARS = 3000

# How long to remember seen URLs (seconds)
SEEN_URL_TTL = 7200  # 2 hours


class CafeBizCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self._seen_urls = {}  # url -> timestamp

    def _is_recently_seen(self, url):
        if url in self._seen_urls:
            if time.time() - self._seen_urls[url] < SEEN_URL_TTL:
                return True
        return False

    def _mark_seen(self, url):
        self._seen_urls[url] = time.time()

    def _cleanup_seen(self):
        """Remove expired entries from seen cache."""
        now = time.time()
        expired = [u for u, t in self._seen_urls.items() if now - t >= SEEN_URL_TTL]
        for u in expired:
            del self._seen_urls[u]

    def fetch_all_titles(self, limit_per_feed=10):
        """
        Fetch article titles from all RSS feeds.
        Returns list of {"title": str, "link": str, "source": str}.
        Deduplicates by URL and skips recently-seen articles.
        """
        self._cleanup_seen()
        all_articles = []
        seen_links = set()

        for source, url in RSS_FEEDS.items():
            try:
                resp = requests.get(url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(resp.content, "xml")
                items = soup.find_all("item")

                for item in items[:limit_per_feed]:
                    title = item.title.text.strip() if item.title else ""
                    link = item.link.text.strip() if item.link else ""

                    if not title or not link:
                        continue
                    if link in seen_links:
                        continue
                    if self._is_recently_seen(link):
                        continue

                    seen_links.add(link)
                    all_articles.append({
                        "title": title,
                        "link": link,
                        "source": source,
                    })

                logger.info(f"RSS [{source}]: fetched {min(len(items), limit_per_feed)} items")

            except Exception as e:
                logger.warning(f"RSS [{source}] failed: {e}")
                continue

        logger.info(f"Total unique titles collected: {len(all_articles)}")
        return all_articles

    def fetch_article_content(self, url):
        """
        Fetch and extract the main text content of an article page.
        Returns cleaned text string, truncated to MAX_ARTICLE_CHARS.
        Returns None on failure.
        """
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(resp.content, "html.parser")

            # Remove non-content elements
            for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
                tag.decompose()

            # CafeBiz article content is typically in these selectors
            content_el = (
                soup.find("div", class_="detail-content") or
                soup.find("div", class_="maincontent") or
                soup.find("article") or
                soup.find("div", class_="content")
            )

            if content_el:
                # Get text from paragraphs for cleaner output
                paragraphs = content_el.find_all("p")
                if paragraphs:
                    text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                else:
                    text = content_el.get_text(separator="\n", strip=True)
            else:
                # Fallback: get all paragraph text from page
                paragraphs = soup.find_all("p")
                text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

            if not text or len(text) < 50:
                logger.warning(f"Article content too short or empty: {url}")
                return None

            # Mark as seen after successful crawl
            self._mark_seen(url)

            # Truncate to control token usage
            if len(text) > MAX_ARTICLE_CHARS:
                text = text[:MAX_ARTICLE_CHARS] + "..."

            return text

        except Exception as e:
            logger.warning(f"Failed to fetch article content: {url} - {e}")
            return None
