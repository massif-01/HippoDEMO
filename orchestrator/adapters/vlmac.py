from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..logging_config import log_event
from ..models import ServiceStatus, now_iso
from .basic_memory import basic_memory_adapter


PROJECT_DIR = Path(__file__).resolve().parents[2]
VLMAC_DIR = PROJECT_DIR / "vlmac"
VLMAC_BUNDLED_RUNTIME_DIR = PROJECT_DIR / "vlmac-runtime"
VLMAC_DEV_RUNTIME_DIR = PROJECT_DIR / ".runtime" / "vlmac-runtime"
VLMAC_BOOTSTRAP_SCRIPT = PROJECT_DIR / "script" / "bootstrap_vlmac_runtime.sh"
RUNTIME_DIR = PROJECT_DIR / ".runtime"
VLMAC_LOG_PATH = RUNTIME_DIR / "vlmac.log"
VLMAC_PID_PATH = RUNTIME_DIR / "vlmac.pid"
VLMAC_PROVIDER_CONFIG_PATH = RUNTIME_DIR / "vlmac-provider.json"
DEFAULT_BASE_URL = "http://127.0.0.1:59092"
DEFAULT_VLM_OPENAI_BASE_URL = "http://127.0.0.1:58000/v1"
DEFAULT_VLM_MODEL = "RM-01 VLM"
STATUS_TIMEOUT_SECONDS = 3.0
STARTUP_TIMEOUT_SECONDS = 8.0
logger = logging.getLogger("orchestrator.adapters.vlmac")


@dataclass
class VlmacIngestResult:
    ok: bool
    summaries: list[dict[str, Any]]
    rolling_context_path: str | None
    detail: str


class VlmacAdapter:
    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = asyncio.Lock()

    def config(self) -> dict[str, Any]:
        basic_memory_config = basic_memory_adapter.config()
        parsed = urlparse(self.base_url)
        return {
            "base_url": self.base_url,
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 59092,
            "vlmac_dir": str(VLMAC_DIR),
            "bundled_runtime_path": str(VLMAC_BUNDLED_RUNTIME_DIR),
            "dev_runtime_path": str(VLMAC_DEV_RUNTIME_DIR),
            "python_path": self.python_path(),
            "project_path": basic_memory_config.get("project_path"),
            "storage": "basic-memory-local",
            "vlm_provider": "openai-compatible",
            "vlm_base_url": self._vlm_base_url(),
            "vlm_model": self._vlm_model(),
            "vlm_api_key_configured": bool(self._vlm_api_key()),
            "provider_config_path": str(VLMAC_PROVIDER_CONFIG_PATH),
            "log_path": str(VLMAC_LOG_PATH),
            "pid_path": str(VLMAC_PID_PATH),
        }

    def update_config(
        self,
        *,
        vlm_base_url: str | None = None,
        vlm_model: str | None = None,
        vlm_api_key: str | None = None,
    ) -> dict[str, Any]:
        if vlm_base_url is None and vlm_model is None and vlm_api_key is None:
            return self.config()

        config = self._read_provider_config()
        updates = {
            "vlm_base_url": vlm_base_url,
            "vlm_model": vlm_model,
            "vlm_api_key": vlm_api_key,
        }
        for key, value in updates.items():
            if value is None:
                continue
            cleaned = str(value).strip()
            if not cleaned:
                config.pop(key, None)
            elif key == "vlm_base_url":
                config[key] = self._normalize_openai_base_url(cleaned)
            else:
                config[key] = cleaned
        self._write_provider_config(config)
        return self.config()

    @property
    def base_url(self) -> str:
        return os.environ.get("HIPPODEMO_VLMAC_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

    def python_path(self) -> str | None:
        override = os.environ.get("HIPPODEMO_VLMAC_PYTHON")
        if override:
            path = Path(override).expanduser()
            if path.exists() and os.access(path, os.X_OK):
                return str(path)
            return None
        candidates = [
            VLMAC_BUNDLED_RUNTIME_DIR / "bin" / "python",
            VLMAC_DEV_RUNTIME_DIR / "bin" / "python",
            VLMAC_DIR / ".venv" / "bin" / "python",
            Path(sys.executable),
        ]
        for candidate in candidates:
            if candidate.exists() and os.access(candidate, os.X_OK):
                ok, _ = self._python_import_check(str(candidate))
                if ok:
                    return str(candidate)
        return None

    async def status(self) -> ServiceStatus:
        if not VLMAC_DIR.exists():
            return ServiceStatus(name="vlmac", status="unavailable", detail=f"vlmac source not found: {VLMAC_DIR}")

        service_payload = await self._get_json("/api/status")
        storage_payload = await self._get_json("/api/storage/status")
        if service_payload is not None:
            if storage_payload is None:
                return ServiceStatus(
                    name="vlmac",
                    status="error",
                    detail=f"vlmac HTTP online but storage status endpoint is unavailable; base_url={self.base_url}",
                )
            if not storage_payload.get("ok"):
                return ServiceStatus(
                    name="vlmac",
                    status="error",
                    detail=(
                        f"vlmac HTTP online but storage unavailable; "
                        f"base_url={self.base_url}; project_path={storage_payload.get('project_path')}; "
                        f"configured={storage_payload.get('project_path_configured')}"
                    ),
                )
            tasks_count = service_payload.get("tasks_count", 0)
            running_count = service_payload.get("running_count", 0)
            storage_path = storage_payload.get("video_context_path") if storage_payload else None
            return ServiceStatus(
                name="vlmac",
                status="online",
                detail=(
                    f"base_url={self.base_url}; vlm_api={self._vlm_base_url()}; "
                    f"tasks={tasks_count}; running={running_count}; "
                    f"storage={storage_path or self._project_path()}"
                ),
            )

        process = self._process
        if process is not None and process.poll() is None:
            return ServiceStatus(
                name="vlmac",
                status="starting",
                detail=f"managed process pid={process.pid}; waiting for {self.base_url}; log={VLMAC_LOG_PATH}",
            )
        if process is not None and process.poll() is not None:
            return ServiceStatus(
                name="vlmac",
                status="error",
                detail=f"managed process exited code={process.returncode}; log={VLMAC_LOG_PATH}; {self._tail_log()}",
            )
        return ServiceStatus(
            name="vlmac",
            status="unavailable",
            detail=(
                f"vlmac not running; base_url={self.base_url}; vlm_api={self._vlm_base_url()}; "
                f"python={self.python_path() or 'missing'}"
            ),
        )

    async def preflight(self, *, auto_setup: bool = True, network: bool = False) -> dict[str, Any]:
        bootstrap: list[dict[str, Any]] = []
        if auto_setup:
            bootstrap.append(await self._ensure_vlmac_runtime())
            bootstrap.append(await self._ensure_basic_memory_project())

        python = self.python_path()
        project_path = self._project_path()
        ffmpeg_ok, ffmpeg_detail = self._ffmpeg_check(python)
        ffprobe = shutil.which("ffprobe")
        checks = [
            self._check("vlmac_source", VLMAC_DIR.exists(), str(VLMAC_DIR)),
            self._check("vlmac_python", bool(python), python or "bootstrap_vlmac_runtime.sh did not create an importable runtime"),
            self._check("basic_memory_project", bool(project_path and Path(project_path).exists()), project_path or "missing"),
            self._check("ffmpeg", ffmpeg_ok, ffmpeg_detail),
            self._check("ffprobe", True, ffprobe or "optional; vlmac falls back to ffmpeg duration probing"),
        ]
        if python:
            imports_ok, imports_detail = await asyncio.to_thread(self._python_import_check, python)
            checks.append(self._check("vlmac_python_imports", imports_ok, imports_detail))
        if network:
            vlm_ok, vlm_detail = await self._vlm_models_check()
        else:
            vlm_ok = True
            vlm_detail = f"not checked; base_url={self._vlm_base_url()}; pass network=true to probe /models"
        checks.append(self._check("vlm_openai_api", vlm_ok, vlm_detail, required=False))
        return {
            "ok": all(check["ok"] for check in checks if check.get("required", True)),
            "checks": checks,
            "bootstrap": bootstrap,
            "config": self.config(),
            "network_checked": network,
        }

    async def start(self) -> ServiceStatus:
        async with self._lock:
            current = await self.status()
            if current.status == "online":
                return current

            preflight = await self.preflight()
            if not preflight["ok"]:
                failed = [check for check in preflight["checks"] if not check["ok"]]
                detail = "; ".join(f"{check['name']}: {check['detail']}" for check in failed)
                return ServiceStatus(name="vlmac", status="unavailable", detail=detail)

            python = self.python_path()
            assert python is not None
            parsed = urlparse(self.base_url)
            host = parsed.hostname or "127.0.0.1"
            port = str(parsed.port or 59092)
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env["HIPPODEMO_VLMAC_STORAGE"] = "basic-memory-local"
            env["HIPPODEMO_BASIC_MEMORY_PROJECT_DIR"] = str(self._project_path())
            env["VLLM_BASE_URL"] = self._vlm_base_url()
            env["VLLM_MODEL"] = self._vlm_model()
            if self._vlm_api_key():
                env["VLLM_API_KEY"] = str(self._vlm_api_key())
            command = [python, "-m", "uvicorn", "server:app", "--host", host, "--port", port]
            try:
                log_event(
                    logger,
                    "adapter_subprocess_started",
                    adapter="vlmac",
                    action="start",
                    command=["python", "-m", "uvicorn", "server:app", "--host", host, "--port", port],
                    cwd=str(VLMAC_DIR),
                )
                with VLMAC_LOG_PATH.open("ab") as log:
                    self._process = subprocess.Popen(
                        command,
                        cwd=str(VLMAC_DIR),
                        env=env,
                        stdout=log,
                        stderr=log,
                        stdin=subprocess.DEVNULL,
                    )
            except Exception as exc:
                log_event(
                    logger,
                    "adapter_subprocess_failed",
                    adapter="vlmac",
                    action="start",
                    error_type=exc.__class__.__name__,
                )
                return ServiceStatus(name="vlmac", status="error", detail=f"start failed: {exc}")

            VLMAC_PID_PATH.write_text(f"{self._process.pid}\n", encoding="utf-8")
            deadline = asyncio.get_running_loop().time() + STARTUP_TIMEOUT_SECONDS
            while asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.25)
                if self._process.poll() is not None:
                    return ServiceStatus(
                        name="vlmac",
                        status="error",
                        detail=f"process exited code={self._process.returncode}; log={VLMAC_LOG_PATH}; {self._tail_log()}",
                    )
                service = await self.status()
                if service.status == "online":
                    return service

            return ServiceStatus(
                name="vlmac",
                status="starting",
                detail=f"started pid={self._process.pid}; waiting for {self.base_url}; log={VLMAC_LOG_PATH}",
            )

    async def stop(self) -> ServiceStatus:
        async with self._lock:
            process = self._process
            if process is None:
                return ServiceStatus(name="vlmac", status="unavailable", detail="no managed vlmac process to stop")
            if process.poll() is None:
                process.terminate()
                try:
                    await asyncio.to_thread(process.wait, 8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    await asyncio.to_thread(process.wait, 3)
            self._process = None
            try:
                VLMAC_PID_PATH.unlink()
            except FileNotFoundError:
                pass
            return ServiceStatus(name="vlmac", status="unavailable", detail=f"managed vlmac stopped; log={VLMAC_LOG_PATH}")

    async def restart(self) -> ServiceStatus:
        await self.stop()
        await asyncio.sleep(0.2)
        return await self.start()

    async def ingest(self, limit: int = 20) -> VlmacIngestResult:
        project_path = self._project_path()
        if not project_path:
            return VlmacIngestResult(False, [], None, "Basic Memory project path is not configured")
        video_dir = Path(project_path) / "hippo" / "context" / "video"
        summaries_dir = video_dir / "summaries"
        rolling_context = video_dir / "rolling_context.jsonl"
        summaries: list[dict[str, Any]] = []
        if summaries_dir.exists():
            for path in sorted(summaries_dir.rglob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload.setdefault("source_path", str(path))
                    summaries.append(payload)
                except Exception:
                    continue
        return VlmacIngestResult(
            ok=bool(summaries),
            summaries=summaries,
            rolling_context_path=str(rolling_context) if rolling_context.exists() else None,
            detail=f"{len(summaries)} vlmac summary item(s) found",
        )

    async def _get_json(self, path: str) -> dict[str, Any] | None:
        try:
            log_event(
                logger,
                "adapter_http_started",
                adapter="vlmac",
                method="GET",
                path=path,
                timeout_seconds=STATUS_TIMEOUT_SECONDS,
            )
            async with httpx.AsyncClient(timeout=STATUS_TIMEOUT_SECONDS) as client:
                response = await client.get(f"{self.base_url}{path}")
            if response.status_code != 200:
                log_event(
                    logger,
                    "adapter_http_failed",
                    adapter="vlmac",
                    method="GET",
                    path=path,
                    status_code=response.status_code,
                )
                return None
            data = response.json()
            log_event(
                logger,
                "adapter_http_completed",
                adapter="vlmac",
                method="GET",
                path=path,
                status_code=response.status_code,
            )
            return data if isinstance(data, dict) else None
        except Exception as exc:
            log_event(
                logger,
                "adapter_http_failed",
                adapter="vlmac",
                method="GET",
                path=path,
                error_type=exc.__class__.__name__,
            )
            return None

    def _project_path(self) -> str | None:
        value = basic_memory_adapter.config().get("project_path")
        return str(value) if value else None

    async def _ensure_vlmac_runtime(self) -> dict[str, Any]:
        python = self.python_path()
        ffmpeg_ok, ffmpeg_detail = self._ffmpeg_check(python)
        if python and ffmpeg_ok:
            return {"name": "vlmac_runtime", "ok": True, "detail": python, "changed": False}
        if not VLMAC_BOOTSTRAP_SCRIPT.exists():
            return {"name": "vlmac_runtime", "ok": False, "detail": f"bootstrap script missing: {VLMAC_BOOTSTRAP_SCRIPT}", "changed": False}

        result = await asyncio.to_thread(
            subprocess.run,
            ["bash", str(VLMAC_BOOTSTRAP_SCRIPT)],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or f"exit={result.returncode}").strip()[-1200:]
            return {"name": "vlmac_runtime", "ok": False, "detail": detail, "changed": False}
        return {
            "name": "vlmac_runtime",
            "ok": bool(self.python_path()),
            "detail": (result.stdout or "").strip()[-1200:] or ffmpeg_detail or str(VLMAC_BUNDLED_RUNTIME_DIR),
            "changed": True,
        }

    async def _ensure_basic_memory_project(self) -> dict[str, Any]:
        project_path = self._project_path()
        try:
            service = await basic_memory_adapter.status()
            if service.status == "online" and project_path and Path(project_path).exists():
                return {"name": "basic_memory_project", "ok": True, "detail": project_path, "changed": False}
        except Exception:
            pass
        try:
            result = await basic_memory_adapter.setup()
        except Exception as exc:
            return {"name": "basic_memory_project", "ok": False, "detail": str(exc), "changed": False}
        return {
            "name": "basic_memory_project",
            "ok": bool(result.get("ok") and result.get("project_path") and Path(str(result.get("project_path"))).exists()),
            "detail": str(result.get("project_path") or result.get("detail") or ""),
            "changed": bool(result.get("added")),
        }

    def _python_import_check(self, python: str) -> tuple[bool, str]:
        result = subprocess.run(
            [python, "-c", "import fastapi, uvicorn, httpx, websockets"],
            capture_output=True,
            text=True,
            cwd=str(VLMAC_DIR),
            timeout=10,
        )
        if result.returncode == 0:
            return True, "fastapi, uvicorn, httpx, websockets importable"
        return False, (result.stderr or result.stdout or f"exit={result.returncode}").strip()[:500]

    def _ffmpeg_check(self, python: str | None) -> tuple[bool, str]:
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return True, system_ffmpeg
        if not python:
            return False, "ffmpeg not found and vlmac Python runtime is unavailable"
        result = subprocess.run(
            [python, "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
            capture_output=True,
            text=True,
            cwd=str(VLMAC_DIR),
            timeout=10,
            check=False,
        )
        path = result.stdout.strip()
        if result.returncode == 0 and path and Path(path).exists():
            return True, path
        return False, (result.stderr or result.stdout or "ffmpeg not found").strip()[:500]

    async def _vlm_models_check(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=STATUS_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    self._openai_endpoint("models"),
                    headers=self._vlm_headers(),
                )
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}: {response.text[:300]}"
            payload = response.json()
            models = payload.get("data") if isinstance(payload, dict) else None
            count = len(models) if isinstance(models, list) else 0
            return count > 0, f"{count} model(s) visible at {self._vlm_base_url()}"
        except Exception as exc:
            return False, str(exc)[:500]

    def _vlm_base_url(self) -> str:
        value = (
            self._provider_config_value("vlm_base_url")
            or os.environ.get("HIPPODEMO_VLM_OPENAI_BASE_URL")
            or os.environ.get("VLLM_BASE_URL")
            or DEFAULT_VLM_OPENAI_BASE_URL
        )
        return self._normalize_openai_base_url(value)

    def _vlm_model(self) -> str:
        value = (
            self._provider_config_value("vlm_model")
            or os.environ.get("HIPPODEMO_VLM_MODEL")
            or os.environ.get("VLLM_MODEL")
            or DEFAULT_VLM_MODEL
        )
        return str(value).strip() or DEFAULT_VLM_MODEL

    def _vlm_api_key(self) -> str | None:
        value = (
            self._provider_config_value("vlm_api_key")
            or os.environ.get("HIPPODEMO_VLM_API_KEY")
            or os.environ.get("VLLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        if not value:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    def _vlm_headers(self) -> dict[str, str] | None:
        api_key = self._vlm_api_key()
        if not api_key:
            return None
        return {"Authorization": f"Bearer {api_key}"}

    def _openai_endpoint(self, path: str) -> str:
        return f"{self._vlm_base_url().rstrip('/')}/{path.lstrip('/')}"

    def _normalize_openai_base_url(self, value: str) -> str:
        cleaned = str(value).strip().rstrip("/")
        if not cleaned:
            raise ValueError("VLM OpenAI-compatible API base URL cannot be empty")
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("VLM OpenAI-compatible API base URL must be an http(s) URL")
        if not cleaned.endswith("/v1"):
            cleaned = f"{cleaned}/v1"
        return cleaned

    def _read_provider_config(self) -> dict[str, Any]:
        if not VLMAC_PROVIDER_CONFIG_PATH.exists():
            return {}
        try:
            payload = json.loads(VLMAC_PROVIDER_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_provider_config(self, payload: dict[str, Any]) -> None:
        VLMAC_PROVIDER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        safe_payload: dict[str, Any] = {}
        base_url = str(payload.get("vlm_base_url") or "").strip()
        if base_url:
            safe_payload["vlm_base_url"] = self._normalize_openai_base_url(base_url)
        model = str(payload.get("vlm_model") or "").strip()
        if model:
            safe_payload["vlm_model"] = model
        api_key = str(payload.get("vlm_api_key") or "").strip()
        if api_key:
            safe_payload["vlm_api_key"] = api_key
        safe_payload["updated_at"] = now_iso()
        VLMAC_PROVIDER_CONFIG_PATH.write_text(
            json.dumps(safe_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _provider_config_value(self, key: str) -> str | None:
        value = self._read_provider_config().get(key)
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    def _check(self, name: str, ok: bool, detail: str, *, required: bool = True) -> dict[str, Any]:
        payload = {"name": name, "ok": bool(ok), "detail": detail}
        if not required:
            payload["required"] = False
        return payload

    def _tail_log(self, limit: int = 1600) -> str:
        if not VLMAC_LOG_PATH.exists():
            return "no log output"
        try:
            data = VLMAC_LOG_PATH.read_bytes()
            return data[-limit:].decode("utf-8", errors="replace").strip()
        except Exception as exc:
            return f"unable to read log: {exc}"


vlmac_adapter = VlmacAdapter()
