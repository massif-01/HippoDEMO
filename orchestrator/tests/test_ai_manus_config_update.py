from __future__ import annotations

import asyncio

from orchestrator import main
from orchestrator.models import AiManusConfigRequest, ServiceStatus
from orchestrator.store import OrchestratorStore


def run(coro):
    return asyncio.run(coro)


class FakeAiManusAdapter:
    def __init__(self) -> None:
        self.restart_called = False

    def update_config(self, **kwargs):
        return {
            "base_url": "http://127.0.0.1:8000",
            "frontend_url": "http://127.0.0.1:5173",
            "api_base_url": "http://127.0.0.1:8000/api/v1",
            "auth_provider": "none",
            "api_key_configured": True,
            "extra_headers_configured": False,
            "model_name": kwargs.get("model_name"),
            "restart_required": True,
        }

    def restart_runtime(self, *, build: bool = False):
        self.restart_called = True
        return {
            "action": "restart",
            "status": "failed",
            "detail": "ai-manus runtime command failed with exit code 1.",
            "returncode": 1,
            "log_path": "/tmp/ai-manus-runtime.log",
        }

    def config(self):
        return {
            "base_url": "http://127.0.0.1:8000",
            "frontend_url": "http://127.0.0.1:5173",
            "api_base_url": "http://127.0.0.1:8000/api/v1",
            "auth_provider": "none",
            "api_key_configured": True,
            "extra_headers_configured": False,
            "model_name": "qwen3.6-27b",
            "restart_required": True,
        }


def test_ai_manus_config_save_returns_payload_when_restart_fails(monkeypatch):
    adapter = FakeAiManusAdapter()
    monkeypatch.setattr(main, "ai_manus_adapter", adapter)
    monkeypatch.setattr(main, "store", OrchestratorStore())

    async def fake_wait_for_status(timeout_seconds: float = 0.0, interval_seconds: float = 0.5):
        return ServiceStatus(name="ai-manus", status="online", detail="api_base_url=http://127.0.0.1:8000/api/v1")

    monkeypatch.setattr(main, "_wait_for_ai_manus_status", fake_wait_for_status)

    response = run(main.ai_manus_update_config(AiManusConfigRequest(model_name="qwen3.6-27b")))

    assert adapter.restart_called is True
    assert response["model_name"] == "qwen3.6-27b"
    assert response["runtime_restart"]["status"] == "failed"
    assert response["detail"].startswith("Saved ai-manus config; restart failed:")
