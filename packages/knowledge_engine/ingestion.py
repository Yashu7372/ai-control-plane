from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .models import KnowledgeNode


class DocumentIngestor:
    """Create generalized knowledge nodes from common repository documents."""

    OPENAPI_NAMES = {
        "openapi.yaml",
        "openapi.yml",
        "swagger.yaml",
        "swagger.yml",
        "api-docs.json",
    }

    def ingest_path(self, path: Path, source: str) -> list[KnowledgeNode]:
        if path.is_dir():
            nodes: list[KnowledgeNode] = []
            for candidate in sorted(path.rglob("*")):
                if candidate.is_file():
                    nodes.extend(self.ingest_path(candidate, source))
            return nodes

        suffix = path.suffix.lower()
        if suffix == ".md":
            return [self._markdown_node(path, source)]
        if path.name.lower() in self.OPENAPI_NAMES:
            node = self._openapi_node(path, source)
            return [node] if node else []
        if suffix == ".jmx":
            return [self._jmeter_node(path, source)]
        if suffix == ".scala":
            node = self._gatling_node(path, source)
            return [node] if node else []
        return []

    def _markdown_node(self, path: Path, source: str) -> KnowledgeNode:
        content = path.read_text(encoding="utf-8", errors="ignore")
        headings = [line.lstrip("#").strip() for line in content.splitlines() if line.startswith("#")]
        return self._node(
            "document.markdown",
            path.name,
            source,
            content,
            {"path": str(path), "headings": headings[:50], "line_count": len(content.splitlines())},
        )

    def _openapi_node(self, path: Path, source: str) -> KnowledgeNode | None:
        try:
            if path.suffix.lower() == ".json":
                document = json.loads(path.read_text(encoding="utf-8"))
            else:
                import yaml
                document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError, TypeError):
            return None
        title = str((document.get("info") or {}).get("title") or path.name)
        paths = document.get("paths") or {}
        return self._node(
            "document.openapi",
            title,
            source,
            path.read_text(encoding="utf-8", errors="ignore"),
            {
                "path": str(path),
                "spec_version": document.get("openapi") or document.get("swagger"),
                "path_count": len(paths),
                "paths": sorted(paths)[:200],
            },
        )

    def _jmeter_node(self, path: Path, source: str) -> KnowledgeNode:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return self._node(
            "test.jmeter",
            path.stem,
            source,
            content,
            {
                "path": str(path),
                "thread_group_count": content.count("<ThreadGroup"),
                "http_sampler_count": content.count("<HTTPSamplerProxy"),
            },
        )

    def _gatling_node(self, path: Path, source: str) -> KnowledgeNode | None:
        content = path.read_text(encoding="utf-8", errors="ignore")
        classes = re.findall(r"class\s+(\w+)\s+extends\s+Simulation", content)
        if not classes:
            return None
        scenarios = re.findall(r"scenario\s*\(\s*[\"']([^\"']+)[\"']", content)
        return self._node(
            "test.gatling",
            classes[0],
            source,
            content,
            {"path": str(path), "classes": classes, "scenarios": scenarios},
        )

    @staticmethod
    def _node(kind: str, name: str, source: str, content: str, metadata: dict[str, Any]) -> KnowledgeNode:
        digest = hashlib.sha256(f"{source}|{kind}|{metadata.get('path', name)}".encode()).hexdigest()[:24]
        return KnowledgeNode(
            id=f"{kind}:{digest}",
            type=kind,
            name=name,
            source=source,
            content=content,
            metadata=metadata,
        )
