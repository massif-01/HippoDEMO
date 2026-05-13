from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import httpx


PROJECT_DIR = Path(__file__).resolve().parents[2]
PROJECT_CORTEX_DIR = PROJECT_DIR / "Project_Cortex"


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


class ProjectCortexAgentAdapter:
    """Direct adapter for Project_Cortex hippo_agent.

    Hippo uses the existing Dify Agent app contract from Project_Cortex, but
    keeps the API key server-side and streams normalized events back to Swift.
    """

    def __init__(self) -> None:
        env = self._project_cortex_env()
        self.base_url = (
            os.getenv("HIPPO_AGENT_BASE_URL")
            or os.getenv("DIFY_BASE_URL")
            or env.get("HIPPO_AGENT_BASE_URL")
            or env.get("DIFY_BASE_URL")
            or "https://difyapp.aoseo.com/v1"
        ).rstrip("/")
        self.api_key = (
            os.getenv("HIPPO_AGENT_API_KEY")
            or os.getenv("DIFY_HIPPO_AGENT_KEY")
            or os.getenv("VITE_DIFY_HIPPO_AGENT_KEY")
            or env.get("HIPPO_AGENT_API_KEY")
            or env.get("DIFY_HIPPO_AGENT_KEY")
            or env.get("VITE_DIFY_HIPPO_AGENT_KEY")
            or ""
        )
        self.timeout_seconds = float(os.getenv("HIPPO_AGENT_TIMEOUT_SECONDS", env.get("HIPPO_AGENT_TIMEOUT_SECONDS", 180)))
        self.default_user = os.getenv("HIPPO_AGENT_USER", env.get("HIPPO_AGENT_USER", "hippo-local-user"))

    def status(self) -> dict[str, Any]:
        if not self.api_key:
            return {
                "name": "Project_Cortex",
                "status": "unconfigured",
                "detail": "hippo_agent Dify API key is not configured.",
                "base_url": self.base_url,
                "api_key_configured": False,
            }
        return {
            "name": "Project_Cortex",
            "status": "available",
            "detail": f"hippo_agent configured for {self.base_url}/chat-messages",
            "base_url": self.base_url,
            "api_key_configured": True,
        }

    def available(self) -> bool:
        return bool(self.api_key)

    async def stream_chat(
        self,
        *,
        query: str,
        skill: str = "",
        context: str = "",
        conversation_id: str | None = None,
        user: str | None = None,
        files: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        if not self.api_key:
            raise RuntimeError("hippo_agent Dify API key is not configured")

        payload: dict[str, Any] = {
            "inputs": {
                "skill": skill,
                "context": context,
            },
            "query": query,
            "response_mode": "streaming",
            "conversation_id": conversation_id or "",
            "user": user or self.default_user,
        }
        if files:
            payload["files"] = files

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        timeout = httpx.Timeout(self.timeout_seconds, read=None)
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            async with client.stream("POST", f"{self.base_url}/chat-messages", json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    text = body.decode("utf-8", errors="replace") if body else ""
                    raise RuntimeError(f"hippo_agent HTTP {response.status_code}: {text[:500]}")

                buffer: dict[str, str] = {}
                async for line in response.aiter_lines():
                    if line == "":
                        event = self._sse_from_buffer(buffer)
                        buffer = {}
                        if event:
                            yield event
                        continue
                    if line.startswith(":") or ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    buffer[key] = f"{buffer.get(key, '')}\n{value.lstrip()}".strip()
                event = self._sse_from_buffer(buffer)
                if event:
                    yield event

    def _sse_from_buffer(self, buffer: dict[str, str]) -> dict[str, Any] | None:
        data = buffer.get("data")
        if not data or data == "[DONE]":
            return None
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return {"event": buffer.get("event") or "message", "data": {"content": data}}
        return {
            "event": str(payload.get("event") or buffer.get("event") or "message"),
            "data": payload,
            "id": payload.get("id") or buffer.get("id"),
        }

    def _project_cortex_env(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for path in (PROJECT_CORTEX_DIR / ".env", PROJECT_CORTEX_DIR / "backend" / ".env"):
            if not path.exists():
                continue
            for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
        return values


hippo_agent_adapter = ProjectCortexAgentAdapter()
