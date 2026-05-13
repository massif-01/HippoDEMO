from __future__ import annotations

import asyncio
import contextlib
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable

from ..adapters.cua_driver import cua_driver_adapter
from ..models import CuaTargetSurface, now_iso, new_id
from . import PlanWorkerStatus


EventSink = Callable[[str, dict[str, Any]], Awaitable[None] | None]


@dataclass
class ForegroundAXSnapshot:
    session_id: str
    safe: bool
    status: str
    mode: str
    reason: str
    bundle_id: str | None = None
    app_name: str | None = None
    pid: int | None = None
    window_id: int | None = None
    window_title: str | None = None
    focused_element: str | None = None
    visible_text: str | None = None
    tree_markdown: str | None = None
    editable_fields: list[dict[str, Any]] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("ax"))
    created_at: str = field(default_factory=now_iso)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


class AXDetectorWorker:
    def __init__(
        self,
        *,
        interval_seconds: float = 3.0,
        event_sink: EventSink | None = None,
    ) -> None:
        self.interval_seconds = max(0.5, interval_seconds)
        self.event_sink = event_sink
        self.session_id: str | None = None
        self.last_snapshot: ForegroundAXSnapshot | None = None
        self._task: asyncio.Task[None] | None = None
        self._status = PlanWorkerStatus(name="ax-detector")

    async def start(self, session_id: str) -> PlanWorkerStatus:
        self.session_id = session_id
        if self._task and not self._task.done():
            return self.status()
        permissions = await cua_driver_adapter.permission_status(prompt=False)
        if not permissions.get("accessibility") or not permissions.get("screen_recording"):
            self._status = PlanWorkerStatus(
                name="ax-detector",
                status="permission_required",
                detail=(
                    "CUA permissions are not already granted; AX detector will not poll in the background. "
                    f"{permissions.get('detail') or ''}"
                ),
                started_at=now_iso(),
                metadata={
                    "session_id": session_id,
                    "accessibility": permissions.get("accessibility"),
                    "screen_recording": permissions.get("screen_recording"),
                },
            )
            return self.status()
        self._status = PlanWorkerStatus(
            name="ax-detector",
            status="running",
            detail="Polling CUA target_surface for foreground AX snapshots.",
            started_at=now_iso(),
        )
        self._task = asyncio.create_task(self._run(), name="ax-detector")
        return self.status()

    async def stop(self) -> PlanWorkerStatus:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._status.status = "stopped"
        self._status.detail = "AX detector stopped."
        self._status.updated_at = now_iso()
        return self.status()

    async def snapshot(self) -> ForegroundAXSnapshot:
        surface = await cua_driver_adapter.target_surface()
        snapshot = self._snapshot_from_surface(surface)
        self.last_snapshot = snapshot
        return snapshot

    def status(self) -> PlanWorkerStatus:
        self._status.metadata = {
            "session_id": self.session_id,
            "last_snapshot_id": self.last_snapshot.id if self.last_snapshot else None,
            "last_signals": self.last_snapshot.signals if self.last_snapshot else [],
        }
        return self._status

    async def _run(self) -> None:
        while True:
            try:
                snapshot = await self.snapshot()
                await self._emit("ax_snapshot", snapshot.to_payload())
                for signal in snapshot.signals:
                    await self._emit(
                        signal,
                        {
                            "snapshot_id": snapshot.id,
                            "bundle_id": snapshot.bundle_id,
                            "app_name": snapshot.app_name,
                            "window_title": snapshot.window_title,
                            "reason": snapshot.reason,
                        },
                    )
                self._status.status = "running"
                self._status.detail = f"Last snapshot status={snapshot.status}; signals={snapshot.signals}"
            except Exception as exc:
                self._status.status = "degraded"
                self._status.detail = f"AX detector failed: {exc}"
            self._status.updated_at = now_iso()
            await asyncio.sleep(self.interval_seconds)

    def _snapshot_from_surface(self, surface: CuaTargetSurface) -> ForegroundAXSnapshot:
        editable_fields = []
        focused = None
        if surface.element_index is not None or surface.element_role:
            focused = f"{surface.element_role or 'AXElement'}#{surface.element_index}"
            editable_fields.append(
                {
                    "element_index": surface.element_index,
                    "element_role": surface.element_role,
                    "safe": surface.safe,
                }
            )
        signals = self._signals(surface)
        return ForegroundAXSnapshot(
            session_id=self.session_id or "",
            safe=surface.safe,
            status=surface.status,
            mode=surface.mode,
            reason=surface.reason,
            bundle_id=surface.bundle_id,
            app_name=surface.app_name,
            pid=surface.pid,
            window_id=surface.window_id,
            window_title=surface.window_title,
            focused_element=focused,
            visible_text=surface.detail,
            tree_markdown=None,
            editable_fields=editable_fields,
            signals=signals,
        )

    def _signals(self, surface: CuaTargetSurface) -> list[str]:
        bundle_id = surface.bundle_id or ""
        app_name = (surface.app_name or "").lower()
        signals: list[str] = []
        if bundle_id in {"com.tencent.xinWeChat", "com.tencent.WeWorkMac"} or "wechat" in app_name:
            signals.append("wechat_intent")
        if bundle_id == "com.apple.mail" and surface.pid is not None:
            signals.append("mail_compose_ready")
        return signals

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self.event_sink:
            return
        result = self.event_sink(event_type, payload)
        if asyncio.iscoroutine(result):
            await result
