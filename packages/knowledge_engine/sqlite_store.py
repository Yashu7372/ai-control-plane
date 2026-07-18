from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import KnowledgeEdge, KnowledgeNode


class SQLiteKnowledgeStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS edges (
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (source_id, target_id, type),
                    FOREIGN KEY (source_id) REFERENCES nodes(id),
                    FOREIGN KEY (target_id) REFERENCES nodes(id)
                );
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
                CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
                """
            )

    def upsert_node(self, node: KnowledgeNode) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO nodes(id, type, name, source, content, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type=excluded.type,
                    name=excluded.name,
                    source=excluded.source,
                    content=excluded.content,
                    metadata_json=excluded.metadata_json
                """,
                (
                    node.id,
                    node.type,
                    node.name,
                    node.source,
                    node.content,
                    json.dumps(node.metadata, sort_keys=True, default=str),
                ),
            )

    def upsert_edge(self, edge: KnowledgeEdge) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO edges(source_id, target_id, type, metadata_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_id, target_id, type) DO UPDATE SET
                    metadata_json=excluded.metadata_json
                """,
                (
                    edge.source_id,
                    edge.target_id,
                    edge.type,
                    json.dumps(edge.metadata, sort_keys=True, default=str),
                ),
            )

    def find_nodes(
        self,
        *,
        node_type: str | None = None,
        name_contains: str | None = None,
        source: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if node_type:
            clauses.append("type = ?")
            parameters.append(node_type)
        if name_contains:
            clauses.append("LOWER(name) LIKE LOWER(?)")
            parameters.append(f"%{name_contains}%")
        if source:
            clauses.append("source = ?")
            parameters.append(source)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM nodes {where} ORDER BY type, name LIMIT ?",
                parameters,
            ).fetchall()
        return [self._decode_node(row) for row in rows]

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        token = f"%{query}%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM nodes
                WHERE name LIKE ? OR content LIKE ? OR metadata_json LIKE ?
                ORDER BY CASE WHEN name LIKE ? THEN 0 ELSE 1 END, name
                LIMIT ?
                """,
                (token, token, token, token, limit),
            ).fetchall()
        return [self._decode_node(row) for row in rows]

    def neighbors(self, node_id: str, direction: str = "both") -> list[dict[str, Any]]:
        if direction not in {"in", "out", "both"}:
            raise ValueError("direction must be in, out or both")
        if direction == "out":
            where, params = "source_id = ?", (node_id,)
        elif direction == "in":
            where, params = "target_id = ?", (node_id,)
        else:
            where, params = "source_id = ? OR target_id = ?", (node_id, node_id)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM edges WHERE {where} ORDER BY type, source_id, target_id",
                params,
            ).fetchall()
        return [
            {
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "type": row["type"],
                "metadata": json.loads(row["metadata_json"]),
            }
            for row in rows
        ]

    @staticmethod
    def _decode_node(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "type": row["type"],
            "name": row["name"],
            "source": row["source"],
            "content": row["content"],
            "metadata": json.loads(row["metadata_json"]),
        }
