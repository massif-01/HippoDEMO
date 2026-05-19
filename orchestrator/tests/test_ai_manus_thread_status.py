from __future__ import annotations

import asyncio

from orchestrator import store as store_module
from orchestrator.adapters.ai_manus import AiManusAdapter
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


def test_ai_manus_status_uses_lightweight_auth_probe(monkeypatch):
    adapter = AiManusAdapter()
    adapter._config["auth_provider"] = "none"
    calls = []

    async def fake_request(method, path, timeout_seconds=None):
        calls.append((method, path, timeout_seconds))
        return {"auth_provider": "none"}

    monkeypatch.setattr(adapter, "_request", fake_request)

    service = run(adapter.status())

    assert service.status == "online"
    assert calls == [("GET", "/auth/status", 2.0)]
