from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ApprovalRecord:
    id: str
    action: str
    resource: str
    requester: str
    state: str
    payload: dict[str, Any]
    decided_by: str | None
    reason: str | None


class ApprovalStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    requester TEXT NOT NULL,
                    state TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    decided_by TEXT,
                    reason TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    def request(self, action: str, resource: str, requester: str, payload: dict[str, Any] | None = None) -> str:
        approval_id = uuid.uuid4().hex
        now = time.time()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO approvals VALUES (?, ?, ?, ?, 'PENDING', ?, NULL, NULL, ?, ?)",
                (approval_id, action, resource, requester, json.dumps(payload or {}, sort_keys=True), now, now),
            )
        return approval_id

    def decide(self, approval_id: str, approved: bool, decided_by: str, reason: str | None = None) -> ApprovalRecord:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            if row is None:
                raise KeyError(approval_id)
            if row["state"] != "PENDING":
                raise ValueError("approval has already been decided")
            state = "APPROVED" if approved else "REJECTED"
            connection.execute(
                "UPDATE approvals SET state=?, decided_by=?, reason=?, updated_at=? WHERE id=?",
                (state, decided_by, reason, time.time(), approval_id),
            )
        return self.get(approval_id)

    def get(self, approval_id: str) -> ApprovalRecord:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if row is None:
            raise KeyError(approval_id)
        return ApprovalRecord(
            id=row["id"], action=row["action"], resource=row["resource"], requester=row["requester"],
            state=row["state"], payload=json.loads(row["payload_json"]), decided_by=row["decided_by"], reason=row["reason"]
        )

    def list_pending(self) -> list[ApprovalRecord]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT id FROM approvals WHERE state='PENDING' ORDER BY created_at").fetchall()
        return [self.get(row["id"]) for row in rows]
