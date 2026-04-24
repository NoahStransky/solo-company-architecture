"""Tests for agents.secretary_agent."""

import re
from unittest.mock import patch, MagicMock

import pytest

from agents.secretary_agent import SecretaryAgent, Task, DevResult, QAResult, TaskStatus


@pytest.fixture
def mock_router():
    return MagicMock()


@pytest.fixture
def agent(mock_router):
    with patch("agents.secretary_agent.ModelRouter", return_value=mock_router):
        return SecretaryAgent(model_router=mock_router)


class TestSecretaryAgent:
    def test_create_task_returns_task_with_valid_id_and_pending_status(self, agent):
        task = agent.create_task("Implement feature X", {"priority": "high"})

        assert isinstance(task, Task)
        assert task.status == "pending"
        assert re.match(r"TASK-\d{8}-\d{6}-[a-f0-9]{6}", task.id)
        assert task.goal == "Implement feature X"
        assert task.context == {"priority": "high"}
        assert task.id in agent._tasks

    def test_delegate_to_dev_success_and_branch_naming(self, agent):
        task = agent.create_task("Implement feature Y", {})
        result = agent.delegate_to_dev(task, "/path/to/code")

        assert isinstance(result, DevResult)
        assert result.success is True
        expected_branch = f"feat/{task.id.lower().replace('-', '_')}"
        assert result.branch == expected_branch
        assert result.message == "Dev completed implementation for /path/to/code"
        assert task.branch == expected_branch
        assert task.status == "in_progress"
        assert agent._dev_results[task.id] == result

    def test_delegate_to_dev_raises_valueerror_for_unknown_task(self, agent):
        unknown_task = Task(id="TASK-UNKNOWN-001", goal="", context={})
        with pytest.raises(ValueError, match="Unknown task: TASK-UNKNOWN-001"):
            agent.delegate_to_dev(unknown_task, "/path/to/code")

    def test_delegate_to_qa_success(self, agent):
        task = agent.create_task("Implement feature Z", {})
        result = agent.delegate_to_qa(task, "feat/test-branch")

        assert isinstance(result, QAResult)
        assert result.passed is True
        assert result.tests_run == 42
        assert result.tests_failed == 0
        assert result.report == "All tests passed on branch feat/test-branch"
        assert agent._qa_results[task.id] == result

    def test_track_status_progresses_through_phases(self, agent):
        task = agent.create_task("Track me", {})

        # Phase 1: pending
        status = agent.track_status(task.id)
        assert isinstance(status, TaskStatus)
        assert status.task_id == task.id
        assert status.status == "pending"
        assert status.current_phase == "pending"

        # Phase 2: dev_complete
        agent.delegate_to_dev(task, "/code")
        status = agent.track_status(task.id)
        assert status.status == "in_progress"
        assert status.current_phase == "dev_complete"

        # Phase 3: qa_complete
        agent.delegate_to_qa(task, task.branch)
        status = agent.track_status(task.id)
        assert status.current_phase == "qa_complete"

    def test_track_status_unknown_task(self, agent):
        status = agent.track_status("TASK-NONEXISTENT-999999")
        assert status.status == "unknown"
        assert status.current_phase == ""
        assert status.message == "Task not found"

    def test_report_to_ceo_formatting(self, agent):
        report = agent.report_to_ceo("Sprint completed successfully")
        assert report == "[CEO Report] Sprint completed successfully"
