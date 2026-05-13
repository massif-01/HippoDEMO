from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import ServiceStatus, now_iso


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PROJECT_DIR = Path(__file__).resolve().parents[2]
RUNTIME_BIN = PROJECT_DIR / ".runtime" / "python" / "bin" / "openchronicle"
LOCAL_BIN = PROJECT_DIR / "OpenChronicle" / ".venv" / "bin" / "openchronicle"
MODEL_STAGES = {"default", "timeline", "reducer", "classifier", "compact"}


@dataclass
class OpenChronicleCommandResult:
    action: str
    ok: bool
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    executable: str | None = None


class OpenChronicleAdapter:
    def __init__(self) -> None:
        self.local_bin = LOCAL_BIN

    def config_path(self) -> Path:
        root = os.environ.get("OPENCHRONICLE_ROOT")
        if root:
            return Path(root).expanduser().resolve() / "config.toml"
        return Path.home() / ".openchronicle" / "config.toml"

    def model_config(self, stage: str = "default") -> dict[str, Any]:
        stage = self._normalize_stage(stage)
        path = self.config_path()
        raw = self._read_config(path)
        models = raw.get("models") if isinstance(raw.get("models"), dict) else {}
        stage_payload = self._model_payload(stage, models.get(stage) if isinstance(models, dict) else {})
        stages = {
            name: self._model_payload(name, models.get(name) if isinstance(models, dict) else {})
            for name in sorted(MODEL_STAGES)
        }
        return {
            **stage_payload,
            "config_path": str(path),
            "config_exists": path.exists(),
            "stages": stages,
            "restart_required": False,
        }

    def update_model_config(
        self,
        *,
        stage: str = "default",
        model: str | None = None,
        base_url: str | None = None,
        api_key_env: str | None = None,
        api_key: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        stage = self._normalize_stage(stage)
        if max_tokens is not None and max_tokens <= 0:
            raise ValueError("max_tokens must be greater than 0")

        path = self.config_path()
        raw = self._read_config(path)
        models = raw.setdefault("models", {})
        if not isinstance(models, dict):
            models = {}
            raw["models"] = models
        section = models.setdefault(stage, {})
        if not isinstance(section, dict):
            section = {}
            models[stage] = section

        for key, value in {
            "model": model,
            "base_url": base_url,
            "api_key_env": api_key_env,
            "max_tokens": max_tokens,
        }.items():
            if value is not None:
                section[key] = value
        if api_key is not None:
            section["api_key"] = api_key

        self._write_config(path, raw)
        payload = self.model_config(stage)
        payload["restart_required"] = True
        return payload

    def executable(self) -> str | None:
        if RUNTIME_BIN.exists():
            return str(RUNTIME_BIN)
        if self.local_bin.exists():
            return str(self.local_bin)
        return shutil.which("openchronicle")

    async def status(self) -> ServiceStatus:
        executable = self.executable()
        if not executable:
            return ServiceStatus(
                name="OpenChronicle",
                status="error",
                detail="openchronicle executable not found",
            )
        result = await self._run("status", ["status"], timeout=20.0)
        return self._status_from_output(result)

    async def start(self) -> ServiceStatus:
        return await self._run_and_refresh("start", ["start"], timeout=10.0)

    async def stop(self) -> ServiceStatus:
        return await self._run_and_refresh("stop", ["stop"], timeout=10.0)

    async def pause(self) -> ServiceStatus:
        return await self._run_and_refresh("pause", ["pause"], timeout=8.0)

    async def resume(self) -> ServiceStatus:
        return await self._run_and_refresh("resume", ["resume"], timeout=8.0)

    async def capture_once(self) -> ServiceStatus:
        return await self._run_and_refresh("capture-once", ["capture-once"], timeout=35.0)

    async def rebuild_captures_index(self) -> ServiceStatus:
        return await self._run_and_refresh(
            "rebuild-captures-index",
            ["rebuild-captures-index"],
            timeout=60.0,
        )

    async def timeline_tick(self) -> ServiceStatus:
        return await self._run_and_refresh("timeline-tick", ["timeline", "tick"], timeout=60.0)

    async def _run_and_refresh(self, action: str, args: list[str], *, timeout: float) -> ServiceStatus:
        result = await self._run(action, args, timeout=timeout)
        if not result.ok and result.returncode is None:
            return self._service_from_result(result, "error")

        status = await self.status()
        if action == "stop" and result.ok:
            for _ in range(8):
                if status.status != "online":
                    break
                await asyncio.sleep(0.5)
                status = await self.status()
        command_detail = self._result_detail(result)
        if command_detail:
            status.detail = f"{status.detail}; {command_detail}" if status.detail else command_detail
        status.updated_at = now_iso()
        return status

    async def _run(self, action: str, args: list[str], *, timeout: float) -> OpenChronicleCommandResult:
        executable = self.executable()
        if not executable:
            return OpenChronicleCommandResult(
                action=action,
                ok=False,
                returncode=None,
                error="openchronicle executable not found",
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                executable,
                *args,
                cwd=str(PROJECT_DIR / "OpenChronicle") if (PROJECT_DIR / "OpenChronicle").exists() else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            stdout = self._summarize(stdout_bytes.decode(errors="replace"))
            stderr = self._summarize(stderr_bytes.decode(errors="replace"))
            return OpenChronicleCommandResult(
                action=action,
                ok=proc.returncode == 0,
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                executable=executable,
            )
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
            return OpenChronicleCommandResult(
                action=action,
                ok=False,
                returncode=None,
                error=f"timed out after {timeout:.0f}s",
                executable=executable,
            )
        except OSError as exc:
            return OpenChronicleCommandResult(
                action=action,
                ok=False,
                returncode=None,
                error=str(exc),
                executable=executable,
            )

    def _status_from_output(self, result: OpenChronicleCommandResult) -> ServiceStatus:
        if not result.ok:
            return self._service_from_result(result, "error")

        text = self._clean(result.stdout)
        daemon = self._status_value(text, "Daemon")
        health = self._status_value(text, "Health")
        capture = self._status_value(text, "Capture")
        last_capture = self._status_value(text, "Last Capture")
        buffer = self._status_value(text, "Buffer")
        model_error = "AuthenticationError" if "AuthenticationError" in text else None

        daemon_l = daemon.lower()
        health_l = health.lower()
        if "healthy" in health_l or "running" in health_l or "running" in daemon_l:
            status = "online"
        elif "stopped" in daemon_l or "stopped" in health_l:
            status = "stopped"
        else:
            status = "available"

        parts = []
        if daemon:
            parts.append(f"daemon={daemon}")
        if health:
            parts.append(f"health={health}")
        if capture:
            parts.append(f"capture={capture}")
        if last_capture:
            parts.append(f"last_capture={last_capture}")
        if buffer:
            parts.append(f"buffer={buffer}")
        if model_error:
            parts.append(f"model={model_error}")
        detail = "; ".join(parts) or "openchronicle status available"
        return ServiceStatus(name="OpenChronicle", status=status, detail=detail)

    def _service_from_result(self, result: OpenChronicleCommandResult, status: str) -> ServiceStatus:
        detail = self._result_detail(result) or "openchronicle command failed"
        return ServiceStatus(name="OpenChronicle", status=status, detail=detail)

    def _result_detail(self, result: OpenChronicleCommandResult) -> str:
        parts = [f"{result.action}"]
        if result.returncode is not None:
            parts.append(f"rc={result.returncode}")
        if result.error:
            parts.append(result.error)
        if result.stdout:
            parts.append(f"stdout={self._inline(result.stdout)}")
        if result.stderr:
            parts.append(f"stderr={self._inline(result.stderr)}")
        return " ".join(parts)

    def _summarize(self, text: str, *, max_chars: int = 1200) -> str:
        clean = self._clean(text)
        lines = [line.strip() for line in clean.splitlines() if line.strip()]
        summary = "\n".join(lines[:16])
        if len(summary) > max_chars:
            summary = summary[: max_chars - 1].rstrip() + "..."
        return summary

    def _inline(self, text: str) -> str:
        return " | ".join(line.strip() for line in text.splitlines() if line.strip())

    def _clean(self, text: str) -> str:
        return ANSI_RE.sub("", text).replace("\r", "")

    def _status_value(self, text: str, key: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(key):
                return stripped[len(key):].strip()
        return ""

    def _normalize_stage(self, stage: str | None) -> str:
        value = (stage or "default").strip().lower()
        if value not in MODEL_STAGES:
            raise ValueError(f"unsupported OpenChronicle model stage: {value}")
        return value

    def _read_config(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {
                "models": {
                    "default": {
                        "model": "gpt-5.4-nano",
                        "api_key_env": "OPENAI_API_KEY",
                    }
                }
            }
        try:
            return tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_config(self, path: Path, raw: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._dump_toml(raw), encoding="utf-8")

    def _model_payload(self, stage: str, value: Any) -> dict[str, Any]:
        section = value if isinstance(value, dict) else {}
        api_key = str(section.get("api_key") or "")
        api_key_env = str(section.get("api_key_env") or "OPENAI_API_KEY")
        env_key = os.environ.get(api_key_env) if api_key_env else None
        return {
            "stage": stage,
            "model": section.get("model") or ("gpt-5.4-nano" if stage == "default" else None),
            "base_url": section.get("base_url") or "",
            "api_key_env": api_key_env,
            "api_key_configured": bool(api_key or env_key),
            "max_tokens": section.get("max_tokens"),
        }

    def _dump_toml(self, raw: dict[str, Any]) -> str:
        lines: list[str] = []
        root_scalars = {key: value for key, value in raw.items() if not isinstance(value, dict)}
        for key, value in root_scalars.items():
            lines.append(f"{key} = {self._toml_value(value)}")
        if root_scalars:
            lines.append("")

        for section_name, section in raw.items():
            if not isinstance(section, dict):
                continue
            nested = {key: value for key, value in section.items() if isinstance(value, dict)}
            scalars = {key: value for key, value in section.items() if not isinstance(value, dict)}
            if scalars:
                lines.append(f"[{section_name}]")
                for key, value in scalars.items():
                    if value is not None:
                        lines.append(f"{key} = {self._toml_value(value)}")
                lines.append("")
            for nested_name, nested_section in nested.items():
                lines.append(f"[{section_name}.{nested_name}]")
                for key, value in nested_section.items():
                    if value is not None:
                        lines.append(f"{key} = {self._toml_value(value)}")
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _toml_value(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return json.dumps(str(value), ensure_ascii=False)

openchronicle_adapter = OpenChronicleAdapter()
