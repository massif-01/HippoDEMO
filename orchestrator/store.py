from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    ActiveTask,
    AiManusThread,
    AiManusThreadEvent,
    AiManusThreadMessage,
    Artifact,
    DemoSession,
    FollowUpPackage,
    ForegroundAXSnapshot,
    HighlightSegment,
    MailDraftInsertResult,
    MemoryContextChunk,
    OrchestratorEvent,
    OrchestratorState,
    PlanWorkerStatus,
    ServiceStatus,
    SkillRecord,
    now_iso,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ARTIFACT_DIR = DATA_DIR / "artifacts"
SESSION_DIR = DATA_DIR / "sessions"
SKILL_DIR = DATA_DIR / "skills"
AI_MANUS_DIR = DATA_DIR / "ai_manus"
AI_MANUS_THREAD_DIR = AI_MANUS_DIR / "threads"
MEMORY_CONTEXT_DIR = DATA_DIR / "memory_context"


def to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class EventBus:
    def __init__(self) -> None:
        self._subscribers: List[asyncio.Queue[OrchestratorEvent]] = []
        self._history: List[OrchestratorEvent] = []

    async def publish(self, event: OrchestratorEvent) -> OrchestratorEvent:
        self._history.append(event)
        self._history = self._history[-200:]
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass
                except asyncio.QueueFull:
                    pass
        return event

    async def subscribe(self) -> asyncio.Queue[OrchestratorEvent]:
        queue: asyncio.Queue[OrchestratorEvent] = asyncio.Queue(maxsize=100)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[OrchestratorEvent]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def history(self, limit: int = 50) -> List[OrchestratorEvent]:
        safe_limit = max(1, min(limit, 200))
        return list(reversed(self._history[-safe_limit:]))


class OrchestratorStore:
    def __init__(self) -> None:
        self.state = OrchestratorState(services=self.default_services())
        self.bus = EventBus()
        self._lock = asyncio.Lock()
        self.load_skills()

    @staticmethod
    def default_services() -> List[ServiceStatus]:
        return [
            ServiceStatus(name="ownscribe", status="available", detail="ownscribe adapter pending status refresh"),
            ServiceStatus(name="ai-manus", status="available", detail="ai-manus adapter pending status refresh"),
            ServiceStatus(name="basic-memory", status="available", detail="Basic Memory adapter pending status refresh"),
            ServiceStatus(name="basic-memory-queue", status="idle", detail="Basic Memory write queue not started"),
            ServiceStatus(name="vlmac", status="available", detail="vlmac adapter pending status refresh"),
            ServiceStatus(name="AX detector", status="idle", detail="Foreground AX detector not started"),
            ServiceStatus(name="OpenChronicle", status="available", detail="OpenChronicle CLI adapter pending status refresh"),
            ServiceStatus(name="cua-driver", status="available", detail="cua-driver adapter pending status refresh"),
            ServiceStatus(name="Project_Cortex", status="mock", detail="/api/sop_generator adapter disabled by default"),
        ]

    def load_skills(self) -> None:
        path = DATA_DIR / "skills.json"
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.state.skills = [SkillRecord(**item) for item in raw]
        except Exception:
            self.state.skills = []

    async def publish(self, event_type: str, payload: Dict[str, Any], session_id: Optional[str] = None) -> None:
        await self.bus.publish(OrchestratorEvent(type=event_type, session_id=session_id, payload=payload))

    async def persist(self) -> None:
        self.state.updated_at = now_iso()
        write_json(DATA_DIR / "state.json", to_dict(self.state))
        write_json(DATA_DIR / "skills.json", [to_dict(skill) for skill in self.state.skills])
        if self.state.current_session:
            write_json(SESSION_DIR / f"{self.state.current_session.id}.json", to_dict(self.state.current_session))
        for task in self.state.active_tasks:
            write_json(DATA_DIR / "active_tasks" / f"{task.id}.json", to_dict(task))

    async def set_session(self, session: DemoSession) -> None:
        self.state.current_session = session
        self.state.jarvis_state = session.state
        await self.persist()

    async def add_artifact(self, artifact: Artifact, session: Optional[DemoSession] = None) -> Artifact:
        artifact_path = ARTIFACT_DIR / f"{artifact.id}_{artifact.type}.md"
        artifact.path = str(artifact_path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(artifact.content, encoding="utf-8")
        if session:
            session.artifacts.append(artifact)
        await self.persist()
        return artifact

    async def add_memory_context_chunk(self, chunk: MemoryContextChunk) -> MemoryContextChunk:
        self.state.memory_context_chunks.append(chunk)
        self.state.memory_context_chunks = self.state.memory_context_chunks[-200:]
        path = MEMORY_CONTEXT_DIR / f"{chunk.id}_{chunk.source}.json"
        write_json(path, to_dict(chunk))
        await self.persist()
        return chunk

    async def set_frontmost_context(self, snapshot: ForegroundAXSnapshot) -> ForegroundAXSnapshot:
        self.state.frontmost_context = snapshot
        await self.persist()
        return snapshot

    async def set_highlight_segment(self, segment: HighlightSegment) -> HighlightSegment:
        self.state.highlight_segment = segment
        await self.persist()
        return segment

    async def set_follow_up_package(self, package: FollowUpPackage) -> FollowUpPackage:
        self.state.follow_up_package = package
        await self.persist()
        return package

    async def set_mail_draft_insert_result(self, result: MailDraftInsertResult) -> MailDraftInsertResult:
        self.state.mail_draft_insert_result = result
        await self.persist()
        return result

    async def set_worker_status(self, status: PlanWorkerStatus) -> PlanWorkerStatus:
        for index, existing in enumerate(self.state.worker_statuses):
            if existing.name.lower() == status.name.lower():
                self.state.worker_statuses[index] = status
                await self.persist()
                return status
        self.state.worker_statuses.append(status)
        await self.persist()
        return status

    async def add_active_task(self, task: ActiveTask) -> ActiveTask:
        self.state.active_tasks.insert(0, task)
        if self.state.current_session and task.source_session_id == self.state.current_session.id:
            self.state.current_session.active_task_ids.append(task.id)
        await self.persist()
        return task

    def get_task(self, task_id: str) -> ActiveTask:
        for task in self.state.active_tasks:
            if task.id == task_id:
                return task
        raise KeyError(task_id)

    async def add_skill(self, skill: SkillRecord, markdown: str) -> SkillRecord:
        path = Path(skill.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        self.state.skills.insert(0, skill)
        await self.persist()
        return skill

    async def delete_skill(self, skill_id: str) -> SkillRecord:
        for index, skill in enumerate(self.state.skills):
            if skill.id != skill_id:
                continue

            removed = self.state.skills.pop(index)
            if removed.path:
                path = Path(removed.path)
                if path.exists() and path.is_file():
                    path.unlink()
            await self.persist()
            return removed

        raise KeyError(skill_id)

    def list_ai_manus_threads(self) -> List[AiManusThread]:
        if not AI_MANUS_THREAD_DIR.exists():
            return []

        threads: List[AiManusThread] = []
        for path in AI_MANUS_THREAD_DIR.glob("*.json"):
            try:
                threads.append(AiManusThread(**json.loads(path.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return sorted(threads, key=lambda thread: thread.updated_at, reverse=True)

    def get_ai_manus_thread(self, session_id: str) -> AiManusThread:
        path = AI_MANUS_THREAD_DIR / f"{session_id}.json"
        if not path.exists():
            raise KeyError(session_id)
        return AiManusThread(**json.loads(path.read_text(encoding="utf-8")))

    async def save_ai_manus_thread(self, thread: AiManusThread) -> AiManusThread:
        thread.updated_at = now_iso()
        write_json(AI_MANUS_THREAD_DIR / f"{thread.session_id}.json", to_dict(thread))
        return thread

    async def append_ai_manus_message(self, session_id: str, message: AiManusThreadMessage) -> AiManusThread:
        thread = self.get_ai_manus_thread(session_id)
        thread.messages.append(message)
        thread.latest_message = message.content
        thread.latest_message_at = int(datetime.fromisoformat(message.timestamp).timestamp())
        return await self.save_ai_manus_thread(thread)

    async def append_ai_manus_event(self, session_id: str, event: AiManusThreadEvent) -> AiManusThread:
        thread = self.get_ai_manus_thread(session_id)
        thread.events.append(event)
        if event.data.get("status"):
            thread.status = str(event.data["status"])
        return await self.save_ai_manus_thread(thread)


store = OrchestratorStore()
