from __future__ import annotations
import re
from typing import Any
_SECRET_PATTERNS=[re.compile(r"(?i)(password\s*[=:]\s*)\S+"),re.compile(r"(?i)(passwd\s*[=:]\s*)\S+"),re.compile(r"(?i)(pwd\s*[=:]\s*)\S+"),re.compile(r"(?i)(token\s*[=:]\s*)\S+"),re.compile(r"(?i)(secret\s*[=:]\s*)\S+"),re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)\S+"),re.compile(r"(?i)(bearer\s+)\S+"),re.compile(r"(?i)(://[^:/\s]+:)[^@\s]+(@)")]
_PII_PATTERNS=[("email",re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),("card",re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{2,4}(?!\d)")),("phone",re.compile(r"(?<!\d)(\+?\d{1,3}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4})(?!\d)"))]
_SENSITIVE_KEYS=re.compile(r"(?i)^(password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key|private[_-]?key|credential|authorization|bearer|ssn|passport)$")
def redact_text(text:str)->str:
    if not text:return text
    value=text
    for pattern in _SECRET_PATTERNS:value=pattern.sub(lambda m:f"{m.group(1)}<redacted>{m.group(2) if m.lastindex and m.lastindex>=2 else ''}",value)
    for label,pattern in _PII_PATTERNS:value=pattern.sub(f"<{label}-redacted>",value)
    return value
def redact_mapping(data:dict[str,Any])->dict[str,Any]:
    return {k:("<redacted>" if _SENSITIVE_KEYS.match(k) else redact_text(v) if isinstance(v,str) else v) for k,v in data.items()}
