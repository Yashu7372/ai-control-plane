from __future__ import annotations
import logging
from typing import Any
from packages.common.redaction import redact_mapping
from packages.governance_engine.policy import PolicyEngine
from .registry import ToolRegistry
logger=logging.getLogger("ai-control-plane.router")
class GovernanceDenied(RuntimeError):pass
class ApprovalRequired(RuntimeError):pass
class ToolRouter:
    def __init__(self,registry:ToolRegistry,policy:PolicyEngine|None=None)->None:
        self.registry=registry;self.policy=policy or PolicyEngine()
    def dispatch(self,tool_name:str,arguments:dict[str,Any]|None=None)->Any:
        args=arguments or {};spec=self.registry.get(tool_name)
        decision=self.policy.decide(str(args.get("environment") or args.get("env") or "local"),spec.action,str(args.get("command") or ""))
        if decision.outcome=="denied":raise GovernanceDenied(decision.reason)
        if decision.outcome=="approval_required":raise ApprovalRequired(decision.reason)
        logger.info("dispatch tool=%s args=%s",tool_name,redact_mapping(args))
        return spec.handler(**args)
