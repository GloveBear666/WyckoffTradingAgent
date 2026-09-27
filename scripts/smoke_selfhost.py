"""Offline HTTP smoke checks, run inside the self-hosted container."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    token = (
        os.getenv("WEB_TOKEN", "").strip()
        or (Path(os.getenv("SELFHOST_DATA_DIR", "/data")) / "access-token").read_text().strip()
    )
    checks = [
        ("/api/health", None, 200),
        ("/", None, 200),
        ("/chat", None, 200),
        ("/api/history", None, 401),
        ("/api/config", "wrong", 401),
        ("/api/config", token, 200),
    ]
    for path, auth, expected in checks:
        request = Request("http://127.0.0.1:8000" + path, headers={"Authorization": f"Bearer {auth}"} if auth else {})
        try:
            with urlopen(request, timeout=10) as response:
                actual = response.status
                if path == "/api/config" and auth == token:
                    assert json.load(response)["exchanges"] == ["okx", "binance", "bybit"]
        except HTTPError as exc:
            actual = exc.code
        assert actual == expected, f"{path}: expected {expected}, got {actual}"
    print("Self-hosted smoke checks passed (health, UI, auth, config).")


if __name__ == "__main__":
    main()
