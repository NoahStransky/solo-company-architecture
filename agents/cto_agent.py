"""CTO Agent — 技术负责人自动化工作流封装."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.model_router import ModelRouter


@dataclass
class ReviewResult:
    """代码审查结果."""

    verdict: str  # APPROVE/REQUEST_CHANGES/COMMENT
    comments: List[str] = field(default_factory=list)
    checklist: Dict[str, bool] = field(default_factory=dict)


@dataclass
class ArchitectureReview:
    """架构审查结果."""

    approved: bool = False
    feedback: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class CTOAgent:
    """CTO Agent — 负责架构设计、代码审查和技术决策."""

    def __init__(self, model_router: Optional[ModelRouter] = None):
        self.model_router = model_router or ModelRouter()

    def review_code(self, diff: str) -> ReviewResult:
        """审查代码 diff，输出 approve/request_changes/comment."""
        comments: List[str] = []
        checklist: Dict[str, bool] = {
            "no_secrets": "password" not in diff.lower() and "secret" not in diff.lower(),
            "error_handling": "try" in diff or "except" in diff or "raise" in diff,
            "tests_included": "test" in diff.lower(),
            "no_debug_code": "print(" not in diff and "debugger" not in diff.lower(),
        }

        if not checklist["no_secrets"]:
            comments.append("Potential secret/credential detected in diff")
        if not checklist["error_handling"]:
            comments.append("Missing error handling patterns")
        if not checklist["tests_included"]:
            comments.append("No tests detected in diff")
        if not checklist["no_debug_code"]:
            comments.append("Debug code (print/debugger) should be removed")

        failed = sum(1 for v in checklist.values() if not v)
        if failed == 0:
            verdict = "APPROVE"
        elif failed <= 2:
            verdict = "COMMENT"
        else:
            verdict = "REQUEST_CHANGES"

        return ReviewResult(
            verdict=verdict,
            comments=comments,
            checklist=checklist,
        )

    def review_architecture(self, spec: str) -> ArchitectureReview:
        """审查架构设计."""
        feedback: List[str] = []
        recommendations: List[str] = []
        approved = True

        spec_lower = spec.lower()
        if "scalability" not in spec_lower and "scale" not in spec_lower:
            recommendations.append("Consider documenting scalability strategy")
        if "security" not in spec_lower:
            recommendations.append("Add security considerations section")
        if "database" not in spec_lower and "data model" not in spec_lower:
            feedback.append("Data layer not explicitly defined")
        if "api" not in spec_lower:
            feedback.append("API surface not described")

        if len(feedback) > 1:
            approved = False

        return ArchitectureReview(
            approved=approved,
            feedback=feedback,
            recommendations=recommendations,
        )

    def merge_pr(self, pr_number: int) -> bool:
        """执行 merge（模拟，返回 bool）."""
        return pr_number > 0
