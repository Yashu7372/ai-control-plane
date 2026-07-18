from pathlib import Path
import yaml
from .engine import Engine

def compile_workflow(path,inputs=None):
    data=yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    steps=data.get("steps",[]); ids=[x["id"] for x in steps]
    if len(ids)!=len(set(ids)):raise ValueError("duplicate step id")
    for step in steps:
        unknown=set(step.get("depends_on",[]))-set(ids)
        if unknown:raise ValueError(f"unknown dependency: {sorted(unknown)}")
    return Engine().create_run(data["name"],inputs or {},steps)
