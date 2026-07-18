from __future__ import annotations
import json,os,re,uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from packages.common.redaction import redact_text
class MemoryStore:
    def __init__(self,root:Path|None=None)->None:
        self.root=(root or Path(os.environ.get("AI_CONTROL_PLANE_HOME",Path.home()/".ai-control-plane"))/"memory").resolve();self.sessions=self.root/"sessions";self.sessions.mkdir(parents=True,exist_ok=True)
    def _now(self)->str:return datetime.now(timezone.utc).isoformat()
    def start_session(self,summary:str,agent:str="assistant",session_id:str|None=None)->str:
        sid=re.sub(r"[^A-Za-z0-9_.-]+","-",session_id or f"{datetime.now(timezone.utc).date()}-{uuid.uuid4().hex[:8]}").strip("-")
        folder=self.sessions/sid;folder.mkdir(parents=True,exist_ok=True)
        (self.root/"current-session.json").write_text(json.dumps({"id":sid,"agent":agent,"summary":redact_text(summary),"startedAt":self._now()},indent=2),encoding="utf-8")
        self.append_event(sid,"session.started",summary,{"agent":agent});return sid
    def append_event(self,session_id:str,event_type:str,title:str,details:dict[str,Any]|None=None)->None:
        path=self.sessions/session_id/"events.jsonl";path.parent.mkdir(parents=True,exist_ok=True)
        record={"timestamp":self._now(),"type":event_type,"title":redact_text(title),"details":details or {}}
        with path.open("a",encoding="utf-8") as handle:handle.write(json.dumps(record,default=str,sort_keys=True)+"\n")
    def record_tool_call(self,session_id:str,tool:str,summary:str,status:str,arguments:dict[str,Any]|None=None)->None:
        self.append_event(session_id,"tool.call",summary,{"tool":tool,"status":status,"arguments":arguments or {}})
    def create_handoff(self,session_id:str,summary:str,next_step:str,status:str="READY")->Path:
        path=self.sessions/session_id/"handoff.md";path.write_text(f"# Current Handoff\n\nGenerated: {self._now()}\nSession: `{session_id}`\nStatus: {status}\n\n## Summary\n{redact_text(summary)}\n\n## Next Step\n{redact_text(next_step)}\n",encoding="utf-8");return path
    def recent_events(self,session_id:str,limit:int=20)->list[dict[str,Any]]:
        path=self.sessions/session_id/"events.jsonl"
        if not path.exists():return []
        rows=[]
        for line in path.read_text(encoding="utf-8").splitlines():
            try:rows.append(json.loads(line))
            except json.JSONDecodeError:continue
        return rows[-limit:]
