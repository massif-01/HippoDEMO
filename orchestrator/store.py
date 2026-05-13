from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    ActiveTask,
    Artifact,
    DemoSession,
    OrchestratorEvent,
    OrchestratorState,
    ServiceStatus,
    SkillRecord,
    now_iso,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ARTIFACT_DIR = DATA_DIR / "artifacts"
SESSION_DIR = DATA_DIR / "sessions"
SKILL_DIR = DATA_DIR / "skills"


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
            ServiceStatus(name="vlmac", status="mock", detail="video capture placeholder"),
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


store = OrchestratorStore()
