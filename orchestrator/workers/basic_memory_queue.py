from __future__ import annotations

import asyncio
import contextlib
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from ..adapters.basic_memory import BasicMemoryAdapter, basic_memory_adapter
from ..models import now_iso, new_id
from . import PlanWorkerStatus


@dataclass
class MemoryContextChunk:
    session_id: str
    source: str
    content: str
    start_at: str | None = None
    end_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("mem"))
    created_at: str = field(default_factory=now_iso)

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["start_at"] = self.start_at or self.created_at
        payload["end_at"] = self.end_at or payload["start_at"]
        return payload


class BasicMemoryWriteQueue:
    def __init__(
        self,
        *,
        adapter: BasicMemoryAdapter = basic_memory_adapter,
        maxsize: int = 256,
    ) -> None:
        self.adapter = adapter
        self.queue: asyncio.Queue[MemoryContextChunk] = asyncio.Queue(maxsize=maxsize)
        self._task: asyncio.Task[None] | None = None
        self._status = PlanWorkerStatus(name="basic-memory-queue")
        self._written_count = 0
        self._last_error: str | None = None

    @property
    def written_count(self) -> int:
        return self._written_count

    async def start(self) -> PlanWorkerStatus:
        if self._task and not self._task.done():
            return self.status()
        self._status = PlanWorkerStatus(
            name="basic-memory-queue",
            status="running",
            detail="Serial BasicMemory write queue is running.",
            started_at=now_iso(),
        )
        self._task = asyncio.create_task(self._run(), name="basic-memory-write-queue")
        return self.status()

    async def stop(self) -> PlanWorkerStatus:
        await self.flush()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._status.status = "stopped"
        self._status.detail = "Serial BasicMemory write queue stopped after flush."
        self._status.updated_at = now_iso()
        self._status.metadata = self._metadata()
        return self.status()

    async def enqueue(self, chunk: MemoryContextChunk | Mapping[str, Any]) -> MemoryContextChunk:
        if isinstance(chunk, MemoryContextChunk):
            normalized = chunk
        else:
            normalized = MemoryContextChunk(
                session_id=str(chunk.get("session_id") or ""),
                source=str(chunk.get("source") or "unknown"),
                content=str(chunk.get("content") or ""),
                start_at=chunk.get("start_at") if chunk.get("start_at") is not None else None,
                end_at=chunk.get("end_at") if chunk.get("end_at") is not None else None,
                metadata=chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {},
                id=str(chunk.get("id") or new_id("mem")),
                created_at=str(chunk.get("created_at") or now_iso()),
            )
        if not self._task or self._task.done():
            await self.start()
        await self.queue.put(normalized)
        self._status.updated_at = now_iso()
        self._status.metadata = self._metadata()
        return normalized

    async def flush(self) -> None:
        await self.queue.join()

    def status(self) -> PlanWorkerStatus:
        self._status.metadata = self._metadata()
        return self._status

    async def _run(self) -> None:
        while True:
            chunk = await self.queue.get()
            try:
                await asyncio.to_thread(self.adapter.write_chunk, chunk.to_payload())
                self._written_count += 1
                self._last_error = None
                self._status.status = "running"
                self._status.detail = "Last BasicMemory chunk persisted."
            except Exception as exc:
                self._last_error = str(exc)
                self._status.status = "degraded"
                self._status.detail = f"BasicMemory write failed: {exc}"
            finally:
                self._status.updated_at = now_iso()
                self._status.metadata = self._metadata()
                self.queue.task_done()

    def _metadata(self) -> dict[str, Any]:
        return {
            "queued": self.queue.qsize(),
            "written_count": self._written_count,
            "last_error": self._last_error,
        }
