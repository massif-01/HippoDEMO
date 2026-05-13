from __future__ import annotations

import asyncio
import contextlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..models import ServiceStatus, now_iso


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PROJECT_DIR = Path(__file__).resolve().parents[2]
LOCAL_BIN = PROJECT_DIR / "OpenChronicle" / ".venv" / "bin" / "openchronicle"


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

    def executable(self) -> str | None:
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

openchronicle_adapter = OpenChronicleAdapter()
