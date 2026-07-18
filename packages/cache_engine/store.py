from __future__ import annotations
import hashlib,json,time
from pathlib import Path
from typing import Any
def stable_key(value:Any)->str:return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
class FileCache:
    def __init__(self,root:Path)->None:self.root=root;root.mkdir(parents=True,exist_ok=True)
    def get(self,namespace:str,key:str)->dict|None:
        path=self.root/namespace/f"{key}.json"
        if not path.exists():return None
        value=json.loads(path.read_text(encoding="utf-8"))
        if value.get("expiresAt") and value["expiresAt"]<time.time():path.unlink(missing_ok=True);return None
        return value.get("value")
    def put(self,namespace:str,key:str,value:dict,ttl_seconds:int|None=3600)->None:
        path=self.root/namespace/f"{key}.json";path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({"value":value,"expiresAt":time.time()+ttl_seconds if ttl_seconds else None},indent=2),encoding="utf-8")
