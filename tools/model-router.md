# Model Router

## 为什么需要模型路由？

不同 Agent 角色对模型的认知能力需求不同：

| 角色 | 任务类型 | 需要的能力 | 推荐模型 |
|------|---------|-----------|---------|
| CTO | 架构设计、技术选型 | 深度推理、长程规划 | Opus/GPT-5 |
| Dev | 编码实现、TDD | 代码准确性、上下文理解 | Sonnet/GPT-4o |
| QA | 测试验证 | 快速执行、低成本 | Haiku/GPT-4o-mini |
| Secretary | 协调汇总 | 平衡速度与推理 | Sonnet/GPT-4o |

## 使用方式

Model Router 由 Secretary 在 dispatch Agent 时使用：

```python
from agent_orchestrator import AgentRegistry, ModelRouter

# Secretary dispatch
agent_name = "cto"
model_config = ModelRouter.resolve(agent_name, project_id="project-a")
# → {"model": "anthropic/claude-opus-4", "provider": "openrouter"}

delegate_task(
    goal="Design architecture for newsletter feature",
    model=model_config,
)
```

## 配置层级

1. **全局默认** (`config/models.yaml`)
2. **项目覆盖** (`config/models.yaml` → `projects.*`)
3. **任务覆盖** (Secretary 可临时调整)

## 降级策略

```
primary model ──→ timeout/error ──→ fallback model
     │
     └─→ 429 rate limit ──→ wait 60s ──→ retry
```

## 成本追踪

每个任务自动记录：
- 使用的模型
- input/output tokens
- 预估成本

用于月度账单分析。
