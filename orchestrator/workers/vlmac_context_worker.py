from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any, Awaitable, Callable

from ..adapters.vlmac import VlmacAdapter, vlmac_adapter
from ..models import now_iso, new_id
from . import PlanWorkerStatus
from .basic_memory_queue import BasicMemoryWriteQueue, MemoryContextChunk


EventSink = Callable[[str, dict[str, Any]], Awaitable[None] | None]


class VlmacContextWorker:
    def __init__(
        self,
        *,
        memory_queue: BasicMemoryWriteQueue,
        adapter: VlmacAdapter = vlmac_adapter,
        interval_seconds: int = 45,
        poll_seconds: float = 10.0,
        event_sink: EventSink | None = None,
    ) -> None:
        self.memory_queue = memory_queue
        self.adapter = adapter
        self.interval_seconds = max(5, interval_seconds)
        self.poll_seconds = max(1.0, poll_seconds)
        self.event_sink = event_sink
        self.session_id: str | None = None
        self.task_id: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._seen_result_keys: set[str] = set()
        self._status = PlanWorkerStatus(name="vlmac-context")

    async def start(self, session_id: str) -> PlanWorkerStatus:
        self.session_id = session_id
        await self.memory_queue.start()
        start_result = await self.adapter.start_task(
            interval=self.interval_seconds,
            timer_prompt=(
                "Summarize the visible screen context for a Jarvis session. "
                "Focus on meeting artifacts, user intent, chat or mail composition cues, and recent changes."
            ),
        )
        if not start_result.get("ok", True) or start_result.get("error"):
            self._status = PlanWorkerStatus(
                name="vlmac-context",
                status="unavailable",
                detail=str(start_result.get("detail") or start_result.get("error") or start_result),
                started_at=now_iso(),
                metadata={"start_result": start_result},
            )
            return self.status()
        self.task_id = str(start_result.get("task_id") or "")
        self._status = PlanWorkerStatus(
            name="vlmac-context",
            status="running",
            detail=f"vlmac task started: {self.task_id or 'compat'}",
            started_at=now_iso(),
            metadata={"task_id": self.task_id, "start_result": start_result},
        )
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._run(), name="vlmac-context-worker")
        await self._emit("vlmac_context_started", {"session_id": session_id, "task_id": self.task_id})
        return self.status()

    async def stop(self) -> PlanWorkerStatus:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        stop_result = await self.adapter.stop_task(self.task_id or None)
        await self.memory_queue.flush()
        self._status.status = "stopped" if stop_result.get("ok", True) else "degraded"
        self._status.detail = str(stop_result.get("detail") or stop_result.get("status") or "vlmac task stopped")
        self._status.updated_at = now_iso()
        self._status.metadata = {"task_id": self.task_id, "stop_result": stop_result}
        await self._emit("vlmac_context_stopped", {"session_id": self.session_id, "task_id": self.task_id})
        self.task_id = None
        return self.status()

    def status(self) -> PlanWorkerStatus:
        self._status.metadata = {
            **self._status.metadata,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "seen_results": len(self._seen_result_keys),
        }
        return self._status

    async def _run(self) -> None:
        while True:
            try:
                await self._poll_once()
                if self._status.status == "degraded":
                    self._status.status = "running"
            except Exception as exc:
                self._status.status = "degraded"
                self._status.detail = f"vlmac result poll failed: {exc}"
                self._status.updated_at = now_iso()
            await asyncio.sleep(self.poll_seconds)

    async def _poll_once(self) -> None:
        result = await self.adapter.results(task_id=self.task_id or None, limit=20)
        if not result.get("ok", True) or result.get("error"):
            self._status.status = "degraded"
            self._status.detail = str(result.get("detail") or result.get("error") or result)
            self._status.updated_at = now_iso()
            return
        for item in result.get("results") or []:
            if not isinstance(item, dict):
                continue
            key = self._result_key(item)
            if key in self._seen_result_keys:
                continue
            content = self._result_content(item)
            if not content:
                continue
            self._seen_result_keys.add(key)
            chunk = MemoryContextChunk(
                session_id=self.session_id or "",
                source="video_context",
                content=content,
                start_at=str(item.get("timestamp") or item.get("created_at") or now_iso()),
                metadata={
                    "vlmac_task_id": self.task_id or item.get("task_id"),
                    "result_key": key,
                    "raw": item,
                },
            )
            await self.memory_queue.enqueue(chunk)
            await self._emit("video_context_ready", chunk.to_payload())
        self._status.detail = f"vlmac results polled; persisted={len(self._seen_result_keys)}"
        self._status.updated_at = now_iso()

    def _result_key(self, item: dict[str, Any]) -> str:
        for key in ("id", "result_id", "timestamp"):
            value = item.get(key)
            if value:
                return str(value)
        return str(abs(hash(json.dumps(item, sort_keys=True, default=str))))

    def _result_content(self, item: dict[str, Any]) -> str:
        for key in ("content", "answer", "text", "summary", "result"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return json.dumps(item, ensure_ascii=False, indent=2, default=str)

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self.event_sink:
            return
        result = self.event_sink(event_type, payload)
        if asyncio.iscoroutine(result):
            await result
