from __future__ import annotations
from dataclasses import dataclass
import re
@dataclass(frozen=True)
class Decision:
    outcome:str
    reason:str
class PolicyEngine:
    BLOCKED=("git reset --hard","git clean","rm -rf","rmdir /s","drop ","truncate ","delete from","alter table")
    READ_ONLY=("git status","git diff","git log","python -m py_compile","node --check")
    APPROVAL_COMMANDS=("docker compose up","java -jar","npm start","npm run start","mvn spring-boot:run")
    DB_WRITES={"db.write","db.migrate","db.seed"}
    RISKY_ACTIONS={"simulator.publish","simulator.run","load-test.run","runtime.start"}
    SAFE_ACTIONS={"runtime.status","runtime.plan","test.plan","memory.write","memory.read","knowledge.read","knowledge.plan","governance.audit","approval.request"}
    def decide(self,environment:str,action:str,command:str="")->Decision:
        env=environment.lower(); normalized=re.sub(r"\s+"," ",command.strip()).lower()
        if env in {"prod","production"} and action in self.DB_WRITES:return Decision("denied","production_writes_blocked")
        if action in self.DB_WRITES and env not in {"local","dev"}:return Decision("approval_required","database_write_requires_approval")
        if action in self.RISKY_ACTIONS and env!="local":return Decision("approval_required","risky_action_requires_approval")
        if any(token in normalized for token in self.BLOCKED):return Decision("denied","destructive_command_pattern")
        if any(normalized.startswith(token) for token in self.APPROVAL_COMMANDS):return Decision("approval_required","command_family_requires_approval")
        if any(normalized.startswith(token) for token in self.READ_ONLY):return Decision("allowed","read_only_command")
        if action.endswith(".read") or action in self.SAFE_ACTIONS:return Decision("allowed","safe_platform_action")
        return Decision("denied","unknown_action_denied_by_default")
