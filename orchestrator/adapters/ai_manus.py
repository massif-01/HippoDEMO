from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, AsyncGenerator
from urllib.parse import urlparse, urlunparse

import httpx

from ..logging_config import log_event
from ..models import ServiceStatus
from ..store import AI_MANUS_DIR, write_json


CONFIG_PATH = AI_MANUS_DIR / "config.json"
PROJECT_DIR = Path(__file__).resolve().parents[2]
AI_MANUS_PROJECT_DIR = PROJECT_DIR / "ai-manus"
AI_MANUS_COMPOSE_PATH = AI_MANUS_PROJECT_DIR / "docker-compose.yml"
AI_MANUS_ENV_PATH = AI_MANUS_PROJECT_DIR / ".env"
AI_MANUS_ENV_EXAMPLE_PATH = AI_MANUS_PROJECT_DIR / ".env.example"
AI_MANUS_RUNTIME_LOG_PATH = AI_MANUS_DIR / "runtime.log"
AI_MANUS_MODEL_ENV_KEYS = (
    "AUTH_PROVIDER",
    "API_BASE",
    "MODEL_NAME",
    "API_KEY",
    "TEMPERATURE",
    "MAX_TOKENS",
    "EXTRA_HEADERS",
)
logger = logging.getLogger("orchestrator.adapters.ai_manus")


class AiManusAPIError(RuntimeError):
    pass


class AiManusAuthRequired(RuntimeError):
    pass


class AiManusAdapter:
    def __init__(self) -> None:
        self._config = self._load_config()
        self._restart_required = False

    def _load_config(self) -> dict[str, Any]:
        config = {
            "base_url": os.getenv("HIPPODEMO_AI_MANUS_URL", "http://127.0.0.1:8000"),
            "frontend_url": os.getenv("HIPPODEMO_AI_MANUS_FRONTEND_URL", "http://127.0.0.1:5173"),
            "auth_provider": os.getenv("AUTH_PROVIDER", os.getenv("HIPPODEMO_AI_MANUS_AUTH_PROVIDER", "none")),
            "api_key": os.getenv("HIPPODEMO_AI_MANUS_API_KEY"),
            "timeout_seconds": float(os.getenv("HIPPODEMO_AI_MANUS_TIMEOUT_SECONDS", "60")),
        }
        if CONFIG_PATH.exists():
            try:
                saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(saved, dict):
                    allowed_saved_keys = {"base_url", "frontend_url", "auth_provider", "timeout_seconds"}
                    config.update(
                        {
                            key: value
                            for key, value in saved.items()
                            if key in allowed_saved_keys and value is not None
                        }
                    )
            except Exception:
                pass
        config["base_url"] = str(config["base_url"]).rstrip("/")
        config["frontend_url"] = str(config["frontend_url"]).rstrip("/")
        config["auth_provider"] = str(config.get("auth_provider") or "none").lower()
        return config

    def config(self) -> dict[str, Any]:
        env_config = self.model_env_config()
        return {
            "base_url": self._config["base_url"],
            "frontend_url": self._config["frontend_url"],
            "api_base_url": self._api_base_url(),
            "auth_provider": self._config["auth_provider"],
            "timeout_seconds": self._config["timeout_seconds"],
            **env_config,
            "api_key_configured": env_config["api_key_configured"] or bool(self._config.get("api_key")),
        }

    def update_config(
        self,
        *,
        base_url: str | None = None,
        frontend_url: str | None = None,
        auth_provider: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        api_base: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_headers: str | None = None,
    ) -> dict[str, Any]:
        if base_url is not None:
            self._config["base_url"] = base_url.rstrip("/")
        if frontend_url is not None:
            self._config["frontend_url"] = frontend_url.rstrip("/")
        if auth_provider is not None:
            self._config["auth_provider"] = auth_provider.lower()
        if timeout_seconds is not None:
            self._config["timeout_seconds"] = max(1.0, float(timeout_seconds))
        write_json(CONFIG_PATH, self._persistable_config())

        env_updates: dict[str, str] = {}
        if auth_provider is not None:
            env_updates["AUTH_PROVIDER"] = auth_provider.lower()
        if api_base is not None:
            env_updates["API_BASE"] = api_base
        if model_name is not None:
            env_updates["MODEL_NAME"] = model_name
        if api_key is not None and api_key.strip():
            env_updates["API_KEY"] = api_key
        if temperature is not None:
            env_updates["TEMPERATURE"] = str(float(temperature))
        if max_tokens is not None:
            env_updates["MAX_TOKENS"] = str(int(max_tokens))
        if extra_headers is not None:
            env_updates["EXTRA_HEADERS"] = extra_headers
        if env_updates:
            self.update_model_env(env_updates)
            self._restart_required = True
        return self.config()

    def model_env_config(self) -> dict[str, Any]:
        values, source = self._read_model_env()
        return {
            "api_base": values.get("API_BASE"),
            "model_name": values.get("MODEL_NAME"),
            "api_key_configured": bool(values.get("API_KEY")),
            "temperature": self._float_or_none(values.get("TEMPERATURE")),
            "max_tokens": self._int_or_none(values.get("MAX_TOKENS")),
            "extra_headers": None,
            "extra_headers_configured": bool(values.get("EXTRA_HEADERS")),
            "env_path": str(AI_MANUS_ENV_PATH),
            "env_exists": AI_MANUS_ENV_PATH.exists(),
            "env_source": source,
            "restart_required": self._restart_required,
        }

    def update_model_env(self, updates: dict[str, str]) -> None:
        AI_MANUS_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        if AI_MANUS_ENV_PATH.exists():
            lines = AI_MANUS_ENV_PATH.read_text(encoding="utf-8").splitlines()
        elif AI_MANUS_ENV_EXAMPLE_PATH.exists():
            lines = AI_MANUS_ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
        else:
            lines = []

        next_lines: list[str] = []
        seen: set[str] = set()
        for line in lines:
            key = self._env_line_key(line)
            if key in updates:
                next_lines.append(f"{key}={self._env_quote(updates[key])}")
                seen.add(key)
            else:
                next_lines.append(line)

        if next_lines and next_lines[-1].strip():
            next_lines.append("")
        for key in AI_MANUS_MODEL_ENV_KEYS:
            if key in updates and key not in seen:
                next_lines.append(f"{key}={self._env_quote(updates[key])}")

        AI_MANUS_ENV_PATH.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")

    def auth_required(self) -> bool:
        return self._config.get("auth_provider") != "none"

    def auth_required_payload(self) -> dict[str, Any]:
        return {
            "status": "auth_required",
            "auth_provider": self._config.get("auth_provider") or "unknown",
            "detail": "ai-manus AUTH_PROVIDER is not none; configure ai-manus with AUTH_PROVIDER=none for HippoDEMO local adapter access.",
        }

    async def status(self) -> ServiceStatus:
        if self.auth_required():
            return ServiceStatus(name="ai-manus", status="auth_required", detail=self.auth_required_payload()["detail"])
        try:
            auth_status = await self._request("GET", "/auth/status", timeout_seconds=2.0)
        except AiManusAuthRequired as exc:
            return ServiceStatus(name="ai-manus", status="auth_required", detail=self._safe_error(exc))
        except Exception as exc:
            return ServiceStatus(name="ai-manus", status="unavailable", detail=self._safe_error(exc))

        remote_auth_provider = self._auth_provider_from_payload(auth_status)
        if remote_auth_provider:
            self._config["auth_provider"] = remote_auth_provider.lower()

        if self.auth_required():
            return ServiceStatus(name="ai-manus", status="auth_required", detail=self.auth_required_payload()["detail"])

        return ServiceStatus(name="ai-manus", status="online", detail=f"api_base_url={self._api_base_url()}")

    async def create_session(self) -> dict[str, Any]:
        self._ensure_no_auth()
        return await self._request("PUT", "/sessions")

    async def list_sessions(self) -> dict[str, Any]:
        self._ensure_no_auth()
        return await self._request("GET", "/sessions")

    async def get_session(self, session_id: str) -> dict[str, Any]:
        self._ensure_no_auth()
        return await self._request("GET", f"/sessions/{session_id}")

    async def vnc_signed_url(self, session_id: str, expire_minutes: int = 15) -> dict[str, Any]:
        return await self.sandbox_access(session_id, expire_minutes)

    async def sandbox_access(self, remote_session_id: str, expire_minutes: int = 15) -> dict[str, Any]:
        self._ensure_no_auth()
        payload = await self._request(
            "POST",
            f"/sessions/{remote_session_id}/vnc/signed-url",
            {"expire_minutes": self._clamp_expire_minutes(expire_minutes)},
        )
        return self._normalize_signed_url_payload(payload, transport="ws")

    async def session_files(self, session_id: str) -> dict[str, Any]:
        self._ensure_no_auth()
        payload = await self._request("GET", f"/sessions/{session_id}/files")
        return self._normalize_file_url_payload(payload)

    async def view_file(self, remote_session_id: str, file_path: str) -> dict[str, Any]:
        self._ensure_no_auth()
        return await self._request("POST", f"/sessions/{remote_session_id}/file", {"file": file_path})

    async def file_signed_url(self, file_id: str, expire_minutes: int = 15) -> dict[str, Any]:
        self._ensure_no_auth()
        payload = await self._request(
            "POST",
            f"/files/{file_id}/signed-url",
            {"expire_minutes": self._clamp_expire_minutes(expire_minutes)},
        )
        return self._normalize_signed_url_payload(payload, transport="http")

    async def stop_session(self, session_id: str) -> dict[str, Any] | None:
        self._ensure_no_auth()
        return await self._request("POST", f"/sessions/{session_id}/stop")

    def start_runtime(self, *, build: bool = False) -> dict[str, Any]:
        return self._spawn_runtime_command("start", self._up_command(build=build))

    def stop_runtime(self) -> dict[str, Any]:
        return self._spawn_runtime_command("stop", self._compose_command("stop", "frontend", "backend"))

    def restart_runtime(self, *, build: bool = False) -> dict[str, Any]:
        command = self._compose_command("up", "-d", "--no-deps", "--force-recreate")
        if build:
            command.append("--build")
        command.append("backend")
        return self._run_runtime_command("restart", command, timeout_seconds=90.0)

    def runtime_logs(self, *, limit: int = 80) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 300))
        if not AI_MANUS_RUNTIME_LOG_PATH.exists():
            return {
                "log_path": str(AI_MANUS_RUNTIME_LOG_PATH),
                "lines": [],
                "detail": "No ai-manus runtime log has been written yet.",
            }
        lines = AI_MANUS_RUNTIME_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        return {
            "log_path": str(AI_MANUS_RUNTIME_LOG_PATH),
            "lines": [self._redact(line) for line in lines[-safe_limit:]],
        }

    async def validate_model_provider(self) -> dict[str, Any]:
        values, source = self._read_model_env()
        api_base = str(values.get("API_BASE") or "").strip()
        model_name = str(values.get("MODEL_NAME") or "").strip()
        api_key = values.get("API_KEY")

        result: dict[str, Any] = {
            "ok": False,
            "status": "failed",
            "api_base": api_base or None,
            "model_name": model_name or None,
            "models_count": 0,
            "model_visible": False,
            "env_source": source,
        }
        if not api_base:
            return {**result, "detail": "API_BASE is not configured."}
        if not model_name:
            return {**result, "detail": "MODEL_NAME is not configured."}

        url = self._join_url(api_base, "/models")
        headers = self._model_provider_headers(values)
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                log_event(
                    logger,
                    "model_provider_validation_started",
                    adapter="ai-manus",
                    path=self._safe_external_url(url),
                )
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            detail = self._redact_model_error(str(exc), api_key=api_key)
            return {
                **result,
                "detail": f"Could not reach model provider /models: {detail}",
                "checked_url": self._safe_external_url(url),
            }

        models = payload.get("data") if isinstance(payload, dict) else None
        model_ids: list[str] = []
        if isinstance(models, list):
            for item in models:
                if isinstance(item, dict) and item.get("id"):
                    model_ids.append(str(item["id"]))
        model_visible = model_name in model_ids
        ok = bool(model_ids) and model_visible
        detail = (
            f"{len(model_ids)} model(s) visible; {model_name} is available."
            if ok
            else f"{len(model_ids)} model(s) visible; {model_name} was not found."
        )
        return {
            **result,
            "ok": ok,
            "status": "ok" if ok else "model_not_found",
            "detail": detail,
            "models_count": len(model_ids),
            "model_visible": model_visible,
            "checked_url": self._safe_external_url(url),
        }

    async def stream_chat(
        self,
        *,
        session_id: str,
        message: str | None,
        timestamp: int | None,
        event_id: str | None,
        attachments: list[dict[str, Any]] | None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        self._ensure_no_auth()
        payload = {
            "message": message,
            "timestamp": timestamp,
            "event_id": event_id,
            "attachments": attachments,
        }
        timeout = httpx.Timeout(float(self._config["timeout_seconds"]), read=None)
        async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
            log_event(
                logger,
                "adapter_sse_started",
                adapter="ai-manus",
                method="POST",
                path=f"/sessions/{session_id}/chat",
                message_chars=len(message or ""),
                attachments_count=len(attachments or []),
            )
            event_count = 0
            async with client.stream(
                "POST",
                self._url(f"/sessions/{session_id}/chat"),
                json=payload,
            ) as response:
                response.raise_for_status()
                buffer: dict[str, str] = {}
                async for line in response.aiter_lines():
                    if line == "":
                        event = self._sse_from_buffer(buffer)
                        buffer = {}
                        if event:
                            event_count += 1
                            yield event
                        continue
                    if line.startswith(":"):
                        continue
                    if ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    buffer[key] = f"{buffer.get(key, '')}\n{value.lstrip()}".strip()
                event = self._sse_from_buffer(buffer)
                if event:
                    event_count += 1
                    yield event
            log_event(
                logger,
                "adapter_sse_completed",
                adapter="ai-manus",
                path=f"/sessions/{session_id}/chat",
                event_count=event_count,
            )

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        timeout = float(timeout_seconds if timeout_seconds is not None else self._config["timeout_seconds"])
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
                log_event(
                    logger,
                    "adapter_http_started",
                    adapter="ai-manus",
                    method=method,
                    path=self._safe_path(path),
                    timeout_seconds=timeout,
                    request_keys=sorted(json_body.keys()) if isinstance(json_body, dict) else [],
                )
                response = await client.request(method, self._url(path), json=json_body)
                response.raise_for_status()
                log_event(
                    logger,
                    "adapter_http_completed",
                    adapter="ai-manus",
                    method=method,
                    path=self._safe_path(path),
                    status_code=response.status_code,
                    response_bytes=len(response.content or b""),
                )
                if not response.content:
                    return None
                return self._unwrap(response.json())
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response else "unknown"
            log_event(
                logger,
                "adapter_http_failed",
                adapter="ai-manus",
                method=method,
                path=self._safe_path(path),
                status_code=status_code,
            )
            if status_code in {401, 403}:
                raise AiManusAuthRequired(
                    f"ai-manus backend rejected Orchestrator access with HTTP {status_code} for {self._safe_path(path)}; "
                    "configure ai-manus AUTH_PROVIDER=none for local adapter access, or set a valid HIPPODEMO_AI_MANUS_API_KEY."
                ) from exc
            raise AiManusAPIError(f"ai-manus HTTP {status_code} for {self._safe_path(path)}") from exc
        except httpx.RequestError as exc:
            log_event(
                logger,
                "adapter_http_failed",
                adapter="ai-manus",
                method=method,
                path=self._safe_path(path),
                error_type=exc.__class__.__name__,
            )
            raise AiManusAPIError(f"ai-manus backend unavailable at {self._safe_origin()}: {exc.__class__.__name__}") from exc

    def _unwrap(self, payload: Any) -> Any:
        if not isinstance(payload, dict) or not {"code", "msg", "data"}.issubset(payload.keys()):
            return payload
        if payload.get("code") not in {0, "0"}:
            raise AiManusAPIError(str(payload.get("msg") or "ai-manus API error"))
        return payload.get("data")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        api_key = self._config.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _model_provider_headers(self, values: dict[str, str]) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        api_key = values.get("API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        extra_headers = str(values.get("EXTRA_HEADERS") or "").strip()
        if extra_headers:
            try:
                parsed = json.loads(extra_headers)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    if key and value is not None:
                        headers[str(key)] = str(value)
        return headers

    def _url(self, path: str) -> str:
        return f"{self._api_base_url()}{path}"

    def _join_url(self, base_url: str, path: str) -> str:
        base = str(base_url or "").rstrip("/")
        suffix = path if path.startswith("/") else f"/{path}"
        return f"{base}{suffix}"

    def _api_base_url(self) -> str:
        base_url = str(self._config["base_url"]).rstrip("/")
        if base_url.endswith("/api/v1"):
            return base_url
        return f"{base_url}/api/v1"

    def _frontend_base_url(self) -> str:
        return str(self._config["frontend_url"]).rstrip("/")

    def _frontend_ws_base_url(self) -> str:
        parsed = urlparse(self._frontend_base_url())
        if parsed.scheme == "https":
            scheme = "wss"
        elif parsed.scheme == "http":
            scheme = "ws"
        else:
            scheme = parsed.scheme or "ws"
        return urlunparse((scheme, parsed.netloc, "", "", "", "")).rstrip("/")

    def _ensure_no_auth(self) -> None:
        if self.auth_required():
            raise AiManusAuthRequired(self.auth_required_payload()["detail"])

    def _up_command(self, *, build: bool) -> list[str]:
        command = self._compose_command("up", "-d", "--no-deps")
        if build:
            command.append("--build")
        command.extend(["mongodb", "redis", "backend", "frontend"])
        return command

    def _compose_command(self, *args: str) -> list[str]:
        docker = shutil.which("docker") or "/usr/local/bin/docker"
        return [docker, "compose", "-f", str(AI_MANUS_COMPOSE_PATH), *args]

    def _dev_script_path(self) -> Path:
        return AI_MANUS_PROJECT_DIR / "dev.sh"

    def _spawn_runtime_command(self, action: str, command: list[str]) -> dict[str, Any]:
        unavailable = self._runtime_unavailable(action)
        if unavailable is not None:
            return unavailable

        if action in {"start", "restart"}:
            self._ensure_runtime_env()

        AI_MANUS_RUNTIME_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            log_event(
                logger,
                "adapter_subprocess_started",
                adapter="ai-manus",
                action=action,
                command=self._display_command(command),
                cwd=str(AI_MANUS_PROJECT_DIR),
            )
            with AI_MANUS_RUNTIME_LOG_PATH.open("a", encoding="utf-8") as log:
                log.write(f"\n$ {' '.join(self._display_command(command))}\n")
                process = subprocess.Popen(
                    command,
                    cwd=str(AI_MANUS_PROJECT_DIR),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except OSError as exc:
            log_event(
                logger,
                "adapter_subprocess_failed",
                adapter="ai-manus",
                action=action,
                error_type=exc.__class__.__name__,
            )
            return {
                "action": action,
                "status": "unavailable",
                "detail": f"Could not dispatch ai-manus runtime command: {exc}",
                "command": self._display_command(command),
                "cwd": str(AI_MANUS_PROJECT_DIR),
                "log_path": str(AI_MANUS_RUNTIME_LOG_PATH),
            }
        detail = {
            "start": "ai-manus startup command dispatched.",
            "restart": "ai-manus recreate command dispatched.",
            "stop": "ai-manus stop command dispatched.",
        }.get(action, "ai-manus runtime command dispatched.")
        return {
            "action": action,
            "status": "running",
            "detail": detail,
            "pid": process.pid,
            "command": self._display_command(command),
            "cwd": str(AI_MANUS_PROJECT_DIR),
            "log_path": str(AI_MANUS_RUNTIME_LOG_PATH),
        }

    def _run_runtime_command(self, action: str, command: list[str], *, timeout_seconds: float) -> dict[str, Any]:
        unavailable = self._runtime_unavailable(action)
        if unavailable is not None:
            return unavailable

        if action in {"start", "restart"}:
            self._ensure_runtime_env()

        AI_MANUS_RUNTIME_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        display_command = self._display_command(command)
        try:
            log_event(
                logger,
                "adapter_subprocess_started",
                adapter="ai-manus",
                action=action,
                command=display_command,
                cwd=str(AI_MANUS_PROJECT_DIR),
                wait=True,
                timeout_seconds=timeout_seconds,
            )
            with AI_MANUS_RUNTIME_LOG_PATH.open("a", encoding="utf-8") as log:
                log.write(f"\n$ {' '.join(display_command)}\n")
                completed = subprocess.run(
                    command,
                    cwd=str(AI_MANUS_PROJECT_DIR),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=timeout_seconds,
                    check=False,
                )
        except subprocess.TimeoutExpired as exc:
            log_event(
                logger,
                "adapter_subprocess_failed",
                adapter="ai-manus",
                action=action,
                error_type=exc.__class__.__name__,
            )
            return {
                "action": action,
                "status": "timeout",
                "detail": f"ai-manus runtime command timed out after {timeout_seconds:.0f}s.",
                "command": display_command,
                "cwd": str(AI_MANUS_PROJECT_DIR),
                "log_path": str(AI_MANUS_RUNTIME_LOG_PATH),
            }
        except OSError as exc:
            log_event(
                logger,
                "adapter_subprocess_failed",
                adapter="ai-manus",
                action=action,
                error_type=exc.__class__.__name__,
            )
            return {
                "action": action,
                "status": "unavailable",
                "detail": f"Could not run ai-manus runtime command: {exc}",
                "command": display_command,
                "cwd": str(AI_MANUS_PROJECT_DIR),
                "log_path": str(AI_MANUS_RUNTIME_LOG_PATH),
            }

        ok = completed.returncode == 0
        if ok and action in {"start", "restart"}:
            self._restart_required = False
        log_event(
            logger,
            "adapter_subprocess_completed",
            adapter="ai-manus",
            action=action,
            returncode=completed.returncode,
        )
        return {
            "action": action,
            "status": "completed" if ok else "failed",
            "detail": "ai-manus backend container recreated." if ok else f"ai-manus runtime command failed with exit code {completed.returncode}.",
            "returncode": completed.returncode,
            "command": display_command,
            "cwd": str(AI_MANUS_PROJECT_DIR),
            "log_path": str(AI_MANUS_RUNTIME_LOG_PATH),
        }

    def _runtime_unavailable(self, action: str) -> dict[str, Any] | None:
        if not AI_MANUS_PROJECT_DIR.exists():
            return {
                "action": action,
                "status": "unavailable",
                "detail": f"ai-manus project not found at {AI_MANUS_PROJECT_DIR}",
            }
        if not AI_MANUS_COMPOSE_PATH.exists():
            return {
                "action": action,
                "status": "unavailable",
                "detail": f"ai-manus compose file not found at {AI_MANUS_COMPOSE_PATH}",
            }
        return None

    def _ensure_runtime_env(self) -> None:
        if AI_MANUS_ENV_PATH.exists():
            return
        self.update_model_env({"AUTH_PROVIDER": self._config.get("auth_provider") or "none"})
        self._restart_required = True

    def _display_command(self, command: list[str]) -> list[str]:
        return [Path(part).name if part == str(self._dev_script_path()) else part for part in command]

    def _persistable_config(self) -> dict[str, Any]:
        return {
            "base_url": self._config["base_url"],
            "frontend_url": self._config["frontend_url"],
            "auth_provider": self._config["auth_provider"],
            "timeout_seconds": self._config["timeout_seconds"],
        }

    def _clamp_expire_minutes(self, value: int | None) -> int:
        try:
            minutes = int(value if value is not None else 15)
        except (TypeError, ValueError):
            minutes = 15
        return max(1, min(minutes, 15))

    def _normalize_signed_url_payload(self, payload: Any, *, transport: str) -> Any:
        if not isinstance(payload, dict):
            return payload
        normalized = dict(payload)
        signed_url = normalized.get("signed_url")
        if isinstance(signed_url, str) and signed_url:
            normalized["signed_url"] = self._absolute_signed_url(signed_url, transport=transport)
        return normalized

    def _normalize_file_url_payload(self, payload: Any) -> Any:
        if isinstance(payload, list):
            return [self._normalize_file_url_payload(item) for item in payload]
        if not isinstance(payload, dict):
            return payload
        normalized = dict(payload)
        file_url = normalized.get("file_url")
        if isinstance(file_url, str) and file_url:
            normalized["file_url"] = self._absolute_signed_url(file_url, transport="http")
        return normalized

    def _absolute_signed_url(self, signed_url: str, *, transport: str) -> str:
        parsed = urlparse(signed_url)
        if parsed.scheme and parsed.netloc:
            if transport == "ws" and parsed.scheme in {"http", "https"}:
                scheme = "wss" if parsed.scheme == "https" else "ws"
                return urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
            return signed_url

        if parsed.netloc:
            base = self._frontend_ws_base_url() if transport == "ws" else self._frontend_base_url()
            base_scheme = urlparse(base).scheme
            scheme = "wss" if transport == "ws" and base_scheme in {"https", "wss"} else ("ws" if transport == "ws" else base_scheme)
            return urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

        path = signed_url if signed_url.startswith("/") else f"/{signed_url}"
        base = self._frontend_ws_base_url() if transport == "ws" else self._frontend_base_url()
        return f"{base}{path}"

    def _read_model_env(self) -> tuple[dict[str, str], str]:
        path = AI_MANUS_ENV_PATH if AI_MANUS_ENV_PATH.exists() else AI_MANUS_ENV_EXAMPLE_PATH
        source = "env" if AI_MANUS_ENV_PATH.exists() else "example"
        values: dict[str, str] = {}
        if not path.exists():
            return values, "missing"
        for line in path.read_text(encoding="utf-8").splitlines():
            key = self._env_line_key(line)
            if key not in AI_MANUS_MODEL_ENV_KEYS:
                continue
            _, raw_value = line.split("=", 1)
            values[key] = self._env_unquote(raw_value.strip())
        return values, source

    def _redact(self, value: str) -> str:
        redacted = value
        for key in ("API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AUTH_TOKEN", "TOKEN"):
            marker = f"{key}="
            if marker in redacted:
                prefix, _, suffix = redacted.partition(marker)
                if suffix:
                    redacted = f"{prefix}{marker}<redacted>"
        return redacted

    def _env_line_key(self, line: str) -> str | None:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            return None
        key, _ = stripped.split("=", 1)
        key = key.strip()
        return key if key in AI_MANUS_MODEL_ENV_KEYS else None

    def _env_unquote(self, value: str) -> str:
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            if value[0] == '"':
                try:
                    decoded = json.loads(value)
                    return str(decoded)
                except json.JSONDecodeError:
                    pass
            return value[1:-1]
        return value

    def _env_quote(self, value: str) -> str:
        value = str(value).strip()
        if "\n" in value:
            value = value.replace("\n", "\\n")
        if any(char.isspace() for char in value) or value.startswith("{"):
            return json.dumps(value, ensure_ascii=False)
        return value

    def _float_or_none(self, value: str | None) -> float | None:
        try:
            return float(value) if value not in {None, ""} else None
        except (TypeError, ValueError):
            return None

    def _int_or_none(self, value: str | None) -> int | None:
        try:
            return int(value) if value not in {None, ""} else None
        except (TypeError, ValueError):
            return None

    def _auth_provider_from_payload(self, payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get("auth_provider") or payload.get("authProvider") or payload.get("provider")
        return str(value).lower() if value else None

    def _safe_origin(self) -> str:
        parsed = urlparse(self._config["base_url"])
        if not parsed.scheme or not parsed.netloc:
            return self._config["base_url"]
        return f"{parsed.scheme}://{parsed.netloc}"

    def _safe_path(self, path: str) -> str:
        return path if path.startswith("/") else f"/{path}"

    def _safe_error(self, exc: Exception) -> str:
        message = str(exc)
        api_key = self._config.get("api_key")
        if api_key:
            message = message.replace(str(api_key), "[redacted]")
        return message

    def _safe_external_url(self, value: str) -> str:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            return value
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    def _redact_model_error(self, message: str, *, api_key: str | None) -> str:
        text = message
        if api_key:
            text = text.replace(api_key, "[redacted]")
        return self._redact(text)

    def _sse_from_buffer(self, buffer: dict[str, str]) -> dict[str, Any] | None:
        if not buffer:
            return None
        data: Any = None
        raw_data = buffer.get("data")
        if raw_data:
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                data = {"text": raw_data}
        return {
            "id": buffer.get("id"),
            "event": buffer.get("event") or "message",
            "data": data,
        }


ai_manus_adapter = AiManusAdapter()
