from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..models import now_iso


@dataclass
class PlanWorkerStatus:
    name: str
    status: str = "idle"
    detail: str | None = None
    started_at: str | None = None
    updated_at: str = field(default_factory=now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)
