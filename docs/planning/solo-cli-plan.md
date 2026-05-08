# Planning: solo CLI — 项目级 Solo Company 工具

> 基于: `docs/research/solo-cli-research.md`
> 参考: [earendil-works/pi](https://github.com/earendil-works/pi)
> 目标: MVP 可运行版本

---

## 一、范围定义 (MVP)

### MVP 包含
| 功能 | 说明 |
|------|------|
| `solo init` | 在当前目录生成 `.solo/` 配置目录 |
| `solo start` | 进入交互式 CLI，对接 Hermes 的 `delegate_task` |
| `solo status` | 查看当前项目任务状态 |
| 配置文件 | `.solo/config.yaml` 模型路由 + 项目信息 |
| 核心复用 | `model_router.py`、Secretary 逻辑移到包内 |

### MVP 不包含（后续迭代）
- `solo list`（扫多项目）
- `solo config`（配置管理）
- `solo dispatch`（直接派任务）
- Templates 系统
- Prompt Templates（类似 pi 的 `/command`）
- Extensions 插件系统
- Web Dashboard

---

## 二、整体架构

```
┌──────────────────────────────────────────────────────────┐
│  solo CLI                                                │
│                                                          │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ click CLI   │  │ 交互式 Loop  │  │ Rich UI 渲染     │ │
│  │ (solo init, │──│ (solo start) │──│ (markdown,       │ │
│  │  status)    │  │ prompt_toolk │  │  面板, 进度条)   │ │
│  └────────────┘  └──────┬───────┘  └──────────────────┘ │
│                         │                                │
│                         ▼                                │
│              ┌─────────────────────┐                     │
│              │   Secretary Core    │                     │
│              │  (任务分解/调度/报告)│                     │
│              └─────────┬───────────┘                     │
│                        │                                 │
│              ┌─────────▼───────────┐                     │
│              │   Model Router      │                     │
│              │  (按角色分模型)     │                     │
│              └─────────┬───────────┘                     │
│                        │                                 │
│              ┌─────────▼───────────┐                     │
│              │   delegate_task     │                     │
│              │   (Hermes 子Agent)  │                     │
│              └─────────────────────┘                     │
└──────────────────────────────────────────────────────────┘
```

**关键决策:** 不重新发明轮子。solo CLI 是 **Hermes 的封装层**，把 `delegate_task` + `Model Router` + 多 Agent 工作流包装成一句 `solo start`。

---

## 三、包结构

```
solo-company-architecture/
├── pyproject.toml                    # pip install solo-company
├── README.md
│
├── src/
│   └── solo/
│       ├── __init__.py
│       ├── __main__.py               # python -m solo
│       │
│       ├── cli.py                    # Click 命令组 (init, start, status)
│       │
│       ├── commands/
│       │   ├── init_cmd.py           # solo init 实现
│       │   ├── start_cmd.py          # solo start 实现（交互循环）
│       │   └── status_cmd.py         # solo status 实现
│       │
│       ├── core/
│       │   ├── project.py            # Project 类：加载/保存 .solo/config.yaml
│       │   ├── config.py             # Config 模型 + 校验 + 合并
│       │   ├── secretary.py          # Secretary Core（任务生命周期）
│       │   ├── model_router.py       # 模型路由（从架构仓库 core/ 移入）
│       │   └── state.py              # 任务状态持久化
│       │
│       ├── templates/                # init 模板
│       │   ├── default/
│       │   │   ├── config.yaml
│       │   │   └── agents/
│       │   │       ├── secretary.md
│       │   │       ├── cto.md
│       │   │       ├── cpo.md
│       │   │       ├── dev.md
│       │   │       ├── qa.md
│       │   │       ├── growth.md
│       │   │       └── analyst.md
│       │   └── py-lib/
│       │       └── ...
│       │
│       └── utils/
│           ├── ui.py                 # Rich 组件复用
│           └── git.py                # Git 操作工具

├── agents/              # 保留: Agent 角色定义 .md 文件（symlink 或复制到模板）
├── core/                # 保留: 原 model_router.py（最终要移到 src/solo/core/ 内）
├── sops/                # 保留: SOP 文档
├── config/              # 保留: models.yaml
├── docs/
│   └── research/
│       └── solo-cli-research.md      ← research doc

├── tests/
│   └── test_solo/
│       ├── test_init.py
│       ├── test_config.py
│       ├── test_project.py
│       └── test_secretary.py
```

### 命名规范
- 包名: `solo-company` (PyPI)
- 模块名: `solo` (`pip install solo-company` → `python -m solo`)
- CLI 入口: `solo` 命令

---

## 四、核心模块设计

### 4.1 `core/config.py` — 配置模型

```python
@dataclass
class AgentConfig:
    provider: str          # "anthropic" | "openai" | "google" | ...
    model: str             # "claude-opus-4" | "gpt-4o" | ...
    temperature: float = 0.3
    max_tokens: int = 32000

@dataclass
class ProjectConfig:
    name: str
    description: str = ""
    version: str = "0.1.0"
    repo: str = ""

@dataclass
class SoloConfig:
    project: ProjectConfig
    agents: Dict[str, AgentConfig]       # key: agent role name
    delegation: Dict = field(default_factory=lambda: {
        "max_parallel": 3,
        "timeout": 300,
        "max_retries": 3,
    })
    default_workflow: List[str] = field(default_factory=lambda: [
        "cpo", "cto", "dev", "qa", "cto_review", "merge", "growth"
    ])
```

### 4.2 `core/project.py` — Project 类

```python
class SoloProject:
    """代表一个 Solo Company 项目"""
    
    path: Path               # 项目根目录
    solo_dir: Path           # .solo/ 目录
    config: SoloConfig       # 加载的配置
    
    @classmethod
    def init(cls, path: str, name: str = None, template: str = "default"):
        """创建新项目（solo init 的核心）"""
    
    @classmethod
    def find(cls, path: str = ".") -> Optional["SoloProject"]:
        """从目录向上查找 .solo/"""
    
    def load(self) -> "SoloProject":
        """加载 .solo/config.yaml"""
    
    def save(self):
        """保存配置"""
    
    def get_agent_config(self, role: str) -> AgentConfig:
        """获取指定角色的模型配置"""
```

### 4.3 `core/secretary.py` — Secretary 核心

```python
class Secretary:
    """CEO Secretary — 任务生命周期管理"""
    
    project: SoloProject
    
    def create_task(self, description: str, workflow: List[str]) -> Task:
        """创建新任务"""
    
    def dispatch_agent(self, task: Task, agent_role: str) -> dict:
        """派发一个 Agent 角色（调用 delegate_task + 模型路由）"""
    
    def execute_workflow(self, task: Task):
        """按 workflow 顺序执行所有 Agent 阶段"""
    
    def generate_report(self, task: Task) -> str:
        """生成最终报告"""
```

**关键决策**: `execute_workflow` 内部调用 `delegate_task`，并传入从 `model_router` 解析的模型配置。这样每个 Agent 角色用不同 provider/model。

### 4.4 `commands/start_cmd.py` — 交互循环

```
solo start 进入的交互循环:
1. 加载项目 .solo/config.yaml
2. 显示 Rich 欢迎面板（项目名、Agent 状态）
3. 进入 prompt_toolkit 循环:
   - 用户输入 → 自然语言需求
   - Secretary 分析 → 确定 workflow
   - 开始执行 workflow（调用 delegate_task）
   - 实时显示进度（Rich 面板更新）
   - 完成后显示报告
4. 回到循环，等待下一个需求
```

### 4.5 `core/model_router.py` — 模型路由（从 core/ 移入）

**复用现有 `ModelRouter` 类**，只做两处调整：

1. 配置源从 `config/models.yaml` 改为 `.solo/config.yaml` 的 `agents` 字段
2. 增加 `provider` 字段（原配置只有 `model` 字符串）

```python
class ModelRouter:
    def resolve(self, agent_name: str) -> dict:
        """返回 {"provider": "anthropic", "model": "claude-opus-4", ...}"""
```

---

## 五、配置设计

```yaml
# .solo/config.yaml (由 solo init 生成)
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

default_workflow:
  - cpo
  - cto
  - ceo_check
  - dev
  - qa
  - cto_review
  - merge
  - growth
```

---

## 六、关键交互流程

### 6.1 `solo init`

```
$ solo init
╔══════════════════════════════════════════╗
║  Solo Company — 项目初始化               ║
╚══════════════════════════════════════════╝

项目名称 [my-project]: social-hotspot-daily
项目描述: 热点追踪与数据仪表盘
选择模板 [default/py-lib/react]: default

✅ 已创建 .solo/config.yaml
✅ 已创建 .solo/agents/ (7个角色)
✅ 已创建 .solo/state/
✅ 已创建 .soloignore

下一步: cd social-hotspot-daily && solo start
```

### 6.2 `solo start` (交互模式)

```
$ solo start

╔══════════════════════════════════════════╗
║  Solo Company — social-hotspot-daily     ║
║  CEO: Noah  |  Secretary: Ready          ║
╚══════════════════════════════════════════╝

  [CTO: opus-4 ✓] [CPO: opus-4 ✓] [Dev: sonnet-4 ✓] [QA: gpt-4o-mini ✓]

  你 > 帮我加一个RSS订阅功能

  秘书 > 好的，让我分析这个需求...

  我建议走以下工作流:
  ┌─ CPO (产品需求) → CTO (架构) → CEO确认 → Dev (开发) → QA → CTO审查 → 合并 ─┐
  │                                                                            │
  │  需要先出 PRD 吗？还是直接开始？                                            │
  └────────────────────────────────────────────────────────────────────────────┘

  你 > 直接开始吧，不用CPO了，我需求很清楚

  秘书 > 好的，跳过 CPO，直接调度 CTO 做架构设计...

  ┌─ CTO ──────────────────────────────────────────────┐
  │ 架构方案:                                          │
  │  ├ 技术栈: XML Feed Parser + 存储到 SQLite          │
  │  ├ 新增文件: rss_fetcher.py, rss_models.py         │
  │  └ 估算: 2-3 小时                                   │
  └─────────────────────────────────────────────────────┘

  你 > 可以，开始开发

  秘书 > 调度 Dev Agent 进行实现...
  ── Dev 进行中 ████████░░ 80% ──

  秘书 > Dev 完成，调度 QA 验证...
  ── QA: 测试通过 (12/12) ✅ ──

  秘书 > 调度 CTO 审查 PR...
  ── CTO 批准 PR #42 ✅ ──

  秘书 > 合并完成。以下是报告:

  📊 RSS订阅功能 完成
  ├ 新增文件: 3
  ├ 测试: 12/12 通过
  ├ 耗时: 45分钟
  └ 模型花费: $0.32

  你 > 不错。帮我查一下当前还有哪些进行中的任务
```

### 6.3 `solo status`

```
$ solo status

📋 任务状态 — social-hotspot-daily

  TASK-20260508-001  RSS订阅功能        ✅ 完成    (45分钟)
  TASK-20260507-003 修复API超时问题     🟡 QA中    (CTO审查通过)
  TASK-20260506-002 添加Dark Mode      🔴 阻塞    (等待第三方库更新)

最近3个任务, 1个进行中
```

---

## 七、依赖与技术选型

### 生产依赖

| 包 | 用途 | 理由 |
|----|------|------|
| `click` | CLI 命令框架 | 轻量、成熟、命令分组好 |
| `pyyaml` | YAML 解析 | config.yaml 读写 |
| `rich` | 终端 UI | 面板、markdown、进度条、表格 |
| `prompt-toolkit` | 交互式输入 | 历史、自动补全、多行 |
| `pydantic` (可选) | 配置校验 | config.yaml 类型安全 |

### 开发依赖

| 包 | 用途 |
|----|------|
| `pytest` | 测试 |
| `pytest-cov` | 覆盖率 |
| `build` | PyPI 构建 |
| `twine` | PyPI 上传 |

### 对 Hermes 的依赖

solo CLI **运行在 Hermes Agent 之上**，依赖:

1. **`delegate_task`** — 所有 Agent 角色的实际执行
2. **`terminal`** — Git 操作、本地命令
3. **`memory`** — 持久化用户偏好 (可选)
4. **`execute_code`** — 超时回退机制

**这意味着 solo CLI 目前只能在 Hermes Agent 环境内运行。** 未来可以发展为独立 CLI（自己实现 delegate_task 逻辑），但 MVP 阶段接受这个约束。

---

## 八、分步实现计划

### Step 1: 项目骨架 + Init

| 任务 | 文件 | 预估 |
|------|------|------|
| 创建 pyproject.toml | `pyproject.toml` | 小型 |
| 创建包目录结构 | `src/solo/` | 小型 |
| 实现 Config 数据类 + YAML 读写 | `core/config.py` | 中型 |
| 实现 Project 类 (init, find, load, save) | `core/project.py` | 中型 |
| 实现 `solo init` 命令 | `commands/init_cmd.py` | 中型 |
| 创建 default 模板 (config.yaml + agents) | `templates/default/` | 小型 |

### Step 2: 模型路由适配

| 任务 | 文件 | 预估 |
|------|------|------|
| 移植 ModelRouter 到 src/solo/core/ | `core/model_router.py` | 小型 |
| 调整配置源 (从 config.yaml 的 agents 字段) | 同上 | 小型 |
| 测试: ModelRouter + SoloConfig 集成 | `tests/test_config.py` | 小型 |

### Step 3: Secretary 核心

| 任务 | 文件 | 预估 |
|------|------|------|
| 实现 Task 数据类 + 状态管理 | `core/state.py` | 中型 |
| 实现 Secretary 类 (create, dispatch, workflow) | `core/secretary.py` | 大型 |
| dispatch 内部: 调 delegate_task + 传模型配置 | 同上 | 中型 |
| 超时处理 + 幽灵完成检查 | 同上 | 中型 |
| 测试: Secretary 生命周期 | `tests/test_secretary.py` | 中型 |

### Step 4: 交互式 CLI (solo start)

| 任务 | 文件 | 预估 |
|------|------|------|
| 实现 Rich 欢迎面板 + UI 组件 | `utils/ui.py` | 中型 |
| 实现 prompt_toolkit 交互循环 | `commands/start_cmd.py` | 大型 |
| 自然语言需求 → workflow 映射 | 同上 | 中型 |
| 实时进度显示 (Rich Live) | 同上 | 中型 |
| 整合: start 循环 + Secretary dispatch | 同上 | 中型 |

### Step 5: Status + 收尾

| 任务 | 文件 | 预估 |
|------|------|------|
| 实现 `solo status` | `commands/status_cmd.py` | 中型 |
| 实现 `python -m solo` 入口 | `__main__.py` | 小型 |
| CLI 入口 `cli.py` 整合所有命令 | `cli.py` | 小型 |
| pyproject.toml 完善 (entry points) | `pyproject.toml` | 小型 |
| 测试: init → start → status 端到端 | `tests/` | 中型 |

---

## 九、关键设计决策总结

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| 1 | CLI 框架 | **Click** | 轻量、命令分组、成熟度 |
| 2 | TUI 渲染 | **Rich** | 已有 Hermes 使用经验 |
| 3 | 交互输入 | **prompt_toolkit** | 多行输入、历史记录 |
| 4 | 配置格式 | **YAML** | 人类可读写，与现有一致 |
| 5 | Agent 执行 | **delegate_task** | 不重新实现 Agent 运行时 |
| 6 | 配置源 | `.solo/config.yaml` | 自包含，不依赖外部文件 |
| 7 | 模型路由 | 从 agents 配置读取 | 每个角色独立配置 provider/model |
| 8 | 包名 | `solo-company` (PyPI) | 与项目名一致 |
| 9 | 发布方式 | PyPI | pip install |
| 10 | 语言 | Python | 与现有代码一致 |
| 11 | 代码组织 | src/ 布局 | 现代 Python 标准 |
| 12 | 模板 | 包内 templates/ | 不依赖外部资源 |

---

## 十、风险与缓解

| 风险 | 可能影响 | 缓解 |
|------|---------|------|
| `delegate_task` 300s 超时 | Agent 任务中途失败 | 幽灵完成检查 + 自动重试 + 拆分成更小的子任务 |
| 用户多个需求待办 | 任务状态管理复杂 | 持久化到 .solo/state/tasks.json |
| 模型配置不兼容 | delegate_task 不支持某些 provider | 回退到默认配置 + 报错提示 |
| 配置变更 | 已生成的 .solo/ 配置需要升级 | 版本号 + 迁移脚本 |
