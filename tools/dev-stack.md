# 🛠️ 开发工具栈推荐 — Solo Developer

> 一人公司选择工具的原则：**托管优先、自动化、低运维负担**

## 🏗️ 全栈开发

### 前端

| 层级 | 推荐 | 备选 | 理由 |
|------|------|------|------|
| 框架 | **React 18** + TypeScript | Vue 3, Svelte | 生态最大，招人容易 |
| 样式 | **Tailwind CSS** | Chakra UI, shadcn | 写样式最快 |
| 状态 | **Zustand** | Redux Toolkit, Jotai | 简单够用 |
| 构建 | **Vite** | Next.js (如需 SSR) | 秒级启动 |
| UI 组件 | **shadcn/ui** | Ant Design, Material UI | 可复制源码，无依赖 |

### 后端

| 层级 | 推荐 | 备选 | 理由 |
|------|------|------|------|
| 语言 | **Python 3.11+** | Node.js, Go | AI 生态最好 |
| 框架 | **FastAPI** | Django, Flask | 自动文档，异步原生 |
| 数据库 | **PostgreSQL** | SQLite (早期), MySQL | 可靠，功能全 |
| ORM | **SQLAlchemy 2.0** | Prisma, Django ORM | 灵活强大 |
| 缓存 | **Redis** | — | 通用，队列也可用 |
| 任务队列 | **Celery + Redis** | RQ, APScheduler | 成熟稳定 |
| API 文档 | **FastAPI 自动生成** | — | 零成本 |

### AI / LLM

| 用途 | 推荐 | 备注 |
|------|------|------|
| 通用 LLM | **OpenRouter** | 一个 key 调所有模型 |
| 图像生成 | **fal.ai** / Replicate | API 简单 |
| 向量数据库 | **Pinecone** (免费层) | pgvector (自建) |
| Embedding | **OpenAI text-embedding** | 或开源模型 |

---

## ☁️ 基础设施（托管优先）

| 服务 | 推荐 | 费用 | 为什么 |
|------|------|------|--------|
| 前端托管 | **Vercel** | 免费 | 自动部署，全球 CDN |
| 后端托管 | **Railway** / Render | 免费起步 | 零配置部署 |
| 数据库 | **Supabase** | 免费 500MB | 托管 Postgres |
| 文件存储 | **Cloudflare R2** | 免费 10GB | S3 兼容，无出口费 |
| 域名 | **Cloudflare** | 成本价 | DNS + CDN + 安全 |
| 监控 | **Sentry** | 免费 5k 事件 | 错误追踪 |
|  uptime | **UptimeRobot** | 免费 50 监控 | 宕机告警 |
| 日志 | **Better Stack** | 免费 1GB/月 | 集中日志 |

---

## 🧪 开发环境

| 工具 | 推荐 | 用途 |
|------|------|------|
| IDE | **Cursor** / VS Code | AI 辅助编程 |
| Terminal | **Warp** / iTerm2 | 现代终端 |
| API 测试 | **HTTPie** / Postman | API 调试 |
| 数据库 GUI | **TablePlus** / Beekeeper | 可视化操作 |
| Git | **GitHub Desktop** / CLI | 版本控制 |
| 笔记 | **Obsidian** | 知识管理 |
| 任务管理 | **Linear** / GitHub Issues | 项目管理 |

---

## 📦 推荐的项目脚手架

```bash
# Python 后端
mkdir myproject && cd myproject
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn sqlalchemy alembic pydantic-settings

# 前端（Vite + React + TS）
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install zustand react-router-dom
```

---

## 💰 一人公司月度基础设施预算参考

| 阶段 | 用户量 | 月度成本 | 配置 |
|------|--------|---------|------|
| MVP | 0-100 | **$0-5** | Vercel + Railway + Supabase 免费层 |
| 起步 | 100-1000 | **$20-50** | Vercel Pro + Railway + Supabase Pro |
| 成长 | 1k-10k | **$100-300** | 升级数据库 + CDN + Sentry |
| 盈利 | 10k+ | **$500+** | 根据收入比例投入 |

> 💡 **原则**：在盈利前，尽可能用免费层。不要预优化。
