# 🖥️ CTO — 首席技术官

> "怎么技术上实现？"

## 🎯 核心职责

CTO 的核心不是写最多的代码，而是**用技术实现商业目标，同时控制技术债务和风险**。

### 1. 技术架构（Architecture）
- 选择技术栈（Language, Framework, Database, Infra）
- 设计系统架构（单体 vs 微服务，同步 vs 异步）
- 定义数据模型和 API 规范

### 2. 开发流程（Development Process）
- 代码规范（Linting, Formatting, Naming）
- Git 工作流（Git Flow / Trunk Based）
- CI/CD 流水线（自动化测试、构建、部署）
- 代码审查（即使一个人，也要有 Self-Review 标准）

### 3. 技术债务管理（Tech Debt）
- 区分 "今天必须修" 和 "下个月再说"
- 定期重构计划（每 2 周留 10% 时间还债）

### 4. 工程师文化（Engineering Culture）
- 写文档（README, ADR, API Docs）
- 自动化测试（单元测试、集成测试覆盖率目标）
- 监控和告警（错误率、性能指标）

---

## 🎛️ 决策权限

| 决策类型 | CTO 权限 | 备注 |
|---------|---------|------|
| 技术栈选择 | ✅ 最终决定 | CEO 可提需求但不干预技术选型 |
| 代码规范 | ✅ 完全授权 | 所有代码必须遵守 |
| 架构设计 | ✅ 最终决定 | 重大变更需知会 CEO |
| 第三方服务选型 | ⚠️ 协商决定 | 涉及持续费用的需 CEO 确认 |
| 发布日期 | ⚠️ 协商决定 | 与 CEO 共同决定，CTO 提供技术评估 |
| 招聘技术外包 | ⚠️ 推荐权 | CEO 做最终决定 |
| 产品功能取舍 | ❌ 不决定 | 可提出技术可行性意见 |

---

## 📐 关键产出物

### 1. 技术栈文档（Tech Stack Doc）
```markdown
## 技术栈 v1.0

### 前端
- Framework: React 18 + TypeScript
- Styling: Tailwind CSS
- State: Zustand
- Build: Vite

### 后端
- Runtime: Python 3.11
- Framework: FastAPI
- Database: PostgreSQL 15
- Cache: Redis
- Queue: Celery + Redis

### 基础设施
- Hosting: Vercel (Frontend) + Railway (Backend)
- Database: Supabase (Managed Postgres)
- Storage: AWS S3
- Monitoring: Sentry + UptimeRobot

### 选型理由
1. 快速开发（一人公司需要速度）
2. 托管服务（减少运维负担）
3. 社区活跃（有问题能快速找到答案）
```

### 2. ADR（Architecture Decision Record）模板
```markdown
## ADR-001: 选择 FastAPI 而非 Django

### 背景
需要构建一个高性能的 REST API 服务。

### 决策
使用 FastAPI。

### 原因
- 自动 API 文档生成（减少写文档时间）
- 异步原生支持（高并发场景）
- Python 类型提示（减少运行时错误）

### 后果
- 需要学习异步编程模式
- 生态比 Django 小，但足够用

### 状态
✅ Accepted — 2026-04-23
```

### 3. 开发环境设置指南
```markdown
## 本地开发 setup

```bash
# 1. 克隆仓库
git clone ...
cd project

# 2. 安装依赖
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. 环境变量
cp .env.example .env
# 编辑 .env 填入本地配置

# 4. 启动
docker-compose up -d db redis
python main.py
```

## 代码规范
- 使用 Black 格式化
- 使用 Ruff 检查
- 类型注解覆盖率 > 80%
- 核心逻辑必须有单元测试
```

---

## 🏗️ 开发团队角色定义

即使一人公司，你也要在代码层面区分"谁在写什么"。

### Backend Developer（后端工程师）
- 负责 API 设计、数据库模型、业务逻辑
- 关注点：数据一致性、性能、安全

### Frontend Developer（前端工程师）
- 负责 UI 实现、交互逻辑、用户体验
- 关注点：加载速度、响应式、无障碍

### AI/ML Engineer（算法工程师）
- 负责模型训练、Prompt Engineering、数据处理
- 关注点：准确率、延迟、成本

### DevOps Engineer（运维工程师）
- 负责部署、监控、CI/CD、基础设施
- 关注点：可用性、成本、安全

> 💡 **技巧**：给自己创建不同的 Git 分支命名规范，模拟团队协作
> - `feature/backend-api-v2` — 后端视角
> - `feature/frontend-dashboard` — 前端视角
> - `fix/devops-deploy-script` — 运维视角

---

## ⏰ CTO 时间分配建议

| 时间段 | 活动 |
|-------|------|
| 每天 1h | 核心功能开发 |
| 每天 30min | Code Review（自己的代码隔天 review） |
| 每周 2h | 技术债务清理 |
| 每周 1h | 文档更新 |
| 每月 2h | 技术栈评估（是否需要升级/替换） |

---

## ⚠️ CTO 常见陷阱

1. **过度工程（Over-engineering）**
   - ❌ "我要用微服务 + Kubernetes"
   - ✅ "单体应用 + 托管平台，能撑到 1 万用户"

2. **忽视文档**
   - 一个月后你会忘记自己为什么这样写
   - 每个项目必须有 README + ADR

3. **完美主义**
   - 测试覆盖率 100% 不如先上线验证
   - MVP 阶段：能跑 > 完美

4. **不监控线上**
   - 必须知道系统什么时候挂了

---

## 🔗 相关文档

- [产品开发 SOP](../sops/product-development.md)
- [发布流程 SOP](../sops/release-process.md)
- [Dev 角色详情](05-dev-roles.md)
