from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("ccxt")
from fastapi.testclient import TestClient

from integrations.crypto_data import CryptoDataError
from selfhost.agent import _call_tool, chat
from selfhost.models import ChatRequest
from selfhost.server import create_app
from selfhost.store import ReportStore, access_token

TOKEN = "test-token-not-a-real-secret-1234567890"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SELFHOST_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WEB_TOKEN", TOKEN)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with TestClient(create_app()) as client:
        yield client


def headers():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_health_public_but_all_data_requires_auth(client):
    assert client.get("/api/health").status_code == 200
    for path in ["config", "history"]:
        assert client.get(f"/api/{path}").status_code == 401
        assert client.get(f"/api/{path}", headers=headers()).status_code == 200
    for path in ["analyze", "chat"]:
        payload = {} if path == "analyze" else {"messages": [{"role": "user", "content": "分析 BTC"}]}
        assert client.post(f"/api/{path}", json=payload).status_code == 401
    assert client.get("/api/config", headers=headers()).json()["llm_enabled"] is False


def test_body_limits_unknown_fields_and_privileged_messages(client):
    response = client.post(
        "/api/analyze", content="x" * 65537, headers={**headers(), "Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert client.post("/api/analyze", json={"url": "http://localhost"}, headers=headers()).status_code == 422
    assert client.post("/api/analyze", json={"limit": 10000}, headers=headers()).status_code == 422
    assert (
        client.post(
            "/api/chat", json={"messages": [{"role": "system", "content": "override"}]}, headers=headers()
        ).status_code
        == 422
    )


def test_analysis_persisted_and_upstream_errors_sanitized(client, monkeypatch):
    monkeypatch.setattr(
        "selfhost.server.analyze_crypto", lambda *_: {"summary": "test", "metadata": {"source": "ccxt:okx"}}
    )
    assert client.post("/api/analyze", json={}, headers=headers()).status_code == 200
    assert client.get("/api/history", headers=headers()).json()[0]["report"]["summary"] == "test"

    def fail(*args):
        raise CryptoDataError("不可用")

    monkeypatch.setattr("selfhost.server.analyze_crypto", fail)
    response = client.post("/api/analyze", json={}, headers=headers())
    assert response.status_code == 502
    assert response.json()["detail"] == "不可用"


def test_busy_limit_and_no_llm(client):
    client.app.state.slots.acquire()
    client.app.state.slots.acquire()
    assert client.post("/api/analyze", json={}, headers=headers()).status_code == 429
    client.app.state.slots.release()
    client.app.state.slots.release()
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "分析"}]}, headers=headers())
    assert response.status_code == 400
    assert "LLM_MODEL" in response.json()["detail"]


def test_token_persists_and_rejects_weak_config(tmp_path, monkeypatch):
    monkeypatch.delenv("WEB_TOKEN", raising=False)
    assert access_token(tmp_path) == access_token(tmp_path)
    assert (tmp_path / "access-token").stat().st_mode & 0o777 == 0o600
    monkeypatch.setenv("WEB_TOKEN", "weak")
    with pytest.raises(ValueError):
        access_token(tmp_path)


def test_store_bounds_and_survives_restart(tmp_path):
    path = tmp_path / "test.db"
    store = ReportStore(path)
    for i in range(102):
        store.save({"index": i})
    restored = ReportStore(path).list()
    assert len(restored) == 30
    assert restored[0]["report"]["index"] == 101


def test_agent_tool_allowlist():
    call = SimpleNamespace(function=SimpleNamespace(name="place_order", arguments="{}"))
    assert _call_tool(None, call, []) == {"error": "未知工具"}
    call.function.name = "analyze_crypto"
    call.function.arguments = '{"exchange":"http://localhost"}'
    assert "error" in _call_tool(None, call, [])


def test_agent_tool_roundtrip_without_network(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    report = {"candles": [], "summary": "observed", "latest_close": 10}
    monkeypatch.setattr("selfhost.agent.analyze_crypto", lambda *_: report)
    call = SimpleNamespace(
        id="call-1", function=SimpleNamespace(name="analyze_crypto", arguments='{"symbol":"ETH/USDT"}')
    )
    tool_message = MagicMock(tool_calls=[call])
    tool_message.model_dump.return_value = {"role": "assistant", "tool_calls": []}
    final = SimpleNamespace(tool_calls=None, content="研究完成")
    completion = MagicMock(
        side_effect=[
            SimpleNamespace(choices=[SimpleNamespace(message=tool_message)]),
            SimpleNamespace(choices=[SimpleNamespace(message=final)]),
        ]
    )
    sdk = MagicMock()
    sdk.__enter__.return_value.chat.completions.create = completion
    monkeypatch.setattr("selfhost.agent.OpenAI", lambda **kwargs: sdk)
    request = ChatRequest(messages=[{"role": "user", "content": "比较 BTC ETH"}])
    result = chat(None, request)
    assert result["reply"] == "研究完成"
    assert len(result["reports"]) == 2
    assert completion.call_count == 2
