from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..logging_config import log_event
from ..models import CuaTargetSurface, ServiceStatus


PROJECT_DIR = Path(__file__).resolve().parents[2]
CUA_DRIVER_DIR = PROJECT_DIR / "cua" / "libs" / "cua-driver"
RUNTIME_DIR = PROJECT_DIR / ".runtime"
DEFAULT_TIMEOUT_SECONDS = 20.0
TEXTEDIT_BUNDLE_ID = "com.apple.TextEdit"
DEFAULT_SAFE_EDITOR_BUNDLES = {
    TEXTEDIT_BUNDLE_ID: "textedit",
    "com.coteditor.CotEditor": "low_risk_editor",
    "com.apple.Notes": "notes_editor",
}
DANGEROUS_ACTIVE_BUNDLES = {
    "com.apple.Terminal",
    "com.googlecode.iterm2",
    "com.mitchellh.ghostty",
    "dev.warp.Warp-Stable",
}
BLOCKED_TARGET_BUNDLES = DANGEROUS_ACTIVE_BUNDLES | {
    "com.apple.mail",
    "com.apple.MobileSMS",
    "com.apple.Safari",
    "com.google.Chrome",
    "com.microsoft.Outlook",
    "com.openai.chat",
    "com.openai.codex",
    "com.tencent.xinWeChat",
    "com.tencent.WeWorkMac",
}
SELF_APP_NAMES = {"HippoJarvis", "HippoDEMO", "Codex", "ChatGPT"}
EDITABLE_AX_ROLES = ("AXTextArea", "AXTextField", "AXComboBox")
EDITABLE_LINE_RE = re.compile(r"\[(?P<index>\d+)\]\s+(?P<role>AXTextArea|AXTextField|AXComboBox)\b")
logger = logging.getLogger("orchestrator.adapters.cua_driver")


@dataclass
class CuaInsertResult:
    ok: bool
    detail: str
    target_pid: int | None = None
    target_app: str | None = None
    target_bundle_id: str | None = None
    text_chars: int = 0


class CuaDriverAdapter:
    def executable(self) -> str | None:
        override = os.environ.get("HIPPODEMO_CUA_DRIVER_BINARY")
        if override:
            path = Path(override).expanduser()
            if path.exists() and path.is_file():
                return str(path)
            return override

        candidates = [
            CUA_DRIVER_DIR / ".build" / "CuaDriver.app" / "Contents" / "MacOS" / "cua-driver",
            CUA_DRIVER_DIR / ".build" / "release" / "cua-driver",
            CUA_DRIVER_DIR / ".build" / "debug" / "cua-driver",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return str(candidate)
        return shutil.which("cua-driver")

    async def status(self) -> ServiceStatus:
        executable = self.executable()
        if not executable:
            return ServiceStatus(
                name="cua-driver",
                status="unavailable",
                detail="cua-driver binary not found; build cua/libs/cua-driver or set HIPPODEMO_CUA_DRIVER_BINARY",
            )

        daemon_ok, daemon_detail = await self._daemon_status(executable)
        if daemon_ok:
            return ServiceStatus(
                name="cua-driver",
                status="online",
                detail=f"daemon running; binary={executable}; {daemon_detail}",
            )

        apps_result = await self._call_tool(executable, "list_apps", {}, timeout=10.0)
        if apps_result["ok"]:
            return ServiceStatus(
                name="cua-driver",
                status="available",
                detail=f"binary={executable}; daemon not running; insertion waits for cua-driver serve",
            )

        return ServiceStatus(
            name="cua-driver",
            status="error",
            detail=f"binary={executable}; list_apps failed: {apps_result['detail']}",
        )

    async def start_daemon(self) -> ServiceStatus:
        executable = self.executable()
        if not executable:
            return ServiceStatus(
                name="cua-driver",
                status="unavailable",
                detail="cua-driver binary not found; build cua/libs/cua-driver or set HIPPODEMO_CUA_DRIVER_BINARY",
            )

        daemon_ok, daemon_detail = await self._daemon_status(executable)
        if daemon_ok:
            return ServiceStatus(
                name="cua-driver",
                status="online",
                detail=f"daemon already running; binary={executable}; {daemon_detail}",
            )

        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        log_path = RUNTIME_DIR / "cua-driver.log"
        process: subprocess.Popen[bytes] | None = None
        launch_detail = ""
        bundle_path = self._bundle_path_for_executable(executable)
        if bundle_path:
            launch_result = await self._launch_bundle_daemon(bundle_path)
            launch_detail = launch_result["detail"]
            if not launch_result["ok"]:
                return ServiceStatus(
                    name="cua-driver",
                    status="error",
                    detail=f"LaunchServices start failed: {launch_detail}",
                )
        else:
            try:
                process = self._spawn_direct_daemon(executable, log_path)
            except Exception as exc:
                return ServiceStatus(name="cua-driver", status="error", detail=f"start failed: {exc}")
            launch_detail = f"direct launcher_pid={process.pid}; log={log_path}"

        for _ in range(50):
            await asyncio.sleep(0.2)
            daemon_ok, daemon_detail = await self._daemon_status(executable)
            if daemon_ok:
                return ServiceStatus(
                    name="cua-driver",
                    status="online",
                    detail=(
                        f"daemon started; {launch_detail}; binary={executable}; "
                        f"{daemon_detail}"
                    ),
                )
            if process is not None and process.poll() is not None:
                return ServiceStatus(
                    name="cua-driver",
                    status="error",
                    detail=f"daemon exited during start; code={process.returncode}; log={log_path}; {self._tail_log(log_path)}",
                )

        return ServiceStatus(
            name="cua-driver",
            status="error",
            detail=f"daemon start timed out; {launch_detail}; log={log_path}; {self._tail_log(log_path)}",
        )

    async def stop_daemon(self) -> ServiceStatus:
        executable = self.executable()
        if not executable:
            return ServiceStatus(
                name="cua-driver",
                status="unavailable",
                detail="cua-driver binary not found; build cua/libs/cua-driver or set HIPPODEMO_CUA_DRIVER_BINARY",
            )

        stop_result = await self._run_management(executable, "stop", timeout=10.0)
        daemon_detail = ""
        for _ in range(30):
            daemon_ok, daemon_detail = await self._daemon_status(executable)
            if not daemon_ok:
                detail = stop_result["detail"] or daemon_detail or "daemon stopped"
                return ServiceStatus(
                    name="cua-driver",
                    status="available",
                    detail=f"daemon stopped; binary={executable}; {detail}",
                )
            await asyncio.sleep(0.1)
        return ServiceStatus(
            name="cua-driver",
            status="error",
            detail=f"stop requested but daemon is still running; {daemon_detail}",
        )

    async def restart_daemon(self) -> ServiceStatus:
        await self.stop_daemon()
        await asyncio.sleep(0.3)
        return await self.start_daemon()

    async def target_surface(self) -> CuaTargetSurface:
        executable = self.executable()
        if not executable:
            return CuaTargetSurface(
                status="unavailable",
                reason="cua-driver binary not found; build cua/libs/cua-driver or set HIPPODEMO_CUA_DRIVER_BINARY",
            )

        daemon_ok, daemon_detail = await self._daemon_status(executable)
        if not daemon_ok:
            return CuaTargetSurface(
                status="unavailable",
                reason="cua-driver daemon is not running; start CuaDriver.app or cua-driver serve before insertion",
                detail=daemon_detail,
            )

        apps_result = await self._call_tool(executable, "list_apps", {}, timeout=10.0)
        if not apps_result["ok"]:
            return CuaTargetSurface(status="error", reason=f"list_apps failed: {apps_result['detail']}")

        target, source = self._resolve_target_app(apps_result.get("payload"))
        if not target:
            return CuaTargetSurface(
                status="unsafe",
                reason=(
                    "No safe target app resolved; focus TextEdit, CotEditor, Notes, or configure a validated "
                    "low-risk target with HIPPODEMO_CUA_SAFE_BUNDLE_IDS"
                ),
            )

        pid = int(target["pid"])
        app_name = str(target.get("name") or "")
        bundle_id = str(target.get("bundle_id") or "")
        base = {
            "app_name": app_name,
            "bundle_id": bundle_id,
            "pid": pid,
            "detail": f"daemon={daemon_detail}; source={source}",
        }

        if app_name in SELF_APP_NAMES or bundle_id in BLOCKED_TARGET_BUNDLES:
            return CuaTargetSurface(
                **base,
                status="unsafe",
                mode="blocked_app",
                reason=f"{app_name or bundle_id} is blocked for CUA insert v0.",
            )

        windows_result = await self._call_tool(executable, "list_windows", {"pid": pid}, timeout=10.0)
        if not windows_result["ok"]:
            return CuaTargetSurface(**base, status="unsafe", reason=f"list_windows failed: {windows_result['detail']}")
        window = self._select_target_window(windows_result.get("payload"))
        if not window:
            return CuaTargetSurface(**base, status="unsafe", reason="No on-screen current-space target window found.")

        window_id = int(window["window_id"])
        window_title = str(window.get("title") or "")
        state_result = await self._call_tool(
            executable,
            "get_window_state",
            {"pid": pid, "window_id": window_id, "query": "AXText"},
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        window_base = {**base, "window_id": window_id, "window_title": window_title}
        if not state_result["ok"]:
            return CuaTargetSurface(
                **window_base,
                status="unsafe",
                reason=f"get_window_state failed: {state_result['detail']}",
            )

        editable = self._first_editable_element(state_result.get("payload"))
        if not editable:
            return CuaTargetSurface(
                **window_base,
                status="unsafe",
                mode="no_editable_text",
                reason="The target window has no editable AX text field in the current snapshot.",
            )

        element_index, element_role = editable
        safe_ids = self._safe_bundle_ids()
        if bundle_id in safe_ids:
            mode = DEFAULT_SAFE_EDITOR_BUNDLES.get(bundle_id, "allowlisted_editor")
            reason = self._safe_reason(app_name=app_name, bundle_id=bundle_id, mode=mode)
            return CuaTargetSurface(
                **window_base,
                safe=True,
                status="safe",
                mode=mode,
                reason=reason,
                element_index=element_index,
                element_role=element_role,
            )
        if self._allow_active_editable_target():
            return CuaTargetSurface(
                **window_base,
                safe=True,
                status="safe",
                mode="current_focused_text",
                reason="Active editable text surface is ready; insertion still targets the focused element and requires user confirmation.",
                element_index=None,
                element_role=element_role,
            )

        return CuaTargetSurface(
            **window_base,
            status="unsafe",
            mode="not_allowlisted",
            reason=(
                f"{app_name or bundle_id} has editable text, but it is not in the v0 safe allowlist. "
                "Use TextEdit first, or explicitly add a validated bundle id."
            ),
            element_index=element_index,
            element_role=element_role,
        )

    async def insert_text(self, text: str, surface_hint: CuaTargetSurface | None = None) -> CuaInsertResult:
        executable = self.executable()
        if not executable:
            return CuaInsertResult(
                ok=False,
                detail="cua-driver binary not found; build cua/libs/cua-driver or set HIPPODEMO_CUA_DRIVER_BINARY",
                text_chars=len(text),
            )

        daemon_ok, daemon_detail = await self._daemon_status(executable)
        if not daemon_ok:
            return CuaInsertResult(
                ok=False,
                detail=(
                    "cua-driver daemon is not running; start CuaDriver.app with `cua-driver serve` "
                    "before using guarded insertion"
                ),
                text_chars=len(text),
            )

        surface = surface_hint if self._usable_surface_hint(surface_hint) else await self.target_surface()
        if not surface.safe or surface.pid is None:
            return CuaInsertResult(
                ok=False,
                detail=f"target surface is not safe: {surface.reason}",
                target_pid=surface.pid,
                target_app=surface.app_name,
                target_bundle_id=surface.bundle_id,
                text_chars=len(text),
            )

        pid = int(surface.pid)
        arguments: dict[str, Any] = {"pid": pid, "text": text}
        if surface.window_id is not None and surface.element_index is not None:
            arguments["window_id"] = surface.window_id
            arguments["element_index"] = surface.element_index
        result = await self._call_tool(
            executable,
            "type_text",
            arguments,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        if not result["ok"]:
            return CuaInsertResult(
                ok=False,
                detail=f"type_text failed: {result['detail']}",
                target_pid=pid,
                target_app=surface.app_name,
                target_bundle_id=surface.bundle_id,
                text_chars=len(text),
            )

        detail = result["detail"] or f"inserted {len(text)} char(s)"
        detail = f"{detail}; target_surface={surface.mode}"
        if daemon_ok:
            detail = f"{detail}; daemon={daemon_detail}"
        return CuaInsertResult(
            ok=True,
            detail=detail,
            target_pid=pid,
            target_app=surface.app_name,
            target_bundle_id=surface.bundle_id,
            text_chars=len(text),
        )

    async def _daemon_status(self, executable: str) -> tuple[bool, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                executable,
                "status",
                cwd=str(CUA_DRIVER_DIR) if CUA_DRIVER_DIR.exists() else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except Exception as exc:
            return False, str(exc)
        detail = self._summarize(stdout.decode(errors="replace") or stderr.decode(errors="replace"))
        return proc.returncode == 0, detail

    async def _call_tool(
        self,
        executable: str,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        timeout: float,
    ) -> dict[str, Any]:
        command = [executable, "call", tool_name]
        if arguments:
            command.append(json.dumps(arguments, ensure_ascii=False))
        try:
            log_event(
                logger,
                "adapter_subprocess_started",
                adapter="cua-driver",
                action=f"call.{tool_name}",
                argument_keys=sorted(arguments.keys()),
                timeout_seconds=timeout,
            )
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(CUA_DRIVER_DIR) if CUA_DRIVER_DIR.exists() else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
            log_event(
                logger,
                "adapter_subprocess_timeout",
                adapter="cua-driver",
                action=f"call.{tool_name}",
                timeout_seconds=timeout,
            )
            return {"ok": False, "detail": f"{tool_name} timed out after {timeout:.0f}s"}
        except Exception as exc:
            log_event(
                logger,
                "adapter_subprocess_failed",
                adapter="cua-driver",
                action=f"call.{tool_name}",
                error_type=exc.__class__.__name__,
            )
            return {"ok": False, "detail": str(exc)}

        stdout_text = stdout.decode(errors="replace").strip()
        stderr_text = stderr.decode(errors="replace").strip()
        detail = self._summarize(stderr_text or stdout_text)
        payload = self._json_payload(stdout_text)
        log_event(
            logger,
            "adapter_subprocess_completed",
            adapter="cua-driver",
            action=f"call.{tool_name}",
            returncode=proc.returncode,
            stdout_chars=len(stdout_text),
            stderr_chars=len(stderr_text),
        )
        return {
            "ok": proc.returncode == 0,
            "detail": detail,
            "payload": payload,
        }

    async def _run_management(self, executable: str, action: str, *, timeout: float) -> dict[str, Any]:
        try:
            log_event(
                logger,
                "adapter_subprocess_started",
                adapter="cua-driver",
                action=action,
                timeout_seconds=timeout,
            )
            proc = await asyncio.create_subprocess_exec(
                executable,
                action,
                cwd=str(CUA_DRIVER_DIR) if CUA_DRIVER_DIR.exists() else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
            log_event(
                logger,
                "adapter_subprocess_timeout",
                adapter="cua-driver",
                action=action,
                timeout_seconds=timeout,
            )
            return {"ok": False, "detail": f"{action} timed out after {timeout:.0f}s"}
        except Exception as exc:
            log_event(
                logger,
                "adapter_subprocess_failed",
                adapter="cua-driver",
                action=action,
                error_type=exc.__class__.__name__,
            )
            return {"ok": False, "detail": str(exc)}
        stdout_text = stdout.decode(errors="replace").strip()
        stderr_text = stderr.decode(errors="replace").strip()
        log_event(
            logger,
            "adapter_subprocess_completed",
            adapter="cua-driver",
            action=action,
            returncode=proc.returncode,
            stdout_chars=len(stdout_text),
            stderr_chars=len(stderr_text),
        )
        return {
            "ok": proc.returncode == 0,
            "detail": self._summarize(stderr_text or stdout_text),
        }

    async def _launch_bundle_daemon(self, bundle_path: Path) -> dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/open",
                "-n",
                "-g",
                str(bundle_path),
                "--args",
                "serve",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
            return {"ok": False, "detail": f"open timed out for {bundle_path}"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
        stdout_text = stdout.decode(errors="replace").strip()
        stderr_text = stderr.decode(errors="replace").strip()
        detail = self._summarize(stderr_text or stdout_text) or f"LaunchServices bundle={bundle_path}"
        return {"ok": proc.returncode == 0, "detail": detail}

    def _spawn_direct_daemon(self, executable: str, log_path: Path) -> subprocess.Popen[bytes]:
        log_file = log_path.open("ab")
        try:
            return subprocess.Popen(
                [executable, "serve", "--no-relaunch"],
                cwd=str(CUA_DRIVER_DIR) if CUA_DRIVER_DIR.exists() else None,
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,
            )
        finally:
            # The child owns the duplicated file descriptor after fork.
            with contextlib.suppress(Exception):
                log_file.close()

    def _bundle_path_for_executable(self, executable: str) -> Path | None:
        path = Path(executable).expanduser()
        for candidate in [path, *path.parents]:
            if candidate.suffix == ".app" and candidate.exists() and candidate.is_dir():
                return candidate
        return None

    def _resolve_target_app(self, payload: Any) -> tuple[dict[str, Any] | None, str]:
        apps = payload.get("apps") if isinstance(payload, dict) else None
        if not isinstance(apps, list):
            return None, "none"

        bundle_id = os.environ.get("HIPPODEMO_CUA_TARGET_BUNDLE_ID", "").strip()
        if bundle_id:
            for app in apps:
                if self._running_app(app) and app.get("bundle_id") == bundle_id:
                    return app, "explicit_bundle"
            return None, "explicit_bundle"

        app_name = os.environ.get("HIPPODEMO_CUA_TARGET_APP", "").strip().lower()
        if app_name:
            for app in apps:
                if self._running_app(app) and app_name in str(app.get("name") or "").lower():
                    return app, "explicit_name"
            return None, "explicit_name"

        for app in apps:
            if not self._running_app(app) or not app.get("active"):
                continue
            name = str(app.get("name") or "")
            bundle = str(app.get("bundle_id") or "")
            if name in SELF_APP_NAMES or bundle in DANGEROUS_ACTIVE_BUNDLES:
                return None, "active_blocked"
            return app, "active"
        return None, "active"

    def _select_target_window(self, payload: Any) -> dict[str, Any] | None:
        windows = payload.get("windows") if isinstance(payload, dict) else None
        if not isinstance(windows, list):
            return None
        candidates = [
            window for window in windows
            if isinstance(window, dict)
            and bool(window.get("is_on_screen"))
            and bool(window.get("on_current_space"))
            and int(window.get("window_id") or 0) > 0
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: int((item.get("bounds") or {}).get("width") or 0) * int((item.get("bounds") or {}).get("height") or 0))

    def _first_editable_element(self, payload: Any) -> tuple[int, str] | None:
        tree = payload.get("tree_markdown") if isinstance(payload, dict) else None
        if not isinstance(tree, str):
            return None
        matches: list[tuple[int, int, str]] = []
        for line in tree.splitlines():
            if "DISABLED" in line:
                continue
            if not any(role in line for role in EDITABLE_AX_ROLES):
                continue
            match = EDITABLE_LINE_RE.search(line)
            if match:
                role = match.group("role")
                matches.append((self._editable_role_rank(role), int(match.group("index")), role))
        if not matches:
            return None
        _, element_index, element_role = min(matches, key=lambda item: (item[0], item[1]))
        return element_index, element_role

    def _editable_role_rank(self, role: str) -> int:
        if role == "AXTextArea":
            return 0
        if role == "AXTextField":
            return 1
        return 2

    def _running_app(self, app: Any) -> bool:
        return isinstance(app, dict) and bool(app.get("running")) and int(app.get("pid") or 0) > 0

    def _allow_direct_cli(self) -> bool:
        return os.environ.get("HIPPODEMO_CUA_ALLOW_DIRECT", "").lower() in {"1", "true", "yes", "on"}

    def _allow_active_editable_target(self) -> bool:
        return os.environ.get("HIPPODEMO_CUA_ALLOW_ACTIVE_EDITABLE", "").lower() in {"1", "true", "yes", "on"}

    def _safe_bundle_ids(self) -> set[str]:
        raw = os.environ.get("HIPPODEMO_CUA_SAFE_BUNDLE_IDS", "")
        values = {item.strip() for item in raw.split(",") if item.strip()}
        values.update(DEFAULT_SAFE_EDITOR_BUNDLES)
        return values

    def _safe_reason(self, *, app_name: str, bundle_id: str, mode: str) -> str:
        name = app_name or bundle_id
        if mode == "textedit":
            return "TextEdit editable document is ready; insertion still requires user confirmation."
        if mode == "notes_editor":
            return "Notes editable surface is ready; insertion still requires user confirmation."
        if mode == "low_risk_editor":
            return f"{name} editable document is ready; insertion still requires user confirmation."
        return f"{name} is explicitly allowlisted and has an editable text surface; insertion still requires user confirmation."

    def _usable_surface_hint(self, surface: CuaTargetSurface | None) -> bool:
        if surface is None or not surface.safe or surface.pid is None:
            return False
        if not surface.bundle_id or surface.bundle_id in BLOCKED_TARGET_BUNDLES:
            return False
        if surface.bundle_id not in self._safe_bundle_ids():
            return False
        if surface.window_id is None or surface.element_index is None:
            return False
        return True

    def _json_payload(self, text: str) -> Any:
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        for line in reversed(text.splitlines()):
            stripped = line.strip()
            if not stripped.startswith(("{", "[")):
                continue
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                continue
        return None

    def _summarize(self, text: str, *, max_chars: int = 900) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        summary = " | ".join(lines[:12])
        if len(summary) > max_chars:
            summary = summary[: max_chars - 1].rstrip() + "..."
        return summary

    def _tail_log(self, path: Path, *, max_chars: int = 900) -> str:
        if not path.exists():
            return "log missing"
        try:
            data = path.read_bytes()[-4096:]
        except Exception as exc:
            return f"log unreadable: {exc}"
        return self._summarize(data.decode(errors="replace"), max_chars=max_chars)


cua_driver_adapter = CuaDriverAdapter()
