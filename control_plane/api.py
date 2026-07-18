from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from .compiler import compile_workflow
from .engine import Engine

app=FastAPI(title="AI Control Plane",version="0.1.0")
engine=Engine()
class RunIn(BaseModel):
    workflow:str="workflows/demo.yaml"; inputs:dict=Field(default_factory=dict)
class Decision(BaseModel):
    approved:bool; actor:str
@app.get("/health")
def health():return {"status":"UP"}
@app.get("/runs")
def runs():return engine.list_runs()
@app.post("/runs",status_code=201)
def create(body:RunIn):
    try:return {"run_id":compile_workflow(body.workflow,body.inputs)}
    except Exception as exc:raise HTTPException(400,str(exc))
@app.get("/runs/{run_id}")
def get(run_id:str):
    try:return engine.get_run(run_id)
    except KeyError:raise HTTPException(404,"run not found")
@app.post("/runs/{run_id}/approvals/{gate}/decision")
def decide(run_id:str,gate:str,body:Decision):
    try:engine.decide(run_id,gate,body.approved,body.actor);return {"accepted":True}
    except KeyError:raise HTTPException(404,"approval not found")
@app.post("/runs/{run_id}/cancel")
def cancel(run_id:str):engine.cancel(run_id);return {"status":"CANCELLED"}
