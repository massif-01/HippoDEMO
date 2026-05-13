from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class JarvisState(str, Enum):
    IDLE = "idle"
    MEETING_ACTIVE = "meeting_active"
    PAUSED = "paused"
    MEETING_WRAPPING_UP = "meeting_wrapping_up"
    ACTIVE_TASK_CANDIDATE = "active_task_candidate"
    INTERVENTION_READY = "intervention_ready"
    AWAITING_REVIEW = "awaiting_review"
    PATTERN_DETECTED = "pattern_detected"


class CaptureStatus(str, Enum):
    IDLE = "idle"
    CAPTURING = "capturing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ActiveTaskStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IGNORED = "ignored"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"


class ServiceStatus(BaseModel):
    name: str
    status: str = "mock"
    detail: Optional[str] = None
    updated_at: str = Field(default_factory=now_iso)


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: new_id("artifact"))
    type: str
    title: str
    content: str
    path: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextFragment(BaseModel):
    id: str = Field(default_factory=lambda: new_id("context"))
    session_id: str
    modality: str
    source: str
    text: str
    started_at: str
    ended_at: Optional[str] = None
    sequence: int = 0
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    synced_at: Optional[str] = None


class ProposedAction(BaseModel):
    id: str = Field(default_factory=lambda: new_id("action"))
    label: str
    target_type: str
    requires_confirmation: bool = True
    reversible: bool = True
    external_visible: bool = False
    status: str = "proposed"
    payload: Dict[str, Any] = Field(default_factory=dict)


class CuaTargetSurface(BaseModel):
    safe: bool = False
    status: str = "unknown"
    mode: str = "none"
    requires_confirmation: bool = True
    reason: str = "Target surface has not been checked."
    app_name: Optional[str] = None
    bundle_id: Optional[str] = None
    pid: Optional[int] = None
    window_id: Optional[int] = None
    window_title: Optional[str] = None
    element_index: Optional[int] = None
    element_role: Optional[str] = None
    detail: Optional[str] = None


class ActiveTask(BaseModel):
    id: str = Field(default_factory=lambda: new_id("task"))
    title: str
    intent: str
    status: ActiveTaskStatus = ActiveTaskStatus.PENDING
    confidence: float = 0.82
    source_session_id: Optional[str] = None
    artifacts: List[Artifact] = Field(default_factory=list)
    proposed_actions: List[ProposedAction] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class SopCapture(BaseModel):
    id: str = Field(default_factory=lambda: new_id("capture"))
    status: CaptureStatus = CaptureStatus.IDLE
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    source_session_id: Optional[str] = None
    generated_skill_id: Optional[str] = None
    error: Optional[str] = None


class DemoSession(BaseModel):
    id: str = Field(default_factory=lambda: new_id("session"))
    title: str = "Investor meeting"
    state: JarvisState = JarvisState.MEETING_ACTIVE
    started_at: str = Field(default_factory=now_iso)
    ended_at: Optional[str] = None
    transcript: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts: List[Artifact] = Field(default_factory=list)
    active_task_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SkillRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("skill"))
    name: str
    description: str
    path: str
    created_at: str = Field(default_factory=now_iso)
    source_session_id: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrchestratorEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("event"))
    type: str
    timestamp: str = Field(default_factory=now_iso)
    session_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class OrchestratorState(BaseModel):
    jarvis_state: JarvisState = JarvisState.IDLE
    current_session: Optional[DemoSession] = None
    sop_capture: SopCapture = Field(default_factory=SopCapture)
    active_tasks: List[ActiveTask] = Field(default_factory=list)
    skills: List[SkillRecord] = Field(default_factory=list)
    services: List[ServiceStatus] = Field(default_factory=list)
    updated_at: str = Field(default_factory=now_iso)


class CaptureFinishRequest(BaseModel):
    check_out: Optional[str] = None


class ActiveTaskGenerateRequest(BaseModel):
    source_session_id: Optional[str] = None
    intent: Optional[str] = None
    target_type: str = "communication"


class SkillGenerateRequest(BaseModel):
    source_session_id: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class OwnscribeConfigRequest(BaseModel):
    audio_source: Optional[str] = None
    mic_device: Optional[str] = None
    audio_display: Optional[bool] = None
    asr_provider: Optional[str] = None
    asr_base_url: Optional[str] = None
    asr_model: Optional[str] = None
    asr_api_key: Optional[str] = None
    summary_provider: Optional[str] = None
    summary_base_url: Optional[str] = None
    summary_model: Optional[str] = None
    summary_api_key: Optional[str] = None
    api_key: Optional[str] = None


class VlmacConfigRequest(BaseModel):
    vlm_base_url: Optional[str] = None
    vlm_model: Optional[str] = None
    vlm_api_key: Optional[str] = None


class AiManusConfigRequest(BaseModel):
    base_url: Optional[str] = None
    frontend_url: Optional[str] = None
    auth_provider: Optional[str] = None
    api_key: Optional[str] = None
    timeout_seconds: Optional[float] = None
    api_base: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    extra_headers: Optional[str] = None


class AiManusCreateSessionRequest(BaseModel):
    title: Optional[str] = None


class AiManusChatRequest(BaseModel):
    timestamp: Optional[int] = None
    message: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    event_id: Optional[str] = None
    route: Optional[str] = None


class AiManusSignedUrlRequest(BaseModel):
    expire_minutes: int = Field(15, ge=1, le=15)


class AiManusRuntimeCommandRequest(BaseModel):
    build: bool = False


class AiManusFileViewRequest(BaseModel):
    file_id: Optional[str] = None
    file_path: Optional[str] = None
    file: Optional[str] = None
    path: Optional[str] = None


class AiManusThreadMessage(BaseModel):
    id: str = Field(default_factory=lambda: new_id("message"))
    role: str
    content: str = ""
    timestamp: str = Field(default_factory=now_iso)
    event_id: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


class AiManusThreadEvent(BaseModel):
    event: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=now_iso)
    event_id: Optional[str] = None


class AiManusThread(BaseModel):
    session_id: str
    manus_session_id: Optional[str] = None
    title: Optional[str] = None
    status: str = "active"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    latest_message: Optional[str] = None
    latest_message_at: Optional[int] = None
    unread_message_count: int = 0
    is_shared: bool = False
    messages: List[AiManusThreadMessage] = Field(default_factory=list)
    events: List[AiManusThreadEvent] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
