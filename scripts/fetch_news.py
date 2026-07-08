import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import httpx

SOURCES_PATH = Path(__file__).parent / "sources.json"
TIMEOUT = 15
MAX_ITEMS = 30
PER_SOURCE_LIMIT = 5
ZH_RATIO = 0.7


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
    items = []
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries[:PER_SOURCE_LIMIT]:
            item = parse_rss(entry, source["name"], source["lang"])
            if item["title"] and item["url"]:
                items.append(item)
    except Exception:
        pass
    return items


def fetch_sina():
    items = []
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(
                "https://feed.mix.sina.com.cn/api/roll/get",
                params={"pageid": 153, "lid": 2509, "k": "", "num": PER_SOURCE_LIMIT, "page": 1},
                headers={"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"},
            )
            resp.raise_for_status()
            data = resp.json()
            for entry in data.get("result", {}).get("data", []):
                title = entry.get("title", "").strip()
                url = entry.get("url", "").strip()
                if title and url:
                    items.append({
                        "title": title,
                        "url": url,
                        "source": "新浪新闻",
                        "lang": "zh",
                        "date_raw": entry.get("ctime"),
                    })
    except Exception:
        pass
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

    for src in sources.get("rss", []):
        if src["name"] == "新浪新闻":
            all_items += fetch_sina()
        else:
            all_items += fetch_rss(src)

    all_items = deduplicate(all_items)
    all_items = balance_language(all_items)
    all_items = all_items[:MAX_ITEMS]

    zh_count = sum(1 for i in all_items if i["lang"] == "zh")
    en_count = sum(1 for i in all_items if i["lang"] == "en")

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
