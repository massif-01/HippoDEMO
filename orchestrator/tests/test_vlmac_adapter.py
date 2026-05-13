from __future__ import annotations

import asyncio
import json
from pathlib import Path

from orchestrator.adapters import vlmac
from orchestrator.adapters.vlmac import VlmacAdapter
from orchestrator.models import ServiceStatus


def run(coro):
    return asyncio.run(coro)


def test_preflight_marks_missing_basic_memory_project(tmp_path, monkeypatch):
    source_dir = tmp_path / "vlmac"
    source_dir.mkdir()
    python = tmp_path / "python"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    python.chmod(0o755)
    missing_project = tmp_path / "missing-project"

    monkeypatch.setattr(vlmac, "VLMAC_DIR", source_dir)
    monkeypatch.setattr(vlmac.basic_memory_adapter, "config", lambda: {"project_path": str(missing_project)})
    monkeypatch.setattr(VlmacAdapter, "python_path", lambda self: str(python))
    monkeypatch.setattr(VlmacAdapter, "_python_import_check", lambda self, path: (True, "imports ok"))
    monkeypatch.setattr(vlmac.shutil, "which", lambda name: f"/usr/bin/{name}")

    result = run(VlmacAdapter().preflight())

    assert result["ok"] is False
    checks = {check["name"]: check for check in result["checks"]}
    assert checks["basic_memory_project"]["ok"] is False
    assert checks["basic_memory_project"]["detail"] == str(missing_project)


def test_status_rejects_legacy_vlmac_without_storage_endpoint(tmp_path, monkeypatch):
    source_dir = tmp_path / "vlmac"
    source_dir.mkdir()
    monkeypatch.setattr(vlmac, "VLMAC_DIR", source_dir)

    class FakeAdapter(VlmacAdapter):
        async def _get_json(self, path):
            if path == "/api/status":
                return {"tasks_count": 0, "running_count": 0}
            return None

    service = run(FakeAdapter().status())

    assert service.status == "error"
    assert "storage status endpoint is unavailable" in (service.detail or "")


def test_start_injects_basic_memory_storage_env(tmp_path, monkeypatch):
    source_dir = tmp_path / "vlmac"
    source_dir.mkdir()
    project_dir = tmp_path / "basic-memory-project"
    project_dir.mkdir()
    runtime_dir = tmp_path / "runtime"
    log_path = runtime_dir / "vlmac.log"
    pid_path = runtime_dir / "vlmac.pid"
    captured: dict[str, object] = {}

    monkeypatch.setattr(vlmac, "VLMAC_DIR", source_dir)
    monkeypatch.setattr(vlmac, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(vlmac, "VLMAC_LOG_PATH", log_path)
    monkeypatch.setattr(vlmac, "VLMAC_PID_PATH", pid_path)

    class FakeProcess:
        pid = 12345
        returncode = None

        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        captured["env"] = kwargs.get("env")
        return FakeProcess()

    class FakeAdapter(VlmacAdapter):
        def __init__(self):
            super().__init__()
            self.status_calls = 0

        def python_path(self):
            return "/tmp/vlmac-python"

        def _project_path(self):
            return str(project_dir)

        async def preflight(self):
            return {"ok": True, "checks": [], "config": self.config()}

        async def status(self):
            self.status_calls += 1
            if self.status_calls == 1:
                return ServiceStatus(name="vlmac", status="unavailable", detail="offline")
            return ServiceStatus(name="vlmac", status="online", detail="ready")

    monkeypatch.setattr(vlmac.subprocess, "Popen", fake_popen)

    service = run(FakeAdapter().start())

    env = captured["env"]
    assert service.status == "online"
    assert isinstance(env, dict)
    assert env["HIPPODEMO_VLMAC_STORAGE"] == "basic-memory-local"
    assert env["HIPPODEMO_BASIC_MEMORY_PROJECT_DIR"] == str(project_dir)
    assert captured["cwd"] == str(source_dir)
    assert captured["command"] == ["/tmp/vlmac-python", "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "59092"]
    assert pid_path.read_text(encoding="utf-8").strip() == "12345"


def test_ingest_reads_timestamped_video_summaries(tmp_path, monkeypatch):
    project_dir = tmp_path / "project"
    summary_dir = project_dir / "hippo" / "context" / "video" / "summaries" / "camera-1"
    summary_dir.mkdir(parents=True)
    rolling_context = project_dir / "hippo" / "context" / "video" / "rolling_context.jsonl"
    rolling_context.write_text("", encoding="utf-8")
    summary_path = summary_dir / "2026-05-14T10-00-00+08-00.json"
    summary_path.write_text(
        json.dumps(
            {
                "system_time_iso": "2026-05-14T10:00:00+08:00",
                "epoch_ms": 1779360000000,
                "source_id": "camera-1",
                "answer": "screen changed",
            }
        ),
        encoding="utf-8",
    )

    class FakeAdapter(VlmacAdapter):
        def _project_path(self):
            return str(project_dir)

    result = run(FakeAdapter().ingest())

    assert result.ok is True
    assert result.rolling_context_path == str(rolling_context)
    assert result.summaries[0]["source_id"] == "camera-1"
    assert result.summaries[0]["source_path"] == str(summary_path)
