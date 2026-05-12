# Planning: solo CLI — 单项目 Solo Company 运行层

> 基于: `docs/research/solo-cli-research.md`
> 关联: `docs/research/solo-os-research.md`
> 目标: 先交付一个可运行、可观测、可被未来 solo-os 管理的单项目 CLI

---

## 一、定位

`solo` 是单项目运行层。它负责把一个 repo 初始化成一家公司式的 Agent 工作空间：

- `.solo/config.yaml` 保存项目元信息、Agent 模型配置、默认 workflow。
- `.solo/agents/` 保存角色 prompt。
- `.solo/workflows/` 保存 feature / bugfix / release 等 SOP。
- `.solo/state/` 保存任务快照和事件日志。
- `.solo/artifacts/` 保存每个任务各阶段产物。

`solo-os` 不在当前项目内实现。它会在另一个项目里作为 control plane，读取多个项目的 `.solo/` 协议并生成 Dashboard。

关键原则：

- 当前 `solo` 项目只管理当前 repo。
- `.solo/` 是稳定文件协议，不只是内部缓存。
- `solo-os` 未来通过 `.solo/` 文件和 `solo ... --json` 命令交互，不 import `solo.core.*`。
- 第一版先做 `init -> dispatch -> status` 闭环，`start` 是薄交互层。

---

## 二、MVP 范围

### MVP 包含

| 功能 | 说明 |
|------|------|
| `solo init` | 在当前目录生成 `.solo/` 协议目录 |
| `solo dispatch` | 创建任务、选择 workflow、生成 Agent 执行包、推进状态 |
| `solo status` | 展示当前项目任务状态，支持 `--json` |
| `.solo/config.yaml` | 项目信息、Agent 模型配置、协议版本 |
| `.solo/state/tasks.json` | 当前任务快照 |
| `.solo/state/events.jsonl` | 追加式事件日志 |
| `.solo/state/messages.jsonl` | Agent 间 durable mailbox |
| `.solo/artifacts/<task_id>/` | 每个任务的阶段输入、输出和报告 |

### MVP 不包含

- Web Dashboard：属于独立 `solo-os` 项目。
- 多项目扫描和注册：属于 `solo-os project add/list/scan`。
- `solo start --os`：不做，入口应是 `solo-os start`。
- 自动真实执行所有 Agent：MVP 先生成执行包和状态流转，真实执行层做成 adapter。
- 用户自定义模板市场：MVP 只内置 default 模板。
- Extensions 插件系统。

---

## 三、目标目录结构

### 当前仓库结构

```text
solo-company-architecture/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── README.md
├── src/
│   └── solo/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── commands/
│       │   ├── init_cmd.py
│       │   ├── dispatch_cmd.py
│       │   ├── complete_cmd.py
│       │   ├── status_cmd.py
│       │   └── start_cmd.py
│       ├── core/
│       │   ├── config.py
│       │   ├── project.py
│       │   ├── state.py
│       │   ├── task.py
│       │   ├── workflow.py
│       │   ├── agent_registry.py
│       │   ├── model_router.py
│       │   ├── secretary.py
│       │   └── dispatcher.py
│       ├── templates/
│       │   └── default/
│       │       ├── config.yaml
│       │       ├── agents/
│       │       ├── skills/
│       │       └── workflows/
│       └── utils/
│           ├── ui.py
│           └── ui.py
└── tests/
    └── test_solo/
```

### `solo init` 后的业务项目结构

```text
my-project/
├── .solo/
│   ├── config.yaml
│   ├── agents/
│   │   ├── secretary.md
│   │   ├── cpo.md
│   │   ├── cto.md
│   │   ├── dev.md
│   │   ├── qa.md
│   │   ├── growth.md
│   │   └── analyst.md
│   ├── workflows/
│   │   ├── feature.yaml
│   │   ├── bugfix.yaml
│   │   └── release.yaml
│   ├── state/
│   │   ├── tasks.json
│   │   ├── events.jsonl
│   │   ├── messages.jsonl
│   │   └── sessions/
│   ├── artifacts/
│   └── contracts/
└── .soloignore
```

---

## 四、`.solo/` 协议

### `.solo/config.yaml`

```yaml
solo_protocol_version: 1

project:
  name: my-project
  description: ""
  version: 0.1.0
  repo: ""

agents:
  secretary:
    provider: openai
    model: gpt-4o
    temperature: 0.3
    max_tokens: 32000
  cto:
    provider: anthropic
    model: claude-opus-4
    temperature: 0.2
    max_tokens: 64000
  cpo:
    provider: anthropic
    model: claude-opus-4
    temperature: 0.3
    max_tokens: 32000
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
    max_tokens: 32000
  analyst:
    provider: anthropic
    model: claude-opus-4
    temperature: 0.2
    max_tokens: 32000

delegation:
  max_parallel: 3
  timeout: 300
  max_retries: 3

default_workflow: feature
```

实际模板还包含三个全局配置块：

- `providers`: 定义 OpenAI、Anthropic、Google、OpenRouter 等 provider 的类型、`api_key_env`、`base_url`。
- `mcp_servers`: 定义 filesystem、git、browser、github 等 MCP server 启动命令。
- `skills`: 定义 planning、architecture、implementation、testing、code-review、research 等常见 skill 文档。

每个 agent 可以独立声明：

```yaml
agents:
  cto:
    provider: anthropic
    model: claude-opus-4
    skills: [architecture, code-review, research]
    mcp_servers: [filesystem, git]
  qa:
    provider: openai
    model: gpt-4o-mini
    skills: [testing, code-review]
```

不在这里存 `related_projects`。跨项目注册由 `solo-os` 的 `~/.solo-os/projects.yaml` 管理。

### `.solo/state/tasks.json`

```json
{
  "schema_version": 1,
  "tasks": [
    {
      "id": "TASK-20260508-001",
      "title": "RSS 订阅功能",
      "description": "实现 RSS 订阅和管理能力",
      "status": "in_progress",
      "workflow": "feature",
      "current_phase": "dev",
      "phases": [
        {"name": "cpo", "type": "agent", "status": "completed"},
        {"name": "cto", "type": "agent", "status": "completed"},
        {"name": "ceo_check", "type": "human_gate", "status": "skipped"},
        {"name": "dev", "type": "agent", "status": "in_progress"},
        {"name": "qa", "type": "agent", "status": "pending"}
      ],
      "artifacts_dir": ".solo/artifacts/TASK-20260508-001",
      "created_at": "2026-05-08T10:00:00+10:00",
      "updated_at": "2026-05-08T10:42:00+10:00"
    }
  ]
}
```

状态枚举：

- `pending`
- `in_progress`
- `blocked`
- `waiting_approval`
- `completed`
- `failed`
- `skipped`

阶段类型：

- `agent`: 需要 Agent 执行。
- `human_gate`: 需要 CEO/用户确认。
- `system`: 由 CLI 执行的系统步骤，如 report generation。

### `.solo/state/events.jsonl`

事件日志采用追加式 JSONL，方便 Dashboard 增量读取，也降低并发覆盖风险。

```jsonl
{"ts":"2026-05-08T10:00:00+10:00","task_id":"TASK-20260508-001","event":"task.created","phase":"secretary"}
{"ts":"2026-05-08T10:05:00+10:00","task_id":"TASK-20260508-001","event":"phase.completed","phase":"cto"}
{"ts":"2026-05-08T10:10:00+10:00","task_id":"TASK-20260508-001","event":"phase.started","phase":"dev"}
```

---

## 五、CLI 设计

### `solo init`

```bash
solo init
solo init --yes
solo init --template default
```

职责：

- 检查当前目录是否已有 `.solo/`。
- 生成 `.solo/config.yaml`。
- 复制 default agents 和 workflows。
- 初始化 `.solo/state/tasks.json`、`.solo/state/events.jsonl`、`.solo/artifacts/`。
- 生成 `.soloignore`。

### `solo dispatch`

```bash
solo dispatch "实现 RSS 订阅功能"
solo dispatch --to cto "评审当前架构"
solo dispatch --workflow bugfix "修复 API 超时"
solo dispatch --json "实现 RSS 订阅功能"
```

职责：

- 创建任务 ID。
- 根据 workflow 展开 phases。
- 为目标 phase 生成执行包。
- 写入 `tasks.json` 和 `events.jsonl`。
- 输出人类可读摘要；`--json` 输出结构化结果，供 `solo-os` 调用。

MVP 的 dispatch 不要求真实调用远程模型。它先生成：

```text
.solo/artifacts/TASK-.../
├── task.json
├── cto_input.json
├── cto_instruction.md
└── report.md
```

### `solo status`

```bash
solo status
solo status --all
solo status --json
```

职责：

- 读取 `.solo/state/tasks.json`。
- 展示最近任务、当前阶段、阻塞信息、产物路径。
- `--json` 输出稳定结构，供 `solo-os dashboard` 聚合。

### `solo complete`

```bash
solo complete
solo complete --task TASK-...
solo complete --phase cto_breakdown
solo complete --json
```

职责：

- 标记当前 phase 完成。
- 跳过 optional human gate。
- 推进到下一 phase。
- 为下一 phase 生成执行包。
- 如果没有下一 phase，则标记 task completed。

### `solo start`

```bash
solo start
```

职责：

- 加载当前项目。
- 提供 CEO 与 Secretary 的交互式入口。
- 内部复用 `dispatch` 和 `status`。
- MVP 不单独实现新的 Agent runtime。

---

## 六、核心模块职责

### `core/project.py`

- `SoloProject.find(path=".")`: 从当前目录向上查找 `.solo/`。
- `SoloProject.init(path, template="default")`: 初始化协议目录。
- `SoloProject.load()`: 加载 config、state、agent registry。

### `core/config.py`

- 定义 `SoloConfig`、`ProjectConfig`、`AgentConfig`。
- 负责 YAML 读写和最小校验。
- 校验 `solo_protocol_version`。

### `core/state.py` / `core/task.py`

- 定义 `Task`、`TaskPhase`、状态枚举。
- 读写 `tasks.json`。
- 追加 `events.jsonl`。
- 使用 `.solo/state/.lock` 做写入互斥。
- 使用临时文件 + replace 原子写入 `tasks.json`。

### `core/workflow.py`

- 读取 `.solo/workflows/*.yaml`。
- 将 `feature` / `bugfix` / `release` 展开成 phases。
- 明确 `agent`、`human_gate`、`system` 三类 phase。

### `core/agent_registry.py`

- 读取 `.solo/agents/*.md`。
- 校验 workflow 中引用的 agent 是否存在。
- 为 dispatch 生成 prompt 上下文。

### `core/model_router.py`

- 从 `.solo/config.yaml` 的 `agents` 字段解析模型。
- 返回 `provider`、`model`、`temperature`、`max_tokens`。

### `core/secretary.py`

- 根据用户输入创建 task。
- 选择 workflow。
- 决定下一阶段。
- 汇总阶段产物为 report。

### `core/dispatcher.py`

- 生成 Agent 执行包。
- 写入 `.solo/artifacts/<task_id>/`。
- 把执行层抽象成 adapter。

Adapter 建议：

| Adapter | 阶段 | 说明 |
|---------|------|------|
| `package` | MVP | 只生成执行包和指令文件 |
| `manual` | MVP | 用户把结果放回 artifacts 后标记完成 |
| `command` | 当前阶段 | 用通用命令适配器接 Hermes / OpenClaw / Codex / Claude Code / 本地 wrapper |
| `provider` | 后续可选 | 直接接模型 provider API |
| `coding-cli` | 后续可选 | Codex / Claude Code 等 coding CLI 的更深封装 |
| `orchestrator` | 后续可选 | Hermes / OpenClaw 等下层编排系统的更深封装 |

---

## 七、实现路线

### Progress Log

#### 2026-05-09

本次进度：

- 将仓库从旧 architecture/prototype 结构收敛为 `src/solo` CLI 项目。
- 删除旧 `agents/`、`core/`、`config/`、`org-chart/`、`sops/`、`tools/` 和旧测试。
- 新增 `pyproject.toml`，提供 `solo` CLI entry point。
- 实现 `solo init`、`solo dispatch`、`solo complete`、`solo status`、`solo start`。
- 实现 `.solo/` 协议：`config.yaml`、`state/tasks.json`、`state/events.jsonl`、`artifacts/`、`agents/`、`workflows/`、`skills/`。
- 实现 per-agent provider/model 配置，以及 `providers`、`mcp_servers`、`skills` 协议。
- 执行包包含 resolved model、provider config、MCP server 声明和 skill 内容。
- 实现 CTO breakdown -> dev pool -> QA -> CTO review -> secretary report 的默认 feature workflow。
- 实现状态文件锁 `.solo/state/.lock` 和 `tasks.json` 原子写入。
- 新增 Docker Compose 测试环境，主机无需 Python/pytest 即可跑测试。
- 当前验证：`docker compose run --rm test` 通过，`11 passed`。

后续增量：

- 明确 `ExecutionAdapter` adapter boundary。
- 新增 `build_dispatcher(adapter, config, agents)` adapter factory。
- `dispatch` / `complete` 通过 adapter factory 使用 `package` adapter。
- 新增 dispatcher adapter 测试。

继续推进：

- 新增 `execution.default_adapter` 和 `execution.command` 配置协议。
- 新增通用 `command` adapter，先生成标准执行包，再把 `{input}`、`{instruction}`、`{output_dir}` 等路径交给外部命令。
- `solo dispatch --adapter command` 可以临时覆盖项目默认 adapter。
- command runtime 会注入 `SOLO_TASK_ID`、`SOLO_PHASE`、`SOLO_AGENT_ROLE`、`SOLO_PACKAGE_INPUT`、`SOLO_PACKAGE_INSTRUCTION`、`SOLO_OUTPUT_DIR`。
- system phase 由 solo 内部生成报告，不强制外部 runtime 执行。
- 当前验证：`docker compose run --rm test` 通过，`16 passed`。

继续推进 runtime 可观测性：

- command runtime 将 `command`、`returncode`、`stdout`、`stderr` 写入 `.solo/artifacts/<task_id>/<phase>_runtime.json`。
- `phase.started` 事件记录轻量 details：adapter、agent_role、input/instruction/report/runtime_report 路径，以及 runtime returncode。
- `solo-os` 可以通过 `events.jsonl` 看到 phase 准备情况，通过 artifact 指针按需读取完整 runtime 结果。
- 当前验证：`docker compose run --rm test` 通过，`16 passed`。

继续推进 solo-os 读取面：

- `solo status --json` 新增 `paths`，暴露 project root、`.solo`、config、tasks、events、artifacts 路径。
- `solo status --json` 新增 `execution`，暴露默认 adapter 和当前 CLI 支持的 adapter 列表。
- 新增 `available_adapters()`，让 dashboard 或测试不用硬编码支持列表。
- 当前验证：`docker compose run --rm test` 通过，`16 passed`。

继续推进 Agent 通信：

- 新增 `.solo/state/messages.jsonl`，作为 Agent 间 durable mailbox。
- `dispatch` 写入 `ceo -> secretary` request 和 `secretary -> 当前执行 agent` assignment。
- `complete` 在 phase 推进时写入当前 agent 到下一 agent 的 handoff；任务结束时写入 agent -> CEO result。
- `solo status --json` 新增 `recent_messages`，并在 `paths.messages` 暴露 mailbox 路径。
- message 只保存路由、摘要和 artifact 指针，正文继续放在 `.solo/artifacts/<task_id>/`。
- 当前验证：`docker compose run --rm test` 通过，`16 passed`。

继续修正 mailbox 语义：

- handoff 的 `artifact` 只指向已存在的上一阶段产物，不再指向下一阶段 instruction。
- 下一阶段执行入口放入 `details.next_instruction`。
- agent pool 阶段按实例展开 mailbox 收件人/发件人，例如 `cto -> dev-1/dev-2` 和 `dev-1/dev-2 -> qa`。
- result message 只在真实 output/report 存在时写 artifact，避免 dashboard 链接指向不存在的文件。
- 当前验证：`docker compose run --rm test` 通过，`16 passed`。

继续推进 runtime profile / setup：

- 新增 `runtime_profiles` 协议，把外部 runtime 配置收敛为可复用 profile。
- Agent 可通过 `agents.<role>.runtime` 选择 profile；没有设置时走 `execution.default_profile` / `execution.default_adapter`。
- 新增 `solo setup runtime`，支持 preset、`--command`、`--arg`、`--env`、`--set-default`、`--for <role>`。
- 当前内置 preset：`package`、`codex`、`claude-code`、`hermes`、`openclaw`。这些是 wrapper 起点，不把外部工具完整配置系统复制进 solo。
- `solo status --json` 的 `execution` 增加 `default_profile` 和 runtime profile 列表，方便 `solo-os` 展示能力。
- 当前验证：`docker compose run --rm test` 通过，`19 passed`。

#### 2026-05-12

继续推进结构化产物 / contracts：

- 新增 `.solo/contracts/work_packages.schema.json`、`agent_result.schema.json`、`qa_report.schema.json`、`message.schema.json`，给 runtime wrapper 和 `solo-os` 一个稳定读取面。
- `solo complete` 在完成 `cto_breakdown` 时，会读取 `.solo/artifacts/<task_id>/work_packages.json` 或 `cto_breakdown_output.json`。
- 结构化 work packages 会写回 `task.work_packages`，并按 dev pool 实例分配到 `dev-1/dev-2/...`。
- 下一阶段 dev package 会包含更新后的 `work_packages` 和 `agent_instances`。
- 当前验证：`docker compose run --rm test` 通过，`21 passed`。

继续推进结构化结果 / QA report：

- 新增 `phase_results` task state，用于保存 agent result 和 QA report 的结构化摘要。
- `solo complete` 会读取 `<phase>_agent_result.json` / `<phase>_result.json`、agent pool 的 `<agent_id>_agent_result.json` / `<agent_id>_result.json`，以及 QA 的 `qa_report.json`。
- 下一阶段 package 会包含 `phase_results`，让 QA / CTO review / secretary report 能看到前序 agent 的结构化输出。
- 当前验证：`docker compose run --rm test` 通过，`23 passed`。

继续推进协议健康检查：

- 新增 `solo validate`，用于检查 `.solo/` 目录、contracts、config 引用、workflow 依赖和 JSON/JSONL 状态文件。
- `solo validate --json` 输出 `ok`、summary、errors、warnings，方便 `solo-os` 或 CI 读取。
- 当前验证：`docker compose run --rm test` 通过，`26 passed`。

继续推进 task inspect 读取面：

- 新增 `solo inspect` / `solo inspect --json`，按 task 输出 task snapshot、events、messages 和 artifact manifest。
- artifact manifest 会标记 input、instruction、runtime、agent_result、qa_report、work_packages、task_snapshot 等 kind。
- 当前验证：`docker compose run --rm test` 通过，`29 passed`。

继续推进 agent pool 执行包：

- `PackageDispatcher` 在 agent pool phase 额外生成 per-instance package，例如 `dev-1_input.json` 和 `dev-1_instruction.md`。
- mailbox handoff 会按收件人写入对应的 `details.next_instruction` / `details.next_input`，并带上该 dev agent 的 work packages。
- phase event details 保留 `agent_packages` 路径摘要，方便 dashboard 展示每个 dev agent 的入口。
- 当前验证：`docker compose run --rm test` 通过，`29 passed`。

继续推进 work package 状态回流：

- dev pool 完成时，`solo complete` 会根据 `dev-1_result.json` / `dev-1_agent_result.json` 等结构化结果更新对应 work package status。
- `work_packages.updated` 事件会记录 dev pool 阶段的状态回流，方便 dashboard 展示每个 work package 的进度。
- 当前验证：`docker compose run --rm test` 通过，`29 passed`。

当前状态：

- MVP 协议闭环完成。
- `package` adapter、`command` adapter、adapter factory 和 `manual complete` 已完成。
- runtime 结果已经落盘，并在事件流里保留 dashboard 友好的摘要。
- `solo status --json` 已包含 solo-os 注册和 dashboard 所需的路径与执行能力。
- Agent 之间的任务分派和交接已经通过 `messages.jsonl` 可追踪，并区分 sender result 和 next instruction。
- Hermes/OpenClaw/Codex/Claude Code 先通过 runtime profile + `command` adapter 接入；专用 adapter 不再是近期优先项。
- CTO -> Dev 的 work package 已从约定文件升级为结构化 task state。
- Agent result 和 QA report 已能回流到 `phase_results`，并进入下一阶段执行包。
- `.solo/` 协议健康检查已由 `solo validate` 覆盖，可给 solo-os / CI 作为兼容性入口。
- `solo inspect --json` 已提供单任务详情读取面，方便 dashboard 避免自行扫描和拼接上下文。
- Agent pool 已生成 per-instance execution package，mailbox 可以把 `dev-1/dev-2/...` 路由到各自 instruction。
- Dev agent result 已能更新对应 work package status。

### Progress Snapshot

| Step | 状态 | 说明 |
|------|------|------|
| Step 1: 项目骨架 + init | Done | `pyproject.toml`、`src/solo`、default template、`solo init` 已实现 |
| Step 2: 状态协议 | Done | `tasks.json` / `events.jsonl` / `.lock` / 原子写入已实现；状态测试已补 |
| Step 3: workflow + dispatch | Done | workflow、agent registry、model router、package dispatcher、`solo dispatch` 已实现 |
| Step 4: status | Done | `solo status` 和 `solo status --json` 已实现 |
| Step 5: start 薄交互层 | Done | `solo start` 已复用 dispatch/status，暂不做真实 runtime |
| Step 6: 执行适配器 | Done for generic runtime | `ExecutionAdapter` boundary、`package` adapter、`command` adapter、`solo complete` manual phase advance 已实现；专用 adapter 后续可选 |
| Docker 测试环境 | Done | `docker compose run --rm test` 可在容器内跑测试 |
| Runtime 可观测性 | Done | command runtime 结果写入 artifacts，phase 事件记录 dashboard 可读摘要 |
| solo-os 读取面 | Done | `solo status --json` 暴露 paths 和 execution capabilities |
| Agent durable mailbox | Done | `.solo/state/messages.jsonl` 已接入 dispatch/complete/status；handoff artifact/next_instruction 和 agent pool 实例路由已修正 |
| Runtime profiles / setup | Done | `runtime_profiles` 和 `solo setup runtime` 已实现，并通过容器测试 |
| Structured contracts / work packages | Done | contracts schema 和 CTO work package ingestion 已实现，并通过容器测试 |
| Structured phase results / QA reports | Done | agent result / QA report 可回流到 task state，并传入下一阶段 package |
| Protocol validation | Done | `solo validate` 检查 `.solo/` 协议结构、配置引用、workflow 和 JSON/JSONL 状态 |
| Task inspect API | Done | `solo inspect --json` 输出 task、events、messages 和 artifact manifest |
| Agent pool per-instance packages | Done | dev pool 会生成每个 agent instance 的 input/instruction，并写入 mailbox handoff |
| Work package status feedback | Done | dev result 会回填对应 work package status，并记录更新事件 |

当前新增能力：

- per-agent `provider/model` 配置。
- `providers` / `mcp_servers` / `skills` 协议。
- 执行包内包含 resolved model、provider、MCP servers、skills 内容。
- CTO -> dev pool -> QA -> CTO review 的 phase 协议。
- `solo complete` 可推进当前任务到下一阶段。
- Docker Compose 测试环境已可用。

### Step 1: 项目骨架 + init

| 任务 | 文件 |
|------|------|
| 创建 `pyproject.toml` 和 src 布局 | `pyproject.toml`, `src/solo/` |
| 实现 CLI 入口 | `src/solo/cli.py`, `src/solo/__main__.py` |
| 实现 config 数据模型 | `src/solo/core/config.py` |
| 实现 project init/find/load | `src/solo/core/project.py` |
| 创建 default 模板 | `src/solo/templates/default/` |
| 实现 `solo init` | `src/solo/commands/init_cmd.py` |

验收：

```bash
solo init --yes
test -f .solo/config.yaml
test -f .solo/state/tasks.json
```

### Step 2: 状态协议

| 任务 | 文件 |
|------|------|
| 定义 Task / TaskPhase | `src/solo/core/task.py` |
| 实现 tasks.json 读写 | `src/solo/core/state.py` |
| 实现 events.jsonl 追加 | `src/solo/core/state.py` |
| 实现状态文件锁和原子写入 | `src/solo/core/state.py` |
| 测试状态枚举和序列化 | `tests/test_solo/test_state.py` |

验收：

```bash
pytest tests/test_solo/test_state.py
```

### Step 3: workflow + dispatch

| 任务 | 文件 |
|------|------|
| 实现 workflow 加载 | `src/solo/core/workflow.py` |
| 实现 agent registry | `src/solo/core/agent_registry.py` |
| 实现 model router 适配 | `src/solo/core/model_router.py` |
| 实现执行包生成 | `src/solo/core/dispatcher.py` |
| 实现 `solo dispatch` | `src/solo/commands/dispatch_cmd.py` |

验收：

```bash
solo dispatch --workflow feature "实现 RSS 订阅功能"
find .solo/artifacts -maxdepth 2 -type f
```

### Step 4: status

| 任务 | 文件 |
|------|------|
| 实现终端状态表 | `src/solo/commands/status_cmd.py`, `src/solo/utils/ui.py` |
| 实现 `--json` 输出 | `src/solo/commands/status_cmd.py` |
| 测试 JSON contract | `tests/test_solo/test_status.py` |

验收：

```bash
solo status
solo status --json
```

### Step 5: start 薄交互层

| 任务 | 文件 |
|------|------|
| 实现欢迎面板 | `src/solo/utils/ui.py` |
| 实现 prompt loop | `src/solo/commands/start_cmd.py` |
| 复用 dispatch/status | `src/solo/commands/start_cmd.py` |

验收：

```bash
solo start
```

### Step 6: 执行适配器

| 任务 | 文件 |
|------|------|
| 定义 adapter interface | `src/solo/core/dispatcher.py` |
| `package` adapter | `src/solo/core/dispatcher.py` |
| `manual complete` 命令或内部 API | `src/solo/commands/complete_cmd.py` |
| `command` runtime adapter | `src/solo/core/dispatcher.py` |
| runtime profiles | `src/solo/core/config.py`, `src/solo/commands/setup_cmd.py` |
| provider / coding-cli / orchestrator adapter | 后续可选 |

---

## 八、测试策略

MVP 测试重点：

- `solo init` 不覆盖已有 `.solo/`。
- `config.yaml` 能加载并校验协议版本。
- `workflow` 中引用的 agent 都存在。
- `dispatch` 会创建任务、追加事件、生成 artifacts。
- `status --json` 输出稳定 schema。
- `SoloProject.find()` 能从子目录找到项目根。

建议测试文件：

```text
tests/test_solo/
├── test_init.py
├── test_config.py
├── test_project.py
├── test_state.py
├── test_workflow.py
├── test_dispatch.py
├── test_dispatcher.py
├── test_complete.py
└── test_status.py
```

---

## 九、关键决策

| # | 决策 | 选择 |
|---|------|------|
| 1 | 当前项目范围 | 单项目 solo CLI |
| 2 | 多项目管理 | 独立 `solo-os` 项目 |
| 3 | 第一版核心 | `.solo/` 协议 + dispatch/status |
| 4 | Agent 执行 | adapter 化，MVP 先生成执行包 |
| 5 | Dashboard | 不在当前项目实现 |
| 6 | CLI 框架 | Click |
| 7 | 终端 UI | Rich |
| 8 | 交互输入 | prompt_toolkit，用于 `solo start` |
| 9 | 配置格式 | YAML |
| 10 | 状态快照 | JSON |
| 11 | 事件日志 | JSONL |
| 12 | 代码组织 | src 布局 |

---

## 十、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 真实 Agent runtime 不稳定 | `solo start` 无法自动完成任务 | MVP 先做执行包生成，runtime 走 adapter |
| `.solo/` 协议频繁变化 | `solo-os` dashboard 后续难兼容 | 加 `solo_protocol_version` 和 schema 测试 |
| 并发写状态 | tasks.json 覆盖或损坏 | events.jsonl 追加优先，后续加文件锁 |
| workflow 混入人类确认步骤 | dispatcher 不知道如何执行 | phase 明确 `agent` / `human_gate` / `system` |
| Dashboard 膨胀 | 当前项目职责变混 | Dashboard 坚持放到独立 `solo-os` |
| 模型 provider 差异 | dispatch 参数不可用 | ModelRouter 只解析配置，真实调用由 adapter 处理 |

---

## 十一、推荐下一步

当前 MVP 闭环：

```bash
solo init --yes
solo dispatch --workflow feature "实现 RSS 订阅功能"
solo complete
solo status
solo status --json
```

容器测试：

```bash
docker compose run --rm test
```

这个闭环完成后，`solo-os` 就可以在另一个项目里开始做 read-only dashboard：注册项目、读取 `.solo/config.yaml`、`.solo/state/tasks.json`、`.solo/state/events.jsonl`，展示全局状态。

如果要先验证外部 runtime，可以把 `.solo/config.yaml` 的 `execution.default_adapter` 改成 `command`，或单次运行：

```bash
solo dispatch --adapter command --json "实现 RSS 订阅功能"
```
