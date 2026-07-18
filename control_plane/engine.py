from sqlalchemy import select
from .db import SessionLocal, init_db
from .models import Approval, Dependency, Evidence, Run, RunStatus, Task, TaskStatus

class Engine:
    def __init__(self): init_db()
    def create_run(self, workflow, inputs, steps):
        with SessionLocal.begin() as s:
            run=Run(workflow=workflow, inputs=inputs); s.add(run); s.flush(); by_key={}
            for step in steps:
                task=Task(run_id=run.id, step_key=step["id"], task_type=step["type"], payload=step.get("payload",{}), status=TaskStatus.BLOCKED)
                s.add(task); s.flush(); by_key[step["id"]]=task
            for step in steps:
                for dep in step.get("depends_on",[]): s.add(Dependency(task_id=by_key[step["id"]].id, depends_on_id=by_key[dep].id))
            self._promote(s, run.id); return run.id
    def _promote(self,s,run_id):
        tasks=list(s.scalars(select(Task).where(Task.run_id==run_id)))
        states={t.id:t.status for t in tasks}
        deps=list(s.scalars(select(Dependency).where(Dependency.task_id.in_([t.id for t in tasks])))) if tasks else []
        grouped={t.id:[] for t in tasks}
        for d in deps: grouped[d.task_id].append(d.depends_on_id)
        for t in tasks:
            if t.status==TaskStatus.BLOCKED and all(states[x]==TaskStatus.SUCCEEDED for x in grouped[t.id]): t.status=TaskStatus.READY
    def lease(self,worker):
        with SessionLocal.begin() as s:
            task=s.scalar(select(Task).where(Task.status==TaskStatus.READY).order_by(Task.id).with_for_update(skip_locked=True))
            if not task:return None
            task.status=TaskStatus.LEASED; task.lease_owner=worker; task.attempts+=1; s.flush(); return {"id":task.id,"run_id":task.run_id,"step_key":task.step_key,"type":task.task_type,"payload":task.payload}
    def complete(self,task_id,result):
        with SessionLocal.begin() as s:
            task=s.get(Task,task_id); task.status=TaskStatus.SUCCEEDED; task.result=result; task.lease_owner=None
            self._promote(s,task.run_id); self._refresh(s,task.run_id)
    def fail(self,task_id,error):
        with SessionLocal.begin() as s:
            task=s.get(Task,task_id); task.error=error; task.lease_owner=None
            task.status=TaskStatus.READY if task.attempts<task.max_attempts else TaskStatus.FAILED
            self._refresh(s,task.run_id)
    def request_approval(self,task):
        with SessionLocal.begin() as s:
            approval=s.scalar(select(Approval).where(Approval.run_id==task["run_id"],Approval.gate_key==task["step_key"]))
            if not approval:s.add(Approval(run_id=task["run_id"],gate_key=task["step_key"]))
            db_task=s.get(Task,task["id"]); db_task.status=TaskStatus.BLOCKED; db_task.lease_owner=None
            s.get(Run,task["run_id"]).status=RunStatus.WAITING_APPROVAL
    def decide(self,run_id,gate,approved,actor):
        with SessionLocal.begin() as s:
            approval=s.scalar(select(Approval).where(Approval.run_id==run_id,Approval.gate_key==gate))
            if not approval:raise KeyError(gate)
            approval.status="APPROVED" if approved else "REJECTED"; approval.decided_by=actor
            task=s.scalar(select(Task).where(Task.run_id==run_id,Task.step_key==gate))
            task.status=TaskStatus.SUCCEEDED if approved else TaskStatus.FAILED
            run=s.get(Run,run_id); run.status=RunStatus.RUNNING if approved else RunStatus.FAILED
            self._promote(s,run_id); self._refresh(s,run_id)
    def cancel(self,run_id):
        with SessionLocal.begin() as s:
            s.get(Run,run_id).status=RunStatus.CANCELLED
            for t in s.scalars(select(Task).where(Task.run_id==run_id,Task.status.in_([TaskStatus.BLOCKED,TaskStatus.READY,TaskStatus.LEASED]))): t.status=TaskStatus.CANCELLED
    def add_evidence(self,run_id,kind,uri):
        with SessionLocal.begin() as s:s.add(Evidence(run_id=run_id,kind=kind,uri=uri))
    def get_run(self,run_id):
        with SessionLocal() as s:
            run=s.get(Run,run_id)
            if not run:raise KeyError(run_id)
            tasks=list(s.scalars(select(Task).where(Task.run_id==run_id)))
            approvals=list(s.scalars(select(Approval).where(Approval.run_id==run_id)))
            evidence=list(s.scalars(select(Evidence).where(Evidence.run_id==run_id)))
            return {"id":run.id,"workflow":run.workflow,"status":run.status.value,"tasks":[{"id":t.id,"step":t.step_key,"type":t.task_type,"status":t.status.value,"result":t.result,"error":t.error} for t in tasks],"approvals":[{"gate":a.gate_key,"status":a.status,"decided_by":a.decided_by} for a in approvals],"evidence":[{"kind":e.kind,"uri":e.uri} for e in evidence]}
    def list_runs(self):
        with SessionLocal() as s:return [{"id":r.id,"workflow":r.workflow,"status":r.status.value} for r in s.scalars(select(Run).order_by(Run.created_at.desc()))]
    def _refresh(self,s,run_id):
        run=s.get(Run,run_id)
        if run.status in [RunStatus.WAITING_APPROVAL,RunStatus.CANCELLED]:return
        states=list(s.scalars(select(Task.status).where(Task.run_id==run_id)))
        if states and all(x==TaskStatus.SUCCEEDED for x in states):run.status=RunStatus.SUCCEEDED
        elif any(x==TaskStatus.FAILED for x in states):run.status=RunStatus.FAILED
