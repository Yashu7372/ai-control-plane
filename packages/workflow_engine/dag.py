from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class DagNode:
    key: str
    dependencies: tuple[str, ...]


class WorkflowDag:
    def __init__(self, nodes: list[DagNode]) -> None:
        self.nodes = {node.key: node for node in nodes}
        if len(self.nodes) != len(nodes):
            raise ValueError("duplicate workflow step id")
        self._validate_dependencies()
        self._validate_acyclic()

    def _validate_dependencies(self) -> None:
        known = set(self.nodes)
        for node in self.nodes.values():
            unknown = set(node.dependencies) - known
            if unknown:
                raise ValueError(
                    f"step '{node.key}' has unknown dependencies: {sorted(unknown)}"
                )
            if node.key in node.dependencies:
                raise ValueError(f"step '{node.key}' cannot depend on itself")

    def _validate_acyclic(self) -> None:
        self.topological_order()

    def topological_order(self) -> list[str]:
        indegree = {key: 0 for key in self.nodes}
        outgoing: dict[str, list[str]] = defaultdict(list)
        for node in self.nodes.values():
            for dependency in node.dependencies:
                indegree[node.key] += 1
                outgoing[dependency].append(node.key)

        ready = deque(sorted(key for key, degree in indegree.items() if degree == 0))
        ordered: list[str] = []
        while ready:
            current = ready.popleft()
            ordered.append(current)
            for target in sorted(outgoing[current]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)

        if len(ordered) != len(self.nodes):
            raise ValueError("workflow contains a dependency cycle")
        return ordered

    def ready_steps(self, completed: set[str], started: set[str] | None = None) -> list[str]:
        active = started or set()
        return [
            key
            for key in self.topological_order()
            if key not in completed
            and key not in active
            and set(self.nodes[key].dependencies).issubset(completed)
        ]
