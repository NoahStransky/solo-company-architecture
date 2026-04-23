import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure agents/ is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

# Mock ModelRouter *before* importing agent_orchestrator so the module loads
_mock_model_router = MagicMock()
_mock_model_router.ModelRouter = MagicMock()
_mock_model_router.ModelRouter.resolve.return_value = {
    "tier": "reasoning",
    "default": "anthropic/claude-opus-4",
    "fallback": "openai/gpt-5",
    "max_tokens": 64000,
    "temperature": 0.2,
}

with patch.dict("sys.modules", {"core.model_router": _mock_model_router}):
    import agent_orchestrator as orch


@pytest.fixture(autouse=True)
def tmp_workspace(monkeypatch):
    """Redirect WORKSPACE to a temporary directory for every test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(orch, "WORKSPACE", Path(tmpdir))
        yield Path(tmpdir)


class TestAgentRegistry:
    def test_agents_contain_model_tier(self):
        """AgentRegistry.AGENTS 每个条目应包含 model_tier 字段."""
        for name, info in orch.AgentRegistry.AGENTS.items():
            assert "model_tier" in info, f"Agent '{name}' 缺少 model_tier"
            # 校验 model_tier 不为空
            assert isinstance(info["model_tier"], str) and info["model_tier"]


class TestSecretary:
    def test_context_package_contains_model_config(self):
        """generate_context_package 应在返回的 package 中包含 model_config."""
        secretary = orch.Secretary()
        task = secretary.create_task("测试任务", ["cpo", "cto", "dev"])
        package = secretary.generate_context_package(task, "cpo")

        assert "model_config" in package
        assert package["model_config"] == _mock_model_router.ModelRouter.resolve.return_value

        # 确保 resolve 被正确调用
        _mock_model_router.ModelRouter.resolve.assert_called_with("cpo")

    def test_context_package_structure_unchanged(self):
        """除了新增的 model_config，其他字段保持不变."""
        secretary = orch.Secretary()
        task = secretary.create_task("另一测试任务", ["cto"])
        package = secretary.generate_context_package(task, "cto")

        expected_keys = {
            "task_id",
            "agent",
            "agent_role",
            "agent_description",
            "task_description",
            "previous_outputs",
            "output_format",
            "output_requirements",
            "timestamp",
            "model_config",
        }
        assert set(package.keys()) == expected_keys
