# Research: solo-os — 董事会秘书 / 跨项目 Dashboard

> 调研日期: 2026-05-08
> 参考项目: [earendil-works/pi](https://github.com/earendil-works/pi) (v0.74.0, 46k+ stars)
> 研究目标: 设计 `solo-os`，作为跨项目管理、大需求拆解、全局可视化的"董事会秘书台"

---

## 一、定位与核心理念

### 1.1 solo-os 是什么

solo-os 是 **可选增强层**，不是必须的。它的存在动机：

> **当一个大需求需要跨多个子项目协作时，solo-os 负责拆解需求、并行派发、追踪进度、协调联调。**

实现上，`solo-os` 应该放在独立项目 / 独立仓库中。它是多个 `solo` 项目的 **control plane**，而不是单项目 `solo` CLI 的子命令集合。

`solo-os` 管理的是已经执行过 `solo init` 的项目。它不负责初始化单个项目的内部组织结构，也不直接拥有某个项目的 Agent prompt、workflow 或模型路由。

### 1.2 与 solo 的关系

```
                    solo-os (董事会秘书台)
                    │
                    │ CLI: solo-os start
                    │ Web: Dashboard (可选)
                    │
                    │ 拆需求、派任务、看全局
                    │
         ┌──────────┼──────────┐
         │          │          │
         ▼          ▼          ▼
    项目 A      项目 B      项目 C
    .solo/      .solo/      .solo/
    solo start  solo start  solo start
    自给自足    自给自足    自给自足
```

| | solo | solo-os |
|---|------|---------|
| **范围** | 单个项目 | 多个项目 |
| **必须** | ✅ 项目自带 | ❌ 可选安装 |
| **视角** | 子公司 CEO | 集团董事会秘书 |
| **能力** | 内部的 CTO/Dev/QA | 跨项目调度/聚合视图 |

### 1.3 依赖边界

`solo-os` 依赖的是稳定协议，不是 `solo` 的内部实现：

```
solo-os
├── 读取: <project>/.solo/config.yaml
├── 读取: <project>/.solo/state/tasks.json
├── 读取: <project>/.solo/state/events.jsonl
├── 读取: <project>/.solo/contracts/
└── 可选调用: solo status --json / solo dispatch --json
```

关键原则：

- `solo-os` 不 import `solo.core.*` 内部 Python 类。
- 项目注册表放在 `~/.solo-os/projects.yaml`，不写进单个项目的 `.solo/config.yaml`。
- 第一版 Dashboard 可以是 read-only；跨项目写操作等 `solo dispatch --json` 稳定后再接入。
- Dashboard 是可视化运营面板，不是第二套 Jira。

---

## 二、使用场景

### 场景 A: 跨项目大需求

```
solo-os start

董事会秘书 > 收到。需求: "实现统一用户认证系统"

我需要把这个拆解成子任务:
  ① auth-service: JWT 登录/注册、OAuth、用户 CRUD
  ② frontend-login: 登录页、注册页、SSO 跳转
  ③ api-gateway: 路由转发、token 验证中间件

每个子任务的进度:
  auth-service     ████████░░ 80% (Dev 完成, QA 中)
  frontend-login   ████░░░░░░ 40% (Dev 开发中)
  api-gateway      ██████░░░░ 60% (架构完成, 开发中)

需要我继续跟进吗？
```

### 场景 B: 全局状态看板

```
solo-os status

┌────────────────────────────────────────────────────────┐
│  Solo Company OS — 全局状态                           │
├────────────────────────────────────────────────────────┤
│                                                        │
│  📊 social-hotspot-daily    🟢 健康                    │
│     ├ 进行中: RSS 订阅功能 (Dev)                       │
│     └ 最近: 3天前发布 v0.3.0                          │
│                                                        │
│  📊 auth-service             🟡 等待审批               │
│     ├ 进行中: JWT 实现 (QA 完成, 待 CTO 审查)          │
│     └ 阻塞: 等 CTO 审查 PR #12                        │
│                                                        │
│  📊 api-gateway              🔴 阻塞                   │
│     └ 阻塞: 依赖 auth-service 的接口契约变更           │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### 场景 C: 契约管理与联调

当多个子项目需要互相配合时，solo-os 管理接口契约：

```
solo-os dispatch auth-service \
  --to cto \
  --task "定义 auth-service 对外的 API 接口契约"

→ 产出: .solo/contracts/auth-api.yaml

solo-os dispatch api-gateway \
  --to dev \
  --task "按照 auth-api.yaml 契约实现路由转发"
```

---

## 三、solo-os CLI 命令设计

```
solo-os
├── start                    # 进入交互式董事会 CLI
│   ├── (默认) 交互模式
│   └── --dashboard          # 启动 Web Dashboard
│
├── status                   # 全局状态看板
│   ├── (默认) 简洁摘要
│   ├── --verbose            # 详细状态
│   └── --json               # JSON 输出（给其他工具）
│
├── dispatch                 # 跨项目派任务
│   ├── solo-os dispatch <project> --to <role> "<任务>"
│   └── solo-os dispatch --all --to dev "更新依赖"
│
├── orchestrate              # 大需求拆解 + 派发
│   └── solo-os orchestrate "做一个认证系统"
│
├── project                  # 项目管理
│   ├── list                 # 列出所有已注册项目
│   ├── add <path>           # 添加项目
│   ├── remove <name>        # 移除项目
│   └── scan                 # 扫描所有含 .solo/ 的目录
│
├── contract                 # 接口契约管理
│   ├── list                 # 列出所有契约
│   ├── add <path>           # 注册契约文件
│   └── validate             # 验证契约一致性
│
├── dashboard                # 启动 Web Dashboard
│   ├── (默认) http://localhost:9810
│   └── --port <port>
│
└── help / -h
```

---

## 四、配置设计

### 4.1 solo-os 自身配置

```
~/.solo-os/
├── config.yaml              # solo-os 全局配置
├── projects.yaml            # 已注册项目列表
└── state/
    └── orchestrations/      # 大需求拆解记录
```

```yaml
# ~/.solo-os/config.yaml
# solo-os 自身配置

dashboard:
  port: 9810
  host: "127.0.0.1"

# 默认分派策略
dispatch:
  default_timeout: 300
  max_parallel: 4
```

```yaml
# ~/.solo-os/projects.yaml
# 项目注册表，由 solo-os project add/remove/scan 维护

projects:
  - name: social-hotspot-daily
    path: ~/projects/social-hotspot-daily
    repo: https://github.com/NoahStransky/social-hotspot-daily
    auto_scan: true
  - name: auth-service
    path: ~/projects/auth-service
    repo: https://github.com/NoahStransky/auth-service
    auto_scan: true
```

### 4.2 与项目 solo 配置的交互

solo-os 不重复存储项目的配置，它通过读取项目下的 `.solo/` 协议文件来获取信息：

```python
class SoloProjectAdapter:
    """表示一个已注册的 solo 项目；只依赖文件协议和 CLI contract."""
    
    def __init__(self, path: str):
        self.path = Path(path)
        self.config = self.load_config()       # 读取 .solo/config.yaml
        self.state = self.load_state()         # 读取 .solo/state/tasks.json
        self.events = self.load_events()       # 读取 .solo/state/events.jsonl
    
    def dispatch(self, agent_role: str, task: str):
        """向此项目的 secretary 派任务"""
        # 优先通过 solo CLI 的结构化接口，而不是直接写 .solo/state
        return run(
            ["solo", "dispatch", "--to", agent_role, "--json", task],
            cwd=self.path,
        )
    
    def get_status(self) -> dict:
        """获取项目当前状态"""
        tasks = self.state.get("tasks", [])
        return {
            "name": self.config["project"]["name"],
            "active_tasks": [t for t in tasks if t["status"] == "in_progress"],
            "last_updated": tasks[-1]["updated_at"] if tasks else None,
        }
```

如果目标项目还没有稳定的 `solo dispatch --json`，`solo-os` 第一版只做 read-only dashboard 和 `status` 聚合。

### 4.3 大需求 Orchestration 设计

当用户使用 `solo-os orchestrate` 时，流程如下：

```
1. 用户: "做一个统一用户认证系统"

2. solo-os → 调度 CPO Agent (用最强模型)
   → 产出: 需求拆解文档
   → 识别出需要 3 个子项目: auth-service, frontend-login, api-gateway

3. solo-os → 展示拆解方案给用户确认
   ┌─────────────────────────────────────────────┐
   │  拆解方案:                                   │
   │                                              │
   │  ① auth-service (JWT/OAuth/CRUD)            │
   │     → 指派给现有项目 / 需要新建              │
   │                                              │
   │  ② frontend-login (登录页/SSO跳转)           │
   │     → 指派给现有项目 / 需要新建              │
   │                                              │
   │  ③ api-gateway (路由/token验证)              │
   │     → 指派给现有项目 / 需要新建              │
   │                                              │
   │  是否确认？[y/N]                             │
   └─────────────────────────────────────────────┘

4. 用户确认后 → 并行调用各项目的 `solo dispatch --json`
   → 每个子项目内部按自己的 workflow 运行或生成执行包

5. solo-os → 持续追踪进度
   → 定期 poll 各项目状态
   → 在 Dashboard 上更新进度条
   → 检测依赖关系（如 api-gateway 等待 auth-service 的接口契约）

6. 所有子项目完成 → 通知联调 → 统一发布
```

---

## 五、Web Dashboard 设计

### 5.1 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 后端框架 | FastAPI | CLI 和 API 共用 project adapter / tracker |
| 前端 | Jinja2 + HTMX（MVP） | 只读监控面板不需要重前端 |
| 实时更新 | 轮询（MVP）→ SSE/WebSocket（后续） | 先降低复杂度，等状态协议稳定后再实时推送 |

MVP Dashboard 只展示：

- 已注册项目列表
- 项目健康状态
- 活跃任务与当前 phase
- 最近事件
- Orchestration 进度（后续）

第一版不做：

- 在 Dashboard 内编辑任务
- 替代 GitHub Issues / Jira
- 直接写入项目内部 `.solo/state`
- 模型账单精算（可先保留占位，后续从 events 聚合）

### 5.2 Dashboard 页面

**主页: 全局概览**
```
┌────────────────────────────────────────────────────────┐
│  🏢 Solo Company OS Dashboard               [刷新]      │
├────────────────────────────────────────────────────────┤
│                                                        │
│  项目状态总览:                                         │
│                                                        │
│  ┌──────────────┬──────┬──────────┬──────────┬──────┐  │
│  │ 项目          │ 状态  │ 活跃任务  │ 最近活动  │ 模型 │  │
│  ├──────────────┼──────┼──────────┼──────────┼──────┤  │
│  │ social-...   │ 🟢   │ RSS订阅   │ 3h ago   │ $0.42│  │
│  │ auth-service │ 🟡   │ JWT实现   │ 1h ago   │ $1.23│  │
│  │ api-gateway  │ 🔴   │ 阻塞中    │ 5h ago   │ $0.89│  │
│  │ frontend     │ 🟢   │ 登录页    │ 30m ago  │ $2.10│  │
│  └──────────────┴──────┴──────────┴──────────┴──────┘  │
│                                                        │
│  活跃 Orchestrations:                                  │
│                                                        │
│  🔄 统一认证系统 (3/5 完成)  ████████░░░░░░░░░ 60%     │
│                                                        │
│  模型用量 (今日):                                      │
│  Claude Opus: 120K tokens ($1.80)                      │
│  GPT-4o: 450K tokens ($1.35)                           │
│  Haiku: 890K tokens ($0.13)                            │
└────────────────────────────────────────────────────────┘
```

**详情页: 单个项目**
```
┌────────────────────────────────────────────────────────┐
│  ← 返回  |  auth-service                               │
├────────────────────────────────────────────────────────┤
│                                                        │
│  基本信息                                               │
│  ├ 路径: ~/projects/auth-service                       │
│  ├ 仓库: github.com/NoahStransky/auth-service          │
│  └ 模型: CTO(Opus) / Dev(Sonnet) / QA(Haiku)           │
│                                                        │
│  任务队列                                               │
│  ├ 🟢 TASK-20260508-001 JWT登录实现 (Dev: ✅, QA: 🟡)  │
│  ├ 🟡 TASK-20260507-002 OAuth集成 (Dev: 🔄)             │
│  └ 🔴 TASK-20260506-003 用户CRUD (CTO审查: ⏳)          │
│                                                        │
│  最近活动                                               │
│  ├ 10:23 Dev 提交 PR #12 (feat: add JWT login)         │
│  ├ 09:45 QA 通过 TASK-20260508-001 测试 (42/42)        │
│  └ 08:30 CTO 批准架构设计                               │
└────────────────────────────────────────────────────────┘
```

---

## 六、实现建议

### 6.1 包结构

```
solo-os/
├── pyproject.toml
├── src/
│   ├── solo_os/
│   │   ├── __init__.py
│   │   ├── __main__.py           # python -m solo_os
│   │   ├── cli.py                # Click/Typer 命令分组
│   │   ├── commands/
│   │   │   ├── start.py
│   │   │   ├── status.py
│   │   │   ├── dispatch.py
│   │   │   ├── orchestrate.py
│   │   │   ├── project.py
│   │   │   ├── contract.py
│   │   │   └── dashboard.py
│   │   ├── core/
│   │   │   ├── registry.py       # 项目注册表管理
│   │   │   ├── orchestrator.py   # 大需求拆解引擎
│   │   │   ├── dispatcher.py     # 跨项目派发
│   │   │   ├── tracker.py        # 进度追踪
│   │   │   └── contract.py       # 接口契约管理
│   │   ├── dashboard/            # Web Dashboard
│   │   │   ├── server.py         # FastAPI 服务
│   │   │   ├── static/           # 前端资源
│   │   │   └── templates/        # Jinja2 模板
│   │   └── utils/
│   │       ├── solo_project.py   # SoloProject 适配器（读取 .solo/）
│   │       ├── ui.py             # Rich/终端组件
│   │       └── scanner.py        # 文件系统扫描
```

### 6.2 关键模块设计

#### Registry（项目注册表）

```python
class ProjectRegistry:
    """管理所有已注册的 solo 项目"""
    
    def add(self, path: str) -> Project:
        """注册一个新项目，验证 .solo/config.yaml 存在"""
    
    def remove(self, name: str):
        """移除项目注册"""
    
    def scan(self, root_dir: str) -> List[Project]:
        """扫描目录下所有含 .solo/ 的项目"""
    
    def get(self, name: str) -> Project:
        """获取项目实例（延迟加载）"""
    
    def list(self) -> List[ProjectSummary]:
        """列出所有项目摘要"""
```

#### Orchestrator（大需求拆解引擎）

```python
class Orchestrator:
    """大需求 → 子任务拆解 → 并行派发 → 跟踪"""
    
    def decompose(self, request: str) -> OrchestrationPlan:
        """用 CPO Agent 分析需求，拆成子任务"""
    
    def dispatch_all(self, plan: OrchestrationPlan):
        """并行派发所有子任务到对应项目"""
    
    def track_progress(self, orchestration_id: str) -> Progress:
        """追踪大需求的整体进度"""
```

### 6.3 路线图

| 阶段 | 功能 | 优先级 |
|------|------|--------|
| **P0** | `project add/list/remove` — 项目注册 | 🚀 |
| **P0** | `solo-os status` — 全局状态看板（终端） | 🚀 |
| **P0** | `solo-os dashboard` — read-only Web 面板 | 🚀 |
| **P1** | `solo-os dispatch` — 通过 `solo dispatch --json` 跨项目派任务 | ⭐ |
| **P1** | 依赖检测 + 阻塞状态提示 | ⭐ |
| **P2** | `solo-os orchestrate` — 大需求拆解 + 用户确认 + 派发 | ✅ |
| **P2** | 模型用量统计（从 events 聚合） | ✅ |
| **P3** | 接口契约管理（contract） | 🌟 |
| **P3** | Webhook / API 集成 | 🌟 |
| **P4** | 实时 WebSocket 更新 | 🔮 |
| **P4** | 通知系统（任务完成、阻塞告警） | 🔮 |

### 6.4 依赖关系

solo-os **依赖 solo 协议**，并可选依赖 `solo` CLI：

```
solo-os
  ├── 必须依赖: 每个项目的 .solo/config.yaml
  ├── 必须依赖: 每个项目的 .solo/state/tasks.json
  ├── 建议依赖: 每个项目的 .solo/state/events.jsonl
  └── 可选依赖: solo status --json / solo dispatch --json
```

`solo-os` 不依赖 `solo.core.model_router`、`solo.core.secretary` 等内部模块。这样 `solo` 和 `solo-os` 可以分属两个项目，并保持清晰解耦。

---

## 七、风险和注意事项

1. **项目路径稳定性** — 如果项目移动位置，solo-os 的注册会失效。考虑用 git remote 或文件 inode 做更鲁棒的定位。
2. **并发冲突** — 同一项目同时被 solo-os 和本地 `solo start` 操作时，任务状态文件可能冲突。需要文件锁或状态合并策略。
3. **Dashboard 的复杂度控制** — Web Dashboard 很容易膨胀成"第二套 Jira"。应严格限制在**可视化监控**范围，不要变成项目管理平台。
4. **跨项目依赖管理** — 最复杂的部分。需要一种轻量的契约机制（如 OpenAPI spec 或 Protobuf）让子项目之间对齐。

---

## 八、对比总结

| 对比维度 | Pi | solo | solo-os |
|---------|----|------|---------|
| 定位 | 编码 Agent CLI | 单项目 Solo Company | 多项目董事会 |
| 用户 | 开发者单人 | 项目 CEO | 多项目管理者 |
| 依赖 | 自给自足 | 自给自足 | 依赖 solo |
| CLI 入口 | `pi` | `solo` | `solo-os` |
| 并行 | 单线程 | 内部 Agent 并行 | 跨项目并行 |
| UI | TUI | TUI | TUI + Web Dashboard |
