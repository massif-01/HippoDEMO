from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .adapters.basic_memory import BasicMemoryAdapter, basic_memory_adapter
from .models import ActiveTask, Artifact, ProposedAction, now_iso, new_id


@dataclass
class FollowUpPackage:
    session_id: str
    subject: str
    body: str
    minutes_path: str | None = None
    context_priority: str = "empty"
    context_chunk_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("followup"))
    created_at: str = field(default_factory=now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def prepare_follow_up_package(
    *,
    session_id: str,
    start_at: str | None = None,
    end_at: str | None = None,
    query: str | None = None,
    adapter: BasicMemoryAdapter = basic_memory_adapter,
) -> FollowUpPackage:
    context = adapter.build_context(session_id=session_id, start_at=start_at, end_at=end_at, query=query)
    chunks = context.get("chunks") if isinstance(context.get("chunks"), list) else []
    context_content = str(context.get("content") or "").strip()
    subject = _subject_from_context(context_content)
    body = _body_from_context(context_content, context.get("context_priority") or "empty")
    minutes_path = _minutes_path(chunks)
    return FollowUpPackage(
        session_id=session_id,
        subject=subject,
        body=body,
        minutes_path=minutes_path,
        context_priority=str(context.get("context_priority") or "empty"),
        context_chunk_ids=[str(chunk.get("id")) for chunk in chunks if isinstance(chunk, dict) and chunk.get("id")],
        metadata={
            "start_at": start_at,
            "end_at": end_at,
            "query": query,
            "chunk_count": context.get("chunk_count", len(chunks)),
        },
    )


def active_task_from_follow_up(package: FollowUpPackage, *, target_type: str = "mail") -> ActiveTask:
    subject_artifact = Artifact(
        type="follow_up_subject",
        title="Follow-up subject",
        content=package.subject,
        metadata={"source": "basic-memory", "follow_up_package_id": package.id},
    )
    body_artifact = Artifact(
        type="follow_up_body",
        title="Follow-up body",
        content=package.body,
        metadata={"source": "basic-memory", "follow_up_package_id": package.id},
    )
    return ActiveTask(
        title="Prepare follow-up draft",
        intent="Prepare a follow-up draft from Jarvis session context; insertion still requires user confirmation.",
        source_session_id=package.session_id,
        artifacts=[subject_artifact, body_artifact],
        proposed_actions=[
            ProposedAction(
                label="Insert mail draft",
                target_type=target_type,
                external_visible=False,
                requires_confirmation=True,
                payload={
                    "mode": "insert_mail_draft",
                    "subject_artifact_id": subject_artifact.id,
                    "body_artifact_id": body_artifact.id,
                    "minutes_path": package.minutes_path,
                    "follow_up_package_id": package.id,
                },
            )
        ],
    )


def _subject_from_context(context: str) -> str:
    for line in context.splitlines():
        text = line.strip(" #-\t")
        if len(text) >= 8 and not text.startswith("{"):
            return f"Follow-up: {text[:72]}"
    return "Follow-up from our conversation"


def _body_from_context(context: str, context_priority: str) -> str:
    if not context:
        return (
            "Hi,\n\n"
            "Thanks for the conversation. I will send a more detailed follow-up once the meeting context is available.\n\n"
            "Best,\n"
        )
    context_label = {
        "video_context": "screen and meeting context",
        "audio_context": "meeting transcript context",
        "memory_context": "session context",
    }.get(context_priority, "session context")
    return (
        "Hi,\n\n"
        f"Thanks for the conversation. Based on the {context_label}, here is the proposed follow-up:\n\n"
        f"{_compact_context(context)}\n\n"
        "Best,\n"
    )


def _compact_context(context: str, max_chars: int = 2400) -> str:
    text = "\n".join(line.rstrip() for line in context.splitlines()).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20].rstrip() + "\n\n[Context truncated]"


def _minutes_path(chunks: list[Any]) -> str | None:
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        for key in ("minutes_path", "artifact_path", "source_path"):
            value = metadata.get(key)
            if value:
                return str(value)
    return None
