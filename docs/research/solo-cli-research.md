# Research: solo CLI — 项目级 Solo Company 工具

> 调研日期: 2026-05-08
> 参考项目: [earendil-works/pi](https://github.com/earendil-works/pi) (v0.74.0, 46k+ stars)
> 研究目标: 设计 `solo` CLI 工具，使每个项目能拥有独立的 Solo Company 自动化体系

---

## 一、参考框架: pi 的核心设计

### 1.1 架构概览

pi 是一个 TypeScript 单体仓库，分 5 个包：

| 包 | 作用 |
|----|------|
| `@earendil-works/pi-ai` | 统一多 provider LLM API（Anthropic, OpenAI, Google, DeepSeek, OpenRouter 等 20+） |
| `@earendil-works/pi-agent-core` | Agent 运行时：tool calling、state management、session 管理 |
| `@earendil-works/pi-coding-agent` | 交互式编码 Agent CLI（bin: `pi`） |
| `@earendil-works/pi-tui` | 终端 UI 库，差分渲染 |
| `@earendil-works/pi-web-ui` | Web Components UI |

### 1.2 CLI 入口

- 入口文件: `packages/coding-agent/src/main.ts`
- `main(process.argv.slice(2))` 解析参数 → 选择运行模式
- 四种模式:
  - **interactive** — TUI 交互模式（默认）
  - **print** — 一次性输出（`pi "写一个排序函数"`）
  - **JSON** — `--json` 结构化输出
  - **RPC** — 进程间通信，用于 SDK 嵌入

### 1.3 配置体系 (三层)

```
~/.pi/settings.json           ← 用户全局配置
~/.pi/auth.json               ← 认证信息（API keys，sub token）
~/.pi/models.json             ← 自定义模型列表
.piplugin                     ← 项目级插件/包配置（在项目目录下）
```

Settings 包含:
- `defaultProvider` / `defaultModel` — 默认模型
- `retry` — 重试策略（最大重试 3 次，指数退避 2s/4s/8s）
- `compaction` — 会话压缩策略（token 上限、保留 tokens）
- `packages` — 加载的插件/包
- `extensions` / `skills` / `prompts` / `themes` — 本地资源路径

### 1.4 Skills 系统

- 存放在 `~/.pi/skills/<name>/SKILL.md`
- 要求: YAML frontmatter（name + description），文件名 = 目录名
- 命名规范: 小写字母、数字、连字符，最长 64 字符
- 支持 `.gitignore` / `.ignore` 忽略规则
- 启动时自动加载到 system prompt

### 1.5 Extensions 系统

- TypeScript 文件，可注册：
  - 自定义工具（Tool）
  - 事件监听（消息开始/结束、工具执行、会话切换）
  - UI 组件（信息行、footer）
  - Slash 命令（`/mycommand`）
- 通过 `.pi/extensions/` 加载项目级 extensions

### 1.6 Prompt Templates

- 目录 `.pi/prompts/` 或 `~/.pi/prompts/`
- YAML frontmatter: `description`, `argument-hint`
- 可通过 `/template-name` slash 命令调用
- pi 自带的模板: `cl.md` (changelog), `is.md` (issue analysis), `pr.md` (PR review), `wr.md` (wrap up)

### 1.7 Provider 架构

- 统一接口: `packages/ai/src/types.ts` 定义 `Api`, `Model`, `Message` 等抽象
- 每个 provider 一个文件: `anthropic.ts`, `openai-responses.ts`, `google.ts`...
- 20+ 内置 provider 支持（AWS Bedrock, Azure, Cloudflare, DeepSeek, Groq, Hugging Face...）
- 通过 `~/.pi/models.json` 可添加自定义 provider

### 1.8 Agent Session 核心循环

`agent-session.ts` 管理:
- Agent 生命周期（初始化、运行、销毁）
- 会话持久化（JSON 文件，支持分支）
- 上下文压缩（compaction 避免超上下文窗口）
- 模型切换 / thinking level 调整
- Turn 循环（用户输入 → Agent 执行 → 工具调用 → 结果回传）

---

## 二、solo CLI 设计要求

### 2.1 核心理念

> **每个项目就是一家公司，.solo/ 就是这家公司的组织架构和运营系统。**
> 不依赖 solo-os 也能完整运行。

### 2.2 CLI 命令设计

```
solo
├── init                          # 初始化 .solo/ 目录
│   ├── (默认交互式问答)
│   ├── --template <name>         # 从模板初始化（react, py, ts...）
│   └── --yes                     # 全默认快速初始化
│
├── start                         # 进入交互式 CLI
│   ├── (默认模式) CEO ↔ Secretary
│   ├── --os                      # 进入 OS 模式（管理多项目）
│   └── --json                    # 一次性任务模式
│
├── status                        # 查看当前项目任务状态
│   ├── (默认) 最近任务摘要
│   └── --all                     # 所有历史任务
│
├── list                          # 扫描所有含 .solo/ 的项目
│
├── config                        # 查看/修改 .solo/ 配置
│   ├── get <key>
│   ├── set <key> <value>
│   └── edit                      # 打开编辑器
│
├── dispatch                      # 直接派任务（无需交互模式）
│   └── solo dispatch --to cto "审查这个PR"
│
├── project                       # 操作关联项目
│   └── solo project add <path>   # 添加关联项目
│
├── version / -v
└── help / -h
```

### 2.3 目录结构

```
my-project/
├── .solo/
│   ├── config.yaml               # 核心配置
│   ├── agents/                   # Agent 角色定义
│   │   ├── secretary.md
│   │   ├── cto.md
│   │   ├── cpo.md
│   │   ├── dev.md
│   │   ├── qa.md
│   │   ├── growth.md
│   │   └── analyst.md
│   ├── state/                    # 状态持久化
│   │   ├── tasks.json
│   │   └── sessions/
│   ├── workflows/                # 自定义 SOP
│   │   ├── bugfix.md
│   │   ├── feature.md
│   │   └── release.md
│   ├── prompts/                  # Prompt 模板（类似 pi 的 /template）
│   └── hooks/                    # Git hooks / 生命周期钩子
│       ├── pre-commit
│       └── post-merge
│
├── .soloignore                   # 可选：排除文件
└── solo                          # CLI 入口 shell 脚本
```

### 2.4 配置设计

```yaml
# .solo/config.yaml
project:
  name: social-hotspot-daily
  description: "热点追踪与数据仪表盘"
  version: 0.1.0
  repo: https://github.com/NoahStransky/social-hotspot-daily

# 模型配置（按角色路由）
agents:
  secretary:
    provider: openai
    model: gpt-4o
    temperature: 0.3
  cto:
    provider: anthropic
    model: claude-opus-4
    temperature: 0.2
    max_tokens: 64000
  cpo:
    provider: anthropic
    model: claude-opus-4
    temperature: 0.3
  dev:
    provider: anthropic
    model: claude-sonnet-4
    temperature: 0.1
    max_tokens: 32000
  qa:
    provider: openai
    model: gpt-4o-mini
    temperature: 0.1
    max_tokens: 16000
  growth:
    provider: openai
    model: gpt-4o
    temperature: 0.7
  analyst:
    provider: anthropic
    model: claude-opus-4
    temperature: 0.2

# 任务调度配置
delegation:
  max_parallel: 3
  timeout: 300
  max_retries: 3

# 工作流默认流程
default_workflow:
  - cpo       # Phase 1: 产品需求
  - cto       # Phase 2: 架构设计
  - ceo_check # Phase 2.5: CEO确认
  - dev       # Phase 3: 开发（并行）
  - qa        # Phase 4: QA验证
  - cto_review # Phase 5: 代码审查
  - merge     # Phase 6: 合并发布
  - growth    # Phase 7: 增长（可与Dev并行，但在此列出以确认顺序）

# 项目关联（供 solo-os 使用）
related_projects:
  - path: ../auth-service
    name: auth-service
  - path: ../api-gateway
    name: api-gateway
```

### 2.5 交互式 CLI 模式 (solo start)

借鉴 pi 的 TUI + Hermes 的会话模式：

```
$ solo start

  ╔══════════════════════════════════════════╗
  ║    Solo Company — social-hotspot-daily   ║
  ║    CEO: Noah  |  Secretary: Ready        ║
  ╚══════════════════════════════════════════╝

  [CTO: ready] [CPO: ready] [Dev: ready] [QA: ready]

  你 > 帮我把RSS订阅功能做出来

  秘书 > 好的，我先调度 CPO 出需求文档...

  ┌─ CPO Output ─────────────────────────────┐
  │ PRD: RSS Subscription Feature            │
  │ User Stories:                            │
  │  - 作为读者，我想订阅博客的RSS            │
  │  - 作为管理员，我想管理订阅源              │
  │  ...                                     │
  └──────────────────────────────────────────┘

  你 > 可以，继续

  秘书 > 调度 CTO 做架构设计...
```

### 2.6 与 pi 的关键区别

| 对比维度 | pi | solo |
|---------|----|------|
| **角色** | 1个编码 Agent | 多个 Agent 组成公司（CEO→Sec→CTO/Dev/QA...） |
| **工作流** | 对话式编码 | **SOP 驱动**: PRD → 架构 → 开发 → QA → 增长 |
| **模型策略** | 手动 /provider 切换 | **按角色自动路由**（CTO 最强，QA 最便宜） |
| **状态** | 单会话 | 任务状态持久化，可追踪多任务并行 |
| **多项目** | 无原生支持 | `related_projects` + solo-os 跨项目编排 |
| **部署** | npm 全局包 | pip install，项目级 `solo` 入口脚本也可独立分发 |

### 2.7 借鉴 pi 的设计

| pi 的好设计 | solo 如何借鉴 |
|-----------|--------------|
| 三层配置（global + user + project） | `~/.solo/` 全局 + 项目 `.solo/` 局部覆盖 |
| Skills 系统（可插拔 prompt） | `agents/*.md` 是内置 Skills，Projects 可自定义 |
| Prompt Templates（/command） | `prompts/` 目录，如 `/pr-review`, `/bugfix` |
| Extensions 系统 | 未来支持 Python 插件（自定义工具、事件监听） |
| Session 持久化 + 分支 | `state/sessions/` JSON 文件 |
| 多 provider 统一接口 | `ModelRouter.resolve(agent_name)` 已有，需包装成 provider 统一层 |
| 轻量 CLI（不依赖大型框架） | 最小依赖，Python stdlib + click/rich |

---

## 三、实现建议

### 3.1 技术选型

- **语言**: Python（与现有 `agent_orchestrator.py`、`model_router.py` 一致）
- **CLI 框架**: [Click](https://click.palletsprojects.com/)（命令分组 + 参数解析）或 [Typer](https://typer.tiangolo.com/)（更现代）
- **终端 UI**: [Rich](https://rich.readthedocs.io/)（markdown 渲染、面板、进度条）
- **交互式循环**: [prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/)（历史、自动补全、多行输入）
- **YAML**: PyYAML / ruamel.yaml
- **发布**: PyPI (`pip install solo-company-cli`)

### 3.2 包结构

```
solo-company-cli/
├── pyproject.toml
├── src/
│   ├── solo/
│   │   ├── __init__.py
│   │   ├── __main__.py           # python -m solo 入口
│   │   ├── cli.py                # Click/Typer 命令分组
│   │   ├── commands/
│   │   │   ├── init.py           # solo init
│   │   │   ├── start.py          # solo start（交互模式）
│   │   │   ├── status.py         # solo status
│   │   │   ├── list.py           # solo list
│   │   │   ├── config.py         # solo config
│   │   │   └── dispatch.py       # solo dispatch
│   │   ├── core/
│   │   │   ├── project.py        # Project 类：.solo/ 加载/保存
│   │   │   ├── config.py         # Config 加载/验证/合并
│   │   │   ├── secretary.py      # Secretary Agent 逻辑
│   │   │   ├── model_router.py   # 模型路由（复用现有）
│   │   │   └── state.py          # 任务状态持久化
│   │   ├── templates/            # init 模板
│   │   │   ├── default/
│   │   │   ├── react/
│   │   │   └── py-lib/
│   │   └── utils/
│   │       ├── ui.py             # Rich 组件
│   │       └── git.py            # git 操作工具
```

### 3.3 路线图

| 阶段 | 功能 | 优先级 |
|------|------|--------|
| **P0** | `solo init` → 生成 `.solo/config.yaml` + agent prompts | 🚀 MVP |
| **P0** | `solo start` → 简单的交互模式，对接现有 Secretary + Model Router | 🚀 MVP |
| **P1** | `solo status` → 任务状态查看 | ⭐ |
| **P1** | 完善交互模式：Rich UI、markdown 渲染、命令历史 | ⭐ |
| **P2** | `solo list` → 扫描多项目 | ✅ |
| **P2** | `solo config` → 配置管理 | ✅ |
| **P3** | Templates 系统（`solo init --template`） | 🌟 |
| **P3** | Prompt Templates（类似 pi 的 `/command`） | 🌟 |
| **P4** | Extensions 插件系统 | 🔮 |
| **P4** | PyPI 发布 + 自动更新 | 🔮 |

---

## 四、风险和注意事项

1. **`delegate_task` 300s 超时问题** — solo CLI 内部会大量使用 delegate_task（每个 Agent 角色都是独立子任务）。需要实现超时检测 + 幽灵完成检查 + 自动重试。
2. **solo-os 依赖发现问题** — solo 的 `related_projects` 配置是 solo-os 调度的基础，但 solo 本身不依赖 solo-os。
3. **config 与 pi 的兼容性** — 用户可能同时用 pi 和 solo，注意避免 `.pi/` 和 `.solo/` 配置冲突（使用不同目录名即可避免）。
4. **多 provider API key 管理** — 类似 pi 的 `auth.json`，solo 需要安全存储不同 provider 的 API keys。
