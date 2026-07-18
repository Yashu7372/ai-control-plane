import subprocess
import time
from .engine import Engine

def execute(task):
    kind=task["type"]; payload=task["payload"]
    if kind=="approval":return "approval"
    if kind=="evidence":Engine().add_evidence(task["run_id"],payload.get("kind","validation"),payload.get("uri","demo://evidence"));return {"recorded":True}
    command=payload.get("command")
    if command:
        done=subprocess.run(command,capture_output=True,text=True,timeout=60)
        if done.returncode:raise RuntimeError(done.stderr)
        return {"stdout":done.stdout.strip()}
    return {"ok":True,"payload":payload}

def run_once(worker_id="local-worker"):
    engine=Engine(); task=engine.lease(worker_id)
    if not task:return False
    if task["type"]=="approval":engine.request_approval(task);return True
    try:engine.complete(task["id"],execute(task))
    except Exception as exc:engine.fail(task["id"],str(exc))
    return True

def run_forever():
    while True:
        if not run_once():time.sleep(0.5)

if __name__=="__main__":run_forever()
