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

### 2.2 设计边界

`solo` 是 **单项目运行层**，负责一个 repo 内部的 Agent 组织、任务状态、执行包、工作流和模型路由。

`solo-os` 是另一个独立项目里的 **多项目控制层**，负责注册多个已初始化的 `.solo/` 项目、聚合状态、跨项目调度和 Dashboard。当前 `solo` 项目不内置多项目 Dashboard，也不承担全局项目注册。

因此 `solo` 的首要交付物不是花哨的 TUI，而是稳定的 `.solo/` 文件协议：

```
.solo/
├── config.yaml               # 项目元信息、Agent 模型配置、默认 workflow
├── agents/                   # 角色 prompt
├── workflows/                # feature / bugfix / release 等 SOP
├── state/
│   ├── tasks.json            # 当前任务快照，供 solo status 和 solo-os 读取
│   ├── events.jsonl          # 追加式事件日志，供 Dashboard/审计读取
│   └── sessions/             # 未来交互式会话记录
├── artifacts/                # 每个任务的阶段产物
└── contracts/                # 可选：跨项目接口契约，主要供 solo-os 使用
```

核心原则：

- `solo` 可以被单独安装和使用。
- `.solo/` 是 `solo-os` 读取项目状态的稳定协议。
- `solo-os` 不应 import `solo` 内部 Python 类；优先通过文件协议和 `solo ... --json` 命令交互。
- 当前项目不实现 Web Dashboard；Dashboard 属于独立的 `solo-os` 项目。

### 2.3 CLI 命令设计

```
solo
├── init                          # 初始化 .solo/ 目录
│   ├── (默认交互式问答)
│   ├── --template <name>         # 后续：从模板初始化（react, py, ts...）
│   └── --yes                     # 全默认快速初始化
│
├── status                        # 查看当前项目任务状态
│   ├── (默认) 最近任务摘要
│   ├── --all                     # 所有历史任务
│   └── --json                    # 给 solo-os / 其他工具消费
│
├── dispatch                      # 直接派任务（无需交互模式）
│   ├── solo dispatch --to cto "审查这个PR"
│   ├── --workflow feature        # 按 SOP 创建任务
│   └── --json                    # 输出结构化结果
│
├── start                         # 进入单项目交互式 CLI（薄壳，复用 dispatch/status）
│   └── (默认模式) CEO ↔ Secretary
│
├── config                        # 后续：查看/修改 .solo/ 配置
│   ├── get <key>
│   ├── set <key> <value>
│   └── edit
│
├── version / -v
└── help / -h
```

不放进 `solo` 的命令：

- `solo list` / `solo project add`：属于 `solo-os` 的项目注册与扫描。
- `solo start --os`：属于独立 `solo-os start`。
- Web Dashboard：属于独立 `solo-os dashboard`。

### 2.4 目录结构

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
│   │   ├── events.jsonl
│   │   └── sessions/
│   ├── artifacts/                # 任务阶段产物
│   │   └── TASK-20260508-001/
│   │       ├── cpo.md
│   │       ├── cto.md
│   │       ├── dev.md
│   │       ├── qa.md
│   │       └── report.md
│   ├── workflows/                # 自定义 SOP
│   │   ├── bugfix.md
│   │   ├── feature.md
│   │   └── release.md
│   ├── prompts/                  # Prompt 模板（类似 pi 的 /template）
│   ├── contracts/                # 可选：跨项目契约，供 solo-os 使用
│   └── hooks/                    # Git hooks / 生命周期钩子
│       ├── pre-commit
│       └── post-merge
│
└── .soloignore                   # 可选：排除文件
```

### 2.5 配置设计

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

# 协议版本：给 future migration 和 solo-os 兼容性检测使用
solo_protocol_version: 1
```

`related_projects` 不放进单项目 `solo` 的核心配置。跨项目注册由独立的 `solo-os` 在 `~/.solo-os/projects.yaml` 维护。

### 2.6 状态协议

`solo status --json` 和 `solo-os dashboard` 都应该从 `.solo/state/tasks.json` 与 `.solo/state/events.jsonl` 读取状态。

建议任务快照结构：

```json
{
  "tasks": [
    {
      "id": "TASK-20260508-001",
      "title": "RSS 订阅功能",
      "status": "in_progress",
      "workflow": "feature",
      "current_phase": "dev",
      "phases": [
        {"name": "cto", "status": "completed"},
        {"name": "dev", "status": "in_progress"},
        {"name": "qa", "status": "pending"}
      ],
      "created_at": "2026-05-08T10:00:00+10:00",
      "updated_at": "2026-05-08T10:42:00+10:00"
    }
  ]
}
```

事件日志采用追加式 JSONL，避免并发写入时覆盖完整状态：

```jsonl
{"ts":"2026-05-08T10:00:00+10:00","task_id":"TASK-20260508-001","event":"task.created","phase":"secretary"}
{"ts":"2026-05-08T10:10:00+10:00","task_id":"TASK-20260508-001","event":"phase.started","phase":"dev"}
```

### 2.7 交互式 CLI 模式 (solo start)

`solo start` 是单项目交互入口。第一版应做成 `dispatch/status` 的薄壳，而不是重新实现一套完整运行时。

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

### 2.8 与 pi 的关键区别

| 对比维度 | pi | solo |
|---------|----|------|
| **角色** | 1个编码 Agent | 多个 Agent 组成公司（CEO→Sec→CTO/Dev/QA...） |
| **工作流** | 对话式编码 | **SOP 驱动**: PRD → 架构 → 开发 → QA → 增长 |
| **模型策略** | 手动 /provider 切换 | **按角色自动路由**（CTO 最强，QA 最便宜） |
| **状态** | 单会话 | 任务状态持久化，可追踪多任务并行 |
| **多项目** | 无原生支持 | 不在 solo 内实现；交给独立 `solo-os` |
| **部署** | npm 全局包 | pip install，项目级 `solo` 入口脚本也可独立分发 |

### 2.9 借鉴 pi 的设计

| pi 的好设计 | solo 如何借鉴 |
|-----------|--------------|
| 三层配置（global + user + project） | 后续可支持 `~/.solo/` 全局 + 项目 `.solo/` 局部覆盖；MVP 先以项目 `.solo/` 为准 |
| Skills 系统（可插拔 prompt） | `agents/*.md` 是内置 Skills，Projects 可自定义 |
| Prompt Templates（/command） | `prompts/` 目录，如 `/pr-review`, `/bugfix` |
| Extensions 系统 | 未来支持 Python 插件（自定义工具、事件监听） |
| Session 持久化 + 分支 | `state/sessions/` JSON 文件 |
| 多 provider 统一接口 | `ModelRouter.resolve(agent_name)` 已有，需包装成 provider 统一层 |
| 轻量 CLI（不依赖大型框架） | 最小依赖，Python stdlib + click/rich |

---

## 三、实现建议

### 3.1 技术选型

- **语言**: Python（适合快速实现 CLI、文件协议和本地编排）
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
│   │   │   ├── status.py         # solo status
│   │   │   ├── dispatch.py       # solo dispatch
│   │   │   ├── start.py          # solo start（交互模式）
│   │   │   ├── config.py         # solo config
│   │   ├── core/
│   │   │   ├── project.py        # Project 类：.solo/ 加载/保存
│   │   │   ├── config.py         # Config 加载/验证/合并
│   │   │   ├── state.py          # 任务状态持久化 + events.jsonl
│   │   │   ├── workflow.py       # SOP 加载/阶段定义
│   │   │   ├── agent_registry.py # Agent prompt 注册
│   │   │   ├── secretary.py      # Secretary 任务生命周期
│   │   │   ├── dispatcher.py     # 执行包/外部 runtime 适配
│   │   │   ├── model_router.py   # 模型路由
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
| **P0** | `.solo/state/tasks.json` + `events.jsonl` 状态协议 | 🚀 MVP |
| **P0** | `solo dispatch` → 创建任务、生成 Agent 执行包、推进状态 | 🚀 MVP |
| **P0** | `solo status --json` → 给本项目和未来 solo-os 消费 | 🚀 MVP |
| **P1** | `solo start` → 简单交互壳，复用 dispatch/status | ⭐ |
| **P1** | 外部执行适配器（Hermes/Codex/Claude Code） | ⭐ |
| **P2** | `solo config` → 配置管理 | ✅ |
| **P2** | 内置模板扩展（`solo init --template`） | ✅ |
| **P3** | Prompt Templates（类似 pi 的 `/command`） | 🌟 |
| **P4** | Extensions 插件系统 | 🔮 |
| **P4** | PyPI 发布 + 自动更新 | 🔮 |

---

## 四、风险和注意事项

1. **执行层不确定** — MVP 应先把 `dispatch` 定义为“生成执行包 + 状态流转”，把 Hermes/Codex/Claude Code 作为可插拔执行适配器。
2. **状态协议稳定性** — `solo-os` 未来会读取 `.solo/state/tasks.json` 和 `events.jsonl`。字段命名、状态枚举、协议版本要从第一版就控制住。
3. **并发写入** — `solo start`、`solo dispatch`、未来 `solo-os dispatch` 可能同时改状态。需要文件锁或事件日志优先的合并策略。
4. **config 与 pi 的兼容性** — 用户可能同时用 pi 和 solo，注意避免 `.pi/` 和 `.solo/` 配置冲突（使用不同目录名即可避免）。
5. **多 provider API key 管理** — 类似 pi 的 `auth.json`，solo 需要安全存储不同 provider 的 API keys；MVP 可以先只读环境变量。

---

## 五、2026-05-13 追加研究: runtime orchestration 下一层

当前代码已经完成 `.solo/` 协议、执行包、runtime profile、durable mailbox、结构化 artifact 回流和 Docker 测试环境。下一步不应该直接写 Hermes/Codex/Claude Code 专用 adapter，而应该把“如何运行一个 phase、如何恢复失败、如何推进到目标 phase”抽成稳定的 orchestration 层。

### 5.1 当前实现的能力边界

已具备：

- `solo dispatch` 创建 task，并生成当前 phase 的 package。
- `solo complete` / `solo run --once` 可推进一个 phase。
- `package` adapter 负责生成 instruction/input。
- `command` adapter 可调用外部 wrapper。
- agent pool 已生成 per-instance package：`dev-1_input.json`、`dev-1_instruction.md` 等。
- mailbox 已能按实例路由：`cto -> dev-1/dev-2`、`dev-1/dev-2 -> qa`。
- runtime returncode 非 0 时，phase/task 会进入 `failed`。

尚未具备：

- `solo run --until <phase|blocked|done>` 的循环推进。
- `solo retry --phase`、`solo retry --agent`、`solo reopen --phase` 的恢复语义。
- 真正并行执行 agent pool；当前 command adapter 是逐个 instance 调用。
- agent pool 的部分失败语义；当前 phase 失败时会把该 phase 下所有 agent instance 标为 failed，不利于只重试失败 agent。

### 5.2 建议抽出的核心概念

应新增一个 core 层，比如 `solo.core.runner`，把命令层从状态推进细节中解耦出来：

| 概念 | 责任 |
|------|------|
| `PhaseRunner` | 运行或准备当前 phase，调用 adapter，写 runtime details |
| `PhaseAdvancer` | 完成当前 phase、选择下一 phase、处理 optional human gate |
| `RecoveryService` | reopen/retry phase 或 agent instance，写恢复事件 |
| `RunLoop` | 实现 `run --once` / `run --until` / stop condition |

这样命令层只负责参数解析和 JSON/text 输出，`complete_cmd.py` 不会继续变成所有生命周期逻辑的中心。

### 5.3 run-until 的语义建议

`solo run --until` 应支持三类目标：

| 目标 | 停止条件 |
|------|----------|
| `<phase>` | task.current_phase 等于目标 phase，且目标 phase 已准备好 |
| `blocked` | 任一 phase/runtime 失败，task.status 为 `failed` |
| `done` | task.status 为 `completed` |

输出建议：

```json
{
  "task": {},
  "stopped_reason": "reached_phase | failed | completed | no_progress",
  "completed_phases": ["cto_breakdown", "dev_pool"],
  "failed_phase": "",
  "last_package": {}
}
```

`run --once` 可以成为 `run --until` 的一个特例：最多推进一次。

### 5.4 retry / reopen 的语义建议

`reopen` 和 `retry` 要分开：

| 命令 | 是否运行 runtime | 状态效果 |
|------|------------------|----------|
| `solo reopen --phase dev_pool` | 否 | 把 failed phase 和对应 instances 重置为 `in_progress`，task 回到该 phase |
| `solo retry --phase dev_pool` | 是 | reopen 后立即重新运行该 phase；成功则推进下一 phase |
| `solo retry --agent dev-1` | 是 | 只重跑目标 agent instance，不重跑同 phase 的成功 instance |

事件建议：

- `phase.reopened`
- `phase.retried`
- `agent.retried`
- `agent.completed`
- `agent.failed`

### 5.5 agent pool 并行执行建议

第一版并行不要引入复杂队列，使用 bounded thread pool 即可：

- 并发上限来自 `delegation.max_parallel_dev_agents`。
- 每个 agent instance 独立调用 command runtime。
- 每个 instance 写自己的 `<agent_id>_runtime.json`。
- phase aggregate runtime 写 `<phase>_runtime.json`。
- phase 是否失败取决于任一 required instance 失败。
- instance status 必须按自身 returncode 更新，不能一刀切。

这会让 `solo-os` dashboard 能看到具体是 `dev-1` 失败还是整个 phase 失败，也为后续 `retry --agent dev-1` 提供状态基础。

### 5.6 下一步推荐顺序

1. 先抽 `PhaseRunner` / `RunLoop`，保持现有测试通过。
2. 实现 `solo run --until`，让已有 strict xfail 测试转正。
3. 实现 `solo reopen --phase`。
4. 实现 `solo retry --phase`。
5. 实现 agent pool 部分失败状态。
6. 实现 `solo retry --agent`。
7. 最后再把 agent pool command runtime 改成 bounded parallel execution。

这个顺序的好处是每一步都有明确测试边界，而且不会先引入真正并发导致调试面扩大。
