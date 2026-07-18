from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TaskRecord:
    id: str
    type: str
    payload: dict[str, Any]
    state: str
    attempts: int
    max_attempts: int
    lease_owner: str | None
    lease_until: float | None
    last_error: str | None


class DurableTaskQueue:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL,
                    lease_owner TEXT,
                    lease_until REAL,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state, created_at);
                CREATE TABLE IF NOT EXISTS task_dependencies (
                    task_id TEXT NOT NULL,
                    depends_on_task_id TEXT NOT NULL,
                    PRIMARY KEY (task_id, depends_on_task_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(id),
                    FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id)
                );
                CREATE INDEX IF NOT EXISTS idx_task_dependencies_task
                    ON task_dependencies(task_id);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def enqueue(
        self,
        task_type: str,
        payload: dict[str, Any],
        max_attempts: int = 3,
        depends_on: tuple[str, ...] = (),
    ) -> str:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if len(depends_on) != len(set(depends_on)):
            raise ValueError("task dependencies must be unique")
        task_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            if depends_on:
                placeholders = ",".join("?" for _ in depends_on)
                count = connection.execute(
                    f"SELECT COUNT(*) FROM tasks WHERE id IN ({placeholders})", depends_on
                ).fetchone()[0]
                if count != len(depends_on):
                    raise KeyError("one or more dependency tasks do not exist")
            initial_state = "BLOCKED" if depends_on else "READY"
            connection.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, 0, ?, NULL, NULL, NULL, ?, ?)",
                (task_id, task_type, json.dumps(payload, sort_keys=True), initial_state, max_attempts, now, now),
            )
            connection.executemany(
                "INSERT INTO task_dependencies(task_id, depends_on_task_id) VALUES (?, ?)",
                ((task_id, dependency) for dependency in depends_on),
            )
        return task_id

    def lease(self, worker_id: str, lease_seconds: int = 60) -> TaskRecord | None:
        now = time.time()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE tasks
                SET state='READY', updated_at=?
                WHERE state='BLOCKED'
                  AND NOT EXISTS (
                    SELECT 1
                    FROM task_dependencies dependency
                    JOIN tasks prerequisite ON prerequisite.id=dependency.depends_on_task_id
                    WHERE dependency.task_id=tasks.id
                      AND prerequisite.state!='SUCCEEDED'
                  )
                """,
                (now,),
            )
            row = connection.execute(
                """
                SELECT * FROM tasks
                WHERE (state='READY' OR (state='LEASED' AND lease_until < ?))
                  AND attempts < max_attempts
                ORDER BY created_at
                LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE tasks
                SET state='LEASED', attempts=attempts+1, lease_owner=?, lease_until=?, updated_at=?
                WHERE id=?
                """,
                (worker_id, now + lease_seconds, now, row["id"]),
            )
            updated = connection.execute("SELECT * FROM tasks WHERE id=?", (row["id"],)).fetchone()
        return self._decode(updated)

    def complete(self, task_id: str, worker_id: str) -> None:
        self._transition(task_id, worker_id, "SUCCEEDED", None)

    def fail(self, task_id: str, worker_id: str, error: str) -> None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            if row["lease_owner"] != worker_id or row["state"] != "LEASED":
                raise PermissionError("task is not leased by this worker")
            next_state = "FAILED" if row["attempts"] >= row["max_attempts"] else "READY"
            connection.execute(
                """
                UPDATE tasks SET state=?, lease_owner=NULL, lease_until=NULL,
                    last_error=?, updated_at=? WHERE id=?
                """,
                (next_state, error, time.time(), task_id),
            )

    def retry(self, task_id: str) -> None:
        with self._connect() as connection:
            row = connection.execute("SELECT state FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            if row["state"] not in {"FAILED", "CANCELLED"}:
                raise ValueError("only failed or cancelled tasks can be retried")
            connection.execute(
                "UPDATE tasks SET state='READY', attempts=0, last_error=NULL, updated_at=? WHERE id=?",
                (time.time(), task_id),
            )

    def get(self, task_id: str) -> TaskRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return self._decode(row)

    def dependencies(self, task_id: str) -> tuple[str, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT depends_on_task_id FROM task_dependencies WHERE task_id=? ORDER BY depends_on_task_id",
                (task_id,),
            ).fetchall()
        return tuple(row["depends_on_task_id"] for row in rows)

    def _transition(self, task_id: str, worker_id: str, state: str, error: str | None) -> None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            if row["lease_owner"] != worker_id or row["state"] != "LEASED":
                raise PermissionError("task is not leased by this worker")
            connection.execute(
                """
                UPDATE tasks SET state=?, lease_owner=NULL, lease_until=NULL,
                    last_error=?, updated_at=? WHERE id=?
                """,
                (state, error, time.time(), task_id),
            )

    @staticmethod
    def _decode(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            type=row["type"],
            payload=json.loads(row["payload_json"]),
            state=row["state"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            lease_owner=row["lease_owner"],
            lease_until=row["lease_until"],
            last_error=row["last_error"],
        )
