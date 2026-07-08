import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
MAX_RESULTS = 15

SYSTEM_PROMPT = """你是一个专业的新闻编辑。你的任务是：

1. 从提供的新闻列表中选择发布日期在7天内的条目
2. 排除明显过时、日期错误、广告或非新闻内容
3. 为每条保留的新闻用中文写一句精炼摘要（20字以内）
4. 估算或保留新闻的分类，如：国际、科技、财经、社会、体育、娱乐
5. 最后给出一句今日要闻概览（30字以内）

请严格按以下 JSON 格式返回，不要包含 markdown 代码块标记：

{
  "summary": "今日要点一句话",
  "items": [
    {
      "title": "原标题",
      "url": "原链接",
      "source": "来源名称",
      "category": "分类",
      "summary": "中文摘要20字内",
      "is_recent": true
    }
  ]
}

只返回 is_recent 为 true 的条目，最多15条。"""

def load_news():
    data = json.load(sys.stdin)
    return data.get("items", [])

def build_user_message(items):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    lines = [f"今天是 {today}，请筛选 {cutoff} 之后发布的新闻。以下是今天抓取到的头条列表：\n"]
    for i, item in enumerate(items, 1):
        date_str = item.get("date_raw", "未知")
        lines.append(f"{i}. [{item['source']}] {item['title']}")
        lines.append(f"   链接: {item['url']}")
        lines.append(f"   原始日期: {date_str}")
        lines.append("")
    return "\n".join(lines)

def call_deepseek(prompt):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print(json.dumps({"error": "DEEPSEEK_API_KEY not set"}, ensure_ascii=False))
        sys.exit(1)

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
        "max_tokens": 4096,
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(DEEPSEEK_API_URL, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()

def parse_response(data):
    content = data["choices"][0]["message"]["content"]
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1])
    return json.loads(content)

def save_output(result):
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output = {
        "date": today_str,
        "generated": datetime.now(timezone.utc).isoformat(),
        "summary": result.get("summary", ""),
        "total": len(result.get("items", [])),
        "items": [item for item in result.get("items", []) if item.get("is_recent")],
    }
    output["items"] = output["items"][:MAX_RESULTS]
    output["total"] = len(output["items"])

    output_path = Path(__file__).parent.parent / "news.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, ensure_ascii=False, indent=2, fp=f)

    print(f"Saved {output['total']} items to news.json")

def main():
    items = load_news()
    if not items:
        print(json.dumps({"error": "No news items to filter"}, ensure_ascii=False))
        sys.exit(1)

    prompt = build_user_message(items)
    print(f"Sending {len(items)} items to DeepSeek API...", file=sys.stderr)

    api_response = call_deepseek(prompt)
    result = parse_response(api_response)
    save_output(result)

if __name__ == "__main__":
    main()
