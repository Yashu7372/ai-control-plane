import pytest

from packages.workflow_engine import compile_workflow


def test_compiles_and_orders_workflow():
    workflow = compile_workflow(
        {
            "name": "delivery",
            "steps": [
                {"id": "context", "type": "context"},
                {"id": "workspace", "type": "workspace", "depends_on": ["context"]},
                {"id": "validate", "type": "validation", "depends_on": ["workspace"]},
            ],
        }
    )
    assert workflow.dag().topological_order() == ["context", "workspace", "validate"]
    assert workflow.dag().ready_steps({"context"}) == ["workspace"]


def test_rejects_unknown_dependency():
    with pytest.raises(ValueError, match="unknown dependencies"):
        compile_workflow(
            {
                "name": "invalid",
                "steps": [
                    {"id": "validate", "type": "validation", "depends_on": ["missing"]}
                ],
            }
        )


def test_rejects_dependency_cycle():
    with pytest.raises(ValueError, match="dependency cycle"):
        compile_workflow(
            {
                "name": "cyclic",
                "steps": [
                    {"id": "a", "type": "task", "depends_on": ["b"]},
                    {"id": "b", "type": "task", "depends_on": ["a"]},
                ],
            }
        )
