from __future__ import annotations

import asyncio
import inspect
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .adapters.openchronicle import openchronicle_adapter
from .adapters.basic_memory import basic_memory_adapter
from .adapters.cua_driver import cua_driver_adapter
from .adapters.vlmac import vlmac_adapter
from .adapters.ai_manus import AiManusAuthRequired, ai_manus_adapter
from .adapters.project_cortex import sop_adapter
from .plan_runtime import plan_runtime
try:
    from .adapters.ownscribe import ownscribe_adapter
except ImportError:
    ownscribe_adapter = None
from .models import (
    ActiveTask,
    ActiveTaskGenerateRequest,
    ActiveTaskStatus,
    AiManusChatRequest,
    AiManusConfigRequest,
    AiManusCreateSessionRequest,
    AiManusFileViewRequest,
    AiManusRuntimeCommandRequest,
    AiManusSignedUrlRequest,
    AiManusThread,
    AiManusThreadEvent,
    AiManusThreadMessage,
    Artifact,
    BasicMemoryEmbeddingConfigRequest,
    CaptureFinishRequest,
    CaptureStatus,
    CuaTargetSurface,
    DemoSession,
    FollowUpPackage,
    ForegroundAXSnapshot,
    HighlightSegment,
    JarvisState,
    MailDraftInsertResult,
    MemoryContextChunk,
    OpenChronicleModelConfigRequest,
    OwnscribeConfigRequest,
    PlanWorkerStatus,
    ProjectCortexConfigRequest,
    ProposedAction,
    ServiceStatus,
    SkillGenerateRequest,
    SkillRecord,
    VlmacConfigRequest,
    new_id,
    now_iso,
)
from .store import SKILL_DIR, store, to_dict


app = FastAPI(title="HippoDEMO Orchestrator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENCHRONICLE_STATUS_TTL_SECONDS = 10.0
OWNSCRIBE_STATUS_TTL_SECONDS = 10.0
CUA_STATUS_TTL_SECONDS = 10.0
AI_MANUS_STATUS_TTL_SECONDS = 10.0
BASIC_MEMORY_STATUS_TTL_SECONDS = 10.0
VLMAC_STATUS_TTL_SECONDS = 10.0
_openchronicle_status_checked_at = 0.0
_ownscribe_status_checked_at = 0.0
_cua_status_checked_at = 0.0
_ai_manus_status_checked_at = 0.0
_basic_memory_status_checked_at = 0.0
_vlmac_status_checked_at = 0.0


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


OWNSCRIBE_STOP_TIMEOUT_SECONDS = _float_env("HIPPODEMO_OWNSCRIBE_STOP_TIMEOUT_SECONDS", 45.0)


def _artifact_payload(artifact: Artifact) -> dict:
    return {
        "id": artifact.id,
        "kind": artifact.type,
        "title": artifact.title,
        "path": artifact.path,
        "content": artifact.content,
        "created_at": artifact.created_at,
        "metadata": artifact.metadata,
    }


def _action_payload(action: ProposedAction) -> dict:
    return {
        "id": action.id,
        "type": action.target_type,
        "label": action.label,
        "requires_confirmation": action.requires_confirmation,
        "status": action.status,
    }


def _task_state(task: ActiveTask) -> str:
    if task.status == ActiveTaskStatus.AWAITING_REVIEW:
        return "task_reviewing"
    if task.status == ActiveTaskStatus.CONFIRMED:
        return "task_executing"
    if task.status == ActiveTaskStatus.COMPLETED:
        return "pattern_detected"
    return "active_task_candidate"


def _task_payload(task: ActiveTask) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "intent": task.intent,
        "confidence": task.confidence,
        "state": _task_state(task),
        "artifacts": [_artifact_payload(item) for item in task.artifacts],
        "proposed_actions": [_action_payload(action) for action in task.proposed_actions],
    }


def _skill_payload(skill: SkillRecord) -> dict:
    content = ""
    if skill.path:
        path = Path(skill.path)
        if path.exists():
            content = path.read_text(encoding="utf-8")
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "content": content,
        "created_at": skill.created_at,
        "source_session_id": skill.source_session_id,
        "source_task_id": skill.metadata.get("source_task_id"),
    }


def _service_payload(service: ServiceStatus) -> dict:
    return {
        "id": service.name.lower().replace(" ", "-"),
        "name": service.name,
        "status": service.status,
        "detail": service.detail,
    }


def _model_payload(model: Any) -> dict[str, Any] | None:
    if model is None:
        return None
    return to_dict(model)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _chunk_overlaps(chunk: MemoryContextChunk, *, start_at: str | None, end_at: str | None) -> bool:
    start = _parse_iso(start_at)
    end = _parse_iso(end_at)
    chunk_start = _parse_iso(chunk.start_at)
    chunk_end = _parse_iso(chunk.end_at)
    if not start or not end or not chunk_start or not chunk_end:
        return True
    return chunk_start <= end and chunk_end >= start


def _memory_chunks_for_window(
    *,
    session_id: str | None,
    start_at: str | None,
    end_at: str | None,
) -> list[MemoryContextChunk]:
    chunks = [
        chunk
        for chunk in store.state.memory_context_chunks
        if (not session_id or chunk.session_id == session_id)
        and _chunk_overlaps(chunk, start_at=start_at, end_at=end_at)
    ]
    known_ids = {chunk.id for chunk in chunks}
    for item in basic_memory_adapter.search_window(
        session_id=session_id,
        start_at=start_at,
        end_at=end_at,
        limit=50,
    ):
        try:
            chunk = MemoryContextChunk.model_validate(item)
        except Exception:
            continue
        if chunk.id in known_ids:
            continue
        chunks.append(chunk)
        known_ids.add(chunk.id)
    return sorted(chunks, key=lambda item: item.start_at)


def _context_priority(chunks: list[MemoryContextChunk]) -> str:
    sources = {chunk.source for chunk in chunks}
    if "video_context" in sources:
        return "video_context"
    if "audio_context" in sources:
        return "audio_context"
    if sources:
        return sorted(sources)[0]
    return "none"


def _context_summary(chunks: list[MemoryContextChunk], *, limit: int = 6) -> str:
    lines = []
    for chunk in chunks[:limit]:
        content = chunk.content.strip().replace("\n", " ")
        if len(content) > 320:
            content = content[:317].rstrip() + "..."
        lines.append(f"- [{chunk.source}] {chunk.start_at} -> {chunk.end_at}: {content}")
    if len(chunks) > limit:
        lines.append(f"- ... {len(chunks) - limit} more context chunk(s)")
    return "\n".join(lines)


def _worker_status_from_payload(payload: dict[str, Any]) -> PlanWorkerStatus:
    return PlanWorkerStatus(
        name=str(payload.get("name") or "worker"),
        status=str(payload.get("status") or "unknown"),
        detail=payload.get("detail"),
        started_at=payload.get("started_at"),
        updated_at=str(payload.get("updated_at") or now_iso()),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    )


def _apply_worker_status_payloads(payloads: list[Any]) -> None:
    statuses = [
        _worker_status_from_payload(payload)
        for payload in payloads
        if isinstance(payload, dict)
    ]
    if not statuses:
        return
    for status in statuses:
        replaced = False
        for index, existing in enumerate(store.state.worker_statuses):
            if existing.name.lower() == status.name.lower():
                store.state.worker_statuses[index] = status
                replaced = True
                break
        if not replaced:
            store.state.worker_statuses.append(status)
        _set_service_status(ServiceStatus(name=status.name, status=status.status, detail=status.detail))


def _runtime_snapshot_to_store(snapshot: dict[str, Any]) -> None:
    workers = snapshot.get("workers") if isinstance(snapshot.get("workers"), list) else []
    _apply_worker_status_payloads(workers)


def _runtime_chunk_from_payload(payload: dict[str, Any]) -> MemoryContextChunk:
    return MemoryContextChunk(
        id=str(payload.get("id") or new_id("chunk")),
        session_id=payload.get("session_id") or (store.state.current_session.id if store.state.current_session else None),
        source=str(payload.get("source") or "memory_context"),
        start_at=str(payload.get("start_at") or payload.get("created_at") or now_iso()),
        end_at=str(payload.get("end_at") or payload.get("start_at") or payload.get("created_at") or now_iso()),
        content=str(payload.get("content") or ""),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        created_at=str(payload.get("created_at") or now_iso()),
    )


def _runtime_frontmost_from_payload(payload: dict[str, Any]) -> ForegroundAXSnapshot:
    editable_fields = payload.get("editable_fields") if isinstance(payload.get("editable_fields"), list) else []
    metadata = {
        "source": "plan_runtime",
        "status": payload.get("status"),
        "mode": payload.get("mode"),
        "reason": payload.get("reason"),
        "signals": payload.get("signals") if isinstance(payload.get("signals"), list) else [],
        "session_id": payload.get("session_id"),
    }
    return ForegroundAXSnapshot(
        bundle_id=payload.get("bundle_id"),
        app_name=payload.get("app_name"),
        window_title=payload.get("window_title"),
        focused_element=payload.get("focused_element"),
        visible_text=str(payload.get("visible_text") or ""),
        tree_markdown=str(payload.get("tree_markdown") or ""),
        editable_fields=editable_fields,
        target_surface=None,
        captured_at=str(payload.get("created_at") or now_iso()),
        metadata=metadata,
    )


async def _plan_runtime_event_sink(event_type: str, payload: dict[str, Any]) -> None:
    session_id = payload.get("session_id")
    if not session_id and store.state.current_session:
        session_id = store.state.current_session.id
    async with store._lock:
        if event_type in {"memory_context_queued", "video_context_ready"}:
            chunk = _runtime_chunk_from_payload(payload)
            await store.add_memory_context_chunk(chunk)
        elif event_type == "ax_snapshot":
            store.state.frontmost_context = _runtime_frontmost_from_payload(payload)
            await store.persist()
        elif event_type in {"plan_runtime_started", "plan_runtime_stopped"}:
            workers = payload.get("workers") if isinstance(payload.get("workers"), list) else []
            _apply_worker_status_payloads(workers)
            await store.persist()
        await store.publish(event_type, payload, session_id=session_id)


plan_runtime.event_sink = _plan_runtime_event_sink


def _ai_manus_session_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    return payload.get("session_id") or payload.get("id")


def _ai_manus_remote_session_id(thread: AiManusThread) -> str:
    return thread.manus_session_id or str(thread.metadata.get("manus_session_id") or thread.session_id)


def _unix_timestamp(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(value).timestamp())
    except ValueError:
        return None


def _ai_manus_message_payload(message: AiManusThreadMessage) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "timestamp": _unix_timestamp(message.timestamp),
        "event_id": message.event_id,
        "attachments": message.attachments,
    }


def _ai_manus_event_payload(event: AiManusThreadEvent) -> dict:
    return {
        "event": event.event,
        "data": event.data,
    }


def _ai_manus_link_metadata() -> dict:
    session = store.state.current_session
    if not session:
        return {
            "hippo_session_id": None,
            "hippo_session_title": None,
            "hippo_artifacts": [],
        }
    return {
        "hippo_session_id": session.id,
        "hippo_session_title": session.title,
        "hippo_artifacts": [
            {
                "id": artifact.id,
                "type": artifact.type,
                "title": artifact.title,
                "path": artifact.path,
            }
            for artifact in session.artifacts
        ],
    }


def _refresh_ai_manus_thread_links(thread: AiManusThread) -> AiManusThread:
    thread.metadata.update(_ai_manus_link_metadata())
    return thread


def _ai_manus_remote_summary(payload: Any) -> dict | None:
    if not isinstance(payload, dict):
        return None
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    file_summary = []
    for item in files[:20]:
        if not isinstance(item, dict):
            continue
        file_summary.append(
            {
                "name": item.get("name") or item.get("filename") or item.get("path"),
                "path": item.get("path"),
                "size": item.get("size") or item.get("size_bytes"),
            }
        )
    return {
        "session_id": payload.get("session_id") or payload.get("id"),
        "title": payload.get("title"),
        "status": payload.get("status"),
        "files_count": len(files),
        "files": file_summary,
    }


def _ai_manus_thread_summary(thread: AiManusThread) -> dict:
    return {
        "session_id": thread.session_id,
        "manus_session_id": _ai_manus_remote_session_id(thread),
        "title": thread.title,
        "status": thread.status,
        "latest_message": thread.latest_message,
        "latest_message_at": thread.latest_message_at,
        "unread_message_count": thread.unread_message_count,
        "is_shared": thread.is_shared,
        "updated_at": thread.updated_at,
    }


def _ai_manus_thread_detail(thread: AiManusThread) -> dict:
    return {
        **_ai_manus_thread_summary(thread),
        "created_at": thread.created_at,
        "messages": [_ai_manus_message_payload(message) for message in thread.messages],
        "events": [_ai_manus_event_payload(event) for event in thread.events],
        "remote": thread.metadata.get("remote"),
        "metadata": {
            key: value
            for key, value in thread.metadata.items()
            if key.lower() not in {"api_key", "authorization", "token"}
        },
    }


def _ai_manus_status_payload(service: ServiceStatus) -> dict:
    return {
        "ok": service.status == "online",
        "status": service.status,
        "detail": service.detail,
        "config": ai_manus_adapter.config(),
    }


def _ai_manus_thread_or_404(thread_id: str) -> AiManusThread:
    try:
        return store.get_ai_manus_thread(thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown ai-manus thread: {thread_id}") from exc


async def _require_ai_manus_online() -> ServiceStatus:
    service = await ai_manus_adapter.status()
    async with store._lock:
        await _apply_ai_manus_status(service)
    if service.status == "auth_required":
        raise HTTPException(status_code=409, detail=ai_manus_adapter.auth_required_payload()["detail"])
    if service.status != "online":
        raise HTTPException(status_code=503, detail=service.detail or "ai-manus backend unavailable")
    return service


def _ai_manus_files_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict) and isinstance(payload.get("files"), list):
        return len(payload["files"])
    return 0


def _ai_manus_file_path(request: AiManusFileViewRequest) -> str:
    file_path = request.file_path or request.file or request.path
    if not file_path:
        raise HTTPException(status_code=422, detail="file_path is required")
    return file_path


def _sse(event: str, data: Any = None, *, event_id: str | None = None) -> str:
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data or {}, ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


def _set_service_status(service: ServiceStatus) -> None:
    for index, existing in enumerate(store.state.services):
        if existing.name.lower() == service.name.lower():
            store.state.services[index] = service
            return
    store.state.services.append(service)


def _ownscribe_unavailable_service(detail: str = "ownscribe adapter not installed") -> ServiceStatus:
    return ServiceStatus(name="ownscribe", status="unavailable", detail=detail)


def _coerce_ownscribe_service(value: Any, *, fallback_status: str = "available", fallback_detail: str | None = None) -> ServiceStatus:
    if isinstance(value, ServiceStatus):
        return ServiceStatus(
            name="ownscribe",
            status=value.status,
            detail=value.detail,
            updated_at=value.updated_at,
        )
    if hasattr(value, "ok"):
        ok = bool(getattr(value, "ok", False))
        detail = getattr(value, "detail", None) or getattr(value, "error", None) or fallback_detail
        if not ok:
            return ServiceStatus(name="ownscribe", status="error", detail=str(detail or "ownscribe command failed"))
        status = fallback_status
        if getattr(value, "transcript_path", None) or getattr(value, "summary_path", None):
            status = "available"
        elif "recording started" in str(detail or "").lower():
            status = "recording"
        return ServiceStatus(name="ownscribe", status=status, detail=str(detail or "ownscribe command completed"))
    if isinstance(value, dict):
        service_value = value.get("service") or value.get("status_service")
        if service_value:
            return _coerce_ownscribe_service(
                service_value,
                fallback_status=fallback_status,
                fallback_detail=fallback_detail,
            )
        return ServiceStatus(
            name=str(value.get("name") or "ownscribe"),
            status=str(value.get("status") or fallback_status),
            detail=str(value.get("detail") or value.get("message") or fallback_detail or ""),
        )
    status = getattr(value, "status", fallback_status)
    detail = getattr(value, "detail", fallback_detail)
    return ServiceStatus(name="ownscribe", status=str(status), detail=str(detail or ""))


def _call_with_supported_kwargs(method, kwargs: dict[str, Any]):
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return method(**kwargs)
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return method(**kwargs)
    accepted = {
        name: value
        for name, value in kwargs.items()
        if name in signature.parameters
    }
    return method(**accepted)


async def _call_ownscribe(method_names: tuple[str, ...], **kwargs: Any) -> tuple[Any, ServiceStatus]:
    if ownscribe_adapter is None:
        return None, _ownscribe_unavailable_service()

    for method_name in method_names:
        method = getattr(ownscribe_adapter, method_name, None)
        if not method:
            continue
        try:
            result = _call_with_supported_kwargs(method, kwargs)
            if inspect.isawaitable(result):
                result = await result
            return result, _coerce_ownscribe_service(result)
        except Exception as exc:
            return None, ServiceStatus(
                name="ownscribe",
                status="error",
                detail=f"{method_name} failed: {exc}",
            )

    return None, _ownscribe_unavailable_service(
        f"ownscribe adapter missing methods: {', '.join(method_names)}",
    )


async def _refresh_openchronicle_status() -> ServiceStatus:
    global _openchronicle_status_checked_at

    now = time.monotonic()
    current = next(
        (service for service in store.state.services if service.name.lower() == "openchronicle"),
        None,
    )
    if current and now - _openchronicle_status_checked_at < OPENCHRONICLE_STATUS_TTL_SECONDS:
        return current

    service = await openchronicle_adapter.status()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
        _openchronicle_status_checked_at = time.monotonic()
        return service


async def _refresh_ownscribe_status() -> ServiceStatus:
    global _ownscribe_status_checked_at

    now = time.monotonic()
    current = next(
        (service for service in store.state.services if service.name.lower() == "ownscribe"),
        None,
    )
    if current and now - _ownscribe_status_checked_at < OWNSCRIBE_STATUS_TTL_SECONDS:
        return current

    result, service = await _call_ownscribe(("status", "get_status"))
    if result is None and service.status == "unavailable" and current:
        service.detail = f"{service.detail}; previous={current.status}"
    async with store._lock:
        _set_service_status(service)
        await store.persist()
        _ownscribe_status_checked_at = time.monotonic()
        return service


async def _refresh_cua_status() -> ServiceStatus:
    global _cua_status_checked_at

    now = time.monotonic()
    current = next(
        (service for service in store.state.services if service.name.lower() == "cua-driver"),
        None,
    )
    if current and now - _cua_status_checked_at < CUA_STATUS_TTL_SECONDS:
        return current

    service = await cua_driver_adapter.status()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
        _cua_status_checked_at = time.monotonic()
        return service


async def _refresh_ai_manus_status() -> ServiceStatus:
    global _ai_manus_status_checked_at

    now = time.monotonic()
    current = next(
        (service for service in store.state.services if service.name.lower() == "ai-manus"),
        None,
    )
    if current and now - _ai_manus_status_checked_at < AI_MANUS_STATUS_TTL_SECONDS:
        return current

    service = await ai_manus_adapter.status()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
        _ai_manus_status_checked_at = time.monotonic()
        return service


async def _refresh_basic_memory_status() -> ServiceStatus:
    global _basic_memory_status_checked_at

    now = time.monotonic()
    current = next(
        (service for service in store.state.services if service.name.lower() == "basic-memory"),
        None,
    )
    if current and now - _basic_memory_status_checked_at < BASIC_MEMORY_STATUS_TTL_SECONDS:
        return current

    service = basic_memory_adapter.status()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
        _basic_memory_status_checked_at = time.monotonic()
        return service


async def _refresh_vlmac_status() -> ServiceStatus:
    global _vlmac_status_checked_at

    now = time.monotonic()
    current = next(
        (service for service in store.state.services if service.name.lower() == "vlmac"),
        None,
    )
    if current and now - _vlmac_status_checked_at < VLMAC_STATUS_TTL_SECONDS:
        return current

    service = await vlmac_adapter.status()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
        _vlmac_status_checked_at = time.monotonic()
        return service


async def _apply_openchronicle_status(service: ServiceStatus) -> None:
    global _openchronicle_status_checked_at

    _set_service_status(service)
    await store.persist()
    _openchronicle_status_checked_at = time.monotonic()


async def _apply_ownscribe_status(service: ServiceStatus) -> None:
    global _ownscribe_status_checked_at

    _set_service_status(service)
    await store.persist()
    _ownscribe_status_checked_at = time.monotonic()


async def _apply_cua_status(service: ServiceStatus) -> None:
    global _cua_status_checked_at

    _set_service_status(service)
    await store.persist()
    _cua_status_checked_at = time.monotonic()


async def _apply_ai_manus_status(service: ServiceStatus) -> None:
    global _ai_manus_status_checked_at

    _set_service_status(service)
    await store.persist()
    _ai_manus_status_checked_at = time.monotonic()


async def _apply_basic_memory_status(service: ServiceStatus) -> None:
    global _basic_memory_status_checked_at

    _set_service_status(service)
    await store.persist()
    _basic_memory_status_checked_at = time.monotonic()


async def _apply_vlmac_status(service: ServiceStatus) -> None:
    global _vlmac_status_checked_at

    _set_service_status(service)
    await store.persist()
    _vlmac_status_checked_at = time.monotonic()


def _sop_state() -> str:
    status = store.state.sop_capture.status
    if status == CaptureStatus.CAPTURING:
        return "sop_marking"
    if status == CaptureStatus.GENERATING:
        return "sop_generating"
    if store.state.jarvis_state == JarvisState.INTERVENTION_READY:
        return "active_task_candidate"
    if store.state.jarvis_state == JarvisState.AWAITING_REVIEW:
        return "task_reviewing"
    return store.state.jarvis_state.value


def _frontend_state() -> str:
    capture_status = store.state.sop_capture.status
    if capture_status == CaptureStatus.CAPTURING:
        return "sop_marking"
    if capture_status == CaptureStatus.GENERATING:
        return "sop_generating"

    if store.state.jarvis_state == JarvisState.INTERVENTION_READY:
        return "active_task_candidate"
    if store.state.jarvis_state == JarvisState.AWAITING_REVIEW:
        return "task_reviewing"
    return store.state.jarvis_state.value


def _status_message(frontend_state: str) -> str:
    messages = {
        "idle": "Waiting for task",
        "meeting_active": "Listening to meeting, screen, and context",
        "paused": "Jarvis paused",
        "sop_marking": "Capture Skill is active",
        "sop_generating": "Generating Skill...",
        "active_task_candidate": "Ready to Act",
        "task_reviewing": "Inserted content is waiting for your review",
        "pattern_detected": "Reusable pattern detected",
    }
    return messages.get(frontend_state, "Jarvis is ready")


def _session_payload(session: DemoSession | None) -> dict | None:
    if not session:
        return None
    return {
        "id": session.id,
        "title": session.title,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "artifacts": [_artifact_payload(item) for item in session.artifacts],
    }


def _current_task() -> ActiveTask | None:
    for task in store.state.active_tasks:
        if task.status not in {ActiveTaskStatus.IGNORED, ActiveTaskStatus.COMPLETED}:
            return task
    return None


def state_payload():
    frontend_state = _frontend_state()
    current_task = _current_task()
    return {
        "jarvis_state": frontend_state,
        "status_message": _status_message(frontend_state),
        "current_session": _session_payload(store.state.current_session),
        "sop_capture": {
            "check_in": store.state.sop_capture.check_in,
            "check_out": store.state.sop_capture.check_out,
            "state": _sop_state(),
        },
        "highlight_segment": _model_payload(store.state.highlight_segment),
        "frontmost_context": _model_payload(store.state.frontmost_context),
        "follow_up_package": _model_payload(store.state.follow_up_package),
        "mail_draft_insert_result": _model_payload(store.state.mail_draft_insert_result),
        "worker_statuses": [to_dict(status) for status in store.state.worker_statuses],
        "memory_context_chunks": [to_dict(chunk) for chunk in store.state.memory_context_chunks[-20:]],
        "current_task": _task_payload(current_task) if current_task else None,
        "skills": [_skill_payload(skill) for skill in store.state.skills],
        "services": [_service_payload(service) for service in store.state.services],
    }


def mock_meeting_artifacts(session: DemoSession) -> list[Artifact]:
    minutes = Artifact(
        type="meeting_minutes",
        title="Investor meeting minutes",
        content=f"""# Investor Meeting Minutes

Session: `{session.id}`
Ended: {session.ended_at or now_iso()}

## Summary
Discussed HippoDEMO as a macOS menu-bar Jarvis that records meeting context, prepares follow-up work, and waits for explicit user confirmation before taking externally visible action.

## Key Points
- Product center is Active Task rather than a single meeting-notes feature.
- First demo path is mock-first and controlled.
- Follow-up content should be ready when the user opens a communication or compose surface.
""",
    )
    follow_up = Artifact(
        type="follow_up_body",
        title="Follow-up draft",
        content="""Hi, thanks again for the conversation today.

I summarized the main points we discussed around HippoDEMO: a macOS menu-bar Jarvis that captures meeting context, prepares follow-up material, and only inserts content after explicit confirmation.

Next steps from our side:
1. Share a short demo build covering Jarvis ON/OFF, Active Task, and Skill capture.
2. Send the architecture note for the orchestrator and local skill store.
3. Follow up with the concrete integration questions we discussed.
""",
    )
    action_items = Artifact(
        type="action_items",
        title="Action items",
        content="""# Action Items

- Share HippoDEMO mock-first demo build.
- Send Orchestrator API contract and local storage note.
- Prepare follow-up answers for investor integration questions.
""",
    )
    return [minutes, follow_up, action_items]


def _payload_from_result(result: Any) -> dict[str, Any]:
    def json_safe(value: Any) -> Any:
        try:
            return json.loads(json.dumps(value, ensure_ascii=False, default=str))
        except TypeError:
            return str(value)

    if result is None:
        return {}
    if isinstance(result, dict):
        return json_safe(result)
    if hasattr(result, "model_dump"):
        return json_safe(result.model_dump(mode="json"))
    if hasattr(result, "__dict__"):
        return json_safe(dict(result.__dict__))
    return {"value": str(result)}


def _stringify_artifact_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def _read_text_if_possible(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    if path.suffix.lower() not in {".md", ".txt", ".json"}:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _artifact_from_path(path: Path, *, artifact_type: str, title: str) -> Artifact | None:
    if not path.exists():
        return None
    content = _read_text_if_possible(path)
    if not content:
        content = f"{title}: {path}"
    return Artifact(
        type=artifact_type,
        title=title,
        content=content,
        metadata={"source": "ownscribe", "source_path": str(path)},
    )


def _ownscribe_artifact_from_item(item: Any) -> Artifact | None:
    payload = _payload_from_result(item)
    artifact_type = payload.get("type") or payload.get("kind")
    title = payload.get("title") or payload.get("name")
    path_value = payload.get("path") or payload.get("file") or payload.get("file_path")
    content = payload.get("content") or payload.get("text") or payload.get("body")
    if not artifact_type and path_value:
        suffix = Path(str(path_value)).name
        if suffix.startswith("transcript."):
            artifact_type = "meeting_transcript"
            title = title or "ownscribe transcript"
        elif suffix.startswith("summary."):
            artifact_type = "meeting_minutes"
            title = title or "ownscribe summary"
        elif suffix.startswith("recording."):
            artifact_type = "audio_recording"
            title = title or "ownscribe audio recording"
        elif suffix.startswith("recording_timeline."):
            artifact_type = "recording_timeline"
            title = title or "ownscribe recording timeline"
    if not artifact_type:
        return None
    if path_value and not content:
        content = _read_text_if_possible(Path(str(path_value)))
    if not content and path_value:
        content = f"{title or artifact_type}: {path_value}"
    if not content:
        return None
    return Artifact(
        type=str(artifact_type),
        title=str(title or artifact_type).replace("_", " ").title(),
        content=_stringify_artifact_value(content),
        metadata={"source": "ownscribe", **dict(payload.get("metadata") or {})},
    )


def ownscribe_artifacts(result: Any, session: DemoSession) -> list[Artifact]:
    payload = _payload_from_result(result)
    artifacts: list[Artifact] = []

    for item in payload.get("artifacts") or []:
        artifact = _ownscribe_artifact_from_item(item)
        if artifact:
            artifacts.append(artifact)

    output_dir = payload.get("output_dir") or payload.get("meeting_dir") or payload.get("directory")
    if output_dir:
        directory = Path(str(output_dir)).expanduser()
        for ext in ("md", "json"):
            transcript = _artifact_from_path(directory / f"transcript.{ext}", artifact_type="meeting_transcript", title="ownscribe transcript")
            if transcript:
                artifacts.append(transcript)
                break
        for ext in ("md", "json"):
            summary = _artifact_from_path(directory / f"summary.{ext}", artifact_type="meeting_minutes", title="ownscribe summary")
            if summary:
                artifacts.append(summary)
                break
        for name in ("recording.wav", "recording.mp3", "recording.m4a"):
            audio = _artifact_from_path(directory / name, artifact_type="audio_recording", title="ownscribe audio recording")
            if audio:
                artifacts.append(audio)
                break
        timeline = _artifact_from_path(
            directory / "recording_timeline.json",
            artifact_type="recording_timeline",
            title="ownscribe recording timeline",
        )
        if timeline:
            artifacts.append(timeline)

    transcript = payload.get("transcript") or payload.get("transcript_text")
    if transcript:
        session.transcript.append(
            {
                "timestamp": now_iso(),
                "speaker": "ownscribe",
                "text": _stringify_artifact_value(transcript),
            }
        )
        artifacts.append(
            Artifact(
                type="meeting_transcript",
                title="ownscribe transcript",
                content=_stringify_artifact_value(transcript),
                metadata={"source": "ownscribe"},
            )
        )

    summary = payload.get("summary") or payload.get("summary_text")
    if summary:
        artifacts.append(
            Artifact(
                type="meeting_minutes",
                title="ownscribe summary",
                content=_stringify_artifact_value(summary),
                metadata={"source": "ownscribe"},
            )
        )

    audio = payload.get("audio") or payload.get("audio_path") or payload.get("recording_path")
    if audio:
        artifacts.append(
            Artifact(
                type="audio_recording",
                title="ownscribe audio recording",
                content=f"Audio recording: {audio}",
                metadata={"source": "ownscribe", "source_path": str(audio)},
            )
        )

    seen: set[tuple[str, str, str]] = set()
    unique_artifacts: list[Artifact] = []
    for artifact in artifacts:
        key = (artifact.type, artifact.title, artifact.content)
        if key in seen:
            continue
        seen.add(key)
        unique_artifacts.append(artifact)
    return unique_artifacts


def build_active_task(session: DemoSession, artifacts: list[Artifact], target_type: str = "communication") -> ActiveTask:
    follow_up = next((item for item in artifacts if item.type == "follow_up_body"), None)
    action_items = next((item for item in artifacts if item.type == "action_items"), None)
    return ActiveTask(
        title="Insert investor follow-up draft",
        intent="Prepare and insert a post-meeting follow-up draft after user confirmation.",
        source_session_id=session.id,
        artifacts=artifacts,
        proposed_actions=[
            ProposedAction(
                label="Insert follow-up body",
                target_type=target_type,
                external_visible=False,
                payload={"artifact_id": follow_up.id if follow_up else None, "mode": "insert_draft"},
            ),
            ProposedAction(
                label="Attach action items",
                target_type="document",
                external_visible=False,
                payload={"artifact_id": action_items.id if action_items else None, "mode": "append_reference"},
            ),
        ],
    )


def _artifact_by_id(task: ActiveTask, artifact_id: str | None) -> Artifact | None:
    if not artifact_id:
        return None
    for artifact in task.artifacts:
        if artifact.id == artifact_id:
            return artifact
    return None


def _insert_action_and_text(task: ActiveTask) -> tuple[ProposedAction | None, str | None]:
    for action in task.proposed_actions:
        if action.payload.get("mode") not in {"insert_draft", "insert_mail_draft"}:
            continue
        artifact = _artifact_by_id(
            task,
            action.payload.get("artifact_id") or action.payload.get("body_artifact_id"),
        )
        if artifact and artifact.content and artifact.content.strip():
            return action, artifact.content.strip()
        return action, None
    return None, None


def _action_target_surface(action: ProposedAction) -> CuaTargetSurface | None:
    payload = action.payload.get("target_surface")
    if not isinstance(payload, dict):
        return None
    try:
        return CuaTargetSurface.model_validate(payload)
    except Exception:
        return None


def _cua_result_payload(result) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "detail": result.detail,
        "target_pid": result.target_pid,
        "target_app": result.target_app,
        "target_bundle_id": result.target_bundle_id,
        "text_chars": result.text_chars,
    }


def _snapshot_from_surface(surface: CuaTargetSurface) -> ForegroundAXSnapshot:
    editable_fields = []
    if surface.element_index is not None:
        editable_fields.append(
            {
                "index": surface.element_index,
                "role": surface.element_role,
                "mode": surface.mode,
            }
        )
    return ForegroundAXSnapshot(
        bundle_id=surface.bundle_id,
        app_name=surface.app_name,
        window_title=surface.window_title,
        focused_element=surface.element_role,
        visible_text=surface.window_title or "",
        tree_markdown="",
        editable_fields=editable_fields,
        target_surface=surface,
        metadata={"source": "cua_target_surface", "status": surface.status, "reason": surface.reason},
    )


def _wechat_intent_from_snapshot(snapshot: ForegroundAXSnapshot) -> dict[str, Any] | None:
    text = "\n".join(
        item
        for item in [snapshot.visible_text, snapshot.tree_markdown, snapshot.window_title or ""]
        if item
    ).lower()
    if snapshot.bundle_id not in {"com.tencent.xinWeChat", "com.tencent.WeWorkMac"} and "微信" not in text and "wechat" not in text:
        return None
    keywords = ["会议纪要", "发邮件", "邮件", "follow up", "follow-up", "send email", "meeting notes"]
    matched = [keyword for keyword in keywords if keyword.lower() in text]
    if not matched:
        return None
    return {
        "type": "wechat_intent",
        "matched": matched,
        "bundle_id": snapshot.bundle_id,
        "window_title": snapshot.window_title,
        "captured_at": snapshot.captured_at,
    }


def _mail_compose_ready_from_snapshot(snapshot: ForegroundAXSnapshot) -> bool:
    if snapshot.bundle_id not in {"com.apple.mail", "com.microsoft.Outlook"}:
        return False
    title = (snapshot.window_title or "").lower()
    if any(marker in title for marker in ["new message", "compose", "新邮件", "撰写"]):
        return True
    return bool(snapshot.editable_fields)


def _target_surface_payload(surface: CuaTargetSurface) -> dict[str, Any]:
    return to_dict(surface)


def _sync_task_target_surface(task: ActiveTask, surface: CuaTargetSurface) -> None:
    payload = _target_surface_payload(surface)
    for action in task.proposed_actions:
        if action.payload.get("mode") != "insert_draft":
            continue
        action.payload["target_surface"] = payload
        if action.status in {"proposed", "target_ready", "waiting_for_target", "insert_failed"}:
            action.status = "target_ready" if surface.safe else "waiting_for_target"


async def generate_skill_record(
    *,
    check_in: str | None,
    check_out: str | None,
    source_session_id: str | None,
    name: str | None = None,
    description: str | None = None,
) -> SkillRecord:
    result = await sop_adapter.generate(
        check_in=check_in,
        check_out=check_out,
        source_session_id=source_session_id,
        name=name,
        description=description,
    )
    sop_config = sop_adapter.config()
    model_configured = bool(sop_config.get("openai_base_url") and sop_config.get("openai_model"))
    skill_id = new_id("skill")
    path = SKILL_DIR / f"{skill_id}.md"
    skill = SkillRecord(
        id=skill_id,
        name=result.name,
        description=result.description,
        path=str(path),
        source_session_id=source_session_id,
        check_in=check_in,
        check_out=check_out,
        metadata={
            "adapter": "Project_Cortex",
            "mock": not sop_adapter.use_real and not model_configured,
            "generation_mode": "project_cortex_service" if sop_adapter.use_real else ("openai_compatible" if model_configured else "mock"),
        },
    )
    await store.add_skill(skill, result.mdfile)
    await store.publish("skill_generated", to_dict(skill), session_id=source_session_id)
    return skill


@app.get("/health", response_model=ServiceStatus)
async def health() -> ServiceStatus:
    return ServiceStatus(name="HippoDEMO Orchestrator", status="ok", detail="mock-first FastAPI service")


@app.get("/state")
async def get_state():
    await _refresh_openchronicle_status()
    await _refresh_ownscribe_status()
    await _refresh_basic_memory_status()
    await _refresh_vlmac_status()
    await _refresh_cua_status()
    await _refresh_ai_manus_status()
    return state_payload()


@app.get("/plan")
async def plan_status():
    return {
        "highlight_segment": _model_payload(store.state.highlight_segment),
        "frontmost_context": _model_payload(store.state.frontmost_context),
        "follow_up_package": _model_payload(store.state.follow_up_package),
        "mail_draft_insert_result": _model_payload(store.state.mail_draft_insert_result),
        "worker_statuses": [to_dict(status) for status in store.state.worker_statuses],
        "memory_context_chunks": [to_dict(chunk) for chunk in store.state.memory_context_chunks[-20:]],
    }


@app.get("/events/history")
async def event_history(limit: int = 50):
    return [to_dict(event) for event in store.bus.history(limit)]


@app.get("/events")
async def events():
    queue = await store.bus.subscribe()

    async def stream() -> AsyncGenerator[str, None]:
        yield "event: connected\ndata: {\"status\":\"ok\"}\n\n"
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(to_dict(event), ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': now_iso()})}\n\n"
        finally:
            store.bus.unsubscribe(queue)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/session/jarvis-on")
async def jarvis_on():
    session = DemoSession(
        transcript=[
            {
                "timestamp": now_iso(),
                "speaker": "system",
                "text": "Recording started. OpenChronicle and ownscribe collectors are being coordinated by Orchestrator.",
            }
        ],
        metadata={"mode": "adapter-first"},
    )
    openchronicle_service = await openchronicle_adapter.start()
    ownscribe_result, ownscribe_service = await _call_ownscribe(
        ("start_recording", "start", "record"),
        session_id=session.id,
    )
    runtime_snapshot = await plan_runtime.start(session.id)
    ownscribe_ok = ownscribe_service.status not in {"error", "unavailable"}
    session.metadata["ownscribe"] = _payload_from_result(ownscribe_result)
    session.metadata["plan_runtime"] = runtime_snapshot
    if not ownscribe_ok:
        session.metadata["mode"] = "adapter-first-with-ownscribe-fallback"
    async with store._lock:
        store.state.current_session = session
        store.state.jarvis_state = JarvisState.MEETING_ACTIVE
        store.state.sop_capture.status = CaptureStatus.IDLE
        _runtime_snapshot_to_store(runtime_snapshot)
        await _apply_openchronicle_status(openchronicle_service)
        await _apply_ownscribe_status(ownscribe_service)
        await store.persist()
        await store.publish("session_started", to_dict(session), session_id=session.id)
        await store.publish(
            "ownscribe_recording_started" if ownscribe_ok else "ownscribe_recording_failed",
            {
                "action": "start_recording",
                "service": to_dict(ownscribe_service),
                "fallback": not ownscribe_ok,
            },
            session_id=session.id,
        )
        return state_payload()


@app.post("/session/jarvis-off")
async def jarvis_off():
    if not store.state.current_session:
        raise HTTPException(status_code=409, detail="No active session to stop.")
    session_id = store.state.current_session.id
    openchronicle_service = await openchronicle_adapter.stop()
    runtime_snapshot = await plan_runtime.stop(session_id)
    ownscribe_result, ownscribe_service = await _call_ownscribe(
        ("stop_recording", "stop", "finish", "finalize"),
        session_id=session_id,
        stop_timeout=OWNSCRIBE_STOP_TIMEOUT_SECONDS,
        terminate_timeout=5.0,
        kill_timeout=2.0,
    )
    async with store._lock:
        session = store.state.current_session
        if not session:
            raise HTTPException(status_code=409, detail="No active session to stop.")
        session.ended_at = now_iso()
        session.state = JarvisState.ACTIVE_TASK_CANDIDATE
        session.metadata["plan_runtime"] = runtime_snapshot
        artifacts = ownscribe_artifacts(ownscribe_result, session)
        ownscribe_ok = ownscribe_service.status not in {"error", "unavailable"} and bool(artifacts)
        if not ownscribe_ok:
            artifacts = mock_meeting_artifacts(session)
            if ownscribe_service.status not in {"error", "unavailable"}:
                ownscribe_service = ServiceStatus(
                    name="ownscribe",
                    status="error",
                    detail="stop_recording returned no transcript, summary, or audio artifacts; using mock fallback",
                )
        persisted_artifacts = []
        for artifact in artifacts:
            persisted_artifacts.append(await store.add_artifact(artifact, session=session))
            await store.publish("artifact_ready", to_dict(artifact), session_id=session.id)
        task = build_active_task(session, persisted_artifacts)
        await store.add_active_task(task)
        store.state.jarvis_state = JarvisState.INTERVENTION_READY
        session.state = JarvisState.INTERVENTION_READY
        await _apply_openchronicle_status(openchronicle_service)
        await _apply_ownscribe_status(ownscribe_service)
        _runtime_snapshot_to_store(runtime_snapshot)
        await store.persist()
        await store.publish(
            "ownscribe_recording_stopped" if ownscribe_ok else "ownscribe_recording_failed",
            {
                "action": "stop_recording",
                "service": to_dict(ownscribe_service),
                "artifact_count": len(persisted_artifacts),
                "fallback": not ownscribe_ok,
                "target_surface": "deferred_until_user_detection_or_insert",
            },
            session_id=session.id,
        )
        if ownscribe_ok:
            await store.publish(
                "ownscribe_artifacts_ingested",
                {
                    "artifact_ids": [artifact.id for artifact in persisted_artifacts],
                    "artifact_types": [artifact.type for artifact in persisted_artifacts],
                },
                session_id=session.id,
            )
        await store.publish("active_task_generated", to_dict(task), session_id=session.id)
        await store.publish(
            "intervention_signal_waiting",
            {
                "task_id": task.id,
                "reason": "target_surface_deferred_until_user_detection_or_insert",
            },
            session_id=session.id,
        )
        await store.publish("session_stopped", to_dict(session), session_id=session.id)
        return state_payload()


@app.post("/session/pause")
async def pause_session():
    async with store._lock:
        if not store.state.current_session:
            raise HTTPException(status_code=409, detail="No active session to pause.")
        store.state.jarvis_state = JarvisState.PAUSED
        store.state.current_session.state = JarvisState.PAUSED
        await store.persist()
        await store.publish("session_paused", {}, session_id=store.state.current_session.id)
        return state_payload()


@app.post("/session/resume")
async def resume_session():
    async with store._lock:
        if not store.state.current_session:
            raise HTTPException(status_code=409, detail="No paused session to resume.")
        store.state.jarvis_state = JarvisState.MEETING_ACTIVE
        store.state.current_session.state = JarvisState.MEETING_ACTIVE
        await store.persist()
        await store.publish("session_resumed", {}, session_id=store.state.current_session.id)
        return state_payload()


async def _openchronicle_command_snapshot(action: str, command) -> dict:
    service = await command()
    async with store._lock:
        await _apply_openchronicle_status(service)
        await store.publish("openchronicle_command", {"action": action, "service": to_dict(service)})
        return state_payload()


@app.post("/integrations/openchronicle/start")
async def openchronicle_start():
    return await _openchronicle_command_snapshot("start", openchronicle_adapter.start)


@app.post("/integrations/openchronicle/stop")
async def openchronicle_stop():
    return await _openchronicle_command_snapshot("stop", openchronicle_adapter.stop)


@app.post("/integrations/openchronicle/pause")
async def openchronicle_pause():
    return await _openchronicle_command_snapshot("pause", openchronicle_adapter.pause)


@app.post("/integrations/openchronicle/resume")
async def openchronicle_resume():
    return await _openchronicle_command_snapshot("resume", openchronicle_adapter.resume)


@app.post("/integrations/openchronicle/capture-once")
async def openchronicle_capture_once():
    return await _openchronicle_command_snapshot("capture-once", openchronicle_adapter.capture_once)


@app.post("/integrations/openchronicle/rebuild-captures-index")
async def openchronicle_rebuild_captures_index():
    return await _openchronicle_command_snapshot(
        "rebuild-captures-index",
        openchronicle_adapter.rebuild_captures_index,
    )


@app.post("/integrations/openchronicle/timeline-tick")
async def openchronicle_timeline_tick():
    return await _openchronicle_command_snapshot("timeline-tick", openchronicle_adapter.timeline_tick)


@app.get("/integrations/openchronicle/model-config")
async def openchronicle_model_config(stage: str = "default"):
    try:
        return openchronicle_adapter.model_config(stage)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/integrations/openchronicle/model-config")
async def openchronicle_update_model_config(request: OpenChronicleModelConfigRequest):
    try:
        config = openchronicle_adapter.update_model_config(
            stage=request.stage,
            model=request.model,
            base_url=request.base_url,
            api_key_env=request.api_key_env,
            api_key=request.api_key,
            max_tokens=request.max_tokens,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    async with store._lock:
        await store.publish(
            "openchronicle_model_config_updated",
            {
                "stage": config.get("stage"),
                "model": config.get("model"),
                "base_url": config.get("base_url"),
                "api_key_configured": config.get("api_key_configured"),
                "restart_required": config.get("restart_required"),
            },
        )
    return config


@app.get("/integrations/vlmac/status")
async def vlmac_status():
    service = await vlmac_adapter.status()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
    return to_dict(service)


@app.get("/integrations/vlmac/config")
async def vlmac_config():
    return vlmac_adapter.config()


@app.post("/integrations/vlmac/config")
async def vlmac_update_config(request: VlmacConfigRequest):
    try:
        config = vlmac_adapter.update_config(
            service_base_url=request.service_base_url,
            vllm_base_url=request.vllm_base_url,
            vllm_model=request.vllm_model,
            vllm_api_key=request.vllm_api_key,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            timeout_seconds=request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    service = await vlmac_adapter.status()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
        await store.publish(
            "vlmac_config_updated",
            {
                "service_base_url": config.get("service_base_url"),
                "vllm_base_url": config.get("vllm_base_url"),
                "vllm_model": config.get("vllm_model"),
                "api_key_configured": config.get("vllm_api_key_configured"),
                "restart_required": config.get("restart_required"),
            },
        )
    return config


@app.get("/integrations/basic-memory/status")
async def basic_memory_status():
    service = basic_memory_adapter.status()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
    return to_dict(service)


@app.get("/integrations/basic-memory/embedding-config")
async def basic_memory_embedding_config():
    return basic_memory_adapter.config()


@app.post("/integrations/basic-memory/embedding-config")
async def basic_memory_update_embedding_config(request: BasicMemoryEmbeddingConfigRequest):
    try:
        config = basic_memory_adapter.update_embedding_config(
            semantic_search_enabled=request.semantic_search_enabled,
            semantic_embedding_provider=request.semantic_embedding_provider,
            semantic_embedding_model=request.semantic_embedding_model,
            semantic_embedding_base_url=request.semantic_embedding_base_url,
            semantic_embedding_api_key=request.semantic_embedding_api_key,
            semantic_embedding_api_key_env=request.semantic_embedding_api_key_env,
            semantic_embedding_dimensions=request.semantic_embedding_dimensions,
            semantic_embedding_batch_size=request.semantic_embedding_batch_size,
            semantic_embedding_request_concurrency=request.semantic_embedding_request_concurrency,
            semantic_embedding_timeout=request.semantic_embedding_timeout,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    service = basic_memory_adapter.status()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
        await store.publish(
            "basic_memory_embedding_config_updated",
            {
                "provider": config.get("semantic_embedding_provider"),
                "model": config.get("semantic_embedding_model"),
                "base_url": config.get("semantic_embedding_base_url"),
                "api_key_configured": config.get("semantic_embedding_api_key_configured"),
                "restart_required": config.get("restart_required"),
            },
        )
    return config


@app.get("/integrations/project-cortex/status")
async def project_cortex_status():
    service = await sop_adapter.status()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
    return to_dict(service)


@app.get("/integrations/project-cortex/config")
async def project_cortex_config():
    return sop_adapter.config()


@app.post("/integrations/project-cortex/config")
async def project_cortex_update_config(request: ProjectCortexConfigRequest):
    try:
        config = sop_adapter.update_config(
            use_real=request.use_real,
            service_base_url=request.service_base_url,
            openai_base_url=request.openai_base_url,
            openai_model=request.openai_model,
            openai_api_key=request.openai_api_key,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            timeout_seconds=request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    service = await sop_adapter.status()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
        await store.publish(
            "project_cortex_config_updated",
            {
                "use_real": config.get("use_real"),
                "service_base_url": config.get("service_base_url"),
                "openai_base_url": config.get("openai_base_url"),
                "openai_model": config.get("openai_model"),
                "api_key_configured": config.get("openai_api_key_configured"),
            },
        )
    return config


def _require_ownscribe_adapter():
    if ownscribe_adapter is None:
        raise HTTPException(status_code=503, detail="ownscribe adapter not installed")
    return ownscribe_adapter


@app.get("/integrations/ownscribe/config")
async def ownscribe_config():
    adapter = _require_ownscribe_adapter()
    return adapter.config()


@app.post("/integrations/ownscribe/config")
async def ownscribe_update_config(request: OwnscribeConfigRequest):
    adapter = _require_ownscribe_adapter()
    try:
        config = adapter.update_config(
            audio_source=request.audio_source,
            mic_device=request.mic_device,
            audio_display=request.audio_display,
            asr_provider=request.asr_provider,
            asr_base_url=request.asr_base_url,
            asr_model=request.asr_model,
            asr_api_key=request.asr_api_key,
            summary_provider=request.summary_provider,
            summary_base_url=request.summary_base_url,
            summary_model=request.summary_model,
            summary_api_key=request.summary_api_key,
            api_key=request.api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    service = await adapter.status()
    async with store._lock:
        await _apply_ownscribe_status(service)
        await store.publish("ownscribe_config_updated", config)
    return config


@app.get("/integrations/ownscribe/audio-devices")
async def ownscribe_audio_devices():
    adapter = _require_ownscribe_adapter()
    return adapter.audio_devices()


@app.get("/integrations/ownscribe/preflight")
async def ownscribe_preflight(network: bool = False):
    adapter = _require_ownscribe_adapter()
    return adapter.preflight(network=network)


@app.get("/integrations/ai-manus/config")
async def ai_manus_config():
    return ai_manus_adapter.config()


@app.post("/integrations/ai-manus/config")
async def ai_manus_update_config(request: AiManusConfigRequest):
    config = ai_manus_adapter.update_config(
        base_url=request.base_url,
        frontend_url=request.frontend_url,
        auth_provider=request.auth_provider,
        api_key=request.api_key,
        timeout_seconds=request.timeout_seconds,
        api_base=request.api_base,
        model_name=request.model_name,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        extra_headers=request.extra_headers,
    )
    service = await ai_manus_adapter.status()
    async with store._lock:
        await _apply_ai_manus_status(service)
        await store.publish(
            "ai_manus_config_updated",
            {
                "base_url": config["base_url"],
                "frontend_url": config["frontend_url"],
                "api_base_url": config["api_base_url"],
                "auth_provider": config["auth_provider"],
                "api_key_configured": config["api_key_configured"],
                "extra_headers_configured": config.get("extra_headers_configured"),
                "model_name": config.get("model_name"),
                "restart_required": config.get("restart_required"),
            },
        )
    return config


@app.get("/integrations/ai-manus/status")
async def ai_manus_status():
    service = await ai_manus_adapter.status()
    async with store._lock:
        await _apply_ai_manus_status(service)
        return _ai_manus_status_payload(service)


@app.post("/integrations/ai-manus/runtime/start")
async def ai_manus_runtime_start(request: AiManusRuntimeCommandRequest | None = None):
    result = ai_manus_adapter.start_runtime(build=bool(request.build) if request else False)
    service = await ai_manus_adapter.status()
    async with store._lock:
        await _apply_ai_manus_status(service)
        await store.publish(
            "ai_manus_runtime_command",
            {
                "action": result.get("action"),
                "status": result.get("status"),
                "pid": result.get("pid"),
                "log_path": result.get("log_path"),
            },
        )
    return {**result, "service": to_dict(service)}


@app.post("/integrations/ai-manus/runtime/stop")
async def ai_manus_runtime_stop():
    result = ai_manus_adapter.stop_runtime()
    service = await ai_manus_adapter.status()
    async with store._lock:
        await _apply_ai_manus_status(service)
        await store.publish(
            "ai_manus_runtime_command",
            {
                "action": result.get("action"),
                "status": result.get("status"),
                "pid": result.get("pid"),
                "log_path": result.get("log_path"),
            },
        )
    return {**result, "service": to_dict(service)}


@app.post("/integrations/ai-manus/runtime/restart")
async def ai_manus_runtime_restart(request: AiManusRuntimeCommandRequest | None = None):
    result = ai_manus_adapter.restart_runtime(build=bool(request.build) if request else False)
    service = await ai_manus_adapter.status()
    async with store._lock:
        await _apply_ai_manus_status(service)
        await store.publish(
            "ai_manus_runtime_command",
            {
                "action": result.get("action"),
                "status": result.get("status"),
                "pid": result.get("pid"),
                "log_path": result.get("log_path"),
            },
        )
    return {**result, "service": to_dict(service)}


@app.get("/integrations/ai-manus/runtime/logs")
async def ai_manus_runtime_logs(limit: int = 80):
    return ai_manus_adapter.runtime_logs(limit=limit)


@app.post("/integrations/ai-manus/session")
@app.put("/integrations/ai-manus/sessions")
async def ai_manus_create_session(request: AiManusCreateSessionRequest | None = None):
    service = await ai_manus_adapter.status()
    async with store._lock:
        await _apply_ai_manus_status(service)
    if service.status == "auth_required":
        raise HTTPException(status_code=409, detail=ai_manus_adapter.auth_required_payload()["detail"])
    if service.status != "online":
        raise HTTPException(status_code=503, detail=service.detail or "ai-manus backend unavailable")
    try:
        data = await ai_manus_adapter.create_session()
    except AiManusAuthRequired:
        raise HTTPException(status_code=409, detail=ai_manus_adapter.auth_required_payload()["detail"]) from None
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ai-manus create session failed: {exc}") from exc

    manus_session_id = _ai_manus_session_id(data)
    if not manus_session_id:
        raise HTTPException(status_code=502, detail="ai-manus create session returned no session_id")
    thread_id = new_id("manus_thread")
    thread = AiManusThread(
        session_id=thread_id,
        manus_session_id=manus_session_id,
        title=(request.title if request else None) or (data.get("title") if isinstance(data, dict) else None),
        status=str(data.get("status") or "active") if isinstance(data, dict) else "active",
        metadata={
            "source": "ai-manus",
            "manus_session_id": manus_session_id,
            **_ai_manus_link_metadata(),
        },
    )
    async with store._lock:
        await store.save_ai_manus_thread(thread)
        await store.publish(
            "ai_manus_session_created",
            {"session_id": thread_id, "manus_session_id": manus_session_id, "status": thread.status},
            session_id=thread_id,
        )
    return {
        "session_id": thread_id,
        "manus_session_id": manus_session_id,
        "thread": _ai_manus_thread_summary(thread),
    }


@app.get("/integrations/ai-manus/sessions")
async def ai_manus_sessions():
    local_threads = [_ai_manus_thread_summary(thread) for thread in store.list_ai_manus_threads()]
    service = await ai_manus_adapter.status()
    async with store._lock:
        await _apply_ai_manus_status(service)
    if service.status == "auth_required":
        return {**ai_manus_adapter.auth_required_payload(), "sessions": local_threads, "local_threads": local_threads}
    if service.status != "online":
        return {
            "status": service.status,
            "detail": service.detail,
            "sessions": local_threads,
            "local_threads": local_threads,
        }
    try:
        data = await ai_manus_adapter.list_sessions()
    except AiManusAuthRequired:
        return {**ai_manus_adapter.auth_required_payload(), "sessions": local_threads, "local_threads": local_threads}
    except Exception as exc:
        return {
            "status": "unavailable",
            "detail": f"ai-manus list sessions failed: {exc}",
            "sessions": local_threads,
            "local_threads": local_threads,
        }
    return {"status": "online", "remote": data, "sessions": local_threads, "local_threads": local_threads}


@app.get("/integrations/ai-manus/session/{session_id}")
@app.get("/integrations/ai-manus/session/{session_id}/detail")
@app.get("/integrations/ai-manus/sessions/{session_id}")
async def ai_manus_session_detail(session_id: str):
    try:
        local_thread = store.get_ai_manus_thread(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown ai-manus thread: {session_id}") from None

    detail = _ai_manus_thread_detail(local_thread)
    service = await ai_manus_adapter.status()
    async with store._lock:
        await _apply_ai_manus_status(service)
    if service.status != "online":
        detail["remote_status"] = service.status
        detail["remote_detail"] = service.detail
        return detail

    try:
        remote_data = await ai_manus_adapter.get_session(_ai_manus_remote_session_id(local_thread))
        remote = _ai_manus_remote_summary(remote_data)
        if remote:
            detail["remote"] = remote
            detail["remote_status"] = remote.get("status")
            if remote.get("title") and not detail.get("title"):
                detail["title"] = remote["title"]
            if remote.get("status"):
                detail["status"] = str(remote["status"])
            async with store._lock:
                local_thread.metadata["remote"] = remote
                await store.save_ai_manus_thread(local_thread)
    except Exception as exc:
        detail["remote_status"] = "unavailable"
        detail["remote_detail"] = str(exc)
    return detail


@app.post("/integrations/ai-manus/session/{session_id}/chat")
@app.post("/integrations/ai-manus/sessions/{session_id}/chat")
async def ai_manus_chat(session_id: str, request: AiManusChatRequest):
    async def stream() -> AsyncGenerator[str, None]:
        try:
            thread = store.get_ai_manus_thread(session_id)
        except KeyError:
            yield _sse("error", {"error": f"Unknown ai-manus thread: {session_id}"})
            return
        thread = _refresh_ai_manus_thread_links(thread)
        await store.save_ai_manus_thread(thread)

        service = await ai_manus_adapter.status()
        async with store._lock:
            await _apply_ai_manus_status(service)
        if service.status == "auth_required":
            yield _sse("auth_required", ai_manus_adapter.auth_required_payload())
            return
        if service.status != "online":
            await store.publish("ai_manus_chat_failed", {"session_id": session_id}, session_id=session_id)
            yield _sse("error", {"error": service.detail or "ai-manus backend unavailable"})
            return

        message_chars = len(request.message or "")
        attachments_count = len(request.attachments or [])
        try:
            if request.message:
                await store.append_ai_manus_message(
                    session_id,
                    AiManusThreadMessage(
                        role="user",
                        content=request.message,
                        event_id=request.event_id,
                        attachments=request.attachments or [],
                    ),
                )
            await store.publish(
                "ai_manus_chat_started",
                {
                    "session_id": session_id,
                    "message_chars": message_chars,
                    "attachments_count": attachments_count,
                },
                session_id=session_id,
            )

            event_count = 0
            async for sse_event in ai_manus_adapter.stream_chat(
                session_id=_ai_manus_remote_session_id(thread),
                message=request.message,
                timestamp=request.timestamp,
                event_id=request.event_id,
                attachments=request.attachments,
            ):
                event_count += 1
                event_name = str(sse_event.get("event") or "message")
                data = sse_event.get("data") or {}
                await store.append_ai_manus_event(
                    session_id,
                    AiManusThreadEvent(
                        event=event_name,
                        data=data if isinstance(data, dict) else {"value": data},
                        event_id=sse_event.get("id"),
                    ),
                )
                if event_name in {"plan", "plan_updated"}:
                    steps_count = 0
                    if isinstance(data, dict) and isinstance(data.get("steps"), list):
                        steps_count = len(data["steps"])
                    await store.publish(
                        "ai_manus_plan_updated",
                        {"session_id": session_id, "steps_count": steps_count},
                        session_id=session_id,
                    )
                if event_name in {"tool", "tool_event"}:
                    tool_payload = {
                        "session_id": session_id,
                        "tool_call_id": data.get("tool_call_id") if isinstance(data, dict) else None,
                        "name": data.get("name") if isinstance(data, dict) else None,
                        "function": data.get("function") if isinstance(data, dict) else None,
                        "status": data.get("status") if isinstance(data, dict) else None,
                    }
                    await store.publish("ai_manus_tool_event", tool_payload, session_id=session_id)
                if event_name == "message" and isinstance(data, dict) and data.get("role") == "assistant":
                    content = str(data.get("content") or data.get("message") or "")
                    if content:
                        await store.append_ai_manus_message(
                            session_id,
                            AiManusThreadMessage(role="assistant", content=content, event_id=sse_event.get("id")),
                        )
                yield _sse(event_name, data, event_id=sse_event.get("id"))

            await store.publish(
                "ai_manus_chat_completed",
                {"session_id": session_id, "event_count": event_count},
                session_id=session_id,
            )
        except AiManusAuthRequired:
            yield _sse("auth_required", ai_manus_adapter.auth_required_payload())
        except Exception as exc:
            with_error = AiManusThreadEvent(event="error", data={"error": str(exc)})
            try:
                await store.append_ai_manus_event(session_id, with_error)
            except KeyError:
                pass
            await store.publish("ai_manus_chat_failed", {"session_id": session_id}, session_id=session_id)
            yield _sse("error", {"error": str(exc)})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/integrations/ai-manus/session/{thread_id}/sandbox-access")
async def ai_manus_sandbox_access(thread_id: str, request: AiManusSignedUrlRequest | None = None):
    thread = _ai_manus_thread_or_404(thread_id)
    remote_session_id = _ai_manus_remote_session_id(thread)
    await _require_ai_manus_online()
    expire_minutes = request.expire_minutes if request else 15
    try:
        data = await ai_manus_adapter.sandbox_access(remote_session_id, expire_minutes)
    except AiManusAuthRequired:
        raise HTTPException(status_code=409, detail=ai_manus_adapter.auth_required_payload()["detail"]) from None
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ai-manus sandbox access failed: {exc}") from exc

    response = data if isinstance(data, dict) else {"remote": data}
    frontend_url = str(ai_manus_adapter.config().get("frontend_url") or "").rstrip("/")
    if frontend_url:
        response.setdefault("frontend_url", frontend_url)
        response.setdefault("interactive_url", f"{frontend_url}/chat/{remote_session_id}")
        response.setdefault("take_over_url", f"{frontend_url}/chat/{remote_session_id}?vnc=1")
    response.setdefault("backend_url", ai_manus_adapter.config().get("api_base_url"))
    if response.get("signed_url"):
        response.setdefault("websocket_url", response["signed_url"])
    response.setdefault("status", "ready")
    response.setdefault("requires_confirmation", True)
    async with store._lock:
        await store.publish(
            "ai_manus_sandbox_access_created",
            {
                "session_id": thread_id,
                "manus_session_id": remote_session_id,
                "expires_in": response.get("expires_in"),
            },
            session_id=thread_id,
        )
    return {"session_id": thread_id, "manus_session_id": remote_session_id, **response}


@app.get("/integrations/ai-manus/session/{thread_id}/files")
async def ai_manus_session_files(thread_id: str):
    thread = _ai_manus_thread_or_404(thread_id)
    remote_session_id = _ai_manus_remote_session_id(thread)
    await _require_ai_manus_online()
    try:
        files = await ai_manus_adapter.session_files(remote_session_id)
    except AiManusAuthRequired:
        raise HTTPException(status_code=409, detail=ai_manus_adapter.auth_required_payload()["detail"]) from None
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ai-manus list files failed: {exc}") from exc

    async with store._lock:
        await store.publish(
            "ai_manus_files_listed",
            {
                "session_id": thread_id,
                "manus_session_id": remote_session_id,
                "files_count": _ai_manus_files_count(files),
            },
            session_id=thread_id,
        )
    return {
        "session_id": thread_id,
        "manus_session_id": remote_session_id,
        "files": files if isinstance(files, list) else files.get("files", []) if isinstance(files, dict) else [],
        "count": _ai_manus_files_count(files),
        "status": "ready",
    }


@app.post("/integrations/ai-manus/session/{thread_id}/file-view")
async def ai_manus_file_view(thread_id: str, request: AiManusFileViewRequest):
    thread = _ai_manus_thread_or_404(thread_id)
    remote_session_id = _ai_manus_remote_session_id(thread)
    file_path = _ai_manus_file_path(request)
    await _require_ai_manus_online()
    try:
        data = await ai_manus_adapter.view_file(remote_session_id, file_path)
    except AiManusAuthRequired:
        raise HTTPException(status_code=409, detail=ai_manus_adapter.auth_required_payload()["detail"]) from None
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ai-manus file preview failed: {exc}") from exc

    content = data.get("content") if isinstance(data, dict) else None
    async with store._lock:
        await store.publish(
            "ai_manus_file_previewed",
            {
                "session_id": thread_id,
                "manus_session_id": remote_session_id,
                "file_path": file_path,
                "content_chars": len(content) if isinstance(content, str) else None,
            },
            session_id=thread_id,
        )
    return {
        "session_id": thread_id,
        "manus_session_id": remote_session_id,
        "file_id": request.file_id,
        "path": file_path,
        "name": Path(file_path).name,
        "content": content,
        "text": content if isinstance(content, str) else None,
        "preview": data,
    }


@app.post("/integrations/ai-manus/files/{file_id}/signed-url")
async def ai_manus_file_signed_url(file_id: str, request: AiManusSignedUrlRequest | None = None):
    await _require_ai_manus_online()
    expire_minutes = request.expire_minutes if request else 15
    try:
        data = await ai_manus_adapter.file_signed_url(file_id, expire_minutes)
    except AiManusAuthRequired:
        raise HTTPException(status_code=409, detail=ai_manus_adapter.auth_required_payload()["detail"]) from None
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ai-manus file download link failed: {exc}") from exc

    response = data if isinstance(data, dict) else {"remote": data}
    if response.get("signed_url"):
        response.setdefault("url", response["signed_url"])
    async with store._lock:
        await store.publish(
            "ai_manus_file_download_link_created",
            {"file_id": file_id, "expires_in": response.get("expires_in")},
        )
    return {"file_id": file_id, **response}


@app.post("/integrations/ai-manus/session/{session_id}/stop")
@app.post("/integrations/ai-manus/sessions/{session_id}/stop")
async def ai_manus_stop_session(session_id: str):
    try:
        thread = store.get_ai_manus_thread(session_id)
        remote_session_id = _ai_manus_remote_session_id(thread)
    except KeyError:
        thread = None
        remote_session_id = session_id

    service = await ai_manus_adapter.status()
    async with store._lock:
        await _apply_ai_manus_status(service)
    if service.status == "auth_required":
        raise HTTPException(status_code=409, detail=ai_manus_adapter.auth_required_payload()["detail"])
    if service.status != "online":
        raise HTTPException(status_code=503, detail=service.detail or "ai-manus backend unavailable")
    try:
        data = await ai_manus_adapter.stop_session(remote_session_id)
    except AiManusAuthRequired:
        raise HTTPException(status_code=409, detail=ai_manus_adapter.auth_required_payload()["detail"]) from None
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ai-manus stop session failed: {exc}") from exc

    async with store._lock:
        if thread:
            thread.status = "stopped"
            await store.save_ai_manus_thread(thread)
        await store.publish("ai_manus_session_stopped", {"session_id": session_id}, session_id=session_id)
    return {"session_id": session_id, "manus_session_id": remote_session_id, "status": "stopped", "remote": data}


@app.get("/integrations/cua/status")
async def cua_status():
    service = await cua_driver_adapter.status()
    async with store._lock:
        await _apply_cua_status(service)
        return to_dict(service)


async def _cua_command_snapshot(action: str, command) -> dict:
    service = await command()
    async with store._lock:
        await _apply_cua_status(service)
        await store.publish("cua_driver_command", {"action": action, "service": to_dict(service)})
        return state_payload()


@app.post("/integrations/cua/start")
async def cua_start():
    return await _cua_command_snapshot("start", cua_driver_adapter.start_daemon)


@app.post("/integrations/cua/stop")
async def cua_stop():
    return await _cua_command_snapshot("stop", cua_driver_adapter.stop_daemon)


@app.post("/integrations/cua/restart")
async def cua_restart():
    return await _cua_command_snapshot("restart", cua_driver_adapter.restart_daemon)


@app.get("/integrations/cua/target-surface")
async def cua_target_surface():
    surface = await cua_driver_adapter.target_surface()
    return _target_surface_payload(surface)


@app.post("/intervention/detect")
async def intervention_detect():
    surface = await cua_driver_adapter.target_surface()
    snapshot = _snapshot_from_surface(surface)
    wechat_intent = _wechat_intent_from_snapshot(snapshot)
    mail_ready = _mail_compose_ready_from_snapshot(snapshot)
    async with store._lock:
        store.state.frontmost_context = snapshot
        task = _current_task()
        if not task:
            await store.publish(
                "intervention_signal_idle",
                {
                    "target_surface": _target_surface_payload(surface),
                    "frontmost_context": to_dict(snapshot),
                    "wechat_intent": wechat_intent,
                    "mail_compose_ready": mail_ready,
                    "reason": "no_active_task",
                },
            )
            return state_payload()

        _sync_task_target_surface(task, surface)
        store.state.jarvis_state = JarvisState.INTERVENTION_READY
        await store.persist()
        event_name = "intervention_signal_detected" if surface.safe else "intervention_signal_waiting"
        await store.publish(
            event_name,
            {
                "task_id": task.id,
                "target_surface": _target_surface_payload(surface),
                "frontmost_context": to_dict(snapshot),
                "wechat_intent": wechat_intent,
                "mail_compose_ready": mail_ready,
            },
            session_id=task.source_session_id,
        )
        if wechat_intent:
            await store.publish("wechat_intent_detected", wechat_intent, session_id=task.source_session_id)
        if mail_ready:
            await store.publish(
                "mail_compose_detected",
                {"target_surface": _target_surface_payload(surface), "frontmost_context": to_dict(snapshot)},
                session_id=task.source_session_id,
            )
        return state_payload()


@app.get("/context/frontmost", response_model=ForegroundAXSnapshot)
async def frontmost_context():
    surface = await cua_driver_adapter.target_surface()
    snapshot = _snapshot_from_surface(surface)
    async with store._lock:
        await store.set_frontmost_context(snapshot)
        await store.publish("frontmost_context_captured", to_dict(snapshot), session_id=snapshot.metadata.get("session_id"))
    return snapshot


@app.get("/frontmost", response_model=ForegroundAXSnapshot)
async def frontmost_context_alias():
    return await frontmost_context()


@app.post("/highlight/start")
async def highlight_start():
    async with store._lock:
        if store.state.highlight_segment and store.state.highlight_segment.status in {"capturing", "generating"}:
            raise HTTPException(status_code=409, detail="Highlight is already active.")
        session_id = store.state.current_session.id if store.state.current_session else None
        check_in = now_iso()
        segment = HighlightSegment(
            check_in=check_in,
            status="capturing",
            source_session_id=session_id,
        )
        store.state.highlight_segment = segment
        store.state.sop_capture.status = CaptureStatus.CAPTURING
        store.state.sop_capture.check_in = check_in
        store.state.sop_capture.check_out = None
        store.state.sop_capture.source_session_id = session_id
        store.state.sop_capture.generated_skill_id = None
        store.state.sop_capture.error = None
        await store.persist()
        await store.publish("highlight_started", to_dict(segment), session_id=session_id)
        return state_payload()


@app.post("/highlight/finish")
async def highlight_finish(request: CaptureFinishRequest | None = None):
    async with store._lock:
        segment = store.state.highlight_segment
        if not segment or segment.status != "capturing":
            raise HTTPException(status_code=409, detail="No active Highlight to finish.")
        segment.status = "generating"
        segment.check_out = request.check_out if request and request.check_out else now_iso()
        store.state.sop_capture.status = CaptureStatus.GENERATING
        store.state.sop_capture.check_out = segment.check_out
        await store.persist()
        await store.publish("highlight_generating", to_dict(segment), session_id=segment.source_session_id)

    chunks = _memory_chunks_for_window(
        session_id=segment.source_session_id,
        start_at=segment.check_in,
        end_at=segment.check_out,
    )
    priority = _context_priority(chunks)
    if priority == "none":
        async with store._lock:
            segment.status = "failed"
            segment.error = "No video_context or audio_context found in Highlight window."
            store.state.sop_capture.status = CaptureStatus.FAILED
            store.state.sop_capture.error = segment.error
            await store.persist()
            await store.publish("highlight_failed", to_dict(segment), session_id=segment.source_session_id)
        raise HTTPException(status_code=409, detail=segment.error)

    try:
        skill = await generate_skill_record(
            check_in=segment.check_in,
            check_out=segment.check_out,
            source_session_id=segment.source_session_id,
            description=f"Generated from {priority} context in Highlight window.",
        )
    except Exception as exc:
        async with store._lock:
            segment.status = "failed"
            segment.error = str(exc)
            store.state.sop_capture.status = CaptureStatus.FAILED
            store.state.sop_capture.error = str(exc)
            await store.persist()
            await store.publish("highlight_failed", to_dict(segment), session_id=segment.source_session_id)
        raise HTTPException(status_code=502, detail=f"Highlight generation failed: {exc}") from exc

    async with store._lock:
        segment.status = "completed"
        segment.context_priority = priority
        segment.context_chunk_ids = [chunk.id for chunk in chunks]
        segment.generated_skill_id = skill.id
        skill.metadata.update(
            {
                "source": "highlight",
                "context_priority": priority,
                "context_chunk_ids": segment.context_chunk_ids,
                "context_summary": _context_summary(chunks),
            }
        )
        store.state.sop_capture.status = CaptureStatus.COMPLETED
        store.state.sop_capture.generated_skill_id = skill.id
        store.state.sop_capture.error = None
        await store.persist()
        await store.publish("highlight_finished", to_dict(segment), session_id=segment.source_session_id)
        return state_payload()


@app.post("/highlight")
async def highlight_toggle():
    segment = store.state.highlight_segment
    if segment and segment.status == "capturing":
        return await highlight_finish()
    return await highlight_start()


@app.post("/sop/capture-start")
async def capture_start():
    async with store._lock:
        if store.state.sop_capture.status == CaptureStatus.CAPTURING:
            raise HTTPException(status_code=409, detail="Capture is already active.")
        session_id = store.state.current_session.id if store.state.current_session else None
        store.state.sop_capture.status = CaptureStatus.CAPTURING
        store.state.sop_capture.check_in = now_iso()
        store.state.sop_capture.check_out = None
        store.state.sop_capture.source_session_id = session_id
        store.state.sop_capture.generated_skill_id = None
        store.state.sop_capture.error = None
        await store.persist()
        await store.publish("sop_capture_started", to_dict(store.state.sop_capture), session_id=session_id)
        return state_payload()


@app.post("/sop/capture-finish")
async def capture_finish(request: CaptureFinishRequest | None = None):
    async with store._lock:
        capture = store.state.sop_capture
        if capture.status != CaptureStatus.CAPTURING:
            raise HTTPException(status_code=409, detail="No active SOP capture to finish.")
        capture.status = CaptureStatus.GENERATING
        capture.check_out = request.check_out if request and request.check_out else now_iso()
        await store.persist()
        await store.publish("sop_capture_generating", to_dict(capture), session_id=capture.source_session_id)
        try:
            skill = await generate_skill_record(
                check_in=capture.check_in,
                check_out=capture.check_out,
                source_session_id=capture.source_session_id,
            )
            capture.status = CaptureStatus.COMPLETED
            capture.generated_skill_id = skill.id
            capture.error = None
            await store.persist()
            await store.publish("sop_capture_finished", to_dict(capture), session_id=capture.source_session_id)
            return state_payload()
        except Exception as exc:
            capture.status = CaptureStatus.FAILED
            capture.error = str(exc)
            await store.persist()
            await store.publish("sop_capture_failed", to_dict(capture), session_id=capture.source_session_id)
            raise HTTPException(status_code=502, detail=f"SOP generation failed: {exc}") from exc


@app.post("/follow-up/prepare", response_model=FollowUpPackage)
async def follow_up_prepare():
    async with store._lock:
        session = store.state.current_session
        if not session:
            raise HTTPException(status_code=409, detail="No active session available for follow-up preparation.")
        chunks = _memory_chunks_for_window(session_id=session.id, start_at=session.started_at, end_at=now_iso())
        priority = _context_priority(chunks)
        context = _context_summary(chunks, limit=10)
        if not context:
            context = "\n".join(
                artifact.content or ""
                for artifact in session.artifacts
                if artifact.type in {"meeting_minutes", "meeting_transcript", "follow_up_body"}
            ).strip()
        if not context:
            raise HTTPException(status_code=409, detail="No BasicMemory context or session artifacts available for follow-up.")

        subject = f"Follow-up: {session.title}"
        body = (
            "Hi,\n\n"
            "Thanks again for the conversation. I captured the main context below for review before sending.\n\n"
            f"{context}\n\n"
            "Best,\n"
        )
        minutes = Artifact(
            type="meeting_minutes",
            title="Follow-up context summary",
            content=f"# Follow-up Context\n\n{context}\n",
            metadata={
                "source": "basic-memory" if chunks else "session_artifacts",
                "context_priority": priority,
            },
        )
        follow_up_artifact = Artifact(
            type="follow_up_body",
            title="Mail follow-up draft",
            content=body,
            metadata={
                "source": "follow_up_package",
                "subject": subject,
                "context_priority": priority,
            },
        )
        persisted_minutes = await store.add_artifact(minutes, session=session)
        persisted_follow_up = await store.add_artifact(follow_up_artifact, session=session)
        package = FollowUpPackage(
            subject=subject,
            body=body,
            minutes_path=persisted_minutes.path,
            context_priority=priority,
            source_session_id=session.id,
            context_chunk_ids=[chunk.id for chunk in chunks],
            metadata={"artifact_ids": [persisted_minutes.id, persisted_follow_up.id]},
        )
        store.state.follow_up_package = package
        task = build_active_task(session, [persisted_minutes, persisted_follow_up], target_type="mail")
        await store.add_active_task(task)
        store.state.jarvis_state = JarvisState.INTERVENTION_READY
        await store.persist()
        await store.publish("follow_up_prepared", to_dict(package), session_id=session.id)
        await store.publish("active_task_generated", to_dict(task), session_id=session.id)
        return package


@app.post("/follow-up", response_model=FollowUpPackage)
async def follow_up_prepare_alias():
    return await follow_up_prepare()


@app.post("/active-task/generate")
async def active_task_generate(request: ActiveTaskGenerateRequest | None = None):
    surface = await cua_driver_adapter.target_surface()
    async with store._lock:
        session = store.state.current_session
        if not session:
            raise HTTPException(status_code=409, detail="No session available for Active Task generation.")
        artifacts = session.artifacts or mock_meeting_artifacts(session)
        if not session.artifacts:
            persisted = []
            for artifact in artifacts:
                persisted.append(await store.add_artifact(artifact, session=session))
            artifacts = persisted
        task = build_active_task(session, artifacts, target_type=(request.target_type if request else "communication"))
        if request and request.intent:
            task.intent = request.intent
        _sync_task_target_surface(task, surface)
        await store.add_active_task(task)
        store.state.jarvis_state = JarvisState.INTERVENTION_READY
        await store.persist()
        await store.publish("active_task_generated", to_dict(task), session_id=session.id)
        await store.publish(
            "intervention_signal_detected" if surface.safe else "intervention_signal_waiting",
            {
                "task_id": task.id,
                "target_surface": _target_surface_payload(surface),
            },
            session_id=session.id,
        )
        return state_payload()


@app.post("/active-task/{task_id}/confirm")
async def active_task_confirm(task_id: str):
    async with store._lock:
        try:
            task = store.get_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Active Task not found.") from exc
        insert_action, text = _insert_action_and_text(task)
        if insert_action is None:
            raise HTTPException(status_code=409, detail="Active Task has no insert action.")
        if not text:
            raise HTTPException(status_code=409, detail="Insert action has no artifact content to insert.")
        insert_action.status = "insert_requested"
        task.status = ActiveTaskStatus.CONFIRMED
        task.updated_at = now_iso()
        await store.persist()
        await store.publish(
            "cua_insert_requested",
            {
                "task_id": task.id,
                "action_id": insert_action.id,
                "text_chars": len(text),
                "target_type": insert_action.target_type,
            },
            session_id=task.source_session_id,
        )

    result = await cua_driver_adapter.insert_text(text, surface_hint=_action_target_surface(insert_action))

    async with store._lock:
        try:
            task = store.get_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Active Task not found.") from exc
        insert_action, _ = _insert_action_and_text(task)
        if insert_action is None:
            raise HTTPException(status_code=409, detail="Active Task has no insert action.")

        insert_action.payload["cua"] = _cua_result_payload(result)
        insert_action.status = "inserted" if result.ok else "insert_failed"
        task.status = ActiveTaskStatus.AWAITING_REVIEW if result.ok else ActiveTaskStatus.PENDING
        task.updated_at = now_iso()
        store.state.jarvis_state = JarvisState.AWAITING_REVIEW if result.ok else JarvisState.INTERVENTION_READY
        await _apply_cua_status(
            ServiceStatus(
                name="cua-driver",
                status="online" if result.ok else "error",
                detail=result.detail,
            )
        )
        await store.persist()
        await store.publish(
            "cua_insert_completed" if result.ok else "cua_insert_failed",
            {
                "task_id": task.id,
                "action_id": insert_action.id,
                "result": _cua_result_payload(result),
            },
            session_id=task.source_session_id,
        )
        await store.publish("active_task_confirmed", to_dict(task), session_id=task.source_session_id)
        if not result.ok:
            raise HTTPException(status_code=502, detail=f"CUA insert failed: {result.detail}")
        return state_payload()


@app.post("/active-task/{task_id}/insert-mail-draft", response_model=MailDraftInsertResult)
async def active_task_insert_mail_draft(task_id: str):
    async with store._lock:
        try:
            task = store.get_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Active Task not found.") from exc
        insert_action, fallback_text = _insert_action_and_text(task)
        if insert_action is None:
            raise HTTPException(status_code=409, detail="Active Task has no insert action.")
        package = store.state.follow_up_package
        subject = package.subject if package and package.source_session_id == task.source_session_id else task.title
        body = package.body if package and package.source_session_id == task.source_session_id else fallback_text
        if not body or not body.strip():
            raise HTTPException(status_code=409, detail="No follow-up body is available for Mail draft insertion.")
        insert_action.status = "insert_requested"
        task.status = ActiveTaskStatus.CONFIRMED
        task.updated_at = now_iso()
        await store.persist()
        await store.publish(
            "mail_draft_insert_requested",
            {"task_id": task.id, "action_id": insert_action.id, "subject": subject},
            session_id=task.source_session_id,
        )

    surface = await cua_driver_adapter.mail_compose_surface()
    text = f"{subject.strip()}\n\n{body.strip()}" if subject.strip() else body.strip()
    result = await cua_driver_adapter.insert_text(text, surface_hint=surface) if surface.safe else None
    if result is None:
        mail_result = MailDraftInsertResult(
            ok=False,
            detail=f"Mail compose surface is not ready: {surface.reason}",
            target_surface=surface,
        )
    else:
        detail = result.detail
        if result.ok:
            detail = f"{detail}; mail_compose_only=true; send_action=false"
        mail_result = MailDraftInsertResult(
            ok=result.ok,
            detail=detail,
            target_surface=surface,
            metadata=_cua_result_payload(result),
        )

    async with store._lock:
        try:
            task = store.get_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Active Task not found.") from exc
        insert_action, _ = _insert_action_and_text(task)
        if insert_action is None:
            raise HTTPException(status_code=409, detail="Active Task has no insert action.")
        insert_action.payload["mail_draft_insert_result"] = to_dict(mail_result)
        insert_action.status = "inserted" if mail_result.ok else "insert_failed"
        task.status = ActiveTaskStatus.AWAITING_REVIEW if mail_result.ok else ActiveTaskStatus.PENDING
        task.updated_at = now_iso()
        store.state.mail_draft_insert_result = mail_result
        store.state.jarvis_state = JarvisState.AWAITING_REVIEW if mail_result.ok else JarvisState.INTERVENTION_READY
        await _apply_cua_status(
            ServiceStatus(
                name="cua-driver",
                status="online" if mail_result.ok else "error",
                detail=mail_result.detail,
            )
        )
        await store.persist()
        await store.publish(
            "mail_draft_inserted" if mail_result.ok else "mail_draft_insert_failed",
            {"task_id": task.id, "result": to_dict(mail_result)},
            session_id=task.source_session_id,
        )
        if not mail_result.ok:
            raise HTTPException(status_code=502, detail=f"Mail draft insert failed: {mail_result.detail}")
        return mail_result


@app.post("/mail-draft", response_model=MailDraftInsertResult)
async def active_task_insert_mail_draft_alias():
    task = _current_task()
    if not task:
        raise HTTPException(status_code=409, detail="No active task available for Mail draft insertion.")
    return await active_task_insert_mail_draft(task.id)


@app.post("/active-task/{task_id}/ignore")
async def active_task_ignore(task_id: str):
    async with store._lock:
        try:
            task = store.get_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Active Task not found.") from exc
        task.status = ActiveTaskStatus.IGNORED
        task.updated_at = now_iso()
        await store.persist()
        await store.publish("active_task_ignored", to_dict(task), session_id=task.source_session_id)
        return state_payload()


@app.post("/active-task/{task_id}/complete")
async def active_task_complete(task_id: str):
    async with store._lock:
        try:
            task = store.get_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Active Task not found.") from exc
        task.status = ActiveTaskStatus.COMPLETED
        task.updated_at = now_iso()
        store.state.jarvis_state = JarvisState.PATTERN_DETECTED
        await store.persist()
        await store.publish("active_task_completed", to_dict(task), session_id=task.source_session_id)
        return state_payload()


@app.post("/skill/generate")
async def skill_generate(request: SkillGenerateRequest | None = None):
    async with store._lock:
        session_id = request.source_session_id if request else None
        if not session_id and store.state.current_session:
            session_id = store.state.current_session.id
        skill = await generate_skill_record(
            check_in=request.check_in if request else None,
            check_out=request.check_out if request else None,
            source_session_id=session_id,
            name=request.name if request else None,
            description=request.description if request else None,
        )
        return state_payload()


@app.get("/skills")
async def skills():
    return [_skill_payload(skill) for skill in store.state.skills]


@app.delete("/skill/{skill_id}")
async def skill_delete(skill_id: str):
    async with store._lock:
        try:
            skill = await store.delete_skill(skill_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Skill not found.") from exc
        await store.publish("skill_deleted", to_dict(skill), session_id=skill.source_session_id)
        return state_payload()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("orchestrator.main:app", host="127.0.0.1", port=8787, reload=True)
