# 每日新闻速览 - 设计文档

**日期**: 2026-07-08
**状态**: 设计完成

---

## 1. 概述

一个每日新闻摘要 Web 应用。每天 UTC+8 零点自动从多个中英文新闻源抓取约 30 条头条，通过 DeepSeek V4 Flash API 筛选出 10-15 条一周内的有效新闻，呈现在简洁美观的网页上。

## 2. 架构

```
GitHub Actions (schedule: cron 0 16 * * *)  ← UTC+8 00:00
  │
  ├─ checkout repo
  ├─ setup Python
  ├─ fetch_news.py
  │   ├─ 抓取 RSS feeds (8-10个中英文源)
  │   ├─ 网页抓取补充 (无RSS的源)
  │   └─ 去重、整理 ~30条
  ├─ deepseek_filter.py
  │   ├─ 调用 DeepSeek V4 Flash API
  │   ├─ 筛选一周内新闻
  │   ├─ 生成中文摘要
  │   └─ 输出 news.json (10-15条)
  ├─ commit & push news.json
  └─ GitHub Pages 自动部署

用户访问 → index.html → 加载 news.json → 渲染页面
```

## 3. 技术选型

| 层级 | 技术 | 理由 |
|------|------|------|
| 抓取脚本 | Python + feedparser + httpx | RSS 解析成熟，请求高效 |
| AI 筛选 | DeepSeek V4 Flash API | 用户指定，新 session 每次独立 |
| 前端 | 纯 HTML/CSS/JS（单文件） | 零依赖，GitHub Pages 直接托管 |
| CI/CD | GitHub Actions + Pages | 免费，自动化 |
| 密钥管理 | GitHub Secrets | API key 不入仓库 |

## 4. 数据流

```
RSS源列表 (配置文件) → fetch_news.py → [{title, url, source, date}]
    → DeepSeek API → news.json
    → index.html → 用户浏览器
```

### news.json 结构
```json
{
  "date": "2026-07-08",
  "generated": "2026-07-08T00:05:00+08:00",
  "summary": "今日要点一句话概述...",
  "total": 12,
  "items": [
    {
      "title": "新闻标题",
      "url": "https://...",
      "source": "BBC News",
      "category": "国际",
      "summary": "DeepSeek 生成的一句话中文摘要",
      "time": "2026-07-07T14:30:00Z"
    }
  ]
}
```

## 5. 新闻源配置

### 英文源（RSS）
| 源 | URL |
|---|-----|
| BBC News | feeds.bbci.co.uk/news/rss.xml |
| Reuters | reuters.com/arc/outboundfeeds/v3/all/... |
| CNN | edition.cnn.com/services/rss/ |
| The Guardian | theguardian.com/world/rss |

### 中文源（RSS + 抓取）
| 源 | 方式 |
|---|------|
| 新华网 | RSS |
| 环球时报 | RSS |
| 澎湃新闻 | 网页抓取 |
| 36氪 | RSS |

## 6. DeepSeek API 调用

```
System: 你是一个新闻编辑。请从以下头条列表中筛选出发布日期在一周内的新闻条目，排除明显过时或日期错误的内容。为每条保留的新闻写一句中文摘要（20字以内）。返回 JSON 格式。

User: [30条新闻标题+链接+来源]

Response: {
  "summary": "今日要点...",
  "items": [...最多15条]
}
```

**安全**：API Key 通过 `DEEPSEEK_API_KEY` 环境变量注入，仅存在于 GitHub Secrets，构建时写入 workflow 环境。

## 7. 前端设计

### 设计系统（UI/UX Pro Max 推荐）

| 维度 | 值 |
|------|-----|
| 风格 | Exaggerated Minimalism |
| 布局 | 极简单栏，移动优先 |
| 动效 | Subtle (2/10) - 仅淡入 |
| 密度 | Spacious (3/10) - 宽松留白 |

### 配色
| 角色 | 色值 |
|------|------|
| 主色 | #DC2626 |
| 背景 | #FEF2F2 |
| 前景文字 | #450A0A |
| 卡片背景 | #FFFFFF |
| 分隔线 | #FECACA |
| 辅助文字 | #991B1B (60% opacity) |

### 字体
- **标题/日期**: Newsreader (serif, Google Fonts)
- **正文**: Roboto (sans-serif, Google Fonts)

### 页面结构
```
┌──────────────────────────────┐
│        2026年7月8日           │  ← 大日期标题 (Newsreader)
│        星期四                 │
│                              │
│    今日要闻 (一句话概述)       │  ← AI 生成的 summary
├──────────────────────────────┤
│  ┌────────────────────────┐  │
│  │ 🔴 BBC News    2h ago │  │  ← 来源标签 + 时间
│  │ 新闻标题，字号较大      │  │
│  │ AI 生成的一句话摘要     │  │
│  └────────────────────────┘  │
│  ┌────────────────────────┐  │
│  │ ...下一条...           │  │
│  └────────────────────────┘  │
│         ...共 12 条          │
├──────────────────────────────┤
│    自动生成 · 每日 UTC+8     │  ← 页脚
└──────────────────────────────┘
```

### 响应式
- **Mobile (< 768px)**：全宽单栏，卡片 padding 减小
- **Tablet/Desktop (≥ 768px)**：居中最大宽 720px

### 交互
- 新闻卡片可点击跳转原文（新标签页）
- 悬停微动效（背景色变化 150ms）
- 首次加载淡入动画

## 8. GitHub Pages 部署

- 分支：`gh-pages`（由 Action 自动维护）
- 源文件：`index.html` + `news.json` + `assets/`
- 无需构建步骤，纯静态文件

## 9. 项目结构

```
/
├── .github/
│   └── workflows/
│       └── daily-news.yml       # 定时抓取工作流
├── scripts/
│   ├── fetch_news.py            # RSS + 网页抓取
│   ├── deepseek_filter.py       # AI 筛选
│   └── sources.json             # 新闻源配置
├── index.html                   # 前端页面
├── assets/
│   └── styles.css               # 样式（或内联于 HTML）
├── news.json                    # 每日生成的数据文件
└── .gitignore
```

## 10. 安全

- API Key 仅存在于 GitHub Secrets (`DEEPSEEK_API_KEY`)
- `news.json` 中不包含任何密钥信息
- `.gitignore` 忽略本地 `.env` 文件
- HTTPS 由 GitHub Pages 默认提供

---

## 自检清单

- [x] 无 TBD/占位符
- [x] 架构与功能描述一致
- [x] 范围明确，可单次实现
- [x] 需求无歧义
