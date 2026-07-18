from __future__ import annotations

from packages.governance_engine import PolicyEngine

from .models import RuntimeCommand, RuntimeProfile


class RuntimePlanner:
    def __init__(self, policy: PolicyEngine | None = None) -> None:
        self.policy = policy or PolicyEngine()

    def plan_start(self, profile: RuntimeProfile, environment: str = "local") -> list[RuntimeCommand]:
        commands: list[RuntimeCommand] = []
        for service in profile.services:
            decision = self.policy.decide(environment, "runtime.start", " ".join(service.start))
            if decision.outcome == "denied":
                raise PermissionError(f"{service.name}: {decision.reason}")
            commands.append(
                RuntimeCommand(
                    service=service.name,
                    action=decision.outcome,
                    command=service.start,
                    working_directory=service.working_directory,
                    environment=service.environment,
                )
            )
        return commands

    def plan_stop(self, profile: RuntimeProfile, environment: str = "local") -> list[RuntimeCommand]:
        commands: list[RuntimeCommand] = []
        for service in reversed(profile.services):
            if not service.stop:
                continue
            decision = self.policy.decide(environment, "runtime.start", " ".join(service.stop))
            if decision.outcome == "denied":
                raise PermissionError(f"{service.name}: {decision.reason}")
            commands.append(
                RuntimeCommand(
                    service=service.name,
                    action=decision.outcome,
                    command=service.stop,
                    working_directory=service.working_directory,
                    environment=service.environment,
                )
            )
        return commands
