from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..logging_config import log_event
from ..models import ServiceStatus, now_iso
from ..store import BASIC_MEMORY_DIR, write_json


PROJECT_DIR = Path(__file__).resolve().parents[2]
BASIC_MEMORY_REPO_DIR = PROJECT_DIR / "basic-memory"
BASIC_MEMORY_CONFIG_DIR = BASIC_MEMORY_DIR / "config"
BASIC_MEMORY_PROJECT_DIR = BASIC_MEMORY_DIR / "project"
BASIC_MEMORY_LEDGER_PATH = BASIC_MEMORY_DIR / "ledger.json"
BASIC_MEMORY_PROJECT_NAME = "hippo"
BUNDLED_RUNTIME_DIR = PROJECT_DIR / "orchestrator-runtime"
DEV_RUNTIME_DIR = PROJECT_DIR / ".runtime" / "basic-memory-runtime"
logger = logging.getLogger("orchestrator.adapters.basic_memory")


def _uv_path() -> str | None:
    path = shutil.which("uv")
    if path:
        return path
    for candidate in (
        Path.home() / ".local" / "bin" / "uv",
        Path.home() / ".cargo" / "bin" / "uv",
        Path("/opt/homebrew/bin/uv"),
        Path("/usr/local/bin/uv"),
    ):
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _executable(path: Path) -> bool:
    return path.exists() and os.access(path, os.X_OK)


@dataclass(frozen=True)
class BasicMemoryRuntime:
    kind: str
    command: tuple[str, ...]
    python_command: tuple[str, ...] | None
    path: str
    detail: str

    @property
    def command_description(self) -> str:
        return " ".join(self.command)


def _runtime_from_bin_dir(kind: str, bin_dir: Path, detail: str) -> BasicMemoryRuntime | None:
    bm = bin_dir / "bm"
    if not _executable(bm):
        return None
    python = bin_dir / "python"
    python_command = (str(python),) if _executable(python) else None
    return BasicMemoryRuntime(
        kind=kind,
        command=(str(bm),),
        python_command=python_command,
        path=str(bm),
        detail=detail,
    )


def _runtime_from_env() -> BasicMemoryRuntime | None:
    bm_path = os.environ.get("HIPPODEMO_BASIC_MEMORY_BM")
    if not bm_path:
        return None
    bm = Path(bm_path).expanduser()
    if not _executable(bm):
        return None
    python_path = os.environ.get("HIPPODEMO_BASIC_MEMORY_PYTHON")
    python = Path(python_path).expanduser() if python_path else bm.parent / "python"
    return BasicMemoryRuntime(
        kind="env",
        command=(str(bm),),
        python_command=(str(python),) if _executable(python) else None,
        path=str(bm),
        detail="HIPPODEMO_BASIC_MEMORY_BM",
    )


def _runtime_from_current_python() -> BasicMemoryRuntime | None:
    try:
        import basic_memory.cli.main  # noqa: F401
    except Exception:
        return None
    return BasicMemoryRuntime(
        kind="current-python",
        command=(sys.executable, "-m", "basic_memory.cli.main"),
        python_command=(sys.executable,),
        path=sys.executable,
        detail="basic_memory importable from Orchestrator Python",
    )


def _runtime_from_uv() -> BasicMemoryRuntime | None:
    uv = _uv_path()
    if not uv or not BASIC_MEMORY_REPO_DIR.exists():
        return None
    prefix = (uv, "run", "--project", str(BASIC_MEMORY_REPO_DIR))
    return BasicMemoryRuntime(
        kind="uv",
        command=(*prefix, "bm"),
        python_command=(*prefix, "python"),
        path=uv,
        detail="developer fallback via uv",
    )


def _resolve_runtime() -> BasicMemoryRuntime | None:
    explicit = _runtime_from_env()
    if explicit:
        return explicit
    for kind, root, detail in (
        ("bundled", BUNDLED_RUNTIME_DIR, "Hippo bundled Basic Memory runtime"),
        ("dev-runtime", DEV_RUNTIME_DIR, "Hippo repo-local Basic Memory runtime"),
        ("repo-venv", BASIC_MEMORY_REPO_DIR / ".venv", "basic-memory repo .venv"),
    ):
        runtime = _runtime_from_bin_dir(kind, root / "bin", detail)
        if runtime:
            return runtime
    current = _runtime_from_current_python()
    if current:
        return current
    return _runtime_from_uv()


class BasicMemoryCommandError(RuntimeError):
    pass


class BasicMemoryAdapter:
    project_name = BASIC_MEMORY_PROJECT_NAME

    def config(self) -> dict[str, Any]:
        runtime = _resolve_runtime()
        uv_path = _uv_path()
        return {
            "enabled": True,
            "status": "configured" if runtime else "unavailable",
            "project": self.project_name,
            "home": str(BASIC_MEMORY_DIR),
            "repo_dir": str(BASIC_MEMORY_REPO_DIR),
            "bundled_runtime_path": str(BUNDLED_RUNTIME_DIR),
            "dev_runtime_path": str(DEV_RUNTIME_DIR),
            "project_path": str(BASIC_MEMORY_PROJECT_DIR),
            "config_path": str(BASIC_MEMORY_CONFIG_DIR),
            "ledger_path": str(BASIC_MEMORY_LEDGER_PATH),
            "runtime_kind": runtime.kind if runtime else None,
            "runtime_path": runtime.path if runtime else None,
            "runtime_detail": runtime.detail if runtime else None,
            "command": runtime.command_description if runtime else None,
            "command_description": runtime.command_description if runtime else None,
            "tools_available": runtime is not None,
            "uv_path": uv_path,
        }

    async def status(self) -> ServiceStatus:
        runtime = _resolve_runtime()
        if not runtime:
            return ServiceStatus(
                name="basic-memory",
                status="unavailable",
                detail=(
                    "Basic Memory runtime is not bundled. Expected "
                    f"{BUNDLED_RUNTIME_DIR}/bin/bm or {DEV_RUNTIME_DIR}/bin/bm; "
                    "uv is only a developer fallback."
                ),
            )
        if runtime.kind == "uv" and not BASIC_MEMORY_REPO_DIR.exists():
            return ServiceStatus(
                name="basic-memory",
                status="unavailable",
                detail=f"basic-memory repo not found: {BASIC_MEMORY_REPO_DIR}",
            )

        try:
            python_version = await self.python_version()
        except Exception as exc:
            return ServiceStatus(
                name="basic-memory",
                status="unavailable",
                detail=f"basic-memory Python runtime unavailable: {self._safe_error(exc)}",
            )
        if tuple(python_version[:2]) < (3, 12):
            return ServiceStatus(
                name="basic-memory",
                status="unavailable",
                detail=f"basic-memory requires Python 3.12+, got {'.'.join(map(str, python_version[:3]))}",
            )

        try:
            projects_payload = await self.list_projects()
        except Exception as exc:
            return ServiceStatus(
                name="basic-memory",
                status="needs_setup",
                detail=f"Project list failed; run setup. {self._safe_error(exc)}",
            )

        project = self._find_project(projects_payload)
        if not project:
            return ServiceStatus(
                name="basic-memory",
                status="needs_setup",
                detail=f"Hippo-local Basic Memory project '{self.project_name}' is not set up.",
            )

        path = project.get("path") or project.get("home") or BASIC_MEMORY_PROJECT_DIR
        return ServiceStatus(
            name="basic-memory",
            status="online",
            detail=(
                f"runtime={runtime.kind}; project={self.project_name}; "
                f"path={path}; config_dir={BASIC_MEMORY_CONFIG_DIR}"
            ),
        )

    async def python_version(self) -> tuple[int, int, int]:
        payload = await self._run_python_json(
            [
                "-c",
                "import json, sys; print(json.dumps({'version': list(sys.version_info[:3])}))",
            ],
            timeout_seconds=20,
        )
        version = payload.get("version") if isinstance(payload, dict) else None
        if not isinstance(version, list) or len(version) < 2:
            raise BasicMemoryCommandError("Unable to read Python version from Basic Memory runtime")
        return tuple(int(part) for part in version[:3])  # type: ignore[return-value]

    async def list_projects(self) -> dict[str, Any]:
        try:
            return await self._run_json(["tool", "list-projects", "--local"], timeout_seconds=45)
        except BasicMemoryCommandError:
            payload = self._local_projects_config_payload()
            if payload["projects"]:
                return payload
            raise

    async def setup(self) -> dict[str, Any]:
        BASIC_MEMORY_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        BASIC_MEMORY_PROJECT_DIR.mkdir(parents=True, exist_ok=True)
        BASIC_MEMORY_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)

        before = await self.list_projects()
        added = False
        if not self._find_project(before):
            await self._run_text(
                [
                    "project",
                    "add",
                    self.project_name,
                    str(BASIC_MEMORY_PROJECT_DIR),
                    "--default",
                    "--local",
                ],
                timeout_seconds=60,
            )
            added = True

        after = await self.list_projects()
        project = self._find_project(after)
        if not project:
            raise BasicMemoryCommandError("basic-memory setup did not create or expose the hippo project")

        service = await self.status()
        return {
            "ok": service.status == "online",
            "status": service.status,
            "detail": service.detail,
            "project": self.project_name,
            "project_path": str(project.get("path") or project.get("home") or BASIC_MEMORY_PROJECT_DIR),
            "config_path": str(BASIC_MEMORY_CONFIG_DIR),
            "added": added,
            "service": self._service_payload(service),
        }

    async def search(self, query: str, limit: int = 10) -> dict[str, Any]:
        self._ensure_query(query)
        safe_limit = max(1, min(int(limit), 50))
        payload = await self._run_json(
            [
                "tool",
                "search-notes",
                query,
                "--page-size",
                str(safe_limit),
                "--project",
                self.project_name,
                "--local",
            ],
            timeout_seconds=60,
        )
        results = self._normalize_search_results(payload)
        return {"ok": True, "query": query, "results": results, "raw": payload}

    async def recent(self, limit: int = 10) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 50))
        payload = await self._run_json(
            [
                "tool",
                "recent-activity",
                "--page-size",
                str(safe_limit),
                "--project",
                self.project_name,
                "--local",
            ],
            timeout_seconds=60,
        )
        notes = self._normalize_recent(payload)
        return {"ok": True, "notes": notes, "items": notes, "raw": payload}

    async def read_note(self, identifier: str) -> dict[str, Any]:
        if not identifier.strip():
            raise BasicMemoryCommandError("note identifier is required")
        payload = await self._run_json(
            [
                "tool",
                "read-note",
                identifier,
                "--include-frontmatter",
                "--project",
                self.project_name,
                "--local",
            ],
            timeout_seconds=60,
        )
        return self._normalize_note(payload, fallback_identifier=identifier)

    async def write_note(
        self,
        *,
        kind: str,
        source_id: str,
        title: str,
        folder: str,
        content: str,
    ) -> dict[str, Any]:
        ledger_key = f"context:{source_id}" if kind.startswith("context") else f"{kind}:{source_id}"
        ledger = self._read_ledger()
        existing = ledger.get(ledger_key)
        if isinstance(existing, dict) and existing.get("identifier"):
            return {
                "ok": True,
                "status": "already_synced",
                "detail": f"{ledger_key} already synced to Basic Memory.",
                "identifier": existing.get("identifier"),
                "path": existing.get("path"),
                "permalink": existing.get("permalink"),
                "note": existing,
            }

        await self._ensure_setup()

        found = await self._find_existing_by_title(title)
        if found:
            record = self._ledger_record(kind, source_id, found, "already_synced")
            ledger[ledger_key] = record
            self._write_ledger(ledger)
            return {
                "ok": True,
                "status": "already_synced",
                "detail": f"Existing Basic Memory note matched title '{title}'.",
                "identifier": record.get("identifier"),
                "path": record.get("path"),
                "permalink": record.get("permalink"),
                "note": record,
            }

        payload = await self._run_json(
            [
                "tool",
                "write-note",
                "--title",
                title,
                "--folder",
                folder,
                "--project",
                self.project_name,
                "--local",
            ],
            input_text=content,
            timeout_seconds=90,
        )
        normalized = self._normalize_note(payload, fallback_identifier=title)
        action = str(payload.get("action") or "").lower() if isinstance(payload, dict) else ""
        has_error = bool(payload.get("error")) if isinstance(payload, dict) else False
        if action == "conflict" or has_error:
            record = self._ledger_record(kind, source_id, normalized, "already_synced")
            ledger[ledger_key] = record
            self._write_ledger(ledger)
            return {
                "ok": True,
                "status": "already_synced",
                "detail": f"Basic Memory note already exists for '{title}'.",
                "identifier": record.get("identifier"),
                "path": record.get("path"),
                "permalink": record.get("permalink"),
                "note": record,
            }

        record = self._ledger_record(kind, source_id, normalized, "synced")
        ledger[ledger_key] = record
        self._write_ledger(ledger)
        return {
            "ok": True,
            "status": "synced",
            "detail": f"Wrote Basic Memory note for {ledger_key}.",
            "identifier": record.get("identifier"),
            "path": record.get("path"),
            "permalink": record.get("permalink"),
            "note": record,
        }

    async def _ensure_setup(self) -> None:
        projects_payload = await self.list_projects()
        if self._find_project(projects_payload):
            return
        await self.setup()

    async def _find_existing_by_title(self, title: str) -> dict[str, Any] | None:
        try:
            payload = await self._run_json(
                [
                    "tool",
                    "search-notes",
                    title,
                    "--title",
                    "--page-size",
                    "5",
                    "--project",
                    self.project_name,
                    "--local",
                ],
                timeout_seconds=45,
            )
        except Exception:
            return None

        for result in self._normalize_search_results(payload):
            if str(result.get("title") or "").strip().casefold() == title.strip().casefold():
                return result
        return None

    async def _run_json(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
        timeout_seconds: int = 60,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._run_sync,
            args,
            input_text=input_text,
            expect_json=True,
            timeout_seconds=timeout_seconds,
        )

    async def _run_text(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
        timeout_seconds: int = 60,
    ) -> str:
        return await asyncio.to_thread(
            self._run_sync,
            args,
            input_text=input_text,
            expect_json=False,
            timeout_seconds=timeout_seconds,
        )

    async def _run_python_json(
        self,
        args: list[str],
        *,
        timeout_seconds: int = 20,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._run_sync,
            args,
            expect_json=True,
            timeout_seconds=timeout_seconds,
            python=True,
        )

    def _run_sync(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
        expect_json: bool,
        timeout_seconds: int,
        python: bool = False,
    ) -> Any:
        runtime = _resolve_runtime()
        if not runtime:
            raise BasicMemoryCommandError("Basic Memory runtime is not bundled or configured")
        if python:
            if not runtime.python_command:
                raise BasicMemoryCommandError(f"Basic Memory runtime has no Python command: {runtime.kind}")
            command = list(runtime.python_command)
        else:
            command = list(runtime.command)
        command.extend(args)
        env = self._env()
        try:
            log_event(
                logger,
                "adapter_subprocess_started",
                adapter="basic-memory",
                runtime_kind=runtime.kind,
                command_args=args,
                expect_json=expect_json,
                timeout_seconds=timeout_seconds,
                stdin_chars=len(input_text) if input_text is not None else 0,
            )
            result = subprocess.run(
                command,
                input=input_text,
                text=True,
                capture_output=True,
                cwd=str(PROJECT_DIR),
                env=env,
                timeout=timeout_seconds,
                stdin=None if input_text is not None else subprocess.DEVNULL,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            log_event(
                logger,
                "adapter_subprocess_timeout",
                adapter="basic-memory",
                runtime_kind=runtime.kind,
                command_args=args[:3],
                timeout_seconds=timeout_seconds,
            )
            raise BasicMemoryCommandError(f"Command timed out after {timeout_seconds}s: {' '.join(command[:5])}") from exc

        log_event(
            logger,
            "adapter_subprocess_completed",
            adapter="basic-memory",
            runtime_kind=runtime.kind,
            command_args=args[:3],
            returncode=result.returncode,
            stdout_chars=len(result.stdout or ""),
            stderr_chars=len(result.stderr or ""),
        )
        if result.returncode != 0:
            detail = self._safe_error(result.stderr or result.stdout or f"exit={result.returncode}")
            raise BasicMemoryCommandError(detail)

        stdout = result.stdout.strip()
        if not expect_json:
            return stdout
        return self._parse_json(stdout)

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "BASIC_MEMORY_CONFIG_DIR": str(BASIC_MEMORY_CONFIG_DIR),
                "BASIC_MEMORY_NO_PROMOS": "1",
                "BASIC_MEMORY_LOG_LEVEL": "ERROR",
                "PYTHONUNBUFFERED": "1",
            }
        )
        return env

    def _parse_json(self, stdout: str) -> dict[str, Any]:
        if not stdout:
            return {}
        try:
            payload = json.loads(stdout)
            return payload if isinstance(payload, dict) else {"items": payload}
        except json.JSONDecodeError:
            pass

        for index, char in enumerate(stdout):
            if char not in "{[":
                continue
            try:
                payload = json.loads(stdout[index:])
            except json.JSONDecodeError:
                continue
            return payload if isinstance(payload, dict) else {"items": payload}
        raise BasicMemoryCommandError(f"Basic Memory command returned non-JSON output: {self._safe_error(stdout)}")

    def _find_project(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        for item in self._projects(payload):
            name = str(item.get("name") or item.get("project") or "")
            if name == self.project_name:
                return item
        return None

    def _local_projects_config_payload(self) -> dict[str, Any]:
        config_path = BASIC_MEMORY_CONFIG_DIR / "config.json"
        if not config_path.exists():
            return {"projects": []}
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return {"projects": []}
        projects = config.get("projects") if isinstance(config, dict) else None
        if not isinstance(projects, dict):
            return {"projects": []}
        normalized = []
        for name, value in projects.items():
            if not isinstance(value, dict):
                continue
            normalized.append(
                {
                    "name": name,
                    "project": name,
                    "path": value.get("path") or value.get("home"),
                    "mode": value.get("mode"),
                    "raw": value,
                }
            )
        return {"projects": normalized, "source": "config.json"}

    def _projects(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        projects = payload.get("projects") if isinstance(payload, dict) else None
        if isinstance(projects, list):
            return [item for item in projects if isinstance(item, dict)]
        items = payload.get("items") if isinstance(payload, dict) else None
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []

    def _normalize_search_results(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: Any = payload.get("results") or payload.get("items") or payload.get("matches") or []
        if isinstance(candidates, dict):
            candidates = candidates.get("results") or candidates.get("items") or []
        if not isinstance(candidates, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("name") or item.get("entity_title")
            path = item.get("file_path") or item.get("path")
            permalink = item.get("permalink")
            normalized.append(
                {
                    "id": item.get("id") or item.get("identifier") or permalink or path or title,
                    "identifier": item.get("identifier") or permalink or path or title,
                    "title": title,
                    "path": path,
                    "type": item.get("type") or item.get("entity_type") or item.get("content_type"),
                    "score": item.get("score"),
                    "snippet": item.get("snippet") or item.get("content") or item.get("summary"),
                    "content": item.get("content"),
                    "permalink": permalink,
                    "metadata": item.get("metadata") or item.get("frontmatter") or {},
                }
            )
        return normalized

    def _normalize_recent(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: Any = (
            payload.get("results")
            or payload.get("items")
            or payload.get("activity")
            or payload.get("notes")
            or []
        )
        if isinstance(candidates, dict):
            candidates = candidates.get("items") or candidates.get("results") or []
        if not isinstance(candidates, list):
            return []
        return [
            self._normalize_note(item, fallback_identifier=str(index))
            for index, item in enumerate(candidates)
            if isinstance(item, dict)
        ]

    def _normalize_note(self, payload: dict[str, Any], *, fallback_identifier: str | None = None) -> dict[str, Any]:
        title = payload.get("title") or payload.get("name")
        path = payload.get("file_path") or payload.get("path")
        permalink = payload.get("permalink")
        content = payload.get("content") or payload.get("text")
        identifier = payload.get("identifier") or payload.get("id") or permalink or path or title or fallback_identifier
        return {
            "id": identifier,
            "identifier": identifier,
            "title": title or fallback_identifier,
            "path": path,
            "content": content,
            "summary": payload.get("summary") or payload.get("snippet"),
            "kind": payload.get("kind") or payload.get("type"),
            "permalink": permalink,
            "created_at": payload.get("created_at") or payload.get("created"),
            "updated_at": payload.get("updated_at") or payload.get("modified_at") or payload.get("timestamp"),
            "frontmatter": payload.get("frontmatter"),
            "metadata": payload.get("metadata") or payload.get("frontmatter") or {},
        }

    def _ledger_record(
        self,
        kind: str,
        source_id: str,
        note: dict[str, Any],
        status: str,
    ) -> dict[str, Any]:
        return {
            "kind": kind,
            "source_id": source_id,
            "identifier": note.get("identifier") or note.get("id") or note.get("permalink") or note.get("path"),
            "path": note.get("path"),
            "permalink": note.get("permalink"),
            "title": note.get("title"),
            "status": status,
            "synced_at": now_iso(),
        }

    def _read_ledger(self) -> dict[str, Any]:
        if not BASIC_MEMORY_LEDGER_PATH.exists():
            return {}
        try:
            payload = json.loads(BASIC_MEMORY_LEDGER_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_ledger(self, ledger: dict[str, Any]) -> None:
        write_json(BASIC_MEMORY_LEDGER_PATH, ledger)

    def _ensure_query(self, query: str) -> None:
        if not query or not query.strip():
            raise BasicMemoryCommandError("query is required")

    def _service_payload(self, service: ServiceStatus) -> dict[str, Any]:
        return {
            "name": service.name,
            "status": service.status,
            "detail": service.detail,
            "updated_at": service.updated_at,
        }

    def _safe_error(self, value: Any) -> str:
        text = " ".join(str(value).split())
        if len(text) > 500:
            return text[:497] + "..."
        return text


basic_memory_adapter = BasicMemoryAdapter()
