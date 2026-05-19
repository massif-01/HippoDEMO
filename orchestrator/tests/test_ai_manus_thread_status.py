from __future__ import annotations

import asyncio
import json

import pytest

from orchestrator import store as store_module
from orchestrator.adapters import ai_manus as ai_manus_module
from orchestrator.adapters.ai_manus import AiManusAPIError, AiManusAdapter
from orchestrator.models import AiManusThread, AiManusThreadEvent
from orchestrator.store import OrchestratorStore


def run(coro):
    return asyncio.run(coro)


def test_step_and_tool_status_do_not_set_thread_status(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "AI_MANUS_THREAD_DIR", tmp_path / "threads")
    store = OrchestratorStore()
    thread = AiManusThread(session_id="chat_thread_status")

    run(store.save_ai_manus_thread(thread))
    run(store.append_ai_manus_event("chat_thread_status", AiManusThreadEvent(event="step", data={"status": "failed"})))
    run(store.append_ai_manus_event("chat_thread_status", AiManusThreadEvent(event="tool", data={"status": "called"})))

    loaded = store.get_ai_manus_thread("chat_thread_status")
    assert loaded.status == "active"


def test_done_and_thread_events_update_thread_status(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "AI_MANUS_THREAD_DIR", tmp_path / "threads")
    store = OrchestratorStore()
    thread = AiManusThread(session_id="chat_thread_done")

    run(store.save_ai_manus_thread(thread))
    run(store.append_ai_manus_event("chat_thread_done", AiManusThreadEvent(event="done")))

    assert store.get_ai_manus_thread("chat_thread_done").status == "completed"

    run(store.append_ai_manus_event("chat_thread_done", AiManusThreadEvent(event="thread", data={"status": "failed"})))

    assert store.get_ai_manus_thread("chat_thread_done").status == "failed"


def test_ai_manus_status_requires_auth_and_session_create_capability(monkeypatch):
    adapter = AiManusAdapter()
    adapter._config["auth_provider"] = "none"
    calls = []
    probed = False

    async def fake_request(method, path, timeout_seconds=None):
        calls.append((method, path, timeout_seconds))
        return {"auth_provider": "none"}

    async def fake_probe():
        nonlocal probed
        probed = True

    monkeypatch.setattr(adapter, "_request", fake_request)
    monkeypatch.setattr(adapter, "_probe_session_create_capability", fake_probe)

    service = run(adapter.status())

    assert service.status == "online"
    assert probed is True
    assert calls == [("GET", "/auth/status", 2.0)]


def test_ai_manus_status_rejects_backend_without_session_create_capability(monkeypatch):
    adapter = AiManusAdapter()
    adapter._config["auth_provider"] = "none"

    async def fake_request(method, path, timeout_seconds=None):
        return {"auth_provider": "none"}

    async def fake_probe():
        raise AiManusAPIError(
            "ai-manus session capability probe missing OpenAPI PUT /api/v1/sessions; "
            "api_base_url=http://127.0.0.1:8000/api/v1; title=Wrong Service; server=TianShanMock/1.0"
        )

    monkeypatch.setattr(adapter, "_request", fake_request)
    monkeypatch.setattr(adapter, "_probe_session_create_capability", fake_probe)

    service = run(adapter.status())

    assert service.status == "unavailable"
    assert "missing OpenAPI PUT" in service.detail
    assert "TianShanMock" in service.detail


class FakeHTTPResponse:
    def __init__(self, *, headers=None, payload=None, status_code: int = 200) -> None:
        self.headers = headers or {}
        self._payload = payload or {}
        self.status_code = status_code
        self.content = json.dumps(self._payload).encode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise ai_manus_module.httpx.HTTPStatusError(
                "HTTP error",
                request=ai_manus_module.httpx.Request("GET", "http://127.0.0.1"),
                response=ai_manus_module.httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


class FakeHTTPClient:
    def __init__(self, *, openapi_payload):
        self.calls = []
        self.openapi_payload = openapi_payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, url: str):
        self.calls.append(("GET", url))
        return FakeHTTPResponse(payload=self.openapi_payload)


class FakeRequestHTTPClient:
    def __init__(self) -> None:
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def request(self, method: str, url: str, json=None):
        self.calls.append((method, url, json))
        return FakeHTTPResponse(payload={"auth_provider": "none"})


def test_ai_manus_backend_request_disables_environment_proxy(monkeypatch):
    adapter = AiManusAdapter()
    client = FakeRequestHTTPClient()
    created_kwargs = {}

    def fake_async_client(*args, **kwargs):
        created_kwargs.update(kwargs)
        return client

    monkeypatch.setattr(ai_manus_module.httpx, "AsyncClient", fake_async_client)

    payload = run(adapter._request("GET", "/auth/status", timeout_seconds=2.0))

    assert payload == {"auth_provider": "none"}
    assert client.calls == [("GET", "http://127.0.0.1:8000/api/v1/auth/status", None)]
    assert created_kwargs["trust_env"] is False


def test_ai_manus_session_capability_probe_checks_openapi_put_route(monkeypatch):
    adapter = AiManusAdapter()
    adapter._config["base_url"] = "http://127.0.0.1:8000/api/v1"
    client = FakeHTTPClient(
        openapi_payload={"info": {"title": "Manus AI Agent"}, "paths": {"/api/v1/sessions": {"put": {}}}},
    )
    created_kwargs = {}

    def fake_async_client(*args, **kwargs):
        created_kwargs.update(kwargs)
        return client

    monkeypatch.setattr(ai_manus_module.httpx, "AsyncClient", fake_async_client)

    run(adapter._probe_session_create_capability())

    assert client.calls == [("GET", "http://127.0.0.1:8000/openapi.json")]
    assert created_kwargs["trust_env"] is False


def test_ai_manus_session_capability_probe_rejects_openapi_without_put(monkeypatch):
    adapter = AiManusAdapter()
    client = FakeHTTPClient(openapi_payload={"info": {"title": "Wrong Service"}, "paths": {}})
    monkeypatch.setattr(ai_manus_module.httpx, "AsyncClient", lambda *args, **kwargs: client)

    with pytest.raises(AiManusAPIError, match="missing OpenAPI PUT"):
        run(adapter._probe_session_create_capability())


def test_ai_manus_model_provider_proxy_env_is_disabled_for_local_urls():
    adapter = AiManusAdapter()

    assert adapter._trust_env_for_url("http://127.0.0.1:58000/v1/models") is False
    assert adapter._trust_env_for_url("http://0.0.0.0:58000/v1/models") is False
    assert adapter._trust_env_for_url("http://192.168.0.159:58000/v1/models") is False
    assert adapter._trust_env_for_url("https://dashscope.aliyuncs.com/compatible-mode/v1/models") is True
