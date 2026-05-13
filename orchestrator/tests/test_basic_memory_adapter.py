from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orchestrator.adapters import basic_memory
from orchestrator.adapters.basic_memory import BasicMemoryAdapter, BasicMemoryRuntime
from orchestrator.models import ServiceStatus


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def isolated_paths(tmp_path, monkeypatch):
    data_dir = tmp_path / "basic_memory"
    monkeypatch.setattr(basic_memory, "BASIC_MEMORY_CONFIG_DIR", data_dir / "config")
    monkeypatch.setattr(basic_memory, "BASIC_MEMORY_PROJECT_DIR", data_dir / "project")
    monkeypatch.setattr(basic_memory, "BASIC_MEMORY_LEDGER_PATH", data_dir / "ledger.json")
    monkeypatch.setattr(basic_memory, "BASIC_MEMORY_REPO_DIR", tmp_path / "basic-memory")
    return data_dir


def test_env_is_hippo_scoped(isolated_paths):
    env = BasicMemoryAdapter()._env()

    assert env["BASIC_MEMORY_CONFIG_DIR"] == str(isolated_paths / "config")
    assert env["BASIC_MEMORY_NO_PROMOS"] == "1"
    assert env["BASIC_MEMORY_LOG_LEVEL"] == "ERROR"


def test_status_reports_runtime_missing(monkeypatch):
    monkeypatch.setattr(basic_memory, "_resolve_runtime", lambda: None)

    service = run(BasicMemoryAdapter().status())

    assert service.status == "unavailable"
    assert "runtime is not bundled" in (service.detail or "")
    assert "uv is only a developer fallback" in (service.detail or "")


def test_config_prefers_bundled_runtime_over_uv(tmp_path, monkeypatch):
    bundled = tmp_path / "orchestrator-runtime"
    bin_dir = bundled / "bin"
    bin_dir.mkdir(parents=True)
    bm = bin_dir / "bm"
    python = bin_dir / "python"
    bm.write_text("#!/bin/sh\n", encoding="utf-8")
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    bm.chmod(0o755)
    python.chmod(0o755)
    monkeypatch.setattr(basic_memory, "BUNDLED_RUNTIME_DIR", bundled)
    monkeypatch.setattr(basic_memory, "DEV_RUNTIME_DIR", tmp_path / "dev-runtime")
    monkeypatch.setattr(basic_memory, "BASIC_MEMORY_REPO_DIR", tmp_path / "basic-memory")
    monkeypatch.setattr(basic_memory, "_uv_path", lambda: "/opt/homebrew/bin/uv")

    config = BasicMemoryAdapter().config()

    assert config["tools_available"] is True
    assert config["runtime_kind"] == "bundled"
    assert config["runtime_path"] == str(bm)


def test_setup_adds_project_then_verifies_json(isolated_paths):
    class FakeAdapter(BasicMemoryAdapter):
        def __init__(self):
            self.calls = 0
            self.project_add_args = None

        async def list_projects(self):
            self.calls += 1
            if self.calls == 1:
                return {"projects": []}
            return {"projects": [{"name": "hippo", "path": str(isolated_paths / "project")}]}

        async def _run_text(self, args, *, input_text=None, timeout_seconds=60):
            self.project_add_args = args
            return "[green]Project added[/green]"

        async def status(self):
            return ServiceStatus(name="basic-memory", status="online", detail="ready")

    adapter = FakeAdapter()
    result = run(adapter.setup())

    assert result["ok"] is True
    assert result["added"] is True
    assert adapter.project_add_args[:3] == ["project", "add", "hippo"]
    assert adapter.project_add_args[-2:] == ["--default", "--local"]


def test_write_note_uses_ledger_to_skip_duplicate(isolated_paths):
    ledger_path = isolated_paths / "ledger.json"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text(
        json.dumps(
            {
                "task:task_123": {
                    "identifier": "hippo/tasks/hippo-task-123",
                    "path": "hippo/tasks/Hippo Task 123.md",
                    "status": "synced",
                }
            }
        ),
        encoding="utf-8",
    )

    class FakeAdapter(BasicMemoryAdapter):
        async def _ensure_setup(self):
            raise AssertionError("setup should not run when ledger already has the source")

    result = run(
        FakeAdapter().write_note(
            kind="task",
            source_id="task_123",
            title="Hippo Task 123",
            folder="hippo/tasks",
            content="# Hippo Task 123",
        )
    )

    assert result["status"] == "already_synced"
    assert result["identifier"] == "hippo/tasks/hippo-task-123"


def test_write_note_conflict_records_ledger(isolated_paths):
    class FakeAdapter(BasicMemoryAdapter):
        async def _ensure_setup(self):
            return None

        async def _find_existing_by_title(self, title):
            return None

        async def _run_json(self, args, *, input_text=None, timeout_seconds=60):
            return {
                "title": "Hippo Skill abc123",
                "permalink": "hippo/skills/hippo-skill-abc123",
                "file_path": "hippo/skills/Hippo Skill abc123.md",
                "action": "conflict",
                "error": "NOTE_ALREADY_EXISTS",
            }

    result = run(
        FakeAdapter().write_note(
            kind="skill",
            source_id="skill_abc123",
            title="Hippo Skill abc123",
            folder="hippo/skills",
            content="# Hippo Skill abc123",
        )
    )

    assert result["status"] == "already_synced"
    ledger = json.loads((isolated_paths / "ledger.json").read_text(encoding="utf-8"))
    assert ledger["skill:skill_abc123"]["permalink"] == "hippo/skills/hippo-skill-abc123"


def test_run_sync_uses_resolved_runtime(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        basic_memory,
        "_resolve_runtime",
        lambda: BasicMemoryRuntime(
            kind="bundled",
            command=("/hippo/runtime/bin/bm",),
            python_command=("/hippo/runtime/bin/python",),
            path="/hippo/runtime/bin/bm",
            detail="test runtime",
        ),
    )

    class Result:
        returncode = 0
        stdout = '{"ok": true}'
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        return Result()

    monkeypatch.setattr(basic_memory.subprocess, "run", fake_run)

    result = BasicMemoryAdapter()._run_sync(
        ["tool", "list-projects", "--local"],
        expect_json=True,
        timeout_seconds=5,
    )

    assert result == {"ok": True}
    assert captured["command"][:2] == ["/hippo/runtime/bin/bm", "tool"]


def test_list_projects_falls_back_to_local_config(isolated_paths):
    config_path = isolated_paths / "config" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "projects": {
                    "hippo": {
                        "path": str(isolated_paths / "project"),
                        "mode": "local",
                    }
                },
                "default_project": "hippo",
            }
        ),
        encoding="utf-8",
    )

    class FakeAdapter(BasicMemoryAdapter):
        async def _run_json(self, args, *, input_text=None, timeout_seconds=60):
            raise basic_memory.BasicMemoryCommandError("Error during list_projects: pop from an empty deque")

    payload = run(FakeAdapter().list_projects())

    assert payload["source"] == "config.json"
    assert payload["projects"][0]["name"] == "hippo"
    assert payload["projects"][0]["path"] == str(isolated_paths / "project")
