# SOP-001: Bug Fix & Issue Resolution Workflow

## Overview

Standard operating procedure for handling GitHub issues, bug reports, and feature requests within the Solo Company AI Agent system.

**Principle:** No code touches `main` without TDD + independent QA + Code Review.

---

## Workflow Diagram

```
CEO (Human)
    │
    │ "Fix issue #1: page has placeholder"
    ▼
Secretary Agent
    │
    │ 1. Read issue, create Context Package
    │ 2. Decide: need CTO? (new feature=yes, bugfix=no)
    │ 3. Dispatch Dev Agent
    ▼
Dev Agent
    │
    ├─ Step 1: Search Codebase
    │     └── read_file / search_files all relevant modules
    │
    ├─ Step 2: Plan
    │     └── Write implementation plan (files, tests, risks)
    │
    ├─ Step 3: TDD Cycle (RED → GREEN → REFACTOR)
    │     └── RED: write failing test FIRST
    │     └── GREEN: write minimum code to pass
    │     └── REFACTOR: clean up, keep tests green
    │
    ├─ Step 4: Create Feature Branch
    │     └── git checkout -b fix/issue-N-description
    │
    ├─ Step 5: Commit & Push
    │     └── git add / git commit / git push origin fix/issue-N-xxx
    │
    └─ Step 6: Report to Secretary
          └── "Branch pushed, tests passing locally"
    │
    ▼
Secretary Agent
    │
    │ 4. Dispatch QA Agent (MUST be different from Dev)
    ▼
QA Agent
    │
    ├─ Step 1: Checkout Branch
    │     └── git fetch && git checkout fix/issue-N-xxx
    │
    ├─ Step 2: Run Full Test Suite
    │     └── pytest tests/ -v
    │
    ├─ Step 3: Manual Validation
    │     └── Check deployment, behavior, edge cases
    │
    └─ Step 4: Report to Secretary
          └── PASS or FAIL with evidence
    │
    ▼
Secretary Agent
    │
    │ 5. If FAIL → back to Dev Agent (with QA report)
    │    If PASS → dispatch Dev Agent to open PR
    ▼
Dev Agent
    │
    └─ Create PR with:
         - Title: "fix: ..."
         - Body: "Fixes #N"
         - Link to issue
    │
    ▼
Secretary Agent
    │
    │ 6. Dispatch CTO/Senior Agent for Code Review
    ▼
CTO Agent
    │
    ├─ Review architecture alignment
    ├─ Check edge cases
    ├─ Verify test coverage
    └─ Approve or Request Changes
    │
    ▼
Secretary Agent
    │
    │ 7. If approved → merge PR
    │    git merge --no-ff fix/issue-N-xxx
    │    git push origin main
    │    git branch -d fix/issue-N-xxx
    │
    │ 8. Verify CI/CD post-merge
    │    Check GitHub Actions + Pages deployment
    │
    │ 9. Issue auto-closed by "Fixes #N" in PR/commit
    │
    │ 10. Report to CEO
    ▼
CEO
    └── "Done. Issue #1 closed, deployed."
```

---

## Agent Responsibilities

| Agent | Can Do | Cannot Do |
|-------|--------|-----------|
| **Secretary** | Dispatch, track, merge approved PRs, verify CI/CD | Write code, commit to main directly |
| **CTO** | Architecture design, code review, tech decisions | Write implementation code |
| **Dev** | Search codebase, plan, TDD, branch dev, open PR | Skip tests, push to main, skip plan |
| **QA** | Checkout branch, run tests, validate, report | Modify code, be same agent as Dev |

---

## Branch Naming Convention

```
fix/issue-N-short-desc     # Bug fixes
feat/TASK-XXX-short-desc   # New features
refactor/module-name       # Refactoring
docs/update-readme         # Documentation
```

---

## Commit Message Convention

```
<type>: <subject>

<body>

Fixes #N
```

Types: `fix`, `feat`, `test`, `refactor`, `docs`, `chore`

---

## State Transitions

```
issue_opened
    ↓
dispatched_to_dev
    ↓
branch_created
    ↓
implementation_complete
    ↓
qa_testing
    ↓ (fail)
back_to_dev ───────┐
    ↓ (pass)       │
pr_opened          │
    ↓              │
in_review          │
    ↓ (reject)     │
back_to_dev ───────┘
    ↓ (approve)
merged
    ↓
deploy_verified
    ↓
issue_closed
```

---

## Escalation Rules

| Situation | Action |
|-----------|--------|
| Dev Agent timeout | Secretary re-dispatches new Dev Agent |
| QA finds regression | Block merge, Dev fixes, re-QA |
| CTO rejects PR | Dev addresses, re-open PR, re-review |
| CI/CD fails post-merge | Secretary immediately alerts CEO |
| Circular dependency in projects | DependencyManager raises CycleError, escalate to CTO |

---

## Checklist (Secretary use)

- [ ] Issue read and understood
- [ ] Context Package assembled for Dev
- [ ] Dev completed: search → plan → TDD → branch → push
- [ ] QA is independent agent (≠ Dev)
- [ ] QA report: PASS with evidence
- [ ] PR opened with `Fixes #N`
- [ ] CTO/Senior reviewed and approved
- [ ] Merged to main via PR
- [ ] CI/CD verified post-merge
- [ ] Issue closed
- [ ] CEO reported
