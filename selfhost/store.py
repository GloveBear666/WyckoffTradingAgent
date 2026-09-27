import json
import os
import secrets
import sqlite3
from pathlib import Path


def access_token(data_dir: Path) -> str:
    configured = os.getenv("WEB_TOKEN", "").strip()
    path = data_dir / "access-token"
    if configured:
        token = configured
    elif path.exists():
        token = path.read_text().strip()
    else:
        token = secrets.token_urlsafe(32)
        path.write_text(token)
        path.chmod(0o600)
    if len(token) < 32:
        raise ValueError("WEB_TOKEN must have at least 32 characters")
    return token


class ReportStore:
    def __init__(self, path: Path):
        self.path = path
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, payload TEXT NOT NULL)"
            )

    def save(self, report: dict):
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO reports(payload) VALUES (?)", (json.dumps(report, ensure_ascii=False, allow_nan=False),)
            )
            db.execute("DELETE FROM reports WHERE id NOT IN (SELECT id FROM reports ORDER BY id DESC LIMIT 100)")

    def list(self) -> list[dict]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT id, created_at, payload FROM reports ORDER BY id DESC LIMIT 30").fetchall()
        return [{"id": row[0], "created_at": row[1], "report": json.loads(row[2])} for row in rows]
