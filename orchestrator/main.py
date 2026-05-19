from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .adapters.basic_memory import basic_memory_adapter
from .adapters.openchronicle import openchronicle_adapter
from .adapters.cua_driver import cua_driver_adapter
from .adapters.ai_manus import AiManusAuthRequired, ai_manus_adapter
from .adapters.project_cortex import hippo_agent_adapter, sop_adapter
from .adapters.vlmac import vlmac_adapter
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
    CaptureFinishRequest,
    CaptureStatus,
    ContextFragment,
    CuaTargetSurface,
    DemoSession,
    JarvisState,
    OwnscribeConfigRequest,
    ProposedAction,
    ServiceStatus,
    SkillGenerateRequest,
    SkillRecord,
    VlmacConfigRequest,
    new_id,
    now_iso,
)
from .store import SESSION_DIR, SKILL_DIR, store, to_dict
from .logging_config import ORCHESTRATOR_LOG_PATH, PROJECT_DIR, RUNTIME_DIR, log_event, redact, setup_logging, tail_log


setup_logging()
logger = logging.getLogger("orchestrator.main")
app = FastAPI(title="HippoDEMO Orchestrator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_http_request(request: Request, call_next):
    started = time.monotonic()
    request_id = request.headers.get("x-request-id") or new_id("request")
    logger.debug(
        "http_request_started",
        extra={
            "event": "http_request_started",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        },
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        log_event(
            logger,
            "http_request_failed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            duration_ms=round((time.monotonic() - started) * 1000, 2),
            error_type=exc.__class__.__name__,
            error_summary=_error_summary(exc),
        )
        raise
    response.headers["x-request-id"] = request_id
    logger.info(
        "http_request_completed",
        extra={
            "event": "http_request_completed",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        },
    )
    return response

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
_openchronicle_autostart_suppressed = False
_vlmac_autostart_suppressed = False
_voice_context_workers: dict[str, asyncio.Task] = {}
_voice_context_stop_events: dict[str, asyncio.Event] = {}
_voice_context_offsets: dict[str, float] = {}
_voice_context_sequences: dict[str, int] = {}


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


OWNSCRIBE_STOP_TIMEOUT_SECONDS = _float_env("HIPPODEMO_OWNSCRIBE_STOP_TIMEOUT_SECONDS", 45.0)
CONTEXT_FRAGMENT_SECONDS = _float_env("HIPPODEMO_CONTEXT_FRAGMENT_SECONDS", 20.0)
CONTEXT_FRAGMENT_OVERLAP_SECONDS = _float_env("HIPPODEMO_CONTEXT_FRAGMENT_OVERLAP_SECONDS", 3.0)
CONTEXT_MIN_FRAGMENT_SECONDS = _float_env("HIPPODEMO_CONTEXT_MIN_FRAGMENT_SECONDS", 1.0)


def _error_summary(exc: Exception, *, limit: int = 300) -> str:
    text = " ".join(str(exc).split()) or exc.__class__.__name__
    redacted = str(redact(text))
    if len(redacted) <= limit:
        return redacted
    return redacted[: max(0, limit - 3)] + "..."


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


def _ai_manus_session_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    return payload.get("session_id") or payload.get("id")


def _ai_manus_remote_session_id(thread: AiManusThread) -> str:
    return thread.manus_session_id or str(thread.metadata.get("manus_session_id") or thread.session_id)


def _ai_manus_remote_session_id_or_none(thread: AiManusThread) -> str | None:
    remote = thread.manus_session_id or thread.metadata.get("manus_session_id")
    return str(remote) if remote else None


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
        "manus_session_id": _ai_manus_remote_session_id_or_none(thread),
        "title": thread.title,
        "status": thread.status,
        "latest_message": thread.latest_message,
        "latest_message_at": thread.latest_message_at,
        "unread_message_count": thread.unread_message_count,
        "is_shared": thread.is_shared,
        "updated_at": thread.updated_at,
    }


def _safe_read_text(path: str | None, *, limit: int = 12_000) -> str:
    if not path:
        return ""
    try:
        value = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return value[:limit]


def _available_skill_summary() -> str:
    if not store.state.skills:
        return ""
    lines = ["# Available Hippo Skills"]
    for skill in store.state.skills[:8]:
        path_stem = Path(skill.path).stem if skill.path else ""
        lines.append(f"- {skill.name}: {skill.description} (id: {skill.id}, handle: {path_stem})")
    return "\n".join(lines)


def _skill_markdown(skill: SkillRecord, *, limit: int = 10_000) -> str:
    content = _safe_read_text(skill.path, limit=limit)
    if not content:
        return ""
    return "\n".join(
        [
            f"# Selected Hippo Skill: {skill.name}",
            f"id: {skill.id}",
            f"description: {skill.description}",
            f"path: {skill.path}",
            "",
            content,
        ]
    )


def _find_mentioned_skill(message: str) -> SkillRecord | None:
    if not store.state.skills:
        return None
    mentions = [item.strip().lower() for item in re.findall(r"@([^\s，,。；;：:]+)", message)]
    if not mentions:
        return None
    latest = store.state.skills[0]
    for mention in mentions:
        if mention in {"skill", "sop"}:
            return latest
        for skill in store.state.skills:
            candidates = {
                skill.id.lower(),
                skill.name.lower(),
                Path(skill.path).stem.lower() if skill.path else "",
            }
            if mention in candidates or any(mention and mention in candidate for candidate in candidates):
                return skill
    return None


def _is_sop_execution_request(message: str) -> bool:
    normalized = re.sub(r"\s+", "", message.lower())
    return any(marker in normalized for marker in {"执行sop", "运行sop", "执行skill", "运行skill"})


def _hippo_agent_skill_input(message: str) -> str:
    skill = _find_mentioned_skill(message)
    if not skill and _is_sop_execution_request(message) and store.state.skills:
        skill = store.state.skills[0]
    if not skill:
        return ""
    return _skill_markdown(skill)


def _hippo_agent_context_input(message: str, session_id: str | None = None, *, limit: int = 16_000) -> str:
    sections: list[str] = []
    session = store.state.current_session
    if session:
        sections.append(
            "\n".join(
                [
                    "# Current Hippo Session",
                    f"id: {session.id}",
                    f"title: {session.title}",
                    f"state: {session.state.value if hasattr(session.state, 'value') else session.state}",
                    f"started_at: {session.started_at}",
                    f"ended_at: {session.ended_at or ''}",
                ]
            )
        )
        if session.artifacts:
            artifact_lines = ["# Session Artifacts"]
            for artifact in session.artifacts[-8:]:
                artifact_lines.append(f"- {artifact.title} ({artifact.type}, id: {artifact.id}, path: {artifact.path or ''})")
            sections.append("\n".join(artifact_lines))

    fragments = store.list_context_fragments(
        session_id=session.id if session else None,
        modality=None,
        limit=12,
    )
    if fragments:
        lines = ["# Recent Context Fragments"]
        for fragment in reversed(fragments):
            text = " ".join(fragment.text.split())
            if len(text) > 700:
                text = f"{text[:700]}..."
            lines.append(
                f"- [{fragment.modality}/{fragment.source}] {fragment.started_at}"
                f"{' -> ' + fragment.ended_at if fragment.ended_at else ''}: {text}"
            )
        sections.append("\n".join(lines))

    if store.state.active_tasks:
        task_lines = ["# Active Tasks"]
        for task in store.state.active_tasks[:5]:
            task_lines.append(f"- {task.title} ({task.status.value if hasattr(task.status, 'value') else task.status}, id: {task.id})")
        sections.append("\n".join(task_lines))

    skill_summary = _available_skill_summary()
    if skill_summary:
        sections.append(skill_summary)
    mentioned_skill = _find_mentioned_skill(message)
    if mentioned_skill:
        sections.append(f"# Routed Skill Mention\nThe user mentioned @{mentioned_skill.name} ({mentioned_skill.id}).")

    context = "\n\n".join(section for section in sections if section)
    return context[:limit]


def _chat_route_for_message(message: str, requested_route: str | None = None) -> str:
    route = (requested_route or "auto").strip().lower()
    if route in {"hippo", "hippo-agent", "hippo_agent", "project_cortex", "project-cortex"}:
        return "hippo_agent"
    if route in {"manus", "ai-manus", "ai_manus"}:
        return "manus"

    text = message.lower()
    normalized = re.sub(r"\s+", "", text)
    manus_markers = [
        "cua",
        "computer use",
        "computer-use",
        "本机操作",
        "操作本机",
        "控制电脑",
        "浏览器",
        "browser",
        "sandbox",
        "沙盒",
        "代码",
        "code",
        "shell",
        "terminal",
    ]
    if any(marker in text for marker in manus_markers):
        return "manus"

    if re.search(r"@\S+", message) or _is_sop_execution_request(message):
        return "hippo_agent"

    meeting_actions = ["预约", "安排", "创建", "发起", "预定", "订", "schedule", "book", "create"]
    doc_actions = ["写", "创建", "新建", "更新", "整理", "生成", "修改", "编辑", "draft", "write", "create", "update", "edit"]
    mail_actions = ["发", "发送", "写", "草拟", "起草", "回复", "send", "draft", "write", "reply"]
    if any(keyword in text for keyword in ["腾讯会议", "tencent meeting", "voov meeting"]) and any(action in text for action in meeting_actions):
        return "hippo_agent"
    if any(keyword in text for keyword in ["飞书会议", "feishu meeting", "lark meeting"]) and any(action in text for action in meeting_actions):
        return "hippo_agent"
    if any(keyword in text for keyword in ["飞书文档", "feishu doc", "feishu docs", "lark doc", "lark docs"]) and any(action in text for action in doc_actions):
        return "hippo_agent"
    if any(keyword in text for keyword in ["邮件", "email", "e-mail"]) and any(action in text for action in mail_actions):
        return "hippo_agent"
    if any(marker in normalized for marker in {"预约腾讯会议", "预约飞书会议", "写飞书文档", "发邮件", "发送邮件", "写邮件"}):
        return "hippo_agent"
    return "manus"


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


def _basic_memory_status_payload(service: ServiceStatus) -> dict:
    config = basic_memory_adapter.config()
    project_path = config.get("project_path")
    return {
        "ok": service.status == "online",
        "status": service.status,
        "detail": service.detail,
        "project": config.get("project"),
        "project_path": project_path,
        "config_path": config.get("config_path"),
        "sync_status": service.status,
        "service": _service_payload(service),
        "config": config,
    }


async def _apply_hippo_agent_status() -> dict[str, Any]:
    payload = hippo_agent_adapter.status()
    service = ServiceStatus(
        name=payload.get("name") or "Project_Cortex",
        status=payload.get("status") or "unknown",
        detail=payload.get("detail"),
    )
    _set_service_status(service)
    await store.persist()
    return payload


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


async def _ensure_ai_manus_remote_session(thread: AiManusThread) -> AiManusThread:
    if _ai_manus_remote_session_id_or_none(thread):
        return thread
    data = await ai_manus_adapter.create_session()
    manus_session_id = _ai_manus_session_id(data)
    if not manus_session_id:
        raise RuntimeError("ai-manus create session returned no session_id")
    thread.manus_session_id = manus_session_id
    thread.metadata["manus_session_id"] = manus_session_id
    thread.metadata["remote_created_by"] = "hippo-chat-auto-route"
    await store.save_ai_manus_thread(thread)
    await store.publish(
        "ai_manus_session_created",
        {"session_id": thread.session_id, "manus_session_id": manus_session_id, "source": "hippo-chat-auto-route"},
        session_id=thread.session_id,
    )
    return thread


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
            if existing.status != service.status or existing.detail != service.detail:
                log_event(
                    logger,
                    "service_status_changed",
                    service=service.name,
                    previous_status=existing.status,
                    next_status=service.status,
                    previous_detail=existing.detail,
                    next_detail=service.detail,
                )
            store.state.services[index] = service
            return
    log_event(
        logger,
        "service_status_changed",
        service=service.name,
        previous_status=None,
        next_status=service.status,
        previous_detail=None,
        next_detail=service.detail,
    )
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

    service = await _openchronicle_status_with_autostart()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
        _openchronicle_status_checked_at = time.monotonic()
        return service


async def _openchronicle_status_with_autostart() -> ServiceStatus:
    service = await openchronicle_adapter.status()
    if service.status in {"stopped", "unavailable"} and not _openchronicle_autostart_suppressed:
        return await openchronicle_adapter.start()
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


async def _wait_for_ai_manus_status(timeout_seconds: float = 0.0, interval_seconds: float = 0.5) -> ServiceStatus:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    service = await ai_manus_adapter.status()
    while service.status != "online" and time.monotonic() < deadline:
        await asyncio.sleep(interval_seconds)
        service = await ai_manus_adapter.status()
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

    service = await basic_memory_adapter.status()
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

    service = await _vlmac_status_with_autostart()
    async with store._lock:
        _set_service_status(service)
        await store.persist()
        _vlmac_status_checked_at = time.monotonic()
        return service


async def _vlmac_status_with_autostart() -> ServiceStatus:
    service = await vlmac_adapter.status()
    if service.status == "unavailable" and not _vlmac_autostart_suppressed:
        return await vlmac_adapter.start()
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


async def _apply_voice_context_status(status: str, detail: str | None = None) -> ServiceStatus:
    service = ServiceStatus(name="voice-context", status=status, detail=detail)
    _set_service_status(service)
    await store.persist()
    return service


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
        if action.payload.get("mode") != "insert_draft":
            continue
        artifact = _artifact_by_id(task, action.payload.get("artifact_id"))
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


def _context_fragment_event_payload(fragment: ContextFragment, *, status: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": fragment.id,
        "session_id": fragment.session_id,
        "modality": fragment.modality,
        "source": fragment.source,
        "started_at": fragment.started_at,
        "ended_at": fragment.ended_at,
        "sequence": fragment.sequence,
        "text_length": len(fragment.text),
        "synced": bool(fragment.synced_at),
    }
    if status:
        payload["status"] = status
    return payload


def _context_timestamp_from_offset(timeline: dict[str, Any], offset_seconds: float) -> str:
    base_epoch = timeline.get("recording_started_epoch_seconds")
    if isinstance(base_epoch, (int, float)):
        return datetime.fromtimestamp(float(base_epoch) + offset_seconds).astimezone().isoformat()
    started_at = timeline.get("recording_started_at")
    if isinstance(started_at, str) and started_at:
        try:
            base = datetime.fromisoformat(started_at)
            return datetime.fromtimestamp(base.timestamp() + offset_seconds).astimezone().isoformat()
        except ValueError:
            pass
    return now_iso()


def _context_note_for_fragment(fragment: ContextFragment) -> tuple[str, str, str]:
    short_id = _short_source_id(fragment.id)
    modality = fragment.modality or "voice"
    title = f"Hippo {modality.title()} Context {short_id}"
    folder = f"hippo/context/{modality}/chunks"
    lines = [
        f"# {title}",
        "",
        "## Source",
        "- source_kind: context_fragment",
        f"- source_id: `{fragment.id}`",
        f"- session_id: `{fragment.session_id}`",
        f"- modality: {fragment.modality}",
        f"- source: {fragment.source}",
        f"- sequence: {fragment.sequence}",
        f"- started_at: {fragment.started_at}",
        f"- ended_at: {fragment.ended_at or ''}",
        f"- confidence: {fragment.confidence if fragment.confidence is not None else ''}",
        "",
        "## Context",
        fragment.text.strip(),
        "",
        "## Relations",
        f"- from_session [[Hippo Session {_short_source_id(fragment.session_id)}]]",
    ]
    offsets = {
        key: value
        for key, value in fragment.metadata.items()
        if key in {"audio_start_offset_seconds", "audio_end_offset_seconds", "segment_path", "asr_provider", "asr_model"}
    }
    if offsets:
        lines.extend(["", "## Capture Metadata"])
        for key, value in offsets.items():
            lines.append(f"- {key}: {value}")
    return title, folder, "\n".join(lines).strip() + "\n"


async def _sync_basic_memory_context(fragment: ContextFragment) -> dict[str, Any]:
    title, folder, content = _context_note_for_fragment(fragment)
    result = await basic_memory_adapter.write_note(
        kind=f"context_{fragment.modality}",
        source_id=fragment.id,
        title=title,
        folder=folder,
        content=content,
    )
    result = {**result, "fragment_id": fragment.id}
    if result.get("ok"):
        fragment = await store.mark_context_fragment_synced(fragment.id)
        await store.publish(
            "context_fragment_synced",
            {
                **_context_fragment_event_payload(fragment, status=str(result.get("status") or "synced")),
                "identifier": result.get("identifier") or result.get("permalink"),
                "path": result.get("path"),
            },
            session_id=fragment.session_id,
        )
    return result


async def _sync_basic_memory_context_best_effort(fragment: ContextFragment) -> None:
    try:
        await _sync_basic_memory_context(fragment)
    except Exception as exc:
        await store.publish(
            "context_fragment_sync_failed",
            {
                **_context_fragment_event_payload(fragment, status="failed"),
                "detail": str(exc),
            },
            session_id=fragment.session_id,
        )


async def _create_voice_context_fragment(
    session_id: str,
    *,
    sequence: int,
    start_offset_seconds: float,
    end_offset_seconds: float,
    allow_partial: bool = False,
) -> ContextFragment | None:
    if ownscribe_adapter is None:
        return None

    segment_path = await asyncio.to_thread(
        ownscribe_adapter.create_audio_segment,
        session_id,
        sequence=sequence,
        start_offset_seconds=start_offset_seconds,
        end_offset_seconds=end_offset_seconds,
        allow_partial=allow_partial,
    )
    transcription = await asyncio.to_thread(ownscribe_adapter.transcribe_audio_segment, segment_path)
    text = str(transcription.get("text") or "").strip()
    if not text:
        return None

    timeline = await asyncio.to_thread(ownscribe_adapter.recording_timeline, session_id)
    fragment = ContextFragment(
        session_id=session_id,
        modality="voice",
        source="ownscribe",
        text=text,
        started_at=_context_timestamp_from_offset(timeline, start_offset_seconds),
        ended_at=_context_timestamp_from_offset(timeline, end_offset_seconds),
        sequence=sequence,
        metadata={
            "audio_start_offset_seconds": round(start_offset_seconds, 3),
            "audio_end_offset_seconds": round(end_offset_seconds, 3),
            "segment_path": str(segment_path),
            "asr_provider": transcription.get("provider"),
            "asr_model": transcription.get("model"),
        },
    )
    await store.save_context_fragment(fragment)
    await store.publish(
        "context_fragment_created",
        _context_fragment_event_payload(fragment, status="created"),
        session_id=session_id,
    )
    asyncio.create_task(_sync_basic_memory_context_best_effort(fragment))
    _voice_context_offsets[session_id] = max(end_offset_seconds - CONTEXT_FRAGMENT_OVERLAP_SECONDS, 0.0)
    _voice_context_sequences[session_id] = sequence + 1
    return fragment


async def _voice_context_worker(session_id: str, stop_event: asyncio.Event) -> None:
    await store.publish(
        "ownscribe_context_worker_started",
        {
            "session_id": session_id,
            "modality": "voice",
            "fragment_seconds": CONTEXT_FRAGMENT_SECONDS,
            "overlap_seconds": CONTEXT_FRAGMENT_OVERLAP_SECONDS,
        },
        session_id=session_id,
    )
    async with store._lock:
        await _apply_voice_context_status("recording", f"voice context running for {session_id}")

    sequence = _voice_context_sequences.get(session_id, 0)
    cursor = _voice_context_offsets.get(session_id, 0.0)

    try:
        while not stop_event.is_set():
            await asyncio.sleep(1.0)
            if ownscribe_adapter is None:
                continue
            try:
                available = await asyncio.to_thread(ownscribe_adapter.recording_audio_duration_seconds, session_id)
            except Exception:
                continue

            target_end = cursor + CONTEXT_FRAGMENT_SECONDS
            if available < target_end:
                continue

            lag = max(0.0, available - target_end)
            if lag > CONTEXT_FRAGMENT_SECONDS * 2:
                await store.publish(
                    "ownscribe_context_worker_backpressure",
                    {
                        "session_id": session_id,
                        "lag_seconds": round(lag, 3),
                        "cursor_seconds": round(cursor, 3),
                        "available_seconds": round(available, 3),
                    },
                    session_id=session_id,
                )
                cursor = max(0.0, available - CONTEXT_FRAGMENT_SECONDS)

            try:
                fragment = await _create_voice_context_fragment(
                    session_id,
                    sequence=sequence,
                    start_offset_seconds=cursor,
                    end_offset_seconds=cursor + CONTEXT_FRAGMENT_SECONDS,
                )
            except Exception as exc:
                await store.publish(
                    "context_fragment_sync_failed",
                    {
                        "session_id": session_id,
                        "modality": "voice",
                        "source": "ownscribe",
                        "sequence": sequence,
                        "status": "transcribe_failed",
                        "detail": str(exc),
                    },
                    session_id=session_id,
                )
                cursor = max(0.0, cursor + CONTEXT_FRAGMENT_SECONDS - CONTEXT_FRAGMENT_OVERLAP_SECONDS)
                sequence += 1
                continue

            cursor = max(0.0, cursor + CONTEXT_FRAGMENT_SECONDS - CONTEXT_FRAGMENT_OVERLAP_SECONDS)
            sequence += 1
            if fragment is None:
                _voice_context_offsets[session_id] = cursor
                _voice_context_sequences[session_id] = sequence
    finally:
        _voice_context_offsets[session_id] = cursor
        _voice_context_sequences[session_id] = sequence
        await store.publish(
            "ownscribe_context_worker_stopped",
            {
                "session_id": session_id,
                "modality": "voice",
                "cursor_seconds": round(cursor, 3),
                "sequence": sequence,
            },
            session_id=session_id,
        )
        async with store._lock:
            await _apply_voice_context_status("idle", f"voice context stopped for {session_id}")


async def _start_voice_context_worker(session_id: str) -> None:
    existing = _voice_context_workers.get(session_id)
    if existing and not existing.done():
        return
    async with store._lock:
        await _apply_voice_context_status("starting", f"voice context starting for {session_id}")
    stop_event = asyncio.Event()
    _voice_context_stop_events[session_id] = stop_event
    _voice_context_offsets.setdefault(session_id, 0.0)
    _voice_context_sequences.setdefault(session_id, 0)
    _voice_context_workers[session_id] = asyncio.create_task(
        _voice_context_worker(session_id, stop_event),
        name=f"voice-context-{session_id}",
    )


async def _stop_voice_context_worker(session_id: str) -> None:
    stop_event = _voice_context_stop_events.get(session_id)
    task = _voice_context_workers.get(session_id)
    if stop_event:
        stop_event.set()
    if task and not task.done():
        try:
            await asyncio.wait_for(task, timeout=10.0)
        except asyncio.TimeoutError:
            task.cancel()
            await store.publish(
                "ownscribe_context_worker_stopped",
                {"session_id": session_id, "modality": "voice", "status": "cancelled"},
                session_id=session_id,
            )


async def _flush_voice_context_fragment(session_id: str) -> None:
    if ownscribe_adapter is None:
        return
    start = _voice_context_offsets.get(session_id, 0.0)
    sequence = _voice_context_sequences.get(session_id, 0)
    try:
        available = await asyncio.to_thread(ownscribe_adapter.recording_audio_duration_seconds, session_id)
    except Exception as exc:
        await store.publish(
            "context_fragment_sync_failed",
            {
                "session_id": session_id,
                "modality": "voice",
                "source": "ownscribe",
                "sequence": sequence,
                "status": "flush_failed",
                "detail": str(exc),
            },
            session_id=session_id,
        )
        return
    if available - start < CONTEXT_MIN_FRAGMENT_SECONDS:
        return
    try:
        await _create_voice_context_fragment(
            session_id,
            sequence=sequence,
            start_offset_seconds=start,
            end_offset_seconds=available,
            allow_partial=True,
        )
    except Exception as exc:
        await store.publish(
            "context_fragment_sync_failed",
            {
                "session_id": session_id,
                "modality": "voice",
                "source": "ownscribe",
                "sequence": sequence,
                "status": "flush_failed",
                "detail": str(exc),
            },
            session_id=session_id,
        )


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
        metadata={"adapter": "Project_Cortex", "mock": not sop_adapter.use_real},
    )
    await store.add_skill(skill, result.mdfile)
    await store.publish("skill_generated", to_dict(skill), session_id=source_session_id)
    return skill


@app.get("/health", response_model=ServiceStatus)
async def health() -> ServiceStatus:
    return ServiceStatus(name="HippoDEMO Orchestrator", status="ok", detail="mock-first FastAPI service")


_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_OWNSCRIBE_DATA_DIR = PROJECT_DIR / "orchestrator" / "data" / "ownscribe"
_DIAGNOSTIC_ORIGIN_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _static_diagnostic_logs() -> dict[str, Path]:
    return {
        "orchestrator": ORCHESTRATOR_LOG_PATH,
        "orchestrator-app": RUNTIME_DIR / "orchestrator-app.log",
        "cua-driver": RUNTIME_DIR / "cua-driver.log",
        "vlmac": RUNTIME_DIR / "vlmac.log",
        "ai-manus-runtime": PROJECT_DIR / "orchestrator" / "data" / "ai_manus" / "runtime.log",
    }


def _ownscribe_session_log_paths(session_id: str) -> dict[str, Path]:
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(status_code=404, detail="Unknown diagnostic session")
    session_dir = _OWNSCRIBE_DATA_DIR / session_id
    candidates = {
        "ownscribe-stdout": session_dir / "ownscribe.stdout.log",
        "ownscribe-stderr": session_dir / "ownscribe.stderr.log",
    }
    base = _OWNSCRIBE_DATA_DIR.resolve()
    safe: dict[str, Path] = {}
    for name, path in candidates.items():
        resolved = path.resolve()
        if not resolved.is_relative_to(base):
            raise HTTPException(status_code=404, detail="Unknown diagnostic session")
        safe[name] = resolved
    return safe


def _diagnostic_logs() -> dict[str, Path]:
    logs = _static_diagnostic_logs()
    session = store.state.current_session
    if session:
        for name, path in _ownscribe_session_log_paths(session.id).items():
            logs[f"current-{name}"] = path
    return logs


def _validate_diagnostics_request(request: Request | None) -> None:
    if request is None:
        return
    origin = request.headers.get("origin")
    if not origin:
        return
    try:
        host = urlparse(origin).hostname
    except ValueError:
        host = None
    if host not in _DIAGNOSTIC_ORIGIN_HOSTS:
        raise HTTPException(status_code=403, detail="Diagnostics logs are only available to local origins")


def _log_descriptor(name: str, path: Path) -> dict[str, Any]:
    try:
        exists = path.exists()
        stat = path.stat() if exists else None
    except OSError:
        exists = False
        stat = None
    return {
        "name": name,
        "exists": exists,
        "bytes": stat.st_size if stat else 0,
        "updated_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat() if stat else None,
    }


@app.get("/diagnostics/logs")
async def diagnostics_logs(request: Request):
    _validate_diagnostics_request(request)
    return {"logs": [_log_descriptor(name, path) for name, path in _diagnostic_logs().items()]}


@app.get("/diagnostics/logs/{name}")
async def diagnostics_log_tail(name: str, request: Request, limit: int = 200):
    _validate_diagnostics_request(request)
    logs = _diagnostic_logs()
    if name not in logs:
        raise HTTPException(status_code=404, detail="Unknown diagnostic log")
    safe_limit = max(1, min(int(limit), 1000))
    path = logs[name]
    return {
        "name": name,
        "limit": safe_limit,
        "entries": tail_log(path, limit=safe_limit),
    }


@app.get("/diagnostics/session/{session_id}/logs")
async def diagnostics_session_logs(session_id: str, request: Request, limit: int = 200):
    _validate_diagnostics_request(request)
    _session_or_404(session_id)
    safe_limit = max(1, min(int(limit), 1000))
    logs = _ownscribe_session_log_paths(session_id)
    return {
        "session_id": session_id,
        "logs": [
            {
                **_log_descriptor(name, path),
                "entries": tail_log(path, limit=safe_limit),
            }
            for name, path in logs.items()
        ],
    }


@app.get("/state")
async def get_state():
    await _refresh_openchronicle_status()
    await _refresh_ownscribe_status()
    await _refresh_cua_status()
    await _refresh_ai_manus_status()
    await _refresh_basic_memory_status()
    await _refresh_vlmac_status()
    return state_payload()


@app.get("/events/history")
async def event_history(limit: int = 50):
    return [to_dict(event) for event in store.bus.history(limit)]


@app.get("/context/recent")
async def context_recent(
    session_id: str | None = None,
    modality: str | None = None,
    limit: int = 50,
):
    fragments = store.list_context_fragments(
        session_id=session_id,
        modality=modality,
        limit=limit,
    )
    return {
        "fragments": [to_dict(fragment) for fragment in fragments],
        "count": len(fragments),
    }


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
    global _openchronicle_autostart_suppressed, _vlmac_autostart_suppressed

    _openchronicle_autostart_suppressed = False
    _vlmac_autostart_suppressed = False
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
    ownscribe_ok = ownscribe_service.status not in {"error", "unavailable"}
    session.metadata["ownscribe"] = _payload_from_result(ownscribe_result)
    if not ownscribe_ok:
        session.metadata["mode"] = "adapter-first-with-ownscribe-fallback"
    vlmac_service = await vlmac_adapter.start()
    session.metadata["vlmac"] = {
        "status": vlmac_service.status,
        "detail": vlmac_service.detail,
        "config": vlmac_adapter.config(),
    }
    response: dict[str, Any] | None = None
    async with store._lock:
        store.state.current_session = session
        store.state.jarvis_state = JarvisState.MEETING_ACTIVE
        store.state.sop_capture.status = CaptureStatus.IDLE
        await _apply_openchronicle_status(openchronicle_service)
        await _apply_ownscribe_status(ownscribe_service)
        await _apply_vlmac_status(vlmac_service)
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
        await store.publish(
            "vlmac_command",
            {"action": "start", "service": to_dict(vlmac_service), "config": vlmac_adapter.config()},
            session_id=session.id,
        )
        response = state_payload()
    if ownscribe_ok:
        await _start_voice_context_worker(session.id)
        response = state_payload()
    return response or state_payload()


@app.post("/session/jarvis-off")
async def jarvis_off():
    global _openchronicle_autostart_suppressed

    if not store.state.current_session:
        raise HTTPException(status_code=409, detail="No active session to stop.")
    session_id = store.state.current_session.id
    _openchronicle_autostart_suppressed = True
    openchronicle_service = await openchronicle_adapter.stop()
    await _stop_voice_context_worker(session_id)
    ownscribe_result, ownscribe_service = await _call_ownscribe(
        ("stop_recording", "stop", "finish", "finalize"),
        session_id=session_id,
        stop_timeout=OWNSCRIBE_STOP_TIMEOUT_SECONDS,
        terminate_timeout=5.0,
        kill_timeout=2.0,
    )
    if ownscribe_service.status not in {"error", "unavailable"}:
        await _flush_voice_context_fragment(session_id)
    vlmac_ingest = await vlmac_adapter.ingest()
    vlmac_sync_results = []
    for summary in vlmac_ingest.summaries:
        try:
            vlmac_sync_results.append(await _sync_basic_memory_vlmac_summary(summary, session_id=session_id))
        except Exception as exc:
            await store.publish(
                "basic_memory_sync_failed",
                {"kind": "vlmac_video_summary", "detail": str(exc)},
                session_id=session_id,
            )
    vlmac_service = await vlmac_adapter.status()
    async with store._lock:
        session = store.state.current_session
        if not session:
            raise HTTPException(status_code=409, detail="No active session to stop.")
        session.ended_at = now_iso()
        session.state = JarvisState.ACTIVE_TASK_CANDIDATE
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
        vlmac_artifacts = [
            artifact
            for artifact in (_vlmac_artifact_from_summary(summary) for summary in vlmac_ingest.summaries)
            if artifact is not None
        ]
        artifacts.extend(vlmac_artifacts)
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
        await _apply_vlmac_status(vlmac_service)
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
        if vlmac_artifacts:
            await store.publish(
                "vlmac_artifacts_ingested",
                {
                    "artifact_ids": [artifact.id for artifact in persisted_artifacts if artifact.type.startswith("vlmac_")],
                    "summary_count": len(vlmac_ingest.summaries),
                    "basic_memory_sync_count": len(vlmac_sync_results),
                    "rolling_context_path": vlmac_ingest.rolling_context_path,
                },
                session_id=session.id,
            )
        else:
            await store.publish(
                "vlmac_capture_unavailable",
                {"detail": vlmac_ingest.detail, "rolling_context_path": vlmac_ingest.rolling_context_path},
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
    global _openchronicle_autostart_suppressed
    _openchronicle_autostart_suppressed = False
    return await _openchronicle_command_snapshot("start", openchronicle_adapter.start)


@app.post("/integrations/openchronicle/stop")
async def openchronicle_stop():
    global _openchronicle_autostart_suppressed
    _openchronicle_autostart_suppressed = True
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


def _short_source_id(source_id: str | None) -> str:
    if not source_id:
        return "unknown"
    return (source_id.split("_")[-1] or source_id)[:8]


def _session_or_404(session_id: str) -> DemoSession:
    if store.state.current_session and store.state.current_session.id == session_id:
        return store.state.current_session
    path = SESSION_DIR / f"{session_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    try:
        return DemoSession(**json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to read session: {exc}") from exc


def _task_or_404(task_id: str) -> ActiveTask:
    try:
        return store.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Active Task not found.") from exc


def _skill_or_404(skill_id: str) -> SkillRecord:
    for skill in store.state.skills:
        if skill.id == skill_id:
            return skill
    raise HTTPException(status_code=404, detail="Skill not found.")


def _note_excerpt(value: str, limit: int = 2_400) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 40].rstrip() + "\n\n...[truncated by Hippo]"


def _artifact_safe_for_memory(artifact: Artifact) -> bool:
    kind = artifact.type.lower()
    if any(blocked in kind for blocked in ("transcript", "audio", "recording", "timeline")):
        return False
    return any(allowed in kind for allowed in ("minutes", "summary", "action", "follow", "task", "skill"))


def _artifact_memory_lines(artifact: Artifact) -> list[str]:
    lines = [
        f"### {artifact.title}",
        f"- id: `{artifact.id}`",
        f"- type: `{artifact.type}`",
    ]
    if artifact.path:
        lines.append(f"- path: `{artifact.path}`")
    if artifact.content and _artifact_safe_for_memory(artifact):
        lines.extend(["", _note_excerpt(artifact.content)])
    else:
        lines.append("- content: omitted by Hippo Basic Memory policy")
    return lines


def _basic_memory_session_note(session: DemoSession) -> tuple[str, str, str]:
    short_id = _short_source_id(session.id)
    title = f"Hippo Session {short_id}"
    lines = [
        f"# {title}",
        "",
        "## Source",
        f"- source_kind: session",
        f"- source_id: `{session.id}`",
        f"- title: {session.title}",
        f"- started_at: {session.started_at}",
        f"- ended_at: {session.ended_at or 'active'}",
        "",
        "## Summary",
        f"Session captured by HippoDEMO. Raw transcript is intentionally not synced to Basic Memory v1.",
    ]
    memory_artifacts = session.artifacts
    if memory_artifacts:
        lines.extend(["", "## Artifacts"])
        for artifact in memory_artifacts:
            lines.extend(_artifact_memory_lines(artifact))
            lines.append("")
    if session.active_task_ids:
        lines.extend(["## Relations"])
        for task_id in session.active_task_ids:
            lines.append(f"- has_task [[Hippo Task {_short_source_id(task_id)}]]")
    return title, "hippo/sessions", "\n".join(lines).strip() + "\n"


def _basic_memory_task_note(task: ActiveTask) -> tuple[str, str, str]:
    short_id = _short_source_id(task.id)
    title = f"Hippo Task {short_id}"
    lines = [
        f"# {title}",
        "",
        "## Source",
        "- source_kind: active_task",
        f"- source_id: `{task.id}`",
        f"- source_session_id: `{task.source_session_id or ''}`",
        f"- status: {task.status.value if hasattr(task.status, 'value') else task.status}",
        f"- confidence: {task.confidence}",
        f"- created_at: {task.created_at}",
        f"- updated_at: {task.updated_at}",
        "",
        "## Intent",
        task.intent,
    ]
    if task.proposed_actions:
        lines.extend(["", "## Proposed Actions"])
        for action in task.proposed_actions:
            lines.append(
                f"- {action.label} -> target: {action.target_type}; status: {action.status}; "
                f"requires_confirmation: {action.requires_confirmation}"
            )
    if task.artifacts:
        lines.extend(["", "## Supporting Artifacts"])
        for artifact in task.artifacts:
            lines.extend(_artifact_memory_lines(artifact))
            lines.append("")
    if task.source_session_id:
        lines.extend(["## Relations", f"- from_session [[Hippo Session {_short_source_id(task.source_session_id)}]]"])
    return title, "hippo/tasks", "\n".join(lines).strip() + "\n"


def _basic_memory_skill_note(skill: SkillRecord) -> tuple[str, str, str]:
    short_id = _short_source_id(skill.id)
    title = f"Hippo Skill {short_id}"
    skill_markdown = ""
    if skill.path:
        path = Path(skill.path)
        if path.exists() and path.is_file():
            skill_markdown = path.read_text(encoding="utf-8", errors="replace")
    lines = [
        f"# {title}",
        "",
        "## Source",
        "- source_kind: skill",
        f"- source_id: `{skill.id}`",
        f"- skill_name: {skill.name}",
        f"- source_session_id: `{skill.source_session_id or ''}`",
        f"- check_in: {skill.check_in or ''}",
        f"- check_out: {skill.check_out or ''}",
        f"- adapter: {skill.metadata.get('adapter') or ''}",
        "",
        "## Summary",
        skill.description,
    ]
    if skill.source_session_id:
        lines.extend(["", "## Relations", f"- distilled_from [[Hippo Session {_short_source_id(skill.source_session_id)}]]"])
    if skill_markdown:
        lines.extend(["", "## Skill Artifact", _note_excerpt(skill_markdown, limit=12_000)])
    return title, "hippo/skills", "\n".join(lines).strip() + "\n"


def _basic_memory_vlmac_summary_note(summary: dict[str, Any]) -> tuple[str, str, str, str]:
    source_id = str(summary.get("source_id") or "unknown")
    epoch_ms = str(summary.get("epoch_ms") or summary.get("system_time_iso") or now_iso())
    title = f"Hippo Video Summary {_short_source_id(source_id)} {str(summary.get('system_time_iso') or '')}".strip()
    chunk_paths = summary.get("chunk_paths") if isinstance(summary.get("chunk_paths"), list) else []
    lines = [
        f"# {title}",
        "",
        "## Source",
        "- source_kind: vlmac_video_summary",
        f"- source_id: `{source_id}`",
        f"- system_time_iso: {summary.get('system_time_iso') or ''}",
        f"- epoch_ms: {summary.get('epoch_ms') or ''}",
        f"- duration_seconds: {summary.get('duration_seconds') or 0}",
        f"- frames_used: {summary.get('frames_used') or 0}",
        f"- activity_events_count: {summary.get('activity_events_count') or 0}",
        f"- summary_path: `{summary.get('source_path') or summary.get('summary_path') or ''}`",
        "",
        "## Summary",
        _note_excerpt(str(summary.get("answer") or summary.get("summary") or ""), limit=12_000),
    ]
    if chunk_paths:
        lines.extend(["", "## Evidence Chunks"])
        for path in chunk_paths[:20]:
            lines.append(f"- `{path}`")
    return title, "hippo/context/video/summaries", "\n".join(lines).strip() + "\n", f"{source_id}:{epoch_ms}"


def _vlmac_artifact_from_summary(summary: dict[str, Any]) -> Artifact | None:
    answer = str(summary.get("answer") or summary.get("summary") or "").strip()
    if not answer:
        return None
    source_id = str(summary.get("source_id") or "unknown")
    system_time = str(summary.get("system_time_iso") or "")
    chunk_paths = summary.get("chunk_paths") if isinstance(summary.get("chunk_paths"), list) else []
    content = "\n".join(
        [
            f"# VLMac Video Summary {system_time}".strip(),
            "",
            "## Source",
            f"- source_id: `{source_id}`",
            f"- system_time_iso: {system_time}",
            f"- epoch_ms: {summary.get('epoch_ms') or ''}",
            f"- duration_seconds: {summary.get('duration_seconds') or 0}",
            f"- frames_used: {summary.get('frames_used') or 0}",
            f"- activity_events_count: {summary.get('activity_events_count') or 0}",
            "",
            "## Summary",
            answer,
            "",
            "## Evidence Chunks",
            *(f"- `{path}`" for path in chunk_paths[:20]),
            "",
        ]
    )
    return Artifact(
        type="vlmac_video_summary",
        title=f"vlmac video summary {system_time}".strip(),
        content=content,
        metadata={
            "source": "vlmac",
            "source_id": source_id,
            "system_time_iso": system_time,
            "epoch_ms": summary.get("epoch_ms"),
            "summary_path": summary.get("source_path") or summary.get("summary_path"),
            "chunk_paths": chunk_paths,
        },
    )


async def _publish_basic_memory_sync_result(
    result: dict[str, Any],
    *,
    kind: str,
    source_id: str,
    session_id: str | None = None,
) -> None:
    await store.publish(
        "basic_memory_note_written",
        {
            "kind": kind,
            "source_id": source_id,
            "status": result.get("status"),
            "identifier": result.get("identifier") or result.get("permalink"),
            "path": result.get("path"),
        },
        session_id=session_id,
    )


async def _sync_basic_memory_session(session: DemoSession) -> dict[str, Any]:
    title, folder, content = _basic_memory_session_note(session)
    result = await basic_memory_adapter.write_note(
        kind="session",
        source_id=session.id,
        title=title,
        folder=folder,
        content=content,
    )
    await _publish_basic_memory_sync_result(result, kind="session", source_id=session.id, session_id=session.id)
    return result


async def _sync_basic_memory_task(task: ActiveTask) -> dict[str, Any]:
    title, folder, content = _basic_memory_task_note(task)
    result = await basic_memory_adapter.write_note(
        kind="task",
        source_id=task.id,
        title=title,
        folder=folder,
        content=content,
    )
    await _publish_basic_memory_sync_result(result, kind="task", source_id=task.id, session_id=task.source_session_id)
    return result


async def _sync_basic_memory_skill(skill: SkillRecord) -> dict[str, Any]:
    title, folder, content = _basic_memory_skill_note(skill)
    result = await basic_memory_adapter.write_note(
        kind="skill",
        source_id=skill.id,
        title=title,
        folder=folder,
        content=content,
    )
    await _publish_basic_memory_sync_result(result, kind="skill", source_id=skill.id, session_id=skill.source_session_id)
    return result


async def _sync_basic_memory_vlmac_summary(summary: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
    title, folder, content, source_key = _basic_memory_vlmac_summary_note(summary)
    result = await basic_memory_adapter.write_note(
        kind="vlmac_video_summary",
        source_id=source_key,
        title=title,
        folder=folder,
        content=content,
    )
    await _publish_basic_memory_sync_result(result, kind="vlmac_video_summary", source_id=source_key, session_id=session_id)
    return result


async def _sync_basic_memory_task_best_effort(task: ActiveTask) -> None:
    try:
        await _sync_basic_memory_task(task)
        if task.source_session_id:
            await _sync_basic_memory_session(_session_or_404(task.source_session_id))
    except Exception as exc:
        await store.publish(
            "basic_memory_sync_failed",
            {"kind": "task", "source_id": task.id, "detail": str(exc)},
            session_id=task.source_session_id,
        )


async def _sync_basic_memory_skill_best_effort(skill: SkillRecord) -> None:
    try:
        await _sync_basic_memory_skill(skill)
    except Exception as exc:
        await store.publish(
            "basic_memory_sync_failed",
            {"kind": "skill", "source_id": skill.id, "detail": str(exc)},
            session_id=skill.source_session_id,
        )


@app.get("/integrations/basic-memory/config")
async def basic_memory_config():
    return basic_memory_adapter.config()


@app.get("/integrations/basic-memory/status")
async def basic_memory_status():
    service = await basic_memory_adapter.status()
    async with store._lock:
        await _apply_basic_memory_status(service)
        return _basic_memory_status_payload(service)


@app.post("/integrations/basic-memory/setup")
async def basic_memory_setup():
    try:
        result = await basic_memory_adapter.setup()
    except Exception as exc:
        service = ServiceStatus(name="basic-memory", status="error", detail=str(exc))
        async with store._lock:
            await _apply_basic_memory_status(service)
            await store.publish("basic_memory_sync_failed", {"kind": "setup", "detail": str(exc)})
        raise HTTPException(status_code=502, detail=f"basic-memory setup failed: {exc}") from exc

    service = await basic_memory_adapter.status()
    async with store._lock:
        await _apply_basic_memory_status(service)
        await store.publish(
            "basic_memory_setup_completed",
            {
                "status": service.status,
                "project": result.get("project"),
                "project_path": result.get("project_path"),
                "added": result.get("added"),
            },
        )
    return {**result, "service": _service_payload(service)}


@app.get("/integrations/basic-memory/search")
async def basic_memory_search(query: str, limit: int = 10):
    try:
        result = await basic_memory_adapter.search(query=query, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"basic-memory search failed: {exc}") from exc
    await store.publish(
        "basic_memory_search_completed",
        {"query": query, "result_count": len(result.get("results") or [])},
    )
    return result


@app.get("/integrations/basic-memory/recent")
async def basic_memory_recent(limit: int = 10):
    try:
        return await basic_memory_adapter.recent(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"basic-memory recent failed: {exc}") from exc


@app.get("/integrations/basic-memory/note/{identifier:path}")
async def basic_memory_note(identifier: str):
    try:
        return await basic_memory_adapter.read_note(identifier)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"basic-memory read note failed: {exc}") from exc


@app.post("/integrations/basic-memory/sync-session/{session_id}")
async def basic_memory_sync_session(session_id: str):
    session = _session_or_404(session_id)
    try:
        return await _sync_basic_memory_session(session)
    except Exception as exc:
        await store.publish("basic_memory_sync_failed", {"kind": "session", "source_id": session_id, "detail": str(exc)}, session_id=session_id)
        raise HTTPException(status_code=502, detail=f"basic-memory sync session failed: {exc}") from exc


@app.post("/integrations/basic-memory/sync-task/{task_id}")
async def basic_memory_sync_task(task_id: str):
    task = _task_or_404(task_id)
    try:
        return await _sync_basic_memory_task(task)
    except Exception as exc:
        await store.publish("basic_memory_sync_failed", {"kind": "task", "source_id": task_id, "detail": str(exc)}, session_id=task.source_session_id)
        raise HTTPException(status_code=502, detail=f"basic-memory sync task failed: {exc}") from exc


@app.post("/integrations/basic-memory/sync-skill/{skill_id}")
async def basic_memory_sync_skill(skill_id: str):
    skill = _skill_or_404(skill_id)
    try:
        return await _sync_basic_memory_skill(skill)
    except Exception as exc:
        await store.publish("basic_memory_sync_failed", {"kind": "skill", "source_id": skill_id, "detail": str(exc)}, session_id=skill.source_session_id)
        raise HTTPException(status_code=502, detail=f"basic-memory sync skill failed: {exc}") from exc


@app.post("/integrations/basic-memory/sync-context/{fragment_id}")
async def basic_memory_sync_context(fragment_id: str):
    try:
        fragment = store.get_context_fragment(fragment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown context fragment: {fragment_id}") from exc
    try:
        return await _sync_basic_memory_context(fragment)
    except Exception as exc:
        await store.publish(
            "context_fragment_sync_failed",
            {
                **_context_fragment_event_payload(fragment, status="failed"),
                "detail": str(exc),
            },
            session_id=fragment.session_id,
        )
        raise HTTPException(status_code=502, detail=f"basic-memory sync context failed: {exc}") from exc


@app.get("/integrations/project-cortex/agent/status")
async def project_cortex_agent_status():
    async with store._lock:
        return await _apply_hippo_agent_status()


@app.post("/chat/session")
async def unified_chat_create_session(request: AiManusCreateSessionRequest | None = None):
    title = request.title if request and request.title else "Hippo Chat"
    thread = AiManusThread(
        session_id=new_id("chat_thread"),
        title=title,
        status="active",
        metadata={
            "source": "hippo-chat",
            "primary_route": "auto",
            **_ai_manus_link_metadata(),
        },
    )
    async with store._lock:
        await store.save_ai_manus_thread(thread)
        await _apply_hippo_agent_status()
        await store.publish(
            "chat_session_created",
            {"session_id": thread.session_id, "primary_route": "auto"},
            session_id=thread.session_id,
        )
    return {"session_id": thread.session_id, "thread": _ai_manus_thread_summary(thread)}


@app.post("/chat/session/{session_id}/message")
async def unified_chat_message(session_id: str, request: AiManusChatRequest):
    route = _chat_route_for_message(request.message or "", request.route)
    await store.publish(
        "chat_route_selected",
        {
            "session_id": session_id,
            "route": route,
            "message_chars": len(request.message or ""),
            "requested_route": request.route or "auto",
        },
        session_id=session_id,
    )
    if route == "hippo_agent":
        return StreamingResponse(_stream_hippo_agent_chat(session_id, request), media_type="text/event-stream")
    return await ai_manus_chat(session_id, request)


async def _stream_hippo_agent_chat(session_id: str, request: AiManusChatRequest) -> AsyncGenerator[str, None]:
    try:
        thread = store.get_ai_manus_thread(session_id)
    except KeyError:
        yield _sse("error", {"error": f"Unknown chat thread: {session_id}"})
        return

    thread = _refresh_ai_manus_thread_links(thread)
    thread.metadata["last_route"] = "hippo_agent"
    await store.save_ai_manus_thread(thread)

    status = await _apply_hippo_agent_status()
    if not status.get("api_key_configured"):
        await store.publish("project_cortex_agent_failed", {"session_id": session_id, "detail": status.get("detail")}, session_id=session_id)
        yield _sse("error", {"error": status.get("detail") or "hippo_agent is not configured"})
        return

    message = (request.message or "").strip()
    if not message:
        yield _sse("error", {"error": "message is required"})
        return

    conversation_id = str(thread.metadata.get("hippo_agent_conversation_id") or "")
    message_id: str | None = None
    full_answer = ""
    event_count = 0

    try:
        await store.append_ai_manus_message(
            session_id,
            AiManusThreadMessage(
                role="user",
                content=message,
                event_id=request.event_id,
                attachments=request.attachments or [],
            ),
        )
        await store.publish(
            "project_cortex_agent_started",
            {"session_id": session_id, "message_chars": len(message)},
            session_id=session_id,
        )

        async for sse_event in hippo_agent_adapter.stream_chat(
            query=message,
            skill=_hippo_agent_skill_input(message),
            context=_hippo_agent_context_input(message, session_id),
            conversation_id=conversation_id or None,
            files=None,
        ):
            event_count += 1
            data = sse_event.get("data") if isinstance(sse_event, dict) else {}
            if not isinstance(data, dict):
                continue
            raw_event = str(data.get("event") or sse_event.get("event") or "message")

            if raw_event in {"message", "agent_message"}:
                chunk = str(data.get("answer") or "")
                if chunk:
                    full_answer += chunk
                    conversation_id = str(data.get("conversation_id") or conversation_id or "")
                    if not message_id:
                        message_id = str(data.get("message_id") or sse_event.get("id") or new_id("hippo_agent_message"))
                    yield _sse(
                        "message_delta",
                        {
                            "role": "assistant",
                            "content": chunk,
                            "source": "hippo_agent",
                            "event_id": message_id,
                            "timestamp": int(time.time()),
                        },
                        event_id=message_id or None,
                    )
                continue

            if raw_event == "agent_thought":
                thought_id = str(data.get("id") or f"hippo_agent_thought_{data.get('position') or event_count}")
                tool_payload = {
                    "tool_call_id": thought_id,
                    "name": data.get("tool") or "HippoAgent",
                    "function": data.get("thought") or data.get("tool") or "agent_thought",
                    "status": "completed" if data.get("observation") else "running",
                    "args": {"tool_input": data.get("tool_input") or ""},
                    "content": {
                        "thought": data.get("thought") or "",
                        "observation": data.get("observation") or "",
                        "message_files": data.get("message_files") or [],
                        "source": "hippo_agent",
                    },
                    "timestamp": int(time.time()),
                    "event_id": thought_id,
                }
                await store.append_ai_manus_event(session_id, AiManusThreadEvent(event="tool", data=tool_payload, event_id=thought_id))
                await store.publish(
                    "project_cortex_agent_thought",
                    {
                        "session_id": session_id,
                        "tool_call_id": thought_id,
                        "tool": tool_payload["name"],
                        "status": tool_payload["status"],
                    },
                    session_id=session_id,
                )
                yield _sse("tool", tool_payload, event_id=thought_id)
                continue

            if raw_event == "message_end":
                conversation_id = str(data.get("conversation_id") or conversation_id or "")
                message_id = str(data.get("id") or message_id or "")
                continue

            if raw_event == "error":
                raise RuntimeError(str(data.get("message") or data.get("error") or "hippo_agent error"))

        if full_answer:
            await store.append_ai_manus_message(
                session_id,
                AiManusThreadMessage(role="assistant", content=full_answer, event_id=message_id or None),
            )
        thread = store.get_ai_manus_thread(session_id)
        if conversation_id:
            thread.metadata["hippo_agent_conversation_id"] = conversation_id
        thread.metadata["last_route"] = "hippo_agent"
        thread.status = "active"
        await store.save_ai_manus_thread(thread)
        await store.publish(
            "project_cortex_agent_completed",
            {"session_id": session_id, "event_count": event_count, "answer_chars": len(full_answer)},
            session_id=session_id,
        )
        yield _sse(
            "message_complete",
            {
                "source": "hippo_agent",
                "conversation_id": conversation_id,
                "message_id": message_id,
                "content_chars": len(full_answer),
            },
        )
    except Exception as exc:
        try:
            await store.append_ai_manus_event(session_id, AiManusThreadEvent(event="error", data={"error": str(exc), "source": "hippo_agent"}))
        except KeyError:
            pass
        await store.publish("project_cortex_agent_failed", {"session_id": session_id, "detail": str(exc)}, session_id=session_id)
        yield _sse("error", {"error": str(exc), "source": "hippo_agent"})


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
    runtime_restart = None
    if config.get("restart_required"):
        runtime_restart = ai_manus_adapter.restart_runtime(build=False)
        if runtime_restart.get("status") in {"completed", "running"}:
            await asyncio.sleep(1.0)
        config = ai_manus_adapter.config()
        config["runtime_restart"] = runtime_restart
        if runtime_restart.get("status") not in {"completed", "running"}:
            config["detail"] = (
                "Saved ai-manus config; restart failed: "
                f"{runtime_restart.get('detail') or 'ai-manus backend restart failed'}"
            )

    wait_for_restart = bool(runtime_restart and runtime_restart.get("status") in {"completed", "running"})
    service = await _wait_for_ai_manus_status(timeout_seconds=18.0 if wait_for_restart else 0.0)
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
                "runtime_restart": runtime_restart,
            },
        )
    return config


@app.get("/integrations/ai-manus/status")
async def ai_manus_status():
    service = await ai_manus_adapter.status()
    async with store._lock:
        await _apply_ai_manus_status(service)
        return _ai_manus_status_payload(service)


@app.post("/integrations/ai-manus/model/validate")
async def ai_manus_validate_model():
    result = await ai_manus_adapter.validate_model_provider()
    await store.publish(
        "ai_manus_model_validation",
        {
            "ok": result.get("ok"),
            "status": result.get("status"),
            "api_base": result.get("api_base"),
            "model_name": result.get("model_name"),
            "models_count": result.get("models_count"),
            "model_visible": result.get("model_visible"),
            "detail": result.get("detail"),
        },
    )
    return result


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

    remote_session_id = _ai_manus_remote_session_id_or_none(local_thread)
    if not remote_session_id:
        detail["remote_status"] = "not_created"
        detail["remote_detail"] = "No ai-manus remote session has been created for this local Hippo thread yet."
        return detail

    try:
        remote_data = await ai_manus_adapter.get_session(remote_session_id)
        remote = _ai_manus_remote_summary(remote_data)
        if remote:
            detail["remote"] = remote
            detail["remote_status"] = remote.get("status")
            if remote.get("title") and not detail.get("title"):
                detail["title"] = remote["title"]
            if remote.get("status"):
                local_thread.status = str(remote["status"])
                detail["status"] = local_thread.status
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
            thread = await _ensure_ai_manus_remote_session(thread)
            thread.metadata["last_route"] = "ai_manus"
            await store.save_ai_manus_thread(thread)
            yield _sse("thread", _ai_manus_thread_summary(thread))
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
            try:
                yield _sse("thread", _ai_manus_thread_summary(store.get_ai_manus_thread(session_id)))
            except KeyError:
                pass
        except AiManusAuthRequired:
            yield _sse("auth_required", ai_manus_adapter.auth_required_payload())
        except Exception as exc:
            with_error = AiManusThreadEvent(event="error", data={"error": str(exc)})
            try:
                await store.append_ai_manus_event(session_id, with_error)
                yield _sse("thread", _ai_manus_thread_summary(store.get_ai_manus_thread(session_id)))
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


@app.get("/integrations/vlmac/status")
async def vlmac_status():
    service = await _vlmac_status_with_autostart()
    async with store._lock:
        await _apply_vlmac_status(service)
        return to_dict(service)


@app.get("/integrations/vlmac/config")
async def vlmac_config():
    return vlmac_adapter.config()


@app.post("/integrations/vlmac/config")
async def vlmac_update_config(request: VlmacConfigRequest):
    try:
        config = vlmac_adapter.update_config(
            vlm_base_url=request.vlm_base_url,
            vlm_model=request.vlm_model,
            vlm_api_key=request.vlm_api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    service = await vlmac_adapter.status()
    async with store._lock:
        await _apply_vlmac_status(service)
        await store.publish("vlmac_config_updated", {"config": config, "service": to_dict(service)})
    return config


@app.get("/integrations/vlmac/preflight")
async def vlmac_preflight(network: bool = False):
    return await vlmac_adapter.preflight(network=network)


async def _vlmac_command_snapshot(action: str, command) -> dict:
    service = await command()
    async with store._lock:
        await _apply_vlmac_status(service)
        await store.publish("vlmac_command", {"action": action, "service": to_dict(service), "config": vlmac_adapter.config()})
        return state_payload()


@app.post("/integrations/vlmac/start")
async def vlmac_start():
    global _vlmac_autostart_suppressed
    _vlmac_autostart_suppressed = False
    return await _vlmac_command_snapshot("start", vlmac_adapter.start)


@app.post("/integrations/vlmac/stop")
async def vlmac_stop():
    global _vlmac_autostart_suppressed
    _vlmac_autostart_suppressed = True
    return await _vlmac_command_snapshot("stop", vlmac_adapter.stop)


@app.post("/integrations/vlmac/restart")
async def vlmac_restart():
    global _vlmac_autostart_suppressed
    _vlmac_autostart_suppressed = False
    return await _vlmac_command_snapshot("restart", vlmac_adapter.restart)


@app.post("/integrations/vlmac/ingest")
async def vlmac_ingest():
    result = await vlmac_adapter.ingest()
    persisted_artifacts: list[Artifact] = []
    sync_results: list[dict[str, Any]] = []
    session = store.state.current_session

    for summary in result.summaries:
        try:
            sync_results.append(await _sync_basic_memory_vlmac_summary(summary, session_id=session.id if session else None))
        except Exception as exc:
            await store.publish(
                "basic_memory_sync_failed",
                {"kind": "vlmac_video_summary", "detail": str(exc)},
                session_id=session.id if session else None,
            )

    async with store._lock:
        session = store.state.current_session
        for summary in result.summaries:
            artifact = _vlmac_artifact_from_summary(summary)
            if artifact is None:
                continue
            persisted = await store.add_artifact(artifact, session=session)
            persisted_artifacts.append(persisted)
            await store.publish("artifact_ready", to_dict(persisted), session_id=session.id if session else None)
        if persisted_artifacts:
            await store.publish(
                "vlmac_artifacts_ingested",
                {
                    "artifact_ids": [artifact.id for artifact in persisted_artifacts],
                    "summary_count": len(result.summaries),
                    "basic_memory_sync_count": len(sync_results),
                    "rolling_context_path": result.rolling_context_path,
                },
                session_id=session.id if session else None,
            )
        else:
            await store.publish(
                "vlmac_capture_unavailable",
                {"detail": result.detail, "rolling_context_path": result.rolling_context_path},
                session_id=session.id if session else None,
            )
    return {
        "ok": result.ok,
        "detail": result.detail,
        "summary_count": len(result.summaries),
        "artifact_ids": [artifact.id for artifact in persisted_artifacts],
        "basic_memory_sync_count": len(sync_results),
        "rolling_context_path": result.rolling_context_path,
    }


@app.post("/intervention/detect")
async def intervention_detect():
    surface = await cua_driver_adapter.target_surface()
    async with store._lock:
        task = _current_task()
        if not task:
            await store.publish(
                "intervention_signal_idle",
                {"target_surface": _target_surface_payload(surface), "reason": "no_active_task"},
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
            },
            session_id=task.source_session_id,
        )
        return state_payload()


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
    skill_to_sync: SkillRecord | None = None
    response: dict[str, Any] | None = None
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
            skill_to_sync = SkillRecord(**to_dict(skill))
            response = state_payload()
        except Exception as exc:
            capture.status = CaptureStatus.FAILED
            capture.error = str(exc)
            await store.persist()
            await store.publish("sop_capture_failed", to_dict(capture), session_id=capture.source_session_id)
            raise HTTPException(status_code=502, detail=f"SOP generation failed: {exc}") from exc
    if skill_to_sync:
        await _sync_basic_memory_skill_best_effort(skill_to_sync)
    return response or state_payload()


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
    task_to_sync: ActiveTask | None = None
    response: dict[str, Any] | None = None
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
        task_to_sync = ActiveTask(**to_dict(task))
        response = state_payload()
    if task_to_sync:
        await _sync_basic_memory_task_best_effort(task_to_sync)
    return response or state_payload()


@app.post("/skill/generate")
async def skill_generate(request: SkillGenerateRequest | None = None):
    skill_to_sync: SkillRecord | None = None
    response: dict[str, Any] | None = None
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
        skill_to_sync = SkillRecord(**to_dict(skill))
        response = state_payload()
    if skill_to_sync:
        await _sync_basic_memory_skill_best_effort(skill_to_sync)
    return response or state_payload()


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
