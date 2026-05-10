"""
News ingestion via NewsAPI.
Pulls headlines + bodies for each ticker in our universe and stores:
  - metadata in PostgreSQL (news_articles table)
  - full article JSON in S3
"""
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import ALL_TICKERS, NEWS_API_KEY, NEWS_LOOKBACK_HOURS
from data.storage.db_client import insert_news_article
from data.storage.s3_client import news_s3_filename, upload_json

logger = logging.getLogger(__name__)

NEWS_API_URL = "https://newsapi.org/v2/everything"


def run(lookback_hours: int = NEWS_LOOKBACK_HOURS) -> int:
    """
    Fetch recent news for all tickers.
    Returns total articles stored.
    """
    if not NEWS_API_KEY:
        raise ValueError("NEWS_API_KEY is not set in environment")

    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    logger.info("Fetching news since %s for %d tickers", since.isoformat(), len(ALL_TICKERS))

    total = 0
    for ticker in ALL_TICKERS:
        total += _ingest_ticker(ticker, since)
        time.sleep(1)

    logger.info("News ingest complete — %d articles stored", total)
    return total


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
def _ingest_ticker(ticker: str, since: datetime) -> int:
    # NewsAPI free tier: search by company name works better than raw ticker
    params = {
        "q":        f'"{ticker}"',
        "from":     since.strftime("%Y-%m-%dT%H:%M:%S"),
        "language": "en",
        "sortBy":   "publishedAt",
        "pageSize": 100,
        "apiKey":   NEWS_API_KEY,
    }

    resp = requests.get(NEWS_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    articles = resp.json().get("articles", [])

    count = 0
    for article in articles:
        if _store_article(ticker, article):
            count += 1

    logger.debug("%s: %d articles stored", ticker, count)
    return count


def _store_article(ticker: str, article: dict) -> bool:
    """Upload to S3, insert metadata to DB. Returns True if stored."""
    published_raw = article.get("publishedAt", "")
    try:
        published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        logger.warning("Bad publishedAt for %s: %s", ticker, published_raw)
        return False

    # Stable dedup key from URL
    url = article.get("url", "")
    article_id = hashlib.md5(url.encode()).hexdigest()[:12]

    payload = {
        "ticker":       ticker,
        "headline":     article.get("title", ""),
        "url":          url,
        "source":       article.get("source", {}).get("name", ""),
        "author":       article.get("author", ""),
        "published_at": published_raw,
        "body":         article.get("content", "") or article.get("description", ""),
    }

    s3_filename = news_s3_filename(ticker, article_id, published_at)
    try:
        s3_path = upload_json(payload, "news", s3_filename)
    except Exception as exc:
        logger.error("S3 upload failed for %s/%s: %s", ticker, article_id, exc)
        return False

    insert_news_article({
        "ticker":       ticker,
        "headline":     payload["headline"],
        "url":          url,
        "source":       payload["source"],
        "author":       payload["author"],
        "published_at": published_at,
        "s3_path":      s3_path,
    })
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
