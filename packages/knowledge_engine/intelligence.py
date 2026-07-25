from __future__ import annotations

import hashlib
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from packages.context_engine import ContextItem, ContextPack, ContextPackBuilder

from .models import KnowledgeEdge, KnowledgeNode


@dataclass(frozen=True)
class KnowledgeGraphBatch:
    nodes: tuple[KnowledgeNode, ...]
    edges: tuple[KnowledgeEdge, ...]

    def persist(self, store: Any) -> None:
        for node in self.nodes:
            store.upsert_node(node)
        for edge in self.edges:
            store.upsert_edge(edge)

    def merged(self, *others: "KnowledgeGraphBatch") -> "KnowledgeGraphBatch":
        nodes = {node.id: node for node in self.nodes}
        edges = {(edge.source_id, edge.target_id, edge.type): edge for edge in self.edges}
        for batch in others:
            nodes.update({node.id: node for node in batch.nodes})
            edges.update({(edge.source_id, edge.target_id, edge.type): edge for edge in batch.edges})
        return KnowledgeGraphBatch(tuple(nodes.values()), tuple(edges.values()))


@dataclass(frozen=True)
class EntityFlow:
    entity: str
    source_service: str
    target_service: str
    nodes: tuple[KnowledgeNode, ...]
    edges: tuple[KnowledgeEdge, ...]

    @property
    def minimum_confidence(self) -> float:
        return min((float(edge.metadata.get("confidence", 1.0)) for edge in self.edges), default=1.0)

    def as_context_pack(self, max_tokens: int = 4_000) -> ContextPack:
        items: list[ContextItem] = []
        for index, node in enumerate(self.nodes):
            if not node.content.strip():
                continue
            items.append(
                ContextItem(
                    id=node.id,
                    source=str(node.metadata.get("path", node.source)),
                    title=f"{node.type}: {node.name}",
                    content=node.content,
                    score=max(0.1, 1.0 - index * 0.02),
                    metadata={
                        **node.metadata,
                        "service": node.source,
                        "flow_entity": self.entity,
                    },
                )
            )
        task = f"Trace {self.entity} from {self.source_service} to {self.target_service}"
        return ContextPackBuilder(max_tokens=max_tokens).build(task, items)


@dataclass(frozen=True)
class _Artifact:
    path: str
    language: str
    content: str


@dataclass(frozen=True)
class _TypeInfo:
    name: str
    node_id: str
    artifact_id: str
    path: str
    content: str
    extends: str | None
    implements: tuple[str, ...]
    fields: dict[str, str]


@dataclass(frozen=True)
class _MethodInfo:
    owner: str
    name: str
    node_id: str
    artifact_id: str
    path: str
    signature: str
    parameters: tuple[tuple[str, str], ...]
    body: str


class IntelligenceReportParser:
    """Turn generated repository-intelligence markdown into a typed code graph.

    The parser deliberately works from embedded source sections rather than report
    prose. This avoids treating generated summaries as equivalent to code evidence.
    """

    SOURCE_BLOCK = re.compile(
        r"^###\s+`(?P<path>[^`]+)`[^\n]*\n+```(?P<language>[^\n]*)\n"
        r"(?P<content>.*?)\n```",
        re.MULTILINE | re.DOTALL,
    )
    TYPE_DECLARATION = re.compile(
        r"\b(?:public\s+)?(?P<kind>class|interface|record)\s+(?P<name>\w+)"
        r"(?:\s+extends\s+(?P<extends>[\w.]+(?:\s*<[^>{}]+>)?))?"
        r"(?:\s+implements\s+(?P<implements>[\w.,\s]+))?"
    )
    METHOD_DECLARATION = re.compile(
        r"^[ \t]*(?P<signature>(?:(?:public|protected|private)\s+)?"
        r"(?:static\s+)?(?:default\s+)?(?:<[^>{}]+>\s+)?[\w.<>, ?\[\]]+?\s+"
        r"(?P<name>\w+)\s*\((?P<parameters>[^)]*)\)"
        r"(?:\s+throws\s+[^{;]+)?)\s*(?P<ending>\{|;)",
        re.MULTILINE,
    )
    FIELD_DECLARATION = re.compile(
        r"\bprivate\s+(?:static\s+)?(?:final\s+)?"
        r"(?P<type>[\w.]+(?:\s*<[^;=]+>)?)\s+(?P<name>\w+)\s*(?:=[^;]+)?;"
    )
    VALUE_FIELD = re.compile(
        r'@Value\(\s*"\$\{(?P<key>[^}:]+)(?::(?P<default>[^}]+))?}"\s*\)'
        r"\s*private\s+String\s+(?P<variable>\w+)\s*;",
        re.DOTALL,
    )
    TABLE_DECLARATION = re.compile(
        r'@Table\s*\(\s*name\s*=\s*"(?P<table>[^"]+)"'
        r'(?:\s*,\s*schema\s*=\s*"(?P<schema>[^"]+)")?',
        re.DOTALL,
    )

    def parse_path(self, path: Path, source: str | None = None) -> KnowledgeGraphBatch:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return self.parse(content, source=source, report_path=str(path))

    def parse(
        self,
        content: str,
        *,
        source: str | None = None,
        report_path: str = "<memory>",
    ) -> KnowledgeGraphBatch:
        service = source or self._service_name(content)
        artifacts = tuple(
            _Artifact(
                match.group("path"),
                match.group("language").strip().lower(),
                match.group("content"),
            )
            for match in self.SOURCE_BLOCK.finditer(content)
        )
        config = self._configuration(artifacts)
        nodes: dict[str, KnowledgeNode] = {}
        edges: dict[tuple[str, str, str], KnowledgeEdge] = {}

        def add_node(node: KnowledgeNode) -> None:
            nodes[node.id] = node

        def add_edge(source_id: str, target_id: str, kind: str, **metadata: Any) -> None:
            edge = KnowledgeEdge(source_id, target_id, kind, metadata)
            edges[(source_id, target_id, kind)] = edge

        service_id = self._id("service", service)
        add_node(
            KnowledgeNode(
                service_id,
                "service",
                service,
                service,
                metadata={"report_path": report_path},
            )
        )

        type_infos: dict[str, _TypeInfo] = {}
        methods: list[_MethodInfo] = []
        value_fields: dict[tuple[str, str], tuple[str, str | None, str]] = {}
        entity_tables: dict[str, str] = {}

        for artifact in artifacts:
            artifact_id = self._id("artifact.source", service, artifact.path)
            add_node(
                KnowledgeNode(
                    artifact_id,
                    "artifact.source",
                    Path(artifact.path).name,
                    service,
                    artifact.content,
                    {
                        "path": artifact.path,
                        "language": artifact.language,
                        "report_path": report_path,
                    },
                )
            )
            add_edge(service_id, artifact_id, "contains", confidence=1.0, evidence="source block")

            declaration = self.TYPE_DECLARATION.search(artifact.content)
            if not declaration:
                continue
            type_name = declaration.group("name")
            type_id = self._id("symbol.type", service, type_name)
            implements = tuple(
                part.strip()
                for part in (declaration.group("implements") or "").split(",")
                if part.strip()
            )
            fields = {
                match.group("name"): self._simple_type(match.group("type"))
                for match in self.FIELD_DECLARATION.finditer(artifact.content)
            }
            type_info = _TypeInfo(
                type_name,
                type_id,
                artifact_id,
                artifact.path,
                artifact.content,
                self._simple_type(declaration.group("extends")) if declaration.group("extends") else None,
                implements,
                fields,
            )
            type_infos[type_name] = type_info
            add_node(
                KnowledgeNode(
                    type_id,
                    f"symbol.{declaration.group('kind')}",
                    type_name,
                    service,
                    declaration.group(0),
                    {"path": artifact.path, "implements": implements},
                )
            )
            add_edge(artifact_id, type_id, "declares", confidence=1.0, evidence="type declaration")

            table_match = self.TABLE_DECLARATION.search(artifact.content)
            if table_match:
                table_name = ".".join(
                    part
                    for part in (table_match.group("schema"), table_match.group("table"))
                    if part
                )
                table_id = self._id("database.table", table_name)
                entity_tables[type_name] = table_id
                add_node(
                    KnowledgeNode(
                        table_id,
                        "database.table",
                        table_name,
                        service,
                        table_match.group(0),
                        {"path": artifact.path},
                    )
                )
                add_edge(type_id, table_id, "maps_to", confidence=1.0, evidence="@Table")

            for value_match in self.VALUE_FIELD.finditer(artifact.content):
                value_fields[(type_name, value_match.group("variable"))] = (
                    value_match.group("key"),
                    value_match.group("default"),
                    artifact.path,
                )

            for method in self._methods(type_info):
                methods.append(method)
                add_node(
                    KnowledgeNode(
                        method.node_id,
                        "symbol.method",
                        f"{method.owner}.{method.name}",
                        service,
                        method.signature + (f" {{\n{method.body}\n}}" if method.body else ";"),
                        {"path": method.path, "owner": method.owner},
                    )
                )
                add_edge(type_id, method.node_id, "declares", confidence=1.0, evidence="method declaration")

        method_index = {(method.owner, method.name): method for method in methods}

        for type_info in type_infos.values():
            for interface in type_info.implements:
                interface_info = type_infos.get(self._simple_type(interface))
                if interface_info:
                    add_edge(
                        interface_info.node_id,
                        type_info.node_id,
                        "implemented_by",
                        confidence=1.0,
                        evidence="implements declaration",
                    )
                    for method in methods:
                        if method.owner != type_info.name:
                            continue
                        interface_method = method_index.get((interface_info.name, method.name))
                        if interface_method:
                            add_edge(
                                interface_method.node_id,
                                method.node_id,
                                "implemented_by",
                                confidence=1.0,
                                evidence="interface implementation",
                            )

        for method in methods:
            owner = type_infos[method.owner]
            self._add_calls(method, owner, method_index, nodes, add_node, add_edge, service)
            self._add_messaging(
                method,
                owner,
                value_fields,
                config,
                nodes,
                add_node,
                add_edge,
                service,
            )

        for type_info in type_infos.values():
            entity_name = self._repository_entity(type_info.content)
            table_id = entity_tables.get(entity_name or "")
            if not table_id:
                continue
            save_id = self._id("symbol.method", service, type_info.name, "save")
            if save_id not in nodes:
                add_node(
                    KnowledgeNode(
                        save_id,
                        "symbol.method",
                        f"{type_info.name}.save",
                        service,
                        metadata={"path": type_info.path, "owner": type_info.name, "inherited": True},
                    )
                )
            add_edge(
                save_id,
                table_id,
                "writes",
                confidence=1.0,
                evidence=f"JpaRepository<{entity_name}> and entity @Table",
            )

        return KnowledgeGraphBatch(tuple(nodes.values()), tuple(edges.values()))

    def _add_calls(
        self,
        method: _MethodInfo,
        owner: _TypeInfo,
        method_index: dict[tuple[str, str], _MethodInfo],
        nodes: dict[str, KnowledgeNode],
        add_node: Any,
        add_edge: Any,
        service: str,
    ) -> None:
        for variable, called_method in re.findall(r"\b(\w+)\.(\w+)\s*\(", method.body):
            target_owner = owner.fields.get(variable)
            if not target_owner:
                continue
            target = method_index.get((target_owner, called_method))
            target_id = target.node_id if target else self._id(
                "symbol.method", service, target_owner, called_method
            )
            if target_id not in nodes:
                add_node(
                    KnowledgeNode(
                        target_id,
                        "symbol.method",
                        f"{target_owner}.{called_method}",
                        service,
                        metadata={"owner": target_owner, "referenced_from": method.path},
                    )
                )
            add_edge(
                method.node_id,
                target_id,
                "calls",
                confidence=1.0,
                evidence=f"{variable}.{called_method}(...)",
                path=method.path,
            )

        for called_method in re.findall(r"(?<![.\w])(\w+)\s*\(", method.body):
            if called_method in {"if", "for", "while", "switch", "catch", "return", "new"}:
                continue
            target = method_index.get((method.owner, called_method))
            if target and target.node_id != method.node_id:
                add_edge(
                    method.node_id,
                    target.node_id,
                    "calls",
                    confidence=1.0,
                    evidence=f"{called_method}(...)",
                    path=method.path,
                )

    def _add_messaging(
        self,
        method: _MethodInfo,
        owner: _TypeInfo,
        value_fields: dict[tuple[str, str], tuple[str, str | None, str]],
        config: dict[str, str],
        nodes: dict[str, KnowledgeNode],
        add_node: Any,
        add_edge: Any,
        service: str,
    ) -> None:
        sends = re.findall(r"\.convertAndSend\s*\(\s*(\w+)", method.body)
        for variable in sends:
            destination_id = self._destination(
                owner.name,
                variable,
                value_fields,
                config,
                service,
                nodes,
                add_node,
            )
            add_edge(
                method.node_id,
                destination_id,
                "sends_to",
                confidence=1.0,
                evidence="JmsTemplate.convertAndSend",
                path=method.path,
            )
            if method.parameters:
                event_type = method.parameters[0][0]
                event_id = self._event(service, event_type, method.path, nodes, add_node)
                add_edge(
                    method.node_id,
                    event_id,
                    "publishes",
                    confidence=1.0,
                    evidence="publisher method parameter",
                    path=method.path,
                )
                add_edge(
                    event_id,
                    destination_id,
                    "carried_by",
                    confidence=1.0,
                    evidence="convertAndSend in publisher method",
                )

        subscriptions = re.findall(
            r"\.subscribe\s*\(\s*(\w+)\s*,\s*(?:true|false)\s*,\s*(\w+)\.class",
            method.body,
        )
        for variable, event_type in subscriptions:
            destination_id = self._destination(
                owner.name,
                variable,
                value_fields,
                config,
                service,
                nodes,
                add_node,
            )
            event_id = self._event(service, event_type, method.path, nodes, add_node)
            add_edge(
                destination_id,
                method.node_id,
                "delivers_to",
                confidence=1.0,
                evidence=f"subscribe(..., {event_type}.class)",
                path=method.path,
            )
            add_edge(
                event_id,
                method.node_id,
                "consumed_by",
                confidence=1.0,
                evidence=f"subscribe(..., {event_type}.class)",
                path=method.path,
            )

    def _destination(
        self,
        owner: str,
        variable: str,
        value_fields: dict[tuple[str, str], tuple[str, str | None, str]],
        config: dict[str, str],
        service: str,
        nodes: dict[str, KnowledgeNode],
        add_node: Any,
    ) -> str:
        key, default, path = value_fields.get((owner, variable), (variable, None, "<unknown>"))
        name = default or config.get(key) or f"${{{key}}}"
        destination_id = self._id("messaging.destination", service, name)
        if destination_id not in nodes:
            add_node(
                KnowledgeNode(
                    destination_id,
                    "messaging.destination",
                    name,
                    service,
                    metadata={"config_key": key, "path": path, "resolved": not name.startswith("${")},
                )
            )
        return destination_id

    def _event(
        self,
        service: str,
        event_type: str,
        path: str,
        nodes: dict[str, KnowledgeNode],
        add_node: Any,
    ) -> str:
        event_type = self._simple_type(event_type)
        event_id = self._id("event.contract", service, event_type)
        if event_id not in nodes:
            add_node(
                KnowledgeNode(
                    event_id,
                    "event.contract",
                    event_type,
                    service,
                    metadata={"path": path},
                )
            )
        return event_id

    def _methods(self, owner: _TypeInfo) -> Iterable[_MethodInfo]:
        for match in self.METHOD_DECLARATION.finditer(owner.content):
            parameters = tuple(self._parameters(match.group("parameters")))
            body = ""
            if match.group("ending") == "{":
                body = self._brace_body(owner.content, match.end() - 1)
            yield _MethodInfo(
                owner.name,
                match.group("name"),
                self._id("symbol.method", owner.node_id, match.group("name")),
                owner.artifact_id,
                owner.path,
                match.group("signature"),
                parameters,
                body,
            )

    @staticmethod
    def _brace_body(content: str, opening_index: int) -> str:
        depth = 0
        for index in range(opening_index, len(content)):
            char = content[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return content[opening_index + 1 : index]
        return content[opening_index + 1 :]

    @staticmethod
    def _parameters(value: str) -> Iterable[tuple[str, str]]:
        for raw in value.split(","):
            cleaned = re.sub(r"@\w+(?:\([^)]*\))?\s*", "", raw).strip()
            parts = cleaned.split()
            if len(parts) >= 2:
                yield IntelligenceReportParser._simple_type(parts[-2]), parts[-1]

    @staticmethod
    def _configuration(artifacts: Iterable[_Artifact]) -> dict[str, str]:
        result: dict[str, str] = {}

        def flatten(value: Any, prefix: str = "") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    flatten(child, f"{prefix}.{key}" if prefix else str(key))
            elif value is not None:
                result[prefix] = str(value)

        for artifact in artifacts:
            if artifact.language not in {"yaml", "yml"}:
                continue
            try:
                flatten(yaml.safe_load(artifact.content) or {})
            except yaml.YAMLError:
                continue
        return result

    @staticmethod
    def _repository_entity(content: str) -> str | None:
        match = re.search(r"(?:JpaRepository|CrudRepository)\s*<\s*(\w+)", content)
        return match.group(1) if match else None

    @staticmethod
    def _service_name(content: str) -> str:
        match = re.search(r"^##\s+(.+?)\s*$", content, re.MULTILINE)
        if not match:
            raise ValueError("intelligence report does not contain a service heading")
        return match.group(1).strip().strip("`")

    @staticmethod
    def _simple_type(value: str | None) -> str:
        if not value:
            return ""
        value = re.sub(r"<.*>", "", value).strip()
        return value.rsplit(".", 1)[-1]

    @staticmethod
    def _id(kind: str, *parts: str) -> str:
        digest = hashlib.sha256("|".join((kind, *parts)).encode()).hexdigest()[:24]
        return f"{kind}:{digest}"


class EntityFlowTracer:
    """Connect and retrieve one evidence-backed cross-service entity flow."""

    def __init__(self, graph: KnowledgeGraphBatch) -> None:
        self.nodes = {node.id: node for node in graph.nodes}
        self.edges = list(graph.edges)

    def trace(
        self,
        entity: str,
        source_service: str,
        target_service: str,
    ) -> EntityFlow:
        working_edges = [*self.edges]
        working_edges.extend(self._broker_routes(entity, source_service, target_service))
        adjacency: dict[str, list[KnowledgeEdge]] = {}
        for edge in working_edges:
            adjacency.setdefault(edge.source_id, []).append(edge)

        service_starts = [
            node.id
            for node in self.nodes.values()
            if node.type == "service" and node.name == source_service
        ]
        targets = {
            node.id
            for node in self.nodes.values()
            if node.source == target_service and node.type == "database.table"
        }
        if not service_starts:
            raise ValueError(f"source service not found: {source_service}")
        if not targets:
            raise ValueError(f"target service has no database table nodes: {target_service}")

        entry = self._source_entry(source_service) or service_starts[0]
        previous: dict[str, tuple[str, KnowledgeEdge] | None] = {entry: None}
        queue: deque[str] = deque((entry,))
        found: str | None = None
        while queue:
            current = queue.popleft()
            if current in targets:
                found = current
                break
            for edge in sorted(adjacency.get(current, []), key=lambda item: item.type):
                if edge.target_id not in previous:
                    previous[edge.target_id] = (current, edge)
                    queue.append(edge.target_id)

        if found is None:
            raise ValueError(
                f"no {entity} flow found from {source_service} to {target_service}"
            )

        node_ids = [found]
        path_edges: list[KnowledgeEdge] = []
        while previous[node_ids[-1]] is not None:
            prior, edge = previous[node_ids[-1]]  # type: ignore[misc]
            path_edges.append(edge)
            node_ids.append(prior)
        node_ids.reverse()
        path_edges.reverse()
        prefix_nodes, prefix_edges = self._ownership_prefix(service_starts[0], entry)
        if prefix_nodes:
            node_ids = [*prefix_nodes[:-1], *node_ids]
            path_edges = [*prefix_edges, *path_edges]
        return EntityFlow(
            entity,
            source_service,
            target_service,
            tuple(self.nodes[node_id] for node_id in node_ids),
            tuple(path_edges),
        )

    def _source_entry(self, service: str) -> str | None:
        producers = {
            edge.source_id
            for edge in self.edges
            if edge.type == "sends_to"
            and self.nodes.get(edge.source_id) is not None
            and self.nodes[edge.source_id].source == service
        }
        if not producers:
            return None
        reverse: dict[str, list[tuple[str, KnowledgeEdge]]] = {}
        for edge in self.edges:
            if edge.type not in {"calls", "implemented_by"}:
                continue
            source = self.nodes.get(edge.source_id)
            target = self.nodes.get(edge.target_id)
            if source and target and source.source == service and target.source == service:
                reverse.setdefault(edge.target_id, []).append((edge.source_id, edge))

        distance = {node_id: 0 for node_id in producers}
        queue: deque[str] = deque(producers)
        while queue:
            current = queue.popleft()
            for prior, _edge in reverse.get(current, []):
                if prior not in distance:
                    distance[prior] = distance[current] + 1
                    queue.append(prior)

        candidates: list[tuple[int, int, str]] = []
        for node_id, hops in distance.items():
            node = self.nodes[node_id]
            if node.type != "symbol.method":
                continue
            outgoing_names = [
                self.nodes[edge.target_id].name.lower()
                for edge in self.edges
                if edge.source_id == node_id
                and edge.type == "calls"
                and edge.target_id in self.nodes
            ]
            has_save = any("save" in name or "persist" in name for name in outgoing_names)
            business_name = any(
                token in node.name.lower() for token in ("process", "update", "persist")
            )
            candidates.append((int(has_save) * 2 + int(business_name), hops, node_id))
        return max(candidates, default=(0, 0, next(iter(producers))))[2]

    def _ownership_prefix(
        self,
        service_id: str,
        entry_id: str,
    ) -> tuple[list[str], list[KnowledgeEdge]]:
        if entry_id == service_id:
            return [service_id], []
        incoming: dict[str, list[KnowledgeEdge]] = {}
        for edge in self.edges:
            if edge.type in {"contains", "declares"}:
                incoming.setdefault(edge.target_id, []).append(edge)
        reverse_nodes = [entry_id]
        reverse_edges: list[KnowledgeEdge] = []
        current = entry_id
        while current != service_id:
            choices = incoming.get(current, [])
            if not choices:
                return [], []
            edge = choices[0]
            reverse_edges.append(edge)
            current = edge.source_id
            reverse_nodes.append(current)
        reverse_nodes.reverse()
        reverse_edges.reverse()
        return reverse_nodes, reverse_edges

    def _broker_routes(
        self,
        entity: str,
        source_service: str,
        target_service: str,
    ) -> list[KnowledgeEdge]:
        source_destinations = [
            node
            for node in self.nodes.values()
            if node.type == "messaging.destination" and node.source == source_service
        ]
        target_destinations = [
            node
            for node in self.nodes.values()
            if node.type == "messaging.destination" and node.source == target_service
        ]
        routes: list[KnowledgeEdge] = []
        entity_token = entity.lower()
        source_events = self._destination_events(source_service)
        target_events = self._destination_events(target_service)
        for source in source_destinations:
            for target in target_destinations:
                exact = source.name == target.name
                semantic = (
                    entity_token in source.name.lower()
                    or any(entity_token in name.lower() for name in source_events.get(source.id, ()))
                ) and (
                    entity_token in target.name.lower()
                    or any(entity_token in name.lower() for name in target_events.get(target.id, ()))
                )
                if not exact and not semantic:
                    continue
                routes.append(
                    KnowledgeEdge(
                        source.id,
                        target.id,
                        "routes_to",
                        {
                            "confidence": 1.0 if exact else 0.55,
                            "evidence": (
                                "matching broker destination"
                                if exact
                                else "inferred from producer/consumer entity semantics; "
                                "broker topic-to-queue binding is absent from the reports"
                            ),
                            "inferred": not exact,
                        },
                    )
                )
        return routes

    def _destination_events(self, service: str) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for edge in self.edges:
            source = self.nodes.get(edge.source_id)
            target = self.nodes.get(edge.target_id)
            if not source or not target:
                continue
            if edge.type == "carried_by" and source.source == service:
                result.setdefault(target.id, set()).add(source.name)
            elif edge.type == "delivers_to" and source.source == service:
                for consumed in self.edges:
                    event = self.nodes.get(consumed.source_id)
                    if (
                        consumed.type == "consumed_by"
                        and consumed.target_id == target.id
                        and event is not None
                    ):
                        result.setdefault(source.id, set()).add(event.name)
        return result
