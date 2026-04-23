# 🏢 Solo Company Architecture

> 一人公司的完整组织架构与运营体系

## 💡 核心理念

一人公司不是"一个人做所有杂事"，而是**一个人扮演多个专业角色**，通过标准化流程（SOP）和自动化工具，实现大公司的专业产出效率。

每个角色都有明确的：
- 📋 职责边界（Responsibilities）
- 🎯 决策权限（Authority）
- 📐 产出标准（Deliverables）
- 🤖 自动化工具（Tools）

---

## 🏛️ 组织架构

```
                    ┌─────────────┐
                    │     CEO     │
                    │  (你本人)   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │    CTO      │ │  CPO/PM     │ │   Growth    │
    │  技术负责人  │ │  产品负责人  │ │  增长负责人  │
    └──────┬──────┘ └─────────────┘ └─────────────┘
           │
    ┌──────┼──────┐
    │      │      │
┌───▼──┐ ┌─▼────┐ ┌─▼────┐ ┌─▼──────┐
│Backend│ │Frontend│ │AI/ML│ │DevOps  │
└───────┘ └────────┘ └─────┘ └────────┘
```

---

## 📂 目录结构

```
solo-company-architecture/
├── README.md                    # 本文件
├── org-chart/                   # 组织架构详情
│   ├── 01-ceo.md               # CEO 职责与决策框架
│   ├── 02-cto.md               # CTO 职责与技术架构
│   ├── 03-cpo.md               # 产品经理职责
│   ├── 04-growth.md            # 增长运营职责
│   └── 05-dev-roles.md         # 开发团队角色定义
├── sops/                        # 标准操作流程
│   ├── product-development.md  # 产品开发 SOP
│   ├── release-process.md      # 发布流程 SOP
│   ├── decision-matrix.md      # 决策矩阵
│   └── weekly-review.md        # 周回顾模板
└── tools/                       # 工具栈推荐
    ├── dev-stack.md
    ├── product-stack.md
    └── automation-stack.md
```

---

## 🎭 角色速览

| 角色 | 核心问题 | 关键产出 | 每周投入 |
|------|---------|---------|---------|
| **CEO** | "我们要去哪里？" | 战略文档、OKR、融资/收入 | 20% |
| **CTO** | "怎么技术上实现？" | 架构设计、技术选型、代码规范 | 30% |
| **CPO/PM** | "用户真正需要什么？" | PRD、用户故事、原型 | 20% |
| **Growth** | "怎么让更多人知道？" | 内容、SEO、社区运营 | 20% |
| **Developer** | "怎么写出好代码？" | 功能实现、Bug 修复、文档 | 40% |

> 注：投入总和 > 100% 是因为一人多岗，时间重叠利用

---

## 🚀 快速开始

1. 阅读 [`org-chart/01-ceo.md`](org-chart/01-ceo.md) 理解整体框架
2. 根据你的项目类型，重点阅读 CTO 或 CPO 文档
3. 将 [`sops/decision-matrix.md`](sops/decision-matrix.md) 打印出来贴墙上
4. 参考 [`tools/`](tools/) 搭建你的工具栈

---

## 📝 License

MIT — 自由使用、修改、分享
