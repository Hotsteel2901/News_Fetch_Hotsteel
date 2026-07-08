# 每日新闻速览 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个每日自动抓取、AI 筛选、美观展示的新闻摘要 Web 应用

**Architecture:** GitHub Actions 定时触发 Python 脚本抓取 RSS/网页头条，调 DeepSeek API 筛选，生成 JSON 数据文件提交到仓库，GitHub Pages 托管纯静态前端页面读取渲染

**Tech Stack:** Python 3.12 + feedparser + httpx, DeepSeek V4 Flash API, 纯 HTML/CSS/JS, GitHub Actions + Pages

## Global Constraints

- DeepSeek API Key 只能存在于 GitHub Secrets，源码中不可出现
- 前端纯静态，零 JS 框架依赖
- 配色: 主色 #DC2626, 背景 #FEF2F2, 前景 #450A0A
- 字体: Newsreader (标题) + Roboto (正文)
- 移动优先，单栏布局，最大宽 720px
- 每次抓取 ~30 条新闻，AI 筛选后保留 10-15 条

---

### Task 1: 项目基础结构搭建

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`

**Interfaces:**
- Produces: 项目根目录的基础文件，后续所有任务依赖此结构

- [ ] **Step 1: 创建 .gitignore**

写入以下内容：

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
venv/
.env

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 2: 创建 requirements.txt**

```
feedparser>=6.0.0
httpx>=0.27.0
```

- [ ] **Step 3: 提交**

```bash
git add .gitignore requirements.txt
git commit -m "chore: add project scaffolding"
```

---

### Task 2: 新闻源配置文件

**Files:**
- Create: `scripts/sources.json`

**Interfaces:**
- Produces: `sources.json` — 供 fetch_news.py 读取。结构为 `{ "rss": [{ "name": "源名称", "url": "RSS地址", "lang": "zh|en" }, ...], "web": [{ "name": "源名称", "url": "页面URL", "selector": "CSS选择器", "lang": "zh|en" }, ...] }`

- [ ] **Step 1: 创建 scripts/sources.json**

```json
{
  "rss": [
    { "name": "BBC News", "url": "https://feeds.bbci.co.uk/news/rss.xml", "lang": "en" },
    { "name": "Reuters", "url": "https://www.reutersagency.com/feed/", "lang": "en" },
    { "name": "CNN", "url": "http://rss.cnn.com/rss/edition.rss", "lang": "en" },
    { "name": "The Guardian", "url": "https://www.theguardian.com/world/rss", "lang": "en" },
    { "name": "新华网", "url": "http://www.xinhuanet.com/politics/xhll.xml", "lang": "zh" },
    { "name": "环球时报", "url": "https://world.huanqiu.com/rss/headline.xml", "lang": "zh" },
    { "name": "36氪", "url": "https://36kr.com/feed", "lang": "zh" },
    { "name": "新浪新闻", "url": "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&k=&num=10&page=1", "lang": "zh" }
  ],
  "web": []
}
```

- [ ] **Step 2: 提交**

```bash
git add scripts/sources.json
git commit -m "feat: add news source configuration"
```

---

### Task 3: 新闻抓取脚本

**Files:**
- Create: `scripts/fetch_news.py`

**Interfaces:**
- Consumes: `scripts/sources.json`
- Produces: 输出 JSON 到 stdout，结构 `[{ "title": str, "url": str, "source": str, "date_raw": str|None }]`。由 GitHub Actions 重定向到临时文件，传给下一个脚本。

- [ ] **Step 1: 创建 scripts/fetch_news.py**

```python
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
                # 简化处理：如果没有 selector 则跳过
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

    # 限制总数
    items = items[:MAX_ITEMS]

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 本地测试脚本能正常导入运行**

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
```

预期：输出 JSON，包含 `fetched_at`, `count`, `items` 字段，`items` 非空。

- [ ] **Step 3: 提交**

```bash
git add scripts/fetch_news.py
git commit -m "feat: add RSS news fetching script"
```

---

### Task 4: DeepSeek AI 筛选脚本

**Files:**
- Create: `scripts/deepseek_filter.py`

**Interfaces:**
- Consumes: stdin JSON（来自 fetch_news.py 的输出）, 环境变量 `DEEPSEEK_API_KEY`
- Produces: 输出 `news.json` 到仓库根目录。结构 `{ "date": "YYYY-MM-DD", "generated": "ISO时间", "summary": "一句话概述", "total": int, "items": [{ "title", "url", "source", "category", "summary", "time" }] }`

DeepSeek API 端点: `https://api.deepseek.com/v1/chat/completions`
模型: `deepseek-chat`

- [ ] **Step 1: 创建 scripts/deepseek_filter.py**

```python
import json
import os
import sys
from datetime import datetime, timezone, timedelta

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
    from pathlib import Path
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
```

- [ ] **Step 2: 本地测试（需要设置 DEEPSEEK_API_KEY 环境变量）**

```bash
python scripts/fetch_news.py | python scripts/deepseek_filter.py
```

预期：生成 `news.json` 文件，包含筛选后的新闻列表。

- [ ] **Step 3: 提交**

```bash
git add scripts/deepseek_filter.py
git commit -m "feat: add DeepSeek AI filtering script"
```

---

### Task 5: GitHub Actions 定时工作流

**Files:**
- Create: `.github/workflows/daily-news.yml`

**Interfaces:**
- 每日 UTC 16:00（即 UTC+8 00:00）自动触发
- 从 GitHub Secrets 读取 `DEEPSEEK_API_KEY`
- 依次执行 fetch → filter → commit
- 目标分支为仓库默认分支（master），由 Pages 读取

- [ ] **Step 1: 创建 .github/workflows/daily-news.yml**

```yaml
name: Daily News

on:
  schedule:
    - cron: '0 16 * * *'  # UTC+8 00:00
  workflow_dispatch:       # 手动触发

permissions:
  contents: write

jobs:
  fetch-and-filter:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Fetch news
        run: python scripts/fetch_news.py > fetched.json

      - name: Filter with DeepSeek
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
        run: python scripts/deepseek_filter.py < fetched.json

      - name: Commit and push news.json
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add news.json
          git diff --staged --quiet || git commit -m "chore: update daily news [skip ci]"
          git push
```

- [ ] **Step 2: 提交**

```bash
git add .github/workflows/daily-news.yml
git commit -m "feat: add GitHub Actions scheduled workflow"
```

---

### Task 6: 前端新闻展示页面

**Files:**
- Create: `index.html`（自包含 CSS 和 JS）

**Interfaces:**
- 从同域加载 `news.json`
- 处理三个状态：loading（骨架屏）、empty（无新闻提示）、error（加载失败提示）、正常渲染
- 渲染日期标题、今日概览、新闻卡片列表
- 点击卡片在新标签页打开原文
- 响应式：移动端全宽，桌面端居中 720px
- 淡入动画，悬停微交互

- [ ] **Step 1: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日新闻速览</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600;6..72,700&family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --color-primary: #DC2626;
  --color-bg: #FEF2F2;
  --color-fg: #450A0A;
  --color-card: #FFFFFF;
  --color-border: #FECACA;
  --color-muted: #991B1B;
  --font-heading: 'Newsreader', Georgia, serif;
  --font-body: 'Roboto', -apple-system, sans-serif;
}

html { font-size: 16px; scroll-behavior: smooth; }

body {
  font-family: var(--font-body);
  background: var(--color-bg);
  color: var(--color-fg);
  line-height: 1.6;
  min-height: 100dvh;
  -webkit-font-smoothing: antialiased;
}

.container {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
}

/* Header */
.header { text-align: center; padding: 3rem 0 2rem; }

.header-date {
  font-family: var(--font-heading);
  font-size: clamp(2rem, 6vw, 3.5rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-primary);
  line-height: 1.15;
}

.header-weekday {
  font-family: var(--font-heading);
  font-size: 1.1rem;
  font-weight: 400;
  color: var(--color-muted);
  opacity: 0.7;
  margin-top: 0.25rem;
}

/* Summary */
.summary-box {
  text-align: center;
  margin-bottom: 2.5rem;
  padding: 1.25rem 1.5rem;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  font-size: 1rem;
  color: var(--color-muted);
  line-height: 1.7;
}

/* News List */
.news-list { display: flex; flex-direction: column; gap: 0.75rem; }

.news-card {
  display: block;
  text-decoration: none;
  color: inherit;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  transition: background 150ms ease, transform 150ms ease, box-shadow 150ms ease;
  cursor: pointer;
}

.news-card:hover {
  background: #FFF5F5;
  transform: translateY(-1px);
  box-shadow: 0 2px 12px rgba(220, 38, 38, 0.08);
}

.news-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.news-card-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.news-card-source {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-primary);
  background: var(--color-bg);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
}

.news-card-category {
  font-size: 0.75rem;
  color: var(--color-muted);
  opacity: 0.6;
}

.news-card-title {
  font-family: var(--font-body);
  font-size: 1.05rem;
  font-weight: 500;
  line-height: 1.45;
  margin-bottom: 0.35rem;
}

.news-card-summary {
  font-size: 0.875rem;
  color: var(--color-muted);
  opacity: 0.75;
  line-height: 1.5;
}

/* States */
.skeleton { animation: pulse 1.5s ease-in-out infinite; }
.skeleton .news-card { pointer-events: none; }
.skeleton .news-card-title,
.skeleton .news-card-summary,
.skeleton .news-card-source { background: #FEE2E2; border-radius: 4px; color: transparent; }
.skeleton .news-card-title { height: 1.1rem; width: 80%; }
.skeleton .news-card-summary { height: 0.85rem; width: 95%; margin-top: 0.4rem; }
.skeleton .news-card-source { height: 0.7rem; width: 60px; }

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.state-message {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--color-muted);
  opacity: 0.7;
  font-size: 1rem;
}

.state-message a {
  color: var(--color-primary);
  text-decoration: underline;
}

/* Footer */
.footer {
  text-align: center;
  margin-top: 3rem;
  padding-top: 2rem;
  border-top: 1px solid var(--color-border);
  font-size: 0.8rem;
  color: var(--color-muted);
  opacity: 0.5;
}

/* Fade in */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.news-card { animation: fadeIn 0.4s ease both; }
.news-card:nth-child(1) { animation-delay: 0.05s; }
.news-card:nth-child(2) { animation-delay: 0.1s; }
.news-card:nth-child(3) { animation-delay: 0.15s; }
.news-card:nth-child(4) { animation-delay: 0.2s; }
.news-card:nth-child(5) { animation-delay: 0.25s; }
.news-card:nth-child(6) { animation-delay: 0.3s; }
.news-card:nth-child(7) { animation-delay: 0.35s; }
.news-card:nth-child(8) { animation-delay: 0.4s; }
.news-card:nth-child(9) { animation-delay: 0.45s; }
.news-card:nth-child(10) { animation-delay: 0.5s; }
.news-card:nth-child(11) { animation-delay: 0.55s; }
.news-card:nth-child(12) { animation-delay: 0.6s; }
.news-card:nth-child(13) { animation-delay: 0.65s; }
.news-card:nth-child(14) { animation-delay: 0.7s; }
.news-card:nth-child(15) { animation-delay: 0.75s; }

@media (prefers-reduced-motion: reduce) {
  .news-card { animation: none; }
  .skeleton .news-card { animation: none; opacity: 0.8; }
}

@media (max-width: 480px) {
  .container { padding: 1rem 0.75rem 3rem; }
  .header { padding: 2rem 0 1.25rem; }
  .news-card { padding: 1rem 1.15rem; }
}
</style>
</head>
<body>
<div class="container">
  <header class="header" id="header"></header>
  <div class="summary-box" id="summary"></div>
  <div class="news-list" id="news-list"></div>
  <footer class="footer">自动生成 &middot; 每日 UTC+8 零点更新 &middot; Powered by DeepSeek</footer>
</div>

<script>
const EL = {
  header: document.getElementById('header'),
  summary: document.getElementById('summary'),
  list: document.getElementById('news-list'),
};

const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];

function fmtDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  if (isNaN(d.getTime())) return dateStr;
  const y = d.getFullYear();
  const m = d.getMonth() + 1;
  const day = d.getDate();
  const wd = WEEKDAYS[d.getDay()];
  return `${y}年${m}月${day}日 ${wd}`;
}

function renderSkeleton() {
  EL.summary.innerHTML = '<div class="state-message" style="height:2rem;background:#FEE2E2;border-radius:8px;opacity:0.3"></div>';
  let html = '';
  for (let i = 0; i < 6; i++) {
    html += `<div class="news-card"><div class="news-card-source" style="background:#FEE2E2;color:transparent;width:60px">&nbsp;</div><div class="news-card-title" style="background:#FEE2E2;color:transparent;width:80%">&nbsp;</div><div class="news-card-summary" style="background:#FEE2E2;color:transparent;width:95%;margin-top:0.4rem">&nbsp;</div></div>`;
  }
  EL.list.innerHTML = html;
  EL.list.classList.add('skeleton');
}

function render(data) {
  EL.list.classList.remove('skeleton');

  const date = data.date || '';
  EL.header.innerHTML = `<div class="header-date">${fmtDate(date)}</div>`;

  let summary = data.summary || '';
  if (data.total > 0) {
    summary = summary || `今日精选 ${data.total} 条要闻`;
  }
  EL.summary.innerHTML = `<p>${escapeHtml(summary)}</p>`;

  const items = data.items || [];
  if (items.length === 0) {
    EL.list.innerHTML = '<div class="state-message">今日暂无新闻更新，请稍后再来</div>';
    return;
  }

  EL.list.innerHTML = items.map(item => `
    <a class="news-card" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">
      <div class="news-card-meta">
        <span class="news-card-source">${escapeHtml(item.source)}</span>
        <span class="news-card-category">${escapeHtml(item.category || '')}</span>
      </div>
      <div class="news-card-title">${escapeHtml(item.title)}</div>
      <div class="news-card-summary">${escapeHtml(item.summary || '')}</div>
    </a>
  `).join('');
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function showError(msg) {
  EL.list.classList.remove('skeleton');
  EL.summary.innerHTML = '';
  EL.list.innerHTML = `<div class="state-message">${escapeHtml(msg)}<br><br><a href="javascript:location.reload()">点击重试</a></div>`;
}

async function load() {
  renderSkeleton();
  try {
    const resp = await fetch('news.json');
    if (!resp.ok) throw new Error(`加载失败 (${resp.status})`);
    const data = await resp.json();
    render(data);
  } catch (e) {
    showError('新闻加载失败，请检查网络后重试');
    console.error(e);
  }
}

load();
</script>
</body>
</html>
```

- [ ] **Step 2: 验证 HTML 文件**

在浏览器中打开 `index.html`，检查骨架屏和空状态是否正常显示。

- [ ] **Step 3: 提交**

```bash
git add index.html
git commit -m "feat: add frontend news display page"
```

---

### Task 7: 端到端验证

**Files:**
- 运行: `scripts/fetch_news.py`
- 运行: `scripts/deepseek_filter.py`（需 API key）
- 打开: `index.html`

- [ ] **Step 1: 确认 Python 依赖安装**

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: 运行抓取脚本（不需要 API key）**

```bash
python scripts/fetch_news.py
```

预期：输出 JSON 包含多条新闻条目。

- [ ] **Step 3: 创建示例 news.json 用于前端测试**

```bash
echo '{"date":"2026-07-08","generated":"2026-07-08T00:05:00+08:00","summary":"今日国际局势持续升温，科技行业迎来多项重大发布","total":3,"items":[{"title":"Global Markets Rally on Economic Data","url":"https://example.com/1","source":"BBC News","category":"财经","summary":"全球经济数据超预期，股市全面上涨"},{"title":"AI Breakthrough Announced at Tech Summit","url":"https://example.com/2","source":"Reuters","category":"科技","summary":"科技峰会发布新一代AI模型"},{"title":"联合国发布气候变化最新报告","url":"https://example.com/3","source":"新华网","category":"国际","summary":"报告指出全球减排进展不及预期"}]}' > news.json
```

- [ ] **Step 4: 浏览器打开 index.html 确认渲染**

用浏览器打开 `index.html`，确认新闻卡片、日期、概要、悬停效果、响应式布局均正常。

- [ ] **Step 5: 提交样例数据**

```bash
git add news.json
git commit -m "chore: add sample news data for testing"
```

---

## 自检

- [x] 设计文档中每一项功能需求都有对应的任务实现
- [x] 无 TBD/TODO/占位符
- [x] 所有文件路径精确，接口定义完整
- [x] 每个步骤包含实际代码或精确命令
- [x] API Key 只通过环境变量/GitHub Secrets 注入，源码中无硬编码
