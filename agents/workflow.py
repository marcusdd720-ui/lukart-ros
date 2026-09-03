"""Deterministic typed workflow orchestration for controlled agents."""

from __future__ import annotations

from dataclasses import dataclass

from agents.contract import AgentRequest
from agents.runner import AgentRunResult, AgentRunStatus, AgentRunner
from core.models.ids import AgentId


@dataclass(frozen=True, slots=True)
class AgentWorkflowStep:
    name: str
    agent_id: AgentId
    agent_version: str
    request: AgentRequest

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("workflow step name is required")


@dataclass(frozen=True, slots=True)
class AgentWorkflowResult:
    completed: bool
    steps: tuple[AgentRunResult, ...]
    failed_step: str | None = None


class AgentWorkflowExecutor:
    """Execute explicit agent steps in order and stop at the first validation failure."""

    def __init__(self, runner: AgentRunner) -> None:
        self.runner = runner

    def execute(self, steps: tuple[AgentWorkflowStep, ...]) -> AgentWorkflowResult:
        results: list[AgentRunResult] = []
        for step in steps:
            result = self.runner.run(
                step.agent_id,
                step.agent_version,
                step.request,
            )
            results.append(result)
            if result.status is AgentRunStatus.FAIL:
                return AgentWorkflowResult(
                    completed=False,
                    steps=tuple(results),
                    failed_step=step.name,
                )

        return AgentWorkflowResult(completed=True, steps=tuple(results))
