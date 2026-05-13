from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ..models import ServiceStatus


PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_DIR / "orchestrator" / "data" / "vlmac_config.json"
VLMAC_ENV_PATH = PROJECT_DIR / "vlmac" / ".env"

DEFAULT_CONFIG: dict[str, Any] = {
    "service_base_url": "http://127.0.0.1:59092",
    "vllm_base_url": "http://localhost:58000",
    "vllm_model": "RM-01 VLM",
    "vllm_api_key": "",
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout_seconds": 120.0,
}


class VlmacAdapter:
    def config(self) -> dict[str, Any]:
        config = self._read_config()
        return self._public_config(config, restart_required=False)

    def update_config(
        self,
        *,
        service_base_url: str | None = None,
        vllm_base_url: str | None = None,
        vllm_model: str | None = None,
        vllm_api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if max_tokens is not None and max_tokens <= 0:
            raise ValueError("max_tokens must be greater than 0")
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")

        config = self._read_config()
        updates = {
            "service_base_url": service_base_url,
            "vllm_base_url": vllm_base_url,
            "vllm_model": vllm_model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout_seconds": timeout_seconds,
        }
        for key, value in updates.items():
            if value is not None:
                config[key] = value
        if vllm_api_key is not None:
            config["vllm_api_key"] = vllm_api_key

        self._write_config(config)
        self._write_env(config)
        return self._public_config(config, restart_required=True)

    async def status(self) -> ServiceStatus:
        config = self._read_config()
        base_url = str(config.get("service_base_url") or DEFAULT_CONFIG["service_base_url"]).rstrip("/")

        def request_status() -> tuple[bool, str]:
            try:
                with urllib.request.urlopen(f"{base_url}/api/status", timeout=2.0) as response:
                    body = response.read(2048).decode("utf-8", errors="replace")
                return True, body
            except urllib.error.URLError as exc:
                return False, str(exc.reason)
            except Exception as exc:
                return False, str(exc)

        ok, detail = await asyncio.to_thread(request_status)
        if not ok:
            return ServiceStatus(name="vlmac", status="unavailable", detail=f"{base_url}: {detail}")
        return ServiceStatus(name="vlmac", status="online", detail=f"{base_url}: {detail[:240]}")

    async def start_task(
        self,
        *,
        device: str | None = None,
        resolution: str = "1920x1080",
        interval: int = 45,
        scene_threshold: float = 0.05,
        min_interval: float = 3.0,
        bitrate: str = "1M",
        timer_prompt: str = "Describe the current screen context and changes relevant to the Jarvis session.",
        system_prompt: str = "",
    ) -> dict[str, Any]:
        payload = {
            "device": device or "",
            "resolution": resolution,
            "interval": interval,
            "scene_threshold": scene_threshold,
            "min_interval": min_interval,
            "bitrate": bitrate,
            "timer_prompt": timer_prompt,
            "system_prompt": system_prompt,
        }
        return await self._request_json("POST", "/api/start", payload=payload)

    async def stop_task(self, task_id: str | None = None) -> dict[str, Any]:
        if task_id:
            return await self._request_json("DELETE", f"/api/tasks/{task_id}")
        return await self._request_json("POST", "/api/stop", payload={})

    async def results(self, *, task_id: str | None = None, limit: int = 10) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 100))
        if task_id:
            return await self._request_json("GET", f"/api/tasks/{task_id}/results?limit={safe_limit}")
        return await self._request_json("GET", f"/api/results?limit={safe_limit}")

    def _read_config(self) -> dict[str, Any]:
        if not CONFIG_PATH.exists():
            return dict(DEFAULT_CONFIG)
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            config = {**DEFAULT_CONFIG, **raw}
            return config
        except Exception:
            return dict(DEFAULT_CONFIG)

    def _write_config(self, config: dict[str, Any]) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_env(self, config: dict[str, Any]) -> None:
        VLMAC_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        values = {
            "VLLM_BASE_URL": config.get("vllm_base_url"),
            "VLLM_MODEL": config.get("vllm_model"),
            "VLLM_API_KEY": config.get("vllm_api_key"),
            "VLLM_TEMPERATURE": config.get("temperature"),
            "VLLM_MAX_TOKENS": config.get("max_tokens"),
            "VLLM_TIMEOUT_SECONDS": config.get("timeout_seconds"),
        }
        lines = [
            f"{key}={self._env_value(value)}"
            for key, value in values.items()
            if value is not None
        ]
        VLMAC_ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _public_config(self, config: dict[str, Any], *, restart_required: bool) -> dict[str, Any]:
        return {
            "service_base_url": config.get("service_base_url"),
            "vllm_base_url": config.get("vllm_base_url"),
            "vllm_model": config.get("vllm_model"),
            "vllm_api_key_configured": bool(config.get("vllm_api_key")),
            "temperature": config.get("temperature"),
            "max_tokens": config.get("max_tokens"),
            "timeout_seconds": config.get("timeout_seconds"),
            "config_path": str(CONFIG_PATH),
            "env_path": str(VLMAC_ENV_PATH),
            "env_exists": VLMAC_ENV_PATH.exists(),
            "restart_required": restart_required,
        }

    def _env_value(self, value: Any) -> str:
        text = str(value or "")
        if not text or any(char.isspace() for char in text):
            return json.dumps(text)
        return text

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        config = self._read_config()
        base_url = str(config.get("service_base_url") or DEFAULT_CONFIG["service_base_url"]).rstrip("/")
        request_timeout = float(timeout or config.get("timeout_seconds") or DEFAULT_CONFIG["timeout_seconds"])
        url = f"{base_url}{path}"

        def perform_request() -> dict[str, Any]:
            data = None
            headers: dict[str, str] = {}
            if payload is not None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                headers["Content-Type"] = "application/json"
            request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
            try:
                with urllib.request.urlopen(request, timeout=request_timeout) as response:
                    body = response.read().decode("utf-8", errors="replace")
                    status_code = response.status
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                return {
                    "ok": False,
                    "status_code": exc.code,
                    "detail": body or str(exc),
                    "url": url,
                }
            except urllib.error.URLError as exc:
                return {"ok": False, "status_code": None, "detail": str(exc.reason), "url": url}
            except Exception as exc:
                return {"ok": False, "status_code": None, "detail": str(exc), "url": url}

            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {"raw": body}
            if isinstance(parsed, dict) and parsed.get("error"):
                return {"ok": False, "status_code": status_code, "detail": str(parsed.get("error")), "url": url, **parsed}
            if isinstance(parsed, dict):
                return {"ok": 200 <= status_code < 300, "status_code": status_code, "url": url, **parsed}
            return {"ok": 200 <= status_code < 300, "status_code": status_code, "url": url, "data": parsed}

        return await asyncio.to_thread(perform_request)


vlmac_adapter = VlmacAdapter()
