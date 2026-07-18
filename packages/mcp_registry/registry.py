from __future__ import annotations
import inspect
from dataclasses import dataclass
from typing import Any,Callable
@dataclass(frozen=True)
class ToolSpec:
    name:str
    description:str
    handler:Callable[...,Any]
    action:str="general.read"
class ToolRegistry:
    def __init__(self)->None:self._tools:dict[str,ToolSpec]={}
    def register(self,spec:ToolSpec)->None:
        if spec.name in self._tools:raise ValueError(f"duplicate tool: {spec.name}")
        self._tools[spec.name]=spec
    def register_function(self,fn:Callable[...,Any],*,name:str|None=None,action:str="general.read")->None:
        self.register(ToolSpec(name or fn.__name__,inspect.getdoc(fn) or fn.__name__,fn,action))
    def get(self,name:str)->ToolSpec:
        if name not in self._tools:raise KeyError(name)
        return self._tools[name]
    def list_specs(self)->list[ToolSpec]:return sorted(self._tools.values(),key=lambda item:item.name)
