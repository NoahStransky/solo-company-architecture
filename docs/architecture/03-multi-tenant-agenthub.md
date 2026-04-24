# 多租户 Hermes Agent 管理平台 — 技术架构方案

> 版本: v0.1.0 | 状态: 草案 | 作者: CTO Agent

---

## 1. 系统愿景

在一台（或多台）服务器上部署 **AgentHub** 管理平台，为每个入驻用户隔离创建一个 **Hermes Solo Company 实例**（Docker 容器）。用户通过 Web UI 或 API 管理自己的 AI Agent 团队，执行项目任务。

核心公式：**1 用户 = 1 Docker 容器 = 1 套 Solo Company 框架**

---

## 2. 总体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户层 (User Layer)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │   Web UI     │  │  CLI 工具    │  │  REST API    │                      │
│  │  (React)     │  │  (Python)    │  │  (OpenAPI)   │                      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                      │
└─────────┼─────────────────┼─────────────────┼──────────────────────────────┘
          │                 │                 │
          └─────────────────┴─────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────────────┐
│                         网关层 (Gateway Layer)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Nginx / Traefik (Reverse Proxy)                   │   │
│  │  - 基于 Subdomain 路由: user1.agenthub.io → user1-container:8080    │   │
│  │  - TLS termination (Let's Encrypt)                                   │   │
│  │  - Rate limiting per tenant                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────────────────┐
│                      控制平面 (Control Plane)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    AgentHub API Server                               │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │   │
│  │  │  Tenant Mgr │ │ Instance Mgr│ │  Billing    │ │  Monitor    │  │   │
│  │  │  租户管理    │ │ 实例生命周期 │ │ 计量计费    │ │ 监控告警    │  │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │   │
│  │                                                                     │   │
│  │  技术栈: Python FastAPI + PostgreSQL + Redis                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │                    │                    │
          │                    │                    │
┌─────────▼──────────┐ ┌──────▼──────┐ ┌──────────▼──────────┐
│   数据平面          │ │  状态存储   │ │    镜像仓库         │
│ (Docker Host)      │ │             │ │                     │
│                    │ │             │ │                     │
│ ┌───────────────┐  │ │  PostgreSQL │ │  Docker Registry    │
│ │ user1-hermes  │  │ │  ( tenants, │ │  (hermes-base       │
│ │  Container    │  │ │   projects, │ │   image + layers)   │
│ │  :8080        │  │ │   tasks,    │ │                     │
│ └───────────────┘  │ │   instances)│ │                     │
│ ┌───────────────┐  │ └─────────────┘ └─────────────────────┘
│ │ user2-hermes  │  │
│ │  Container    │  │ ┌───────────────┐
│ │  :8081        │  │ │     Redis     │
│ └───────────────┘  │ │  (sessions,   │
│ ┌───────────────┐  │ │   queues,     │
│ │ user3-hermes  │  │ │   rate limits)│
│ │  Container    │  │ └───────────────┘
│ │  :8082        │  │
│ └───────────────┘  │
└────────────────────┘
```

---

## 3. 技术选型

### 3.1 前端技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| **框架** | React 19 + TypeScript | 生态最成熟，AI 工具链（Vercel AI SDK）支持最好 |
| **构建** | Vite | 冷启动快，HMR 极速，比 CRA 轻量 |
| **UI 组件** | shadcn/ui + Tailwind CSS | 可定制性强，不绑定特定设计系统 |
| **状态管理** | Zustand | 比 Redux 轻量，适合中小型应用 |
| **数据获取** | TanStack Query (React Query) | 自动缓存、重试、乐观更新 |
| **实时通信** | WebSocket (原生) | 任务状态实时推送 |
| **可视化** | ReactFlow (工作流编排) | 拖拽式 Agent 工作流设计器 |
| **代码编辑** | Monaco Editor | VS Code 同款，用于编辑 Prompt / 配置 |

**前端架构要点**:
- 用户登录后，前端拿到 tenant token，后续所有 API 请求带 `X-Tenant-ID` header
- 任务执行页面通过 WebSocket 接收实时日志流（SSE 备选）
- 提供"工作流编排器"：用户可拖拽连接不同 Agent 节点

### 3.2 后端技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| **API 框架** | Python FastAPI | 异步高性能、自动 OpenAPI 文档、Python 与 AI 生态无缝衔接 |
| **ORM** | SQLAlchemy 2.0 (async) | 成熟的 Python ORM，支持 async |
| **迁移** | Alembic | SQLAlchemy 官方迁移工具 |
| **任务队列** | Celery + Redis | 实例创建/销毁等耗时操作异步化 |
| **缓存** | Redis | Session、Rate Limit、Cache |
| **认证** | JWT (PyJWT) + OAuth2 | 标准、无状态、易扩展 |
| **容器编排** | Docker SDK for Python | 直接调用 Docker API 管理容器，比 K8s 轻量 |
| **配置管理** | Pydantic Settings | 类型安全的配置解析 |
| **日志** | structlog + JSON | 结构化日志，便于 ELK/Loki 收集 |

**后端模块划分**:
```
agenthub/
├── api/                    # FastAPI routers
│   ├── auth.py            # 认证 (注册/登录/Token)
│   ├── tenants.py         # 租户管理
│   ├── instances.py       # 实例生命周期 (CRUD + 启停)
│   ├── projects.py        # 项目 CRUD
│   ├── tasks.py           # 任务下发 / 状态查询
│   └── billing.py         # 用量查询 / 限额
├── core/                   # 核心业务逻辑
│   ├── tenant_manager.py  # 租户隔离逻辑
│   ├── instance_manager.py # Docker 容器管理
│   ├── model_proxy.py     # 模型 API 代理 / 计费拦截
│   └── scheduler.py       # 任务调度
├── models/                 # SQLAlchemy ORM models
├── schemas/                # Pydantic DTOs
├── workers/                # Celery 异步任务
├── docker/                 # Dockerfile templates
└── cli.py                  # 管理 CLI
```

### 3.3 部署技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| **容器引擎** | Docker CE + Docker Compose | 单机多租户最简方案，Swarm/K8s 后续平滑迁移 |
| **反向代理** | Traefik | 原生支持 Docker 服务发现，自动 Let's Encrypt，动态路由 |
| **数据库** | PostgreSQL 16 | 多租户推荐，支持 Row-Level Security (RLS) |
| **缓存/队列** | Redis 7 | 持久化 + Stream 数据结构 |
| **监控** | Prometheus + Grafana | 容器/主机/应用指标 |
| **日志** | Loki (Grafana 生态) | 轻量级日志聚合 |
| **CI/CD** | GitHub Actions | 构建 Hermes 基础镜像 |

**部署拓扑（单服务器 MVP）**:
```yaml
# docker-compose.yml (Control Plane)
version: "3.8"
services:
  traefik:
    image: traefik:v3.0
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

  api:
    image: agenthub-api:latest
    environment:
      - DATABASE_URL=postgresql://agenthub:xxx@postgres:5432/agenthub
      - REDIS_URL=redis://redis:6379
      - DOCKER_HOST=unix:///var/run/docker.sock
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # 管理数据平面容器

  postgres:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

  # 监控
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
```

---

## 4. 核心数据流

### 4.1 用户注册 & 实例创建

```
[用户] ──POST /auth/register──→ [AgentHub API]
                                      │
                                      ▼
                              [TenantManager]
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
            [PostgreSQL: tenants表]         [Celery Worker: create_instance]
                                                        │
                                                        ▼
                                              [Docker SDK: docker run]
                                                        │
                                                        ▼
                                              [启动 user-xxx-hermes 容器]
                                                        │
                    ┌───────────────────────────────────┘
                    ▼
            [Traefik 自动发现容器标签]
                    │
                    ▼
            [user1.agenthub.io 可访问]
```

### 4.2 任务下发 & 执行

```
[用户] ──POST /tasks──→ [AgentHub API]
                              │
                              ▼
                      [权限检查: 租户是否有活跃实例?]
                              │
                              ▼
                      [TaskManager 写入 tasks 表]
                              │
                              ▼
                      [WebSocket 推送: task_created]
                              │
                              ▼
                      [HTTP 转发到对应容器]
                              │  POST http://user1-hermes:8080/api/tasks
                              ▼
                      [容器内 Orchestrator 执行任务]
                              │
                              ▼
                      [WebSocket 回传实时日志]
                              │
                              ▼
                      [AgentHub API 更新任务状态]
```

### 4.3 模型 API 代理（计费拦截）

```
[容器内 Agent] ──调用 OpenRouter──→ [AgentHub ModelProxy]
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
            [用量计量: tokens/请求数]                 [租户配额检查]
                    │                                           │
                    ▼                                           ▼
            [PostgreSQL: usage_logs]              [超额? → 429 返回]
                    │
                    ▼
            [转发到真实 OpenRouter API]
```

**关键设计**: 所有容器内的外部 API 调用**不直接走公网**，而是经过 AgentHub 的 ModelProxy。这样平台可以：
- 统一计费、配额管控
- 审计所有模型调用
- 防止租户滥用/泄露 API key

---

## 5. 多租户隔离策略

### 5.1 隔离矩阵

| 资源 | 隔离方式 | 共享程度 |
|------|----------|----------|
| **计算** | Docker 容器（CPU/内存/GPU cgroup） | 完全隔离 |
| **文件系统** | Docker Volume per tenant | 完全隔离 |
| **网络** | 独立容器端口 + Traefik 路由 | 逻辑隔离 |
| **数据库** | PostgreSQL RLS (行级安全) | 共享实例，逻辑隔离 |
| **模型配置** | 租户级 `models.yaml` overlay | 基础共享，租户可覆盖 |
| **API Keys** | 平台统一代理，租户无感知 | 平台托管 |
| **SOP/模板** | 全局模板 + 租户自定义 | 基础共享 |

### 5.2 PostgreSQL 行级安全（RLS）

```sql
-- 所有业务表增加 tenant_id 列
ALTER TABLE tasks ADD COLUMN tenant_id UUID REFERENCES tenants(id);

-- 启用 RLS
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

-- 策略：用户只能看到自己的数据
CREATE POLICY tenant_isolation ON tasks
    USING (tenant_id = current_setting('app.current_tenant')::UUID);
```

这样即使 API 层有 bug，数据库层也保证租户数据不可越界。

---

## 6. Docker 容器设计

### 6.1 Hermes 基础镜像

```dockerfile
# Dockerfile.hermes-base
FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

# 安装 Hermes Agent 框架
COPY solo-company-architecture/ /app/solo-company/
RUN pip install -e /app/solo-company

# 安装常用 AI/ML 工具
RUN pip install openai anthropic pyyaml pydantic requests

# 预装 Claude Code / Codex CLI（可选）
# RUN npm install -g @anthropics/claude-code

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3   CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

ENTRYPOINT ["python", "-m", "solo_company.agent_server"]
```

### 6.2 容器标签（Traefik 服务发现）

```yaml
# 创建容器时自动附加的标签
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.user1.rule=Host(`user1.agenthub.io`)"
  - "traefik.http.services.user1.loadbalancer.server.port=8080"
  - "agenthub.tenant_id=user-xxx"
  - "agenthub.instance_id=inst-yyy"
```

### 6.3 资源配额模板

```python
# instance_manager.py
RESOURCE_TIERS = {
    "free":     {"cpu": "1.0",  "memory": "1g",  "gpu": None},
    "pro":      {"cpu": "2.0",  "memory": "4g",  "gpu": None},
    "team":     {"cpu": "4.0",  "memory": "8g",  "gpu": "nvidia.com/gpu=1"},
    "enterprise": {"cpu": "8.0", "memory": "16g", "gpu": "nvidia.com/gpu=2"},
}

docker.run(
    image="hermes-base:latest",
    name=f"hermes-{tenant_id}",
    cpu_quota=int(float(tier["cpu"]) * 100000),
    mem_limit=tier["memory"],
    device_requests=[DeviceRequest(count=1, capabilities=[["gpu"]])] if tier["gpu"] else None,
    volumes={f"hermes-data-{tenant_id}": {"bind": "/app/workspace", "mode": "rw"}},
    labels=traefik_labels,
    network="agenthub-tenant",
    detach=True,
)
```

---

## 7. 关键设计决策（Trade-offs）

### 7.1 为什么选 Docker SDK 而不是 Kubernetes？

| 维度 | Docker SDK | Kubernetes |
|------|-----------|------------|
| **复杂度** | 低，单文件 Python 调用 | 高，需掌握大量概念 |
| **运维成本** | 低，一台机器 docker-compose up | 高，需 etcd、控制平面 |
| **扩展性** | 中等，可平滑迁移到 Swarm | 极高，云原生标准 |
| **当前阶段** | ✅ **MVP 最优** | 用户量 > 1000 时迁移 |

**决策**: MVP 用 Docker SDK，架构预留 K8s 接口。当单机容器数 > 200 或需要多机时，迁移到 K8s + CRD。

### 7.2 为什么选 PostgreSQL RLS 而不是独立 DB per tenant？

| 维度 | 共享 DB + RLS | 独立 DB / Schema |
|------|--------------|-----------------|
| **资源开销** | 低，一个 PG 实例 | 高，每个租户一个 DB |
| **备份复杂度** | 低，全局备份 | 高，需按租户细粒度备份 |
| **扩展性** | 可水平分片 (Citus) | 连接数爆炸风险 |
| **隔离强度** | 逻辑隔离 + 策略兜底 | 物理隔离 |

**决策**: 共享 DB + RLS。对于 enterprise 租户可配置独立 schema 升级。

### 7.3 为什么容器内 Hermes 要暴露 HTTP API 而不是纯文件系统？

| 维度 | HTTP API | 文件系统共享 |
|------|---------|------------|
| **控制平面通信** | 标准、可审计 | 需挂载 volume，耦合重 |
| **安全性** | 可设防火墙规则 | volume 挂载增加攻击面 |
| **水平扩展** | 天然支持负载均衡 | 需共享存储 |

**决策**: 每个 Hermes 容器内运行轻量 HTTP server（FastAPI/Flask），AgentHub 通过 HTTP 与之通信。

---

## 8. MVP 范围定义

### Phase 1: 最小可行产品（4-6 周）

**必须包含**:
- [ ] 用户注册/登录（JWT 认证）
- [ ] 创建/删除 Hermes 实例（Docker 容器）
- [ ] 基础 Dashboard（查看实例状态、任务列表）
- [ ] 通过 Web UI 创建任务并下发到容器
- [ ] 任务日志实时查看（WebSocket/SSE）
- [ ] 基础配额限制（免费版 1 实例 + 每日 token 限额）

**技术栈锁定**:
- 前端: React + Vite + shadcn/ui
- 后端: FastAPI + PostgreSQL + Redis + Celery
- 部署: Docker Compose + Traefik
- 容器: Docker SDK for Python

### Phase 2: 产品化（4-6 周）

- [ ] 工作流编排器（ReactFlow 拖拽 Agent 流水线）
- [ ] 计费系统（Stripe 集成，按 token/实例时长计费）
- [ ] 团队/Workspace（一个租户下多个成员）
- [ ] 自定义模型配置（租户上传自己的 models.yaml）
- [ ] 模板市场（共享 SOP / Prompt 模板）

### Phase 3: 规模化（6-8 周）

- [ ] K8s 迁移（Operator 管理 Hermes Pod）
- [ ] 多区域部署（就近调度容器）
- [ ] GPU 集群调度（NVIDIA MPS / vGPU）
- [ ] 冷启动优化（Warm Pool 预创建容器）
- [ ] 企业级 SSO（SAML/OIDC）

---

## 9. 风险清单

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| **容器逃逸** | 🔴 高 | 中 | 非 root 运行、seccomp、AppArmor、定期安全扫描 |
| **资源耗尽** | 🔴 高 | 高 | cgroup 配额、自动扩缩容、租户级资源上限 |
| **冷启动慢** | 🟡 中 | 高 | Warm Pool 预加载、镜像瘦身、分层缓存 |
| **数据泄露** | 🔴 高 | 低 | RLS、卷加密、网络隔离、审计日志 |
| **Docker Socket 安全风险** | 🔴 高 | 中 | API 层过滤、只读 socket（docker-socket-proxy）、未来换 K8s API |
| **单点故障** | 🟡 中 | 中 | 数据库主从、Redis Sentinel、Traefik 多实例 |
| **模型 API 费用失控** | 🟡 中 | 高 | ModelProxy 配额拦截、实时用量告警、预付费模式 |

---

## 10. 下一步建议

1. **CTO 确认本方案后**，Dev Agent 可进入 Phase 1 实现
2. **优先搭建 Control Plane 骨架**：FastAPI + PostgreSQL + Docker SDK 的基础实例 CRUD
3. **同时并行**：前端 React 的 Dashboard 原型
4. **最后集成**：WebSocket 实时日志 + Traefik 动态路由

---

*文档结束*
