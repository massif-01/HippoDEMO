from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from orchestrator import main
from orchestrator import logging_config
from orchestrator.adapters import basic_memory
from orchestrator.adapters.basic_memory import BasicMemoryAdapter, BasicMemoryRuntime
from orchestrator.logging_config import (
    BACKUP_COUNT,
    MAX_BYTES,
    JsonlFormatter,
    redact,
    setup_logging,
    tail_log,
)
from orchestrator.models import DemoSession
from orchestrator.store import OrchestratorStore


def run(coro):
    return asyncio.run(coro)


def _flush_orchestrator_handlers() -> None:
    for handler in logging.getLogger("orchestrator").handlers:
        handler.flush()


def _request(origin: str | None = None):
    headers = {"origin": origin} if origin else {}
    return SimpleNamespace(headers=headers)


def test_redact_masks_common_secret_shapes():
    payload = {
        "api_key": "sk-test-secret",
        "headers": {"Authorization": "Bearer abc.def"},
        "url": "https://example.com/file?token=abc&safe=yes&X-Amz-Signature=deadbeef",
        "env": "API_KEY=sk-test-secret Authorization: Bearer abcdef",
    }

    redacted = redact(payload)
    rendered = json.dumps(redacted)

    assert "sk-test-secret" not in rendered
    assert "abc.def" not in rendered
    assert "deadbeef" not in rendered
    assert "[REDACTED]" in rendered
    assert "safe=yes" in rendered


def test_setup_logging_writes_jsonl_without_duplicate_handlers(tmp_path):
    path = tmp_path / "orchestrator.jsonl"

    setup_logging(log_path=path, level=logging.DEBUG)
    setup_logging(log_path=path, level=logging.DEBUG)
    logger = logging.getLogger("orchestrator.test")
    logger.info("hello sk-test-secret", extra={"event": "test_event", "api_key": "secret"})
    _flush_orchestrator_handlers()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event"] == "test_event"
    assert payload["message"] == "hello [REDACTED]"
    assert payload["api_key"] == "[REDACTED]"

    handler = next(item for item in logging.getLogger("orchestrator").handlers if getattr(item, "_hippo_orchestrator_jsonl_handler", False))
    assert handler.maxBytes == MAX_BYTES
    assert handler.backupCount == BACKUP_COUNT
    assert isinstance(handler.formatter, JsonlFormatter)


def test_setup_logging_falls_back_when_file_handler_is_unavailable(tmp_path, monkeypatch):
    def broken_handler(*args, **kwargs):
        raise OSError("read-only log directory")

    monkeypatch.setattr(logging_config, "RotatingFileHandler", broken_handler)
    path = tmp_path / "blocked" / "orchestrator.jsonl"

    setup_logging(log_path=path, level=logging.DEBUG)
    logging.getLogger("orchestrator.test").info("logging must not block startup")
    _flush_orchestrator_handlers()

    handler = next(item for item in logging.getLogger("orchestrator").handlers if getattr(item, "_hippo_orchestrator_jsonl_handler", False))
    assert isinstance(handler, logging.NullHandler)


def test_tail_log_reads_json_and_plain_lines_with_redaction(tmp_path):
    path = tmp_path / "mixed.log"
    path.write_text(
        "\n".join(
            [
                json.dumps({"message": "ok", "token": "secret"}),
                "plain Authorization: Bearer abcdef",
            ]
        ),
        encoding="utf-8",
    )

    entries = tail_log(path, limit=10)

    assert entries[0]["token"] == "[REDACTED]"
    assert entries[1]["message"] == "plain Authorization: [REDACTED]"
    assert "abcdef" not in json.dumps(entries)


def test_tail_log_returns_empty_when_file_disappears(tmp_path, monkeypatch):
    path = tmp_path / "rotating.log"
    path.write_text("hello\n", encoding="utf-8")
    monkeypatch.setattr(logging_config, "_tail_lines", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("rotated")))

    assert tail_log(path, limit=10) == []


def test_diagnostics_allowlist_and_tail(tmp_path, monkeypatch):
    runtime_dir = tmp_path / ".runtime"
    logs_dir = runtime_dir / "logs"
    ownscribe_dir = tmp_path / "orchestrator" / "data" / "ownscribe"
    orchestrator_log = logs_dir / "orchestrator.jsonl"
    app_log = runtime_dir / "orchestrator-app.log"
    session_dir = ownscribe_dir / "session_test"
    for path in (orchestrator_log, app_log, session_dir / "ownscribe.stdout.log", session_dir / "ownscribe.stderr.log"):
        path.parent.mkdir(parents=True, exist_ok=True)
    orchestrator_log.write_text(json.dumps({"message": "Authorization: Bearer abcdef"}) + "\n", encoding="utf-8")
    app_log.write_text("API_KEY=sk-test-secret\n", encoding="utf-8")
    (session_dir / "ownscribe.stdout.log").write_text("stdout token=abc\n", encoding="utf-8")
    (session_dir / "ownscribe.stderr.log").write_text("stderr ok\n", encoding="utf-8")

    store = OrchestratorStore()
    store.state.current_session = DemoSession(id="session_test")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "ORCHESTRATOR_LOG_PATH", orchestrator_log)
    monkeypatch.setattr(main, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(main, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(main, "_OWNSCRIBE_DATA_DIR", ownscribe_dir)

    listing = run(main.diagnostics_logs(_request()))
    names = {item["name"] for item in listing["logs"]}
    assert {"orchestrator", "orchestrator-app", "current-ownscribe-stdout", "current-ownscribe-stderr"}.issubset(names)
    assert all("path" not in item for item in listing["logs"])

    tail = run(main.diagnostics_log_tail("orchestrator-app", _request(), limit=50))
    assert tail["limit"] == 50
    assert "path" not in tail
    assert "sk-test-secret" not in json.dumps(tail)

    session_tail = run(main.diagnostics_session_logs("session_test", _request(), limit=50))
    assert session_tail["session_id"] == "session_test"
    assert len(session_tail["logs"]) == 2
    assert all("path" not in item for item in session_tail["logs"])
    assert "abc" not in json.dumps(session_tail)


def test_diagnostics_rejects_unknown_log_and_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", OrchestratorStore())
    monkeypatch.setattr(main, "_OWNSCRIBE_DATA_DIR", tmp_path / "ownscribe")

    with pytest.raises(HTTPException) as unknown:
        run(main.diagnostics_log_tail("../secret", _request(), limit=10))
    assert unknown.value.status_code == 404

    with pytest.raises(HTTPException) as unknown_session:
        run(main.diagnostics_session_logs("session_test", _request(), limit=10))
    assert unknown_session.value.status_code == 404

    with pytest.raises(HTTPException) as traversal:
        run(main.diagnostics_session_logs("../secret", _request(), limit=10))
    assert traversal.value.status_code == 404

    with pytest.raises(HTTPException) as forbidden:
        run(main.diagnostics_logs(_request("https://example.com")))
    assert forbidden.value.status_code == 403


def test_basic_memory_adapter_logs_subprocess_boundary(tmp_path, monkeypatch):
    log_path = tmp_path / "orchestrator.jsonl"
    setup_logging(log_path=log_path, level=logging.DEBUG)
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
        return Result()

    monkeypatch.setattr(basic_memory.subprocess, "run", fake_run)

    result = BasicMemoryAdapter()._run_sync(
        ["tool", "list-projects", "--local"],
        expect_json=True,
        timeout_seconds=5,
    )
    _flush_orchestrator_handlers()

    assert result == {"ok": True}
    rendered = log_path.read_text(encoding="utf-8")
    assert "adapter_subprocess_started" in rendered
    assert "adapter_subprocess_completed" in rendered
    assert "basic-memory" in rendered
