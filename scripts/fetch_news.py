import asyncio
import html
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aiohttp
import feedparser
import trafilatura

SOURCES_PATH = Path(__file__).parent / "sources.json"
OUTPUT_PATH = Path(__file__).parent.parent / "news.json"

MAX_ITEMS = 30
PER_SOURCE_LIMIT = 5
ZH_RATIO = 0.7
DESCRIPTION_LIMIT = 180
CONTENT_LIMIT = 10000

SCRAPE_TIMEOUT = aiohttp.ClientTimeout(total=10)
SCRAPE_CONCURRENCY = 6
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

CST = timezone(timedelta(hours=8))
TAG_RE = re.compile(r"<[^>]+>")


def log(msg):
    print(msg, file=sys.stderr)


def now_cst():
    return datetime.now(CST)


def clean_text(raw, limit=DESCRIPTION_LIMIT):
    if not raw:
        return ""
    text = TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def load_sources():
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_rss(item, source_name, source_lang):
    published = None
    if getattr(item, "published_parsed", None):
        published = datetime(*item.published_parsed[:6], tzinfo=timezone.utc).isoformat()
    return {
        "title": html.unescape(item.get("title", "")).strip(),
        "url": item.get("link", "").strip(),
        "source": source_name,
        "lang": source_lang,
        "published": published,
        "description": clean_text(item.get("summary") or item.get("description") or ""),
        "content": "",
    }


def fetch_rss(source):
    name = source["name"]
    items = []
    try:
        feed = feedparser.parse(source["url"])
        if feed.bozo and not feed.entries:
            log(f"  [SKIP] {name}: {feed.bozo_exception}")
            return items
        count = 0
        for entry in feed.entries:
            if count >= PER_SOURCE_LIMIT:
                break
            item = parse_rss(entry, name, source["lang"])
            if item["title"] and item["url"]:
                items.append(item)
                count += 1
        log(f"  [OK] {name}: {count} items")
    except Exception as e:
        log(f"  [FAIL] {name}: {e}")
    return items


def fetch_google_news():
    items = []
    try:
        url = "https://news.google.com/rss/search?q=news&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            if count >= PER_SOURCE_LIMIT:
                break
            title = html.unescape(entry.get("title", "")).strip()
            link = entry.get("link", "").strip()
            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "source": "Google News",
                    "lang": "zh",
                    "published": None,
                    "description": clean_text(entry.get("summary") or ""),
                    "content": "",
                })
                count += 1
        log(f"  [OK] Google News (zh): {count} items")
    except Exception as e:
        log(f"  [FAIL] Google News: {e}")
    return items


def deduplicate(items):
    seen = set()
    unique = []
    for item in items:
        key = re.sub(r"\s+", "", item["title"])[:30].lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def balance_language(items):
    zh_items = [i for i in items if i["lang"] == "zh"]
    en_items = [i for i in items if i["lang"] == "en"]

    zh_target = int(MAX_ITEMS * ZH_RATIO)
    en_target = MAX_ITEMS - zh_target

    return zh_items[:zh_target] + en_items[:en_target]


async def scrape_one(session, url):
    try:
        async with session.get(url, timeout=SCRAPE_TIMEOUT) as resp:
            if resp.status != 200:
                return ""
            html_text = await resp.text(errors="ignore")
            text = trafilatura.extract(
                html_text,
                output_format="txt",
                include_comments=False,
                include_tables=False,
                deduplicate=True,
            )
            text = (text or "").strip()
            if len(text) < 80:
                return ""
            if len(text) > CONTENT_LIMIT:
                text = text[:CONTENT_LIMIT].rstrip() + "…"
            return text
    except Exception as e:
        log(f"  [SCRAPE FAIL] {url}: {e}")
        return ""


async def scrape_all(items):
    semaphore = asyncio.Semaphore(SCRAPE_CONCURRENCY)

    async def bound_scrape(session, item):
        async with semaphore:
            item["content"] = await scrape_one(session, item.get("url", ""))
            return item

    async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
        await asyncio.gather(*[bound_scrape(session, item) for item in items])
    return items


def build_output(items):
    zh_count = sum(1 for i in items if i["lang"] == "zh")
    en_count = sum(1 for i in items if i["lang"] == "en")
    return {
        "date": now_cst().strftime("%Y-%m-%d"),
        "generated": now_cst().isoformat(),
        "total": len(items),
        "zh_count": zh_count,
        "en_count": en_count,
        "items": items,
    }


def save_output(output):
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log(f"Saved {output['total']} items to {OUTPUT_PATH}")


async def main():
    sources = load_sources()
    all_items = []

    log("Fetching RSS sources...")
    for src in sources.get("rss", []):
        all_items += fetch_rss(src)

    log("Fetching Google News zh...")
    all_items += fetch_google_news()

    log(f"Total before dedup: {len(all_items)}")

    all_items = deduplicate(all_items)
    log(f"After dedup: {len(all_items)}")

    all_items = balance_language(all_items)
    all_items = all_items[:MAX_ITEMS]

    zh_count = sum(1 for i in all_items if i["lang"] == "zh")
    en_count = sum(1 for i in all_items if i["lang"] == "en")
    log(f"Final: zh={zh_count} en={en_count} total={len(all_items)}")

    if not all_items:
        log("[ERROR] No news items fetched")
        sys.exit(1)

    log("Scraping article content...")
    await scrape_all(all_items)
    with_content = sum(1 for i in all_items if i["content"])
    log(f"Scraped content for {with_content}/{len(all_items)} items")

    save_output(build_output(all_items))


if __name__ == "__main__":
    asyncio.run(main())