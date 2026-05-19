from __future__ import annotations

import asyncio

import pytest

from orchestrator import main
from orchestrator import store as store_module
from orchestrator.models import AiManusThread
from orchestrator.store import OrchestratorStore


def run(coro):
    return asyncio.run(coro)


def test_ai_manus_delete_session_removes_local_thread(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "AI_MANUS_THREAD_DIR", tmp_path / "threads")
    local_store = OrchestratorStore()
    monkeypatch.setattr(main, "store", local_store)

    run(local_store.save_ai_manus_thread(AiManusThread(session_id="chat_thread_delete", title="Delete me")))
    run(local_store.save_ai_manus_thread(AiManusThread(session_id="chat_thread_keep", title="Keep me")))

    response = run(main.ai_manus_delete_session("chat_thread_delete"))

    assert response["status"] == "deleted"
    assert [thread["session_id"] for thread in response["sessions"]] == ["chat_thread_keep"]
    assert not (tmp_path / "threads" / "chat_thread_delete.json").exists()
    with pytest.raises(KeyError):
        local_store.get_ai_manus_thread("chat_thread_delete")
