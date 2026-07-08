import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import httpx

SOURCES_PATH = Path(__file__).parent / "sources.json"
TIMEOUT = 15
MAX_ITEMS = 30
PER_SOURCE_LIMIT = 5
ZH_RATIO = 0.7


def log(msg):
    print(msg, file=sys.stderr)


def load_sources():
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_rss(item, source_name, source_lang):
    published = None
    if hasattr(item, "published_parsed") and item.published_parsed:
        published = datetime(*item.published_parsed[:6], tzinfo=timezone.utc).isoformat()
    return {
        "title": item.get("title", "").strip(),
        "url": item.get("link", "").strip(),
        "source": source_name,
        "lang": source_lang,
        "date_raw": published,
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
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "source": "Google News",
                    "lang": "zh",
                    "date_raw": None,
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
        key = item["title"][:30]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def balance_language(items):
    zh_items = [i for i in items if i["lang"] == "zh"]
    en_items = [i for i in items if i["lang"] == "en"]

    zh_target = int(MAX_ITEMS * ZH_RATIO)
    en_target = MAX_ITEMS - zh_target

    zh_items = zh_items[:zh_target]
    en_items = en_items[:en_target]

    return zh_items + en_items


def main():
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

    zh_before = sum(1 for i in all_items if i["lang"] == "zh")
    en_before = sum(1 for i in all_items if i["lang"] == "en")
    log(f"Before balance: zh={zh_before} en={en_before}")

    all_items = balance_language(all_items)
    all_items = all_items[:MAX_ITEMS]

    zh_count = sum(1 for i in all_items if i["lang"] == "zh")
    en_count = sum(1 for i in all_items if i["lang"] == "en")
    log(f"Final: zh={zh_count} en={en_count} total={len(all_items)}")

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(all_items),
        "zh_count": zh_count,
        "en_count": en_count,
        "items": all_items,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
