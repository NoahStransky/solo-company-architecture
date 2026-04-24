"""Tests for agents.cto_agent."""

from unittest.mock import patch, MagicMock

import pytest

from agents.cto_agent import CTOAgent, ReviewResult, ArchitectureReview


@pytest.fixture
def mock_router():
    return MagicMock()


@pytest.fixture
def agent(mock_router):
    with patch("agents.cto_agent.ModelRouter", return_value=mock_router):
        return CTOAgent(model_router=mock_router)


class TestCTOAgent:
    def test_review_code_clean_diff_returns_approve(self, agent):
        diff = """
        def add(a, b):
            try:
                return a + b
            except TypeError:
                raise ValueError("Invalid types")
        
        def test_add():
            assert add(1, 2) == 3
        """
        result = agent.review_code(diff)

        assert isinstance(result, ReviewResult)
        assert result.verdict == "APPROVE"
        assert result.comments == []
        assert result.checklist["no_secrets"] is True
        assert result.checklist["error_handling"] is True
        assert result.checklist["tests_included"] is True
        assert result.checklist["no_debug_code"] is True

    def test_review_code_with_password_or_secret_returns_request_changes(self, agent):
        diff = 'password = "super_secret_123"\nsecret_key = "abc"'
        result = agent.review_code(diff)

        assert isinstance(result, ReviewResult)
        assert result.verdict == "REQUEST_CHANGES"
        assert any("secret/credential" in c for c in result.comments)
        assert result.checklist["no_secrets"] is False

    def test_review_code_with_debug_code_returns_comment(self, agent):
        diff = """
        def debug_add(a, b):
            print(f"Adding {a} and {b}")
            try:
                return a + b
            except TypeError:
                raise ValueError("Invalid types")
        
        def test_debug_add():
            assert debug_add(1, 2) == 3
        """
        result = agent.review_code(diff)

        assert isinstance(result, ReviewResult)
        # debug code triggers no_debug_code failure, but other checks pass (2 failures max -> COMMENT)
        assert result.verdict == "COMMENT"
        assert any("Debug code" in c for c in result.comments)
        assert result.checklist["no_debug_code"] is False

    def test_review_architecture_returns_architecture_review(self, agent):
        spec = """
        This system handles scalability via horizontal scaling.
        Security is ensured through OAuth2 and TLS.
        The database layer uses PostgreSQL with a defined data model.
        API endpoints are documented via OpenAPI.
        """
        result = agent.review_architecture(spec)

        assert isinstance(result, ArchitectureReview)
        assert result.approved is True
        assert result.feedback == []
        assert result.recommendations == []

    def test_merge_pr_returns_bool(self, agent):
        assert agent.merge_pr(42) is True
        assert agent.merge_pr(1) is True
        assert agent.merge_pr(0) is False
        assert agent.merge_pr(-1) is False
