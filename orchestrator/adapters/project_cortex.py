from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from ..models import ServiceStatus


PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_DIR / "orchestrator" / "data" / "project_cortex_config.json"

DEFAULT_CONFIG: dict[str, object] = {
    "use_real": False,
    "service_base_url": "http://localhost:8000",
    "openai_base_url": "",
    "openai_model": "",
    "openai_api_key": "",
    "temperature": 0.2,
    "max_tokens": 2400,
    "timeout_seconds": 60.0,
}


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
        self._config = self._load_config()

    async def generate(
        self,
        *,
        check_in: Optional[str],
        check_out: Optional[str],
        source_session_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> SopGeneratorResult:
        config = self._runtime_config()
        if bool(config.get("use_real")):
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{str(config['service_base_url']).rstrip('/')}/api/sop_generator",
                    json={"check_in": check_in, "check_out": check_out},
                )
                response.raise_for_status()
                data = response.json()
                return SopGeneratorResult(
                    name=data.get("name") or name or "Captured Skill",
                    description=data.get("description") or description or "Generated from captured workflow.",
                    mdfile=data.get("mdfile") or data.get("markdown") or "",
                )

        if config.get("openai_base_url") and config.get("openai_model"):
            return await self._generate_openai_compatible(
                config=config,
                check_in=check_in,
                check_out=check_out,
                source_session_id=source_session_id,
                name=name,
                description=description,
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

    @property
    def use_real(self) -> bool:
        return bool(self._runtime_config().get("use_real"))

    def config(self) -> dict[str, object]:
        config = self._runtime_config()
        return {
            "use_real": bool(config.get("use_real")),
            "service_base_url": config.get("service_base_url"),
            "openai_base_url": config.get("openai_base_url"),
            "openai_model": config.get("openai_model"),
            "openai_api_key_configured": bool(config.get("openai_api_key") or os.getenv("PROJECT_CORTEX_OPENAI_API_KEY")),
            "temperature": config.get("temperature"),
            "max_tokens": config.get("max_tokens"),
            "timeout_seconds": config.get("timeout_seconds"),
            "config_path": str(CONFIG_PATH),
            "config_exists": CONFIG_PATH.exists(),
        }

    def update_config(
        self,
        *,
        use_real: bool | None = None,
        service_base_url: str | None = None,
        openai_base_url: str | None = None,
        openai_model: str | None = None,
        openai_api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        config = self._runtime_config()
        if use_real is not None:
            config["use_real"] = bool(use_real)
        if service_base_url is not None:
            config["service_base_url"] = self._normalize_url(service_base_url)
        if openai_base_url is not None:
            config["openai_base_url"] = self._normalize_url(openai_base_url)
        if openai_model is not None:
            config["openai_model"] = openai_model.strip()
        if openai_api_key is not None and openai_api_key.strip():
            config["openai_api_key"] = openai_api_key.strip()
        if temperature is not None:
            config["temperature"] = float(temperature)
        if max_tokens is not None:
            if max_tokens <= 0:
                raise ValueError("max_tokens must be greater than 0")
            config["max_tokens"] = int(max_tokens)
        if timeout_seconds is not None:
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds must be greater than 0")
            config["timeout_seconds"] = float(timeout_seconds)
        self._config = config
        self._write_config(config)
        return self.config()

    async def status(self) -> ServiceStatus:
        config = self._runtime_config()
        if bool(config.get("use_real")):
            return ServiceStatus(
                name="Project_Cortex",
                status="available",
                detail=f"real_service={config.get('service_base_url')}",
            )
        if config.get("openai_base_url") and config.get("openai_model"):
            return ServiceStatus(
                name="Project_Cortex",
                status="available",
                detail=f"openai_compatible={config.get('openai_base_url')}; model={config.get('openai_model')}",
            )
        return ServiceStatus(
            name="Project_Cortex",
            status="mock",
            detail="Skill generation is using local mock templates; configure Project_Cortex real service or OpenAI-compatible fallback.",
        )

    async def _generate_openai_compatible(
        self,
        *,
        config: dict[str, object],
        check_in: Optional[str],
        check_out: Optional[str],
        source_session_id: Optional[str],
        name: Optional[str],
        description: Optional[str],
    ) -> SopGeneratorResult:
        skill_name = name or "Captured Jarvis Skill"
        skill_description = description or "Generated from the selected Jarvis Highlight window."
        prompt = (
            "Create a concise Markdown skill/SOP for a Jarvis workflow capture.\n"
            f"Name: {skill_name}\n"
            f"Description: {skill_description}\n"
            f"check_in: {check_in or 'session start'}\n"
            f"check_out: {check_out or 'session end'}\n"
            f"source_session_id: {source_session_id or 'manual capture'}\n\n"
            "Return only Markdown. Include Description, Trigger, Inputs, Steps, and Guardrails."
        )
        headers = {"Content-Type": "application/json"}
        api_key = str(config.get("openai_api_key") or os.getenv("PROJECT_CORTEX_OPENAI_API_KEY") or "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": config.get("openai_model"),
            "messages": [
                {"role": "system", "content": "You write practical workflow skills for a local Jarvis assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": config.get("temperature"),
            "max_tokens": config.get("max_tokens"),
        }
        timeout = float(config.get("timeout_seconds") or DEFAULT_CONFIG["timeout_seconds"])
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{str(config['openai_base_url']).rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        choices = data.get("choices") if isinstance(data, dict) else None
        content = ""
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else {}
            content = str(message.get("content") or "").strip()
        return SopGeneratorResult(
            name=skill_name,
            description=skill_description,
            mdfile=content or f"# {skill_name}\n\n## Description\n{skill_description}\n",
        )

    def _runtime_config(self) -> dict[str, object]:
        config = {**DEFAULT_CONFIG, **self._config}
        config["use_real"] = bool(config.get("use_real")) or os.getenv("HIPPO_USE_PROJECT_CORTEX", "false").lower() == "true"
        config["service_base_url"] = self._normalize_url(
            str(os.getenv("PROJECT_CORTEX_URL") or config.get("service_base_url") or DEFAULT_CONFIG["service_base_url"])
        )
        config["openai_base_url"] = self._normalize_url(
            str(os.getenv("PROJECT_CORTEX_OPENAI_BASE_URL") or config.get("openai_base_url") or "")
        )
        config["openai_model"] = str(os.getenv("PROJECT_CORTEX_OPENAI_MODEL") or config.get("openai_model") or "")
        config["openai_api_key"] = str(os.getenv("PROJECT_CORTEX_OPENAI_API_KEY") or config.get("openai_api_key") or "")
        return config

    def _load_config(self) -> dict[str, object]:
        if not CONFIG_PATH.exists():
            return dict(DEFAULT_CONFIG)
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return {**DEFAULT_CONFIG, **loaded}
        except Exception:
            pass
        return dict(DEFAULT_CONFIG)

    def _write_config(self, config: dict[str, object]) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    def _normalize_url(self, value: str) -> str:
        return value.strip().rstrip("/")


sop_adapter = ProjectCortexSopAdapter()
