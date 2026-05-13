from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class SopGeneratorResult:
    name: str
    description: str
    mdfile: str


class ProjectCortexSopAdapter:
    """Adapter compatible with Project_Cortex `/api/sop_generator`.

    Mock mode is the default for this demo. Set `HIPPO_USE_PROJECT_CORTEX=true`
    and optionally `PROJECT_CORTEX_URL=http://localhost:8000` to call the real
    backend later without changing Orchestrator routes.
    """

    def __init__(self) -> None:
        self.use_real = os.getenv("HIPPO_USE_PROJECT_CORTEX", "false").lower() == "true"
        self.base_url = os.getenv("PROJECT_CORTEX_URL", "http://localhost:8000").rstrip("/")

    async def generate(
        self,
        *,
        check_in: Optional[str],
        check_out: Optional[str],
        source_session_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> SopGeneratorResult:
        if self.use_real:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/sop_generator",
                    json={"check_in": check_in, "check_out": check_out},
                )
                response.raise_for_status()
                data = response.json()
                return SopGeneratorResult(
                    name=data.get("name") or name or "Captured Skill",
                    description=data.get("description") or description or "Generated from captured workflow.",
                    mdfile=data.get("mdfile") or data.get("markdown") or "",
                )

        skill_name = name or "Investor Follow-up Skill"
        skill_description = description or "Turn a finished meeting into minutes, follow-up copy, action items, and a confirmed insertion task."
        mdfile = f"""# {skill_name}

## Description
{skill_description}

## Trigger
- A Jarvis session has ended.
- Meeting artifacts are ready.
- The user opens a communication, compose, document, browser form, or CRM note surface.

## Inputs
- `check_in`: {check_in or "session start"}
- `check_out`: {check_out or "session end"}
- `source_session_id`: {source_session_id or "manual capture"}

## Steps
1. Collect transcript, screen context, and explicit user capture markers.
2. Generate meeting minutes, follow-up body, and action items.
3. Create an Active Task with proposed insertion actions.
4. Wait for the user to confirm before inserting any externally visible content.
5. Mark the task complete only after user review.

## Guardrails
- Never send, submit, or publish content automatically.
- Keep insertion reversible whenever the target surface allows it.
- Preserve source artifacts for later review.
"""
        return SopGeneratorResult(name=skill_name, description=skill_description, mdfile=mdfile)


sop_adapter = ProjectCortexSopAdapter()

