from __future__ import annotations

from typing import Any

from .models import ValidationResult, ValidationScenario


class EvidenceValidator:
    def validate(self, scenario: ValidationScenario, evidence: dict[str, Any]) -> ValidationResult:
        results: list[dict[str, Any]] = []
        for check in scenario.checks:
            actual, found = self._resolve(evidence, check.path)
            passed = found and self._compare(actual, check.operator, check.expected)
            results.append(
                {
                    "name": check.name,
                    "path": check.path,
                    "operator": check.operator,
                    "expected": check.expected,
                    "actual": actual if found else None,
                    "passed": passed,
                }
            )
        return ValidationResult(
            scenario=scenario.name,
            passed=all(item["passed"] for item in results),
            checks=tuple(results),
        )

    @staticmethod
    def _resolve(document: dict[str, Any], path: str) -> tuple[Any, bool]:
        current: Any = document
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return None, False
            current = current[part]
        return current, True

    @staticmethod
    def _compare(actual: Any, operator: str, expected: Any) -> bool:
        if operator == "eq":
            return actual == expected
        if operator == "ne":
            return actual != expected
        if operator == "contains":
            return expected in actual
        if operator == "in":
            return actual in expected
        if operator == "gt":
            return actual > expected
        if operator == "gte":
            return actual >= expected
        if operator == "lt":
            return actual < expected
        if operator == "lte":
            return actual <= expected
        if operator == "exists":
            return actual is not None
        raise ValueError(f"unsupported validation operator: {operator}")
