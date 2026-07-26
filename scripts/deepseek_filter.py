import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import httpx
import trafilatura

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
MAX_RESULTS = 12
PER_ITEM_SUMMARY_MAX = 40
SCRAPE_TIMEOUT = aiohttp.ClientTimeout(total=8)
SCRAPE_CONCURRENCY = 5
API_TIMEOUT = 30

SYSTEM_PROMPT = (
    "你是新闻编辑。从候选列表中选出最多12条重要新闻，"
    f"每条用{PER_ITEM_SUMMARY_MAX}字以内中文摘要并给出分类。输出JSON对象，包含items数组。"
)

OUTPUT_PATH = Path(__file__).parent.parent / "news.json"


def log(msg):
    print(msg, file=sys.stderr)


def load_news():
    data = json.load(sys.stdin)
    return data.get("items", [])


def load_today_cache():
    try:
        if not OUTPUT_PATH.exists():
            return None
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if data.get("date") == today_str:
            return data
        return None
    except Exception:
        return None


def build_user_message(items):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"今天是 {today}。候选列表（标题 来源 链接）："]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. [{item.get('source', '未知')}] {item.get('title', '')}")
        lines.append(f"   {item.get('url', '')}")
    return "\n".join(lines)


def call_deepseek(prompt):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=API_TIMEOUT) as client:
        resp = client.post(DEEPSEEK_API_URL, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()


def parse_response(data):
    content = data["choices"][0]["message"]["content"].strip()
    parsed = json.loads(content)
    if isinstance(parsed, dict) and "items" in parsed:
        return parsed["items"]
    if isinstance(parsed, list):
        return parsed
    return []


def fallback_items(items):
    log("API failed or unavailable, using fallback selection")
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "source": item.get("source", ""),
            "category": "未分类",
            "summary": "",
        }
        for item in items[:MAX_RESULTS]
    ]


async def scrape_one(session, url):
    try:
        async with session.get(url, timeout=SCRAPE_TIMEOUT) as resp:
            if resp.status != 200:
                return ""
            html = await resp.text()
            text = trafilatura.extract(
                html,
                output_format="txt",
                include_comments=False,
                include_tables=False,
                deduplicate=True,
            )
            return (text or "").strip()
    except Exception as e:
        log(f"  [SCRAPE FAIL] {url}: {e}")
        return ""


async def scrape_all(items):
    semaphore = asyncio.Semaphore(SCRAPE_CONCURRENCY)

    async def bound_scrape(session, item):
        async with semaphore:
            content = await scrape_one(session, item.get("url", ""))
            item["content"] = content
            return item

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        await asyncio.gather(*[bound_scrape(session, item) for item in items])
    return items


def select_and_summarize(items):
    cached = load_today_cache()
    if cached:
        log("Today's news.json already exists, using cached selection")
        return cached.get("items", [])

    prompt = build_user_message(items)
    try:
        api_response = call_deepseek(prompt)
        selected = parse_response(api_response)
    except Exception as e:
        log(f"[API ERROR] {e}")
        selected = fallback_items(items)

    selected = selected[:MAX_RESULTS]
    for item in selected:
        item.setdefault("category", "未分类")
        item.setdefault("summary", "")
    return selected


def save_output(items, summary=""):
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output = {
        "date": today_str,
        "generated": datetime.now(timezone.utc).isoformat(),
        "summary": summary or f"今日精选 {len(items)} 条要闻",
        "total": len(items),
        "items": items,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, ensure_ascii=False, indent=2, fp=f)
    log(f"Saved {output['total']} items to {OUTPUT_PATH}")


async def main():
    items = load_news()
    if not items:
        print(json.dumps({"error": "No news items to filter"}, ensure_ascii=False))
        sys.exit(1)

    log(f"Received {len(items)} candidate items")
    cached = load_today_cache()
    selected = select_and_summarize(items)
    summary = cached.get("summary", "") if cached else ""

    items_to_scrape = [item for item in selected if not item.get("content")]
    if items_to_scrape:
        log(f"Scraping content for {len(items_to_scrape)} items...")
        await scrape_all(items_to_scrape)

    save_output(selected, summary=summary)


if __name__ == "__main__":
    asyncio.run(main())
