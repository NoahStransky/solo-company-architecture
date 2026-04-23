#!/usr/bin/env python3
"""
Agent Orchestrator — AI Agent 团队协作调度器

用法：
    python agent_orchestrator.py --task "开发一个AI新闻摘要功能" --agents cpo,cto,dev

设计原则：
1. 每个 Agent 是一个独立的工作单元，有明确的输入和输出
2. Secretary 负责协调，不直接执行技术工作
3. 状态持久化，支持断点续跑
4. 所有产出写入 workspace/，方便审查
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from core.model_router import ModelRouter

WORKSPACE = Path(__file__).parent / "workspace"
WORKSPACE.mkdir(exist_ok=True)


@dataclass
class Task:
    id: str
    description: str
    agents: List[str]
    status: str = "pending"  # pending, running, completed, failed
    current_phase: str = ""
    outputs: Dict[str, dict] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


class AgentRegistry:
    """Agent 注册表：定义每个 Agent 的角色、Prompt 和输出规范。"""

    AGENTS = {
        "secretary": {
            "name": "CEO Secretary",
            "role": "协调者",
            "prompt_file": "01-secretary.md",
            "output_format": "task_plan.json",
            "description": "需求拆解、任务分配、进度追踪、结果汇总",
            "model_tier": "coding",
        },
        "cpo": {
            "name": "CPO Agent",
            "role": "产品负责人",
            "prompt_file": "03-cpo-agent.md",
            "output_format": "prd.md",
            "description": "需求分析、PRD 撰写、用户画像",
            "model_tier": "reasoning",
        },
        "cto": {
            "name": "CTO Agent",
            "role": "技术负责人",
            "prompt_file": "02-cto-agent.md",
            "output_format": "tech_spec.md",
            "description": "架构设计、技术选型、代码审查",
            "model_tier": "reasoning",
        },
        "dev": {
            "name": "Dev Agent",
            "role": "开发工程师",
            "prompt_file": "05-dev-agent.md",
            "output_format": "implementation.md",
            "description": "编码实现、测试、部署",
            "model_tier": "coding",
        },
        "growth": {
            "name": "Growth Agent",
            "role": "增长负责人",
            "prompt_file": "04-growth-agent.md",
            "output_format": "content_plan.md",
            "description": "内容营销、增长实验、社区运营",
            "model_tier": "coding",
        },
        "analyst": {
            "name": "Analyst Agent",
            "role": "数据分析师",
            "prompt_file": "06-analyst-agent.md",
            "output_format": "analysis_report.md",
            "description": "数据处理、竞品研究、报告生成",
            "model_tier": "reasoning",
        },
    }

    @classmethod
    def get_agent(cls, name: str) -> dict:
        return cls.AGENTS.get(name, {})

    @classmethod
    def list_agents(cls) -> List[str]:
        return list(cls.AGENTS.keys())


class Secretary:
    """
    CEO Secretary — 协调核心

    注意：这里的 "execute" 不是直接运行代码，而是：
    1. 根据 Agent 定义生成完整的 Context Package
    2. 输出到 workspace/，供外部 AI（如 Claude Code / Codex）执行
    3. 收集执行结果，更新任务状态
    """

    def __init__(self):
        self.tasks_file = WORKSPACE / "tasks.json"
        self.tasks: Dict[str, Task] = {}
        self._load_tasks()

    def _load_tasks(self):
        if self.tasks_file.exists():
            data = json.loads(self.tasks_file.read_text())
            for tid, tdata in data.items():
                self.tasks[tid] = Task(**tdata)

    def _save_tasks(self):
        data = {tid: t.__dict__ for tid, t in self.tasks.items()}
        self.tasks_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def create_task(self, description: str, agents: List[str]) -> Task:
        """CEO 提出需求，Secretary 创建任务。"""
        task_id = f"TASK-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        task = Task(id=task_id, description=description, agents=agents)
        self.tasks[task_id] = task
        self._save_tasks()
        print(f"[Secretary] 任务创建: {task_id}")
        print(f"[Secretary] 描述: {description}")
        print(f"[Secretary] 参与 Agent: {', '.join(agents)}")
        return task

    def generate_context_package(self, task: Task, agent_name: str) -> dict:
        """为指定 Agent 生成上下文包。"""
        agent_info = AgentRegistry.get_agent(agent_name)
        if not agent_info:
            raise ValueError(f"未知 Agent: {agent_name}")

        # 收集前置 Agent 的输出作为上下文
        previous_outputs = {}
        agent_order = task.agents
        current_idx = agent_order.index(agent_name)
        for prev_agent in agent_order[:current_idx]:
            if prev_agent in task.outputs:
                previous_outputs[prev_agent] = task.outputs[prev_agent]

        package = {
            "task_id": task.id,
            "agent": agent_name,
            "agent_role": agent_info["role"],
            "agent_description": agent_info["description"],
            "task_description": task.description,
            "previous_outputs": previous_outputs,
            "output_format": agent_info["output_format"],
            "output_requirements": self._get_output_requirements(agent_name),
            "timestamp": datetime.now().isoformat(),
            "model_config": ModelRouter.resolve(agent_name),
        }
        return package

    def _get_output_requirements(self, agent_name: str) -> List[str]:
        """定义每个 Agent 的输出要求。"""
        requirements = {
            "cpo": [
                "用户画像（Who）",
                "核心痛点（Problem）",
                "功能优先级（Must Have / Nice to Have）",
                "用户故事（User Stories）",
                "验收标准（Acceptance Criteria）",
            ],
            "cto": [
                "技术架构图或文字描述",
                "技术选型及理由",
                "数据模型/API 设计",
                "工作量估算（乐观/最可能/悲观）",
                "风险评估与缓解方案",
            ],
            "dev": [
                "变更文件清单",
                "核心实现逻辑说明",
                "测试用例及结果",
                "部署步骤",
                "已知问题清单",
            ],
            "growth": [
                "推广文案",
                "发布渠道建议",
                "预期效果估算",
                "内容日历更新",
            ],
            "analyst": [
                "数据来源及范围",
                "关键发现（带数据支撑）",
                "可视化图表建议",
                "可执行建议",
            ],
        }
        return requirements.get(agent_name, ["结构化输出"])

    def execute_agent(self, task_id: str, agent_name: str):
        """
        生成 Agent 执行包。

        在实际使用中，这个输出会被交给外部 AI Agent（Claude Code / Codex）执行。
        执行完成后，调用 submit_agent_output() 提交结果。
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        package = self.generate_context_package(task, agent_name)

        # 写入 workspace
        package_file = WORKSPACE / f"{task_id}_{agent_name}_input.json"
        package_file.write_text(json.dumps(package, indent=2, ensure_ascii=False))

        # 生成人类可读的执行指令
        instruction_file = WORKSPACE / f"{task_id}_{agent_name}_instruction.md"
        instruction = self._generate_instruction(package)
        instruction_file.write_text(instruction)

        task.current_phase = agent_name
        task.status = "running"
        self._save_tasks()

        print(f"\n[Secretary] Agent 执行包已生成: {agent_name}")
        print(f"[Secretary] 输入文件: {package_file}")
        print(f"[Secretary] 指令文件: {instruction_file}")
        print(f"\n{'='*50}")
        print("请将此指令交给对应的 AI Agent 执行")
        print(f"{'='*50}\n")

        return package_file, instruction_file

    def _generate_instruction(self, package: dict) -> str:
        """生成给 AI Agent 的执行指令。"""
        agent = package["agent"]
        role = package["agent_role"]
        desc = package["agent_description"]

        lines = [
            f"# Agent 执行指令: {agent}",
            f"",
            f"## 角色",
            f"你是 **{role}**，负责 {desc}。",
            f"",
            f"## 任务",
            f"{package['task_description']}",
            f"",
        ]

        if package["previous_outputs"]:
            lines.extend([
                f"## 前置输出（请基于这些信息工作）",
                f"",
            ])
            for prev_agent, output in package["previous_outputs"].items():
                lines.extend([
                    f"### {prev_agent} 的输出",
                    f"```json",
                    f"{json.dumps(output, ensure_ascii=False, indent=2)}",
                    f"```",
                    f"",
                ])

        lines.extend([
            f"## 输出要求",
            f"请生成以下文件：",
            f"",
        ])
        for req in package["output_requirements"]:
            lines.append(f"- {req}")

        lines.extend([
            f"",
            f"## 输出格式",
            f"将结果写入: `workspace/{package['task_id']}_{agent}_output.md`",
            f"",
            f"## 注意事项",
            f"- 严格基于提供的上下文工作，不要凭空假设",
            f"- 如果不确定，明确标注出来",
            f"- 输出必须是可直接使用的",
            f"",
        ])

        return "\n".join(lines)

    def submit_agent_output(self, task_id: str, agent_name: str, output: dict):
        """Agent 执行完成后，提交结果。"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        task.outputs[agent_name] = output

        # 检查是否所有 Agent 都完成
        if all(a in task.outputs for a in task.agents):
            task.status = "completed"
            task.completed_at = datetime.now().isoformat()
            print(f"[Secretary] 任务完成: {task_id}")
        else:
            print(f"[Secretary] Agent {agent_name} 完成，等待其他 Agent")

        self._save_tasks()
        return task

    def generate_final_report(self, task_id: str) -> str:
        """生成最终汇报给 CEO 的报告。"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        lines = [
            f"# 📊 执行报告: {task.description}",
            f"",
            f"**任务 ID**: {task.id}",
            f"**状态**: {task.status}",
            f"**耗时**: {self._calculate_duration(task)}",
            f"",
            f"---",
            f"",
        ]

        for agent_name in task.agents:
            agent_info = AgentRegistry.get_agent(agent_name)
            output = task.outputs.get(agent_name, {})
            lines.extend([
                f"## {agent_info['name']} ({agent_info['role']})",
                f"",
            ])
            if output:
                # 摘要展示，避免过长
                summary = output.get("summary", str(output)[:500])
                lines.extend([
                    f"**产出摘要**: {summary}",
                    f"",
                ])
                if "files" in output:
                    lines.append("**产出文件**:")
                    for f in output["files"]:
                        lines.append(f"- {f}")
                    lines.append("")
            else:
                lines.extend([
                    f"⚠️ 尚未提交输出",
                    f"",
                ])

        lines.extend([
            f"---",
            f"",
            f"## 📁 工作文件",
            f"所有中间产出位于: `{WORKSPACE}/{task_id}_*\"`",
            f"",
        ])

        report = "\n".join(lines)

        # 保存报告
        report_file = WORKSPACE / f"{task_id}_final_report.md"
        report_file.write_text(report)

        print(f"\n[Secretary] 最终报告已生成: {report_file}")
        return report

    def _calculate_duration(self, task: Task) -> str:
        if not task.completed_at:
            return "进行中"
        start = datetime.fromisoformat(task.created_at)
        end = datetime.fromisoformat(task.completed_at)
        delta = end - start
        hours = delta.total_seconds() / 3600
        return f"{hours:.1f} 小时"

    def show_status(self):
        """显示所有任务状态。"""
        print("\n" + "=" * 60)
        print("📋 Agent 任务状态板")
        print("=" * 60)

        if not self.tasks:
            print("暂无任务")
            return

        for tid, task in self.tasks.items():
            progress = len(task.outputs) / len(task.agents) * 100 if task.agents else 0
            print(f"\n{tid}: {task.description}")
            print(f"  状态: {task.status} | 进度: {progress:.0f}%")
            print(f"  参与 Agent: {', '.join(task.agents)}")
            print(f"  当前阶段: {task.current_phase or '未开始'}")
            print(f"  已完成: {', '.join(task.outputs.keys()) or '无'}")

        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Agent Orchestrator — AI Agent 协作调度")
    parser.add_argument("--task", "-t", help="任务描述")
    parser.add_argument(
        "--agents", "-a",
        help="参与 Agent，逗号分隔，如: cpo,cto,dev"
    )
    parser.add_argument("--status", "-s", action="store_true", help="显示任务状态板")
    parser.add_argument(
        "--submit",
        nargs=2,
        metavar=("TASK_ID", "AGENT"),
        help="提交 Agent 输出: --submit TASK-xxx cpo"
    )
    parser.add_argument(
        "--report",
        metavar="TASK_ID",
        help="生成最终报告: --report TASK-xxx"
    )

    args = parser.parse_args()
    secretary = Secretary()

    if args.status:
        secretary.show_status()
        return

    if args.submit:
        task_id, agent = args.submit
        # 模拟输出，实际使用时应读取文件
        output_file = WORKSPACE / f"{task_id}_{agent}_output.md"
        if output_file.exists():
            output = {"summary": output_file.read_text()[:1000], "files": [str(output_file)]}
        else:
            output = {"summary": "Agent 已完成工作", "files": []}
        secretary.submit_agent_output(task_id, agent, output)
        return

    if args.report:
        secretary.generate_final_report(args.report)
        return

    # 创建新任务
    if not args.task or not args.agents:
        parser.print_help()
        sys.exit(1)
    
    agents = [a.strip() for a in args.agents.split(",")]
    task = secretary.create_task(args.task, agents)

    # 顺序生成每个 Agent 的执行包
    print(f"\n{'='*50}")
    print(f"开始为任务 {task.id} 生成 Agent 执行包")
    print(f"{'='*50}\n")

    for agent in agents:
        if agent == "secretary":
            continue
        secretary.execute_agent(task.id, agent)

    print(f"\n{'='*50}")
    print(f"所有 Agent 执行包已生成！")
    print(f"工作目录: {WORKSPACE}")
    print(f"请依次执行各 Agent 的指令文件")
    print(f"完成后使用: python agent_orchestrator.py --submit {task.id} <agent>")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
