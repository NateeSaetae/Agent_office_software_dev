"""Persistence. Each mutation and its event are committed in one transaction."""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from sqlalchemy import create_engine, text


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{path}", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as c:
            c.execute(text("PRAGMA journal_mode=WAL"))
            c.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(kind,id))"
                )
            )
            c.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL)"
                )
            )

    def all(self, kind: str) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            return [
                json.loads(r[0])
                for r in c.execute(
                    text("SELECT body FROM records WHERE kind=:k ORDER BY rowid"),
                    {"k": kind},
                )
            ]

    def get(self, kind: str, id: str) -> dict[str, Any]:
        with self.engine.connect() as c:
            row = c.execute(
                text("SELECT body FROM records WHERE kind=:k AND id=:id"),
                {"k": kind, "id": id},
            ).first()
        if not row:
            raise KeyError(id)
        return json.loads(row[0])

    def save(self, kind: str, data: dict[str, Any], event: str, **payload: Any) -> None:
        body = {
            "type": event,
            "at": now(),
            "project_id": data.get("project_id"),
            "agent_id": data.get("agent_id"),
            "entity": kind,
            "entity_id": data["id"],
            "task_id": data["id"] if kind == "tasks" else data.get("task_id"),
            "run_id": data.get("run_id"),
            **payload,
        }
        with self.engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO records(kind,id,body) VALUES(:k,:id,:b) ON CONFLICT(kind,id) DO UPDATE SET body=:b"
                ),
                {"k": kind, "id": data["id"], "b": json.dumps(data)},
            )
            c.execute(
                text("INSERT INTO events(body) VALUES(:b)"), {"b": json.dumps(body)}
            )

    def emit(self, event: str, **payload: Any) -> None:
        with self.engine.begin() as c:
            c.execute(
                text("INSERT INTO events(body) VALUES(:b)"),
                {"b": json.dumps({"type": event, "at": now(), **payload})},
            )

    def events(self, after: int = 0, limit: int = 250) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            return [
                {"id": r[0], **json.loads(r[1])}
                for r in c.execute(
                    text("SELECT id,body FROM events WHERE id>:a ORDER BY id LIMIT :n"),
                    {"a": after, "n": limit},
                )
            ]

    def recent(self) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            rows = c.execute(
                text("SELECT id,body FROM events ORDER BY id DESC LIMIT 100")
            ).all()
        return [{"id": r[0], **json.loads(r[1])} for r in reversed(rows)]

    def delete_project(self, project: dict[str, Any]) -> None:
        """Remove project records together and retain one deletion audit event."""
        with self.engine.begin() as c:
            c.execute(
                text(
                    "DELETE FROM records WHERE (kind='projects' AND id=:id) OR (kind IN ('tasks','runs','approvals') AND json_extract(body, '$.project_id')=:id)"
                ),
                {"id": project["id"]},
            )
            c.execute(
                text("DELETE FROM events WHERE json_extract(body, '$.project_id')=:id"),
                {"id": project["id"]},
            )
            c.execute(
                text("INSERT INTO events(body) VALUES(:b)"),
                {
                    "b": json.dumps(
                        {
                            "type": "project.deleted",
                            "at": now(),
                            "project_id": project["id"],
                            "message": "Deleted project and workspace: "
                            + project["name"],
                            "workspace": project["workspace"],
                        }
                    )
                },
            )
