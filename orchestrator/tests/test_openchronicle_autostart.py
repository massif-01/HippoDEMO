from __future__ import annotations

import asyncio

from orchestrator import main
from orchestrator.models import ServiceStatus
from orchestrator.store import OrchestratorStore


def run(coro):
    return asyncio.run(coro)


class FakeOpenChronicleAdapter:
    def __init__(self, status: str = "stopped") -> None:
        self.started = False
        self._status = status

    async def status(self) -> ServiceStatus:
        return ServiceStatus(name="OpenChronicle", status=self._status, detail="daemon=stopped")

    async def start(self) -> ServiceStatus:
        self.started = True
        return ServiceStatus(name="OpenChronicle", status="online", detail="started")

    async def stop(self) -> ServiceStatus:
        return ServiceStatus(name="OpenChronicle", status="stopped", detail="stopped")


def test_refresh_openchronicle_status_autostarts_stopped_service(monkeypatch):
    adapter = FakeOpenChronicleAdapter("stopped")
    monkeypatch.setattr(main, "openchronicle_adapter", adapter)
    monkeypatch.setattr(main, "store", OrchestratorStore())
    monkeypatch.setattr(main, "_openchronicle_status_checked_at", 0.0)
    monkeypatch.setattr(main, "_openchronicle_autostart_suppressed", False)

    service = run(main._refresh_openchronicle_status())

    assert adapter.started is True
    assert service.status == "online"


def test_refresh_openchronicle_status_autostarts_unavailable_service(monkeypatch):
    adapter = FakeOpenChronicleAdapter("unavailable")
    monkeypatch.setattr(main, "openchronicle_adapter", adapter)
    monkeypatch.setattr(main, "store", OrchestratorStore())
    monkeypatch.setattr(main, "_openchronicle_status_checked_at", 0.0)
    monkeypatch.setattr(main, "_openchronicle_autostart_suppressed", False)

    service = run(main._refresh_openchronicle_status())

    assert adapter.started is True
    assert service.status == "online"


def test_refresh_openchronicle_status_respects_manual_stop_suppression(monkeypatch):
    adapter = FakeOpenChronicleAdapter("stopped")
    monkeypatch.setattr(main, "openchronicle_adapter", adapter)
    monkeypatch.setattr(main, "store", OrchestratorStore())
    monkeypatch.setattr(main, "_openchronicle_status_checked_at", 0.0)
    monkeypatch.setattr(main, "_openchronicle_autostart_suppressed", True)

    service = run(main._refresh_openchronicle_status())

    assert adapter.started is False
    assert service.status == "stopped"


def test_openchronicle_manual_start_clears_autostart_suppression(monkeypatch):
    adapter = FakeOpenChronicleAdapter("stopped")
    monkeypatch.setattr(main, "openchronicle_adapter", adapter)
    monkeypatch.setattr(main, "store", OrchestratorStore())
    monkeypatch.setattr(main, "_openchronicle_autostart_suppressed", True)

    run(main.openchronicle_start())

    assert main._openchronicle_autostart_suppressed is False


def test_openchronicle_manual_stop_sets_autostart_suppression(monkeypatch):
    adapter = FakeOpenChronicleAdapter("online")
    monkeypatch.setattr(main, "openchronicle_adapter", adapter)
    monkeypatch.setattr(main, "store", OrchestratorStore())
    monkeypatch.setattr(main, "_openchronicle_autostart_suppressed", False)

    run(main.openchronicle_stop())

    assert main._openchronicle_autostart_suppressed is True
