#!/usr/bin/env python3
"""
Bot Trade - Standalone News Crawler Process (2-Step AI Pipeline)

Step 1: Fetch all titles from CafeBiz RSS → AI filters relevant articles
Step 2: Crawl full article content → AI scores impact on watchlist stocks

Usage:
    python run_crawler.py          # Run continuously (30min loop)
    python run_crawler.py --once   # Run one cycle and exit (for testing)
"""
import sys
import os
import time
import logging
import requests as http_requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.adapters.cafebiz_crawler import CafeBizCrawler
from src.core.ai_analyzer import AIAnalyzer
from src.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] crawler: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("crawler")

CRAWL_INTERVAL_SECONDS = 1800  # 30 minutes
AI_CALL_DELAY_SECONDS = 3      # Delay between OpenRouter API calls
SERVER_URL = f"http://localhost:{settings.port}/api/v1/sentiments"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10


def fetch_and_analyze(crawler, analyzer, watchlist):
    """
    2-step AI pipeline:
    1. Fetch all titles → AI picks relevant articles
    2. Crawl full content → AI scores impact per stock
    """
    all_articles = crawler.fetch_all_titles()
    if not all_articles:
        logger.info("No articles found from CafeBiz RSS feeds.")
        return {}

    selected = analyzer.filter_titles(all_articles)
    if not selected:
        logger.info("AI filter: no relevant articles found.")
        return {}

    logger.info(f"Processing {len(selected)} selected articles...")

    # TẠO MỘT DICT ĐỂ LƯU DANH SÁCH ĐIỂM (Chưa cộng vội)
    # Ví dụ: raw_scores = {'FPT': [1, 1, 2], 'SSI': [-1]}
    raw_scores = {} 
    
    for i, article in enumerate(selected):
        title = article["title"]
        link = article["link"]

        content = crawler.fetch_article_content(link)
        if not content:
            logger.info(f"  [{i+1}/{len(selected)}] Skipping (failed to fetch): {title[:50]}...")
            continue

        result = analyzer.analyze_article(content, title, watchlist)
        if result and result.get("impacts"):
            for impact in result["impacts"]:
                sym = impact["symbol"]
                score = impact["score"]
                reason = impact.get('reason', '')
                
                # Gom điểm vào mảng thay vì cộng dồn
                raw_scores.setdefault(sym, []).append(score)
                
                logger.info(f"  [{i+1}/{len(selected)}] {sym}: {'+' if score > 0 else ''}{score} ({reason})")
        else:
            logger.info(f"  [{i+1}/{len(selected)}] No impact: {title[:50]}...")

        if i < len(selected) - 1:
            time.sleep(AI_CALL_DELAY_SECONDS)

    # BƯỚC MỚI: TỔNG HỢP ĐIỂM (AGGREGATE)
    final_sentiments = {}
    if raw_scores:
        logger.info("Aggregating scores to prevent noise accumulation...")
        for sym, scores_list in raw_scores.items():
            # Sử dụng hàm chống nhiễu từ AIAnalyzer
            final_score = analyzer.aggregate_sentiment(scores_list, strategy="max_impact")
            final_sentiments[sym] = final_score
            logger.info(f"  -> {sym} Final Score: {final_score} (from {scores_list})")

    return final_sentiments


def post_sentiments(sentiments):
    """POST sentiment data to the FastAPI server with retries."""
    payload = {"sentiments": sentiments}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = http_requests.post(SERVER_URL, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Posted sentiments to server: {sentiments} -> {data}")
            return True
        except http_requests.ConnectionError:
            logger.warning(
                f"Server not reachable (attempt {attempt}/{MAX_RETRIES}). "
                f"Retrying in {RETRY_DELAY_SECONDS}s..."
            )
            time.sleep(RETRY_DELAY_SECONDS)
        except Exception as e:
            logger.error(f"Failed to post sentiments: {e}")
            return False

    logger.error(f"Could not reach server after {MAX_RETRIES} attempts.")
    return False


def main():
    run_once = "--once" in sys.argv
    watchlist = settings.watchlist_symbols

    print("\n" + "=" * 50)
    print("Bot Trade - News Crawler (2-Step AI Pipeline)")
    print("=" * 50)
    print(f"Server URL: {SERVER_URL}")
    print(f"Watchlist: {watchlist}")
    print(f"Crawl interval: {CRAWL_INTERVAL_SECONDS // 60} minutes")
    print(f"AI call delay: {AI_CALL_DELAY_SECONDS}s between calls")
    if run_once:
        print("Mode: --once (single cycle)")
    print("=" * 50 + "\n")

    try:
        crawler = CafeBizCrawler()
        analyzer = AIAnalyzer()
        logger.info(f"Crawler & AI Analyzer initialized (model: {analyzer.model_name})")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        sys.exit(1)

    while True:
        try:
            logger.info("Starting crawl cycle...")
            sentiments = fetch_and_analyze(crawler, analyzer, watchlist)

            if sentiments:
                post_sentiments(sentiments)
            else:
                # Post empty to clear stale sentiments on server
                post_sentiments({})

        except KeyboardInterrupt:
            logger.info("Crawler stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in crawl cycle: {e}")

        if run_once:
            logger.info("--once mode: exiting after single cycle.")
            break

        logger.info(f"Next crawl in {CRAWL_INTERVAL_SECONDS // 60} minutes...")
        time.sleep(CRAWL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
