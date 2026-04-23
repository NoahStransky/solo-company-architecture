# 🤖 AI Agent Team — Solo Company Edition

> 把一人公司升级为 AI Agent 协作体系

## 💡 核心理念

你不是一个人在战斗。每个公司角色（CEO、CTO、CPO、Growth）都对应一个 **AI Agent**，他们有自己的：

- **🧠 System Prompt** — 角色定义、思维模式
- **🛠️ Skills** — 专属工具和能力
- **📋 SOP** — 标准操作流程
- **📊 Memory** — 项目上下文和历史决策

**你（CEO）→ CEO 秘书（我）→ Agent 团队 → 执行 → 汇报 → 总结**

---

## 🏛️ Agent 组织架构

```
                        ┌─────────────┐
                        │     CEO     │
                        │   (你本人)   │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │ CEO Secretary│ ← 我
                        │  协调/拆解   │
                        └──────┬──────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
    ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
    │  CTO Agent  │   │  CPO Agent  │   │Growth Agent │
    │  技术实现    │   │  需求分析    │   │ 增长运营     │
    └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
           │                   │                   │
    ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
    │ Dev Agents  │   │  Analyst    │   │  Writer     │
    │ 编码执行     │   │  数据分析师  │   │  内容创作    │
    └─────────────┘   └─────────────┘   └─────────────┘
```

---

## 📋 Agent 目录

| Agent | 职责 | 核心技能 | 对应文件 |
|-------|------|---------|---------|
| **CEO Secretary** | 需求接收、任务拆解、进度追踪、汇报总结 | 沟通协调、任务分配 | `01-secretary.md` |
| **CTO Agent** | 技术架构、技术选型、代码审查 | 架构设计、技术评估 | `02-cto-agent.md` |
| **CPO Agent** | 需求分析、PRD 撰写、用户体验 | 用户研究、产品设计 | `03-cpo-agent.md` |
| **Growth Agent** | 内容营销、SEO、数据分析 | 增长实验、内容创作 | `04-growth-agent.md` |
| **Dev Agent** | 编码实现、测试、部署 | 编程、调试、DevOps | `05-dev-agent.md` |
| **Analyst Agent** | 数据分析、竞品研究、报告生成 | 数据处理、可视化 | `06-analyst-agent.md` |

---

## 🔄 标准协作流程

### 流程 1：新项目启动

```
CEO: "我要做一个 AI 新闻聚合工具"
    ↓
Secretary: 拆解任务 → 启动 CPO Agent 做需求分析
    ↓
CPO Agent: 输出用户画像 + PRD → 返回 Secretary
    ↓
Secretary: 将 PRD 同步给 CTO Agent 做技术评估
    ↓
CTO Agent: 输出技术方案 + 工作量估算 → 返回 Secretary
    ↓
Secretary: 汇总方案 → CEO 确认 → 启动 Dev Agent 开发
    ↓
Dev Agent: 编码实现 → 返回 Secretary
    ↓
Secretary: CTO Agent 代码审查 → 返回 Secretary
    ↓
Secretary: 汇总最终报告 → CEO
```

### 流程 2：日常迭代

```
CEO: "加一个邮件订阅功能"
    ↓
Secretary: 直接启动 Dev Agent（已有上下文）
    ↓
Dev Agent: 实现 → 返回
    ↓
Secretary: CTO Agent 快速审查 → Growth Agent 准备推广文案
    ↓
Secretary: 汇总 → CEO
```

---

## 🚀 快速开始

1. 阅读 [`01-secretary.md`](01-secretary.md) 了解协调机制
2. 根据项目类型，重点配置对应 Agent 的 Prompt
3. 在 `workflows/` 目录定义你的项目专属流程

---

## 📝 设计原则

1. **Single Source of Truth** — Secretary 是所有信息的汇聚点
2. **Context Handoff** — Agent 之间传递的是结构化上下文，不是原始对话
3. **Fail Fast** — 任何 Agent 卡住时，Secretary 立即升级给 CEO
4. **Human in the Loop** — 关键决策（发布、架构变更）必须 CEO 确认
