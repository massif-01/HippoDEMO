from __future__ import annotations

import asyncio

from orchestrator import main
from orchestrator.models import ServiceStatus
from orchestrator.store import OrchestratorStore


def run(coro):
    return asyncio.run(coro)


class FakeVlmacAdapter:
    def __init__(self) -> None:
        self.started = False

    async def status(self) -> ServiceStatus:
        return ServiceStatus(name="vlmac", status="unavailable", detail="vlmac not running")

    async def start(self) -> ServiceStatus:
        self.started = True
        return ServiceStatus(name="vlmac", status="online", detail="started")


def test_refresh_vlmac_status_autostarts_unavailable_service(monkeypatch):
    adapter = FakeVlmacAdapter()
    monkeypatch.setattr(main, "vlmac_adapter", adapter)
    monkeypatch.setattr(main, "store", OrchestratorStore())
    monkeypatch.setattr(main, "_vlmac_status_checked_at", 0.0)
    monkeypatch.setattr(main, "_vlmac_autostart_suppressed", False)

    service = run(main._refresh_vlmac_status())

    assert adapter.started is True
    assert service.status == "online"


def test_refresh_vlmac_status_respects_manual_stop_suppression(monkeypatch):
    adapter = FakeVlmacAdapter()
    monkeypatch.setattr(main, "vlmac_adapter", adapter)
    monkeypatch.setattr(main, "store", OrchestratorStore())
    monkeypatch.setattr(main, "_vlmac_status_checked_at", 0.0)
    monkeypatch.setattr(main, "_vlmac_autostart_suppressed", True)

    service = run(main._refresh_vlmac_status())

    assert adapter.started is False
    assert service.status == "unavailable"
