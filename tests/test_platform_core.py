from pathlib import Path
import pytest
from packages.governance_engine import PolicyEngine
from packages.mcp_registry import ApprovalRequired,ToolRegistry,ToolRouter
from packages.memory_engine import MemoryStore

def test_governance_denies_unknown_and_blocks_production_write():
    policy=PolicyEngine();assert policy.decide("local","unknown").outcome=="denied";assert policy.decide("production","db.write").outcome=="denied"
def test_router_enforces_approval():
    registry=ToolRegistry();registry.register_function(lambda **_:"ok",name="start",action="runtime.start")
    with pytest.raises(ApprovalRequired):ToolRouter(registry).dispatch("start",{"environment":"test"})
def test_memory_session_and_handoff(tmp_path:Path):
    store=MemoryStore(tmp_path);sid=store.start_session("generic delivery task");store.record_tool_call(sid,"search","done","SUCCEEDED");assert store.recent_events(sid);assert store.create_handoff(sid,"complete","validate").exists()
