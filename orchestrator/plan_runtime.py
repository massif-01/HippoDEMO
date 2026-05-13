from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable

from .adapters.basic_memory import basic_memory_adapter
from .followup import FollowUpPackage, prepare_follow_up_package
from .models import now_iso, new_id
from .workers import PlanWorkerStatus
from .workers.ax_detector import AXDetectorWorker, ForegroundAXSnapshot
from .workers.basic_memory_queue import BasicMemoryWriteQueue, MemoryContextChunk
from .workers.vlmac_context_worker import VlmacContextWorker


EventSink = Callable[[str, dict[str, Any]], Awaitable[None] | None]


@dataclass
class HighlightSegment:
    session_id: str
    check_in: str
    check_out: str | None = None
    status: str = "open"
    context_priority: str = "empty"
    generated_skill_id: str | None = None
    context_chunk_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("highlight"))
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


class PlanSessionRuntime:
    def __init__(
        self,
        *,
        session_id: str,
        event_sink: EventSink | None = None,
        vlmac_interval_seconds: int = 45,
    ) -> None:
        self.session_id = session_id
        self.event_sink = event_sink
        self.memory_queue = BasicMemoryWriteQueue()
        self.ax_detector = AXDetectorWorker(event_sink=self._emit)
        self.vlmac_worker = VlmacContextWorker(
            memory_queue=self.memory_queue,
            interval_seconds=vlmac_interval_seconds,
            event_sink=self._emit,
        )
        self.started_at: str | None = None
        self.stopped_at: str | None = None
        self.highlights: dict[str, HighlightSegment] = {}
        self.last_follow_up: FollowUpPackage | None = None
        self._running = False

    async def start(self) -> dict[str, Any]:
        if self._running:
            return self.snapshot()
        self.started_at = now_iso()
        self.stopped_at = None
        self._running = True
        await self.memory_queue.start()
        ax_status, vlmac_status = await asyncio.gather(
            self.ax_detector.start(self.session_id),
            self.vlmac_worker.start(self.session_id),
        )
        await self._emit(
            "plan_runtime_started",
            {
                "session_id": self.session_id,
                "workers": [ax_status.to_payload(), vlmac_status.to_payload(), self.memory_queue.status().to_payload()],
            },
        )
        return self.snapshot()

    async def stop(self) -> dict[str, Any]:
        if not self._running:
            return self.snapshot()
        vlmac_status, ax_status = await asyncio.gather(
            self.vlmac_worker.stop(),
            self.ax_detector.stop(),
        )
        memory_status = await self.memory_queue.stop()
        self.stopped_at = now_iso()
        self._running = False
        await self._emit(
            "plan_runtime_stopped",
            {
                "session_id": self.session_id,
                "workers": [vlmac_status.to_payload(), ax_status.to_payload(), memory_status.to_payload()],
            },
        )
        return self.snapshot()

    async def write_context(
        self,
        *,
        source: str,
        content: str,
        start_at: str | None = None,
        end_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryContextChunk:
        chunk = MemoryContextChunk(
            session_id=self.session_id,
            source=source,
            content=content,
            start_at=start_at,
            end_at=end_at,
            metadata=metadata or {},
        )
        await self.memory_queue.enqueue(chunk)
        await self._emit("memory_context_queued", chunk.to_payload())
        return chunk

    async def current_frontmost(self) -> ForegroundAXSnapshot:
        snapshot = await self.ax_detector.snapshot()
        await self._emit("ax_snapshot", snapshot.to_payload())
        return snapshot

    async def highlight_start(self, *, check_in: str | None = None) -> HighlightSegment:
        segment = HighlightSegment(
            session_id=self.session_id,
            check_in=check_in or now_iso(),
        )
        self.highlights[segment.id] = segment
        await self._emit("highlight_started", segment.to_payload())
        return segment

    async def highlight_finish(
        self,
        *,
        highlight_id: str | None = None,
        check_out: str | None = None,
        query: str | None = None,
    ) -> HighlightSegment:
        segment = self._resolve_highlight(highlight_id)
        segment.check_out = check_out or now_iso()
        context = basic_memory_adapter.build_context(
            session_id=self.session_id,
            start_at=segment.check_in,
            end_at=segment.check_out,
            query=query,
        )
        chunks = context.get("chunks") if isinstance(context.get("chunks"), list) else []
        segment.context_priority = str(context.get("context_priority") or "empty")
        segment.context_chunk_ids = [str(chunk.get("id")) for chunk in chunks if isinstance(chunk, dict) and chunk.get("id")]
        segment.status = "completed" if segment.context_chunk_ids else "empty"
        segment.updated_at = now_iso()
        segment.metadata = {
            "query": query,
            "chunk_count": context.get("chunk_count", len(chunks)),
        }
        await self._emit("highlight_finished", segment.to_payload())
        return segment

    async def prepare_follow_up(
        self,
        *,
        start_at: str | None = None,
        end_at: str | None = None,
        query: str | None = None,
    ) -> FollowUpPackage:
        package = prepare_follow_up_package(
            session_id=self.session_id,
            start_at=start_at,
            end_at=end_at,
            query=query,
        )
        self.last_follow_up = package
        await self._emit("follow_up_prepared", package.to_payload())
        return package

    async def flush(self) -> None:
        await self.memory_queue.flush()

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "running": self._running,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "workers": [status.to_payload() for status in self.worker_statuses()],
            "highlight_count": len(self.highlights),
            "last_follow_up": self.last_follow_up.to_payload() if self.last_follow_up else None,
        }

    def worker_statuses(self) -> list[PlanWorkerStatus]:
        return [
            self.memory_queue.status(),
            self.vlmac_worker.status(),
            self.ax_detector.status(),
        ]

    def _resolve_highlight(self, highlight_id: str | None) -> HighlightSegment:
        if highlight_id:
            if highlight_id not in self.highlights:
                raise KeyError(highlight_id)
            return self.highlights[highlight_id]
        for segment in reversed(list(self.highlights.values())):
            if segment.status == "open":
                return segment
        raise KeyError("No open highlight segment.")

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self.event_sink:
            return
        result = self.event_sink(event_type, payload)
        if asyncio.iscoroutine(result):
            await result


class PlanRuntimeManager:
    def __init__(self, *, event_sink: EventSink | None = None) -> None:
        self.event_sink = event_sink
        self._runtimes: dict[str, PlanSessionRuntime] = {}

    def get(self, session_id: str) -> PlanSessionRuntime | None:
        return self._runtimes.get(session_id)

    def get_or_create(self, session_id: str) -> PlanSessionRuntime:
        runtime = self._runtimes.get(session_id)
        if runtime:
            return runtime
        runtime = PlanSessionRuntime(session_id=session_id, event_sink=self.event_sink)
        self._runtimes[session_id] = runtime
        return runtime

    async def start(self, session_id: str) -> dict[str, Any]:
        return await self.get_or_create(session_id).start()

    async def stop(self, session_id: str) -> dict[str, Any]:
        runtime = self.get_or_create(session_id)
        snapshot = await runtime.stop()
        return snapshot

    def snapshot(self, session_id: str | None = None) -> dict[str, Any]:
        if session_id:
            runtime = self._runtimes.get(session_id)
            return runtime.snapshot() if runtime else {"session_id": session_id, "running": False, "workers": []}
        return {"runtimes": [runtime.snapshot() for runtime in self._runtimes.values()]}


plan_runtime = PlanRuntimeManager()
