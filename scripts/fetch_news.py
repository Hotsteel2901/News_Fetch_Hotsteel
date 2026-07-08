import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import httpx

SOURCES_PATH = Path(__file__).parent / "sources.json"
TIMEOUT = 15
MAX_ITEMS = 30

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

def fetch_rss(sources):
    all_items = []
    for src in sources:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries:
                all_items.append(parse_rss(entry, src["name"], src["lang"]))
        except Exception:
            continue
    return all_items

def fetch_web(sources):
    items = []
    for src in sources:
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                resp = client.get(src["url"])
                resp.raise_for_status()
        except Exception:
            continue
    return items

def deduplicate(items):
    seen = set()
    unique = []
    for item in items:
        key = item["title"][:50]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique

def main():
    sources = load_sources()
    items = fetch_rss(sources.get("rss", []))
    items += fetch_web(sources.get("web", []))
    items = deduplicate(items)

    items = items[:MAX_ITEMS]

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
