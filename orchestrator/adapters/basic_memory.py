from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from ..models import ServiceStatus


PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_DIR / "orchestrator" / "data" / "basic_memory" / "config"
PROJECT_MEMORY_DIR = PROJECT_DIR / "orchestrator" / "data" / "basic_memory" / "project"
CONFIG_PATH = CONFIG_DIR / "config.json"
CHUNKS_JSONL_PATH = PROJECT_MEMORY_DIR / "memory_context_chunks.jsonl"
CHUNKS_MARKDOWN_DIR = PROJECT_MEMORY_DIR / "chunks"

DEFAULT_CONFIG: dict[str, Any] = {
    "env": "dev",
    "projects": {
        "hippo": {
            "path": str(PROJECT_MEMORY_DIR),
            "mode": "local",
            "workspace_id": None,
            "local_sync_path": None,
            "bisync_initialized": False,
            "last_sync": None,
        }
    },
    "default_project": "hippo",
    "log_level": "ERROR",
    "semantic_search_enabled": True,
    "semantic_embedding_provider": "fastembed",
    "semantic_embedding_model": "bge-small-en-v1.5",
    "semantic_embedding_base_url": None,
    "semantic_embedding_api_key": None,
    "semantic_embedding_api_key_env": "OPENAI_API_KEY",
    "semantic_embedding_dimensions": None,
    "semantic_embedding_batch_size": 2,
    "semantic_embedding_request_concurrency": 4,
    "semantic_embedding_timeout": 30.0,
}


class BasicMemoryAdapter:
    def config(self) -> dict[str, Any]:
        config = self._read_config()
        return self._public_config(config, restart_required=False)

    def update_embedding_config(
        self,
        *,
        semantic_search_enabled: bool | None = None,
        semantic_embedding_provider: str | None = None,
        semantic_embedding_model: str | None = None,
        semantic_embedding_base_url: str | None = None,
        semantic_embedding_api_key: str | None = None,
        semantic_embedding_api_key_env: str | None = None,
        semantic_embedding_dimensions: int | None = None,
        semantic_embedding_batch_size: int | None = None,
        semantic_embedding_request_concurrency: int | None = None,
        semantic_embedding_timeout: float | None = None,
    ) -> dict[str, Any]:
        provider = semantic_embedding_provider.strip().lower() if semantic_embedding_provider else None
        if provider == "openai-compatible":
            provider = "openai"
        if provider is not None and provider not in {"fastembed", "openai"}:
            raise ValueError("semantic_embedding_provider must be fastembed or openai-compatible")
        for key, value in {
            "semantic_embedding_dimensions": semantic_embedding_dimensions,
            "semantic_embedding_batch_size": semantic_embedding_batch_size,
            "semantic_embedding_request_concurrency": semantic_embedding_request_concurrency,
        }.items():
            if value is not None and value <= 0:
                raise ValueError(f"{key} must be greater than 0")
        if semantic_embedding_timeout is not None and semantic_embedding_timeout <= 0:
            raise ValueError("semantic_embedding_timeout must be greater than 0")

        config = self._read_config()
        self._ensure_hippo_project(config)
        updates = {
            "semantic_search_enabled": semantic_search_enabled,
            "semantic_embedding_provider": provider,
            "semantic_embedding_model": semantic_embedding_model,
            "semantic_embedding_base_url": semantic_embedding_base_url,
            "semantic_embedding_api_key_env": semantic_embedding_api_key_env,
            "semantic_embedding_dimensions": semantic_embedding_dimensions,
            "semantic_embedding_batch_size": semantic_embedding_batch_size,
            "semantic_embedding_request_concurrency": semantic_embedding_request_concurrency,
            "semantic_embedding_timeout": semantic_embedding_timeout,
        }
        for key, value in updates.items():
            if value is not None:
                config[key] = value
        if semantic_embedding_api_key is not None:
            config["semantic_embedding_api_key"] = semantic_embedding_api_key

        self._write_config(config)
        return self._public_config(config, restart_required=True)

    def status(self) -> ServiceStatus:
        config = self._read_config()
        provider = str(config.get("semantic_embedding_provider") or "fastembed")
        key_env = str(config.get("semantic_embedding_api_key_env") or "")
        if provider == "openai" and not (config.get("semantic_embedding_api_key") or (key_env and os.getenv(key_env))):
            return ServiceStatus(
                name="basic-memory",
                status="unconfigured",
                detail="OpenAI embedding provider selected without API key or key env",
            )
        return ServiceStatus(
            name="basic-memory",
            status="available" if CONFIG_PATH.exists() else "needs_setup",
            detail=f"embedding_provider={provider}; config={CONFIG_PATH}",
        )

    def write_chunk(self, chunk: Mapping[str, Any]) -> dict[str, Any]:
        payload = self._normalize_chunk(chunk)
        self._write_config(self._read_config())
        CHUNKS_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CHUNKS_JSONL_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        self._write_chunk_markdown(payload)
        return payload

    def search_window(
        self,
        *,
        session_id: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        source: str | None = None,
        query: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        start = self._parse_timestamp(start_at)
        end = self._parse_timestamp(end_at)
        normalized_source = source.strip() if source else None
        normalized_query = query.strip().lower() if query else None
        results: list[dict[str, Any]] = []
        for chunk in self._read_chunks():
            if session_id and chunk.get("session_id") != session_id:
                continue
            if normalized_source and chunk.get("source") != normalized_source:
                continue
            chunk_start = self._parse_timestamp(chunk.get("start_at") or chunk.get("created_at"))
            chunk_end = self._parse_timestamp(chunk.get("end_at") or chunk.get("created_at")) or chunk_start
            if start and chunk_end and chunk_end < start:
                continue
            if end and chunk_start and chunk_start > end:
                continue
            content = str(chunk.get("content") or "")
            if normalized_query and normalized_query not in content.lower():
                metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
                if normalized_query not in json.dumps(metadata, ensure_ascii=False).lower():
                    continue
            results.append(chunk)
        results.sort(key=lambda item: str(item.get("start_at") or item.get("created_at") or ""), reverse=True)
        safe_limit = max(1, min(limit, 200))
        return results[:safe_limit]

    def build_context(
        self,
        *,
        session_id: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        query: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        chunks = list(
            reversed(
                self.search_window(
                    session_id=session_id,
                    start_at=start_at,
                    end_at=end_at,
                    query=query,
                    limit=limit,
                )
            )
        )
        priority = self._context_priority(chunks)
        sections = []
        for chunk in chunks:
            source = chunk.get("source") or "context"
            timestamp = chunk.get("start_at") or chunk.get("created_at") or ""
            content = str(chunk.get("content") or "").strip()
            if not content:
                continue
            sections.append(f"### {source} {timestamp}\n\n{content}")
        return {
            "session_id": session_id,
            "start_at": start_at,
            "end_at": end_at,
            "context_priority": priority,
            "chunks": chunks,
            "content": "\n\n".join(sections).strip(),
            "chunk_count": len(chunks),
        }

    def _read_config(self) -> dict[str, Any]:
        if not CONFIG_PATH.exists():
            return dict(DEFAULT_CONFIG)
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            config = {**DEFAULT_CONFIG, **raw}
            self._ensure_hippo_project(config)
            return config
        except Exception:
            return dict(DEFAULT_CONFIG)

    def _write_config(self, config: dict[str, Any]) -> None:
        self._ensure_hippo_project(config)
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROJECT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    def _ensure_hippo_project(self, config: dict[str, Any]) -> None:
        projects = config.setdefault("projects", {})
        if not isinstance(projects, dict):
            projects = {}
            config["projects"] = projects
        projects.setdefault("hippo", DEFAULT_CONFIG["projects"]["hippo"])
        config.setdefault("default_project", "hippo")

    def _public_config(self, config: dict[str, Any], *, restart_required: bool) -> dict[str, Any]:
        hippo_project = (config.get("projects") or {}).get("hippo") or {}
        key_env = str(config.get("semantic_embedding_api_key_env") or "")
        return {
            "config_path": str(CONFIG_PATH),
            "config_exists": CONFIG_PATH.exists(),
            "project_path": hippo_project.get("path") or str(PROJECT_MEMORY_DIR),
            "default_project": config.get("default_project"),
            "semantic_search_enabled": config.get("semantic_search_enabled"),
            "semantic_embedding_provider": config.get("semantic_embedding_provider"),
            "semantic_embedding_model": config.get("semantic_embedding_model"),
            "semantic_embedding_base_url": config.get("semantic_embedding_base_url"),
            "semantic_embedding_api_key_env": config.get("semantic_embedding_api_key_env"),
            "semantic_embedding_api_key_configured": bool(
                config.get("semantic_embedding_api_key") or (key_env and os.getenv(key_env))
            ),
            "semantic_embedding_dimensions": config.get("semantic_embedding_dimensions"),
            "semantic_embedding_batch_size": config.get("semantic_embedding_batch_size"),
            "semantic_embedding_request_concurrency": config.get("semantic_embedding_request_concurrency"),
            "semantic_embedding_timeout": config.get("semantic_embedding_timeout"),
            "restart_required": restart_required,
        }

    def _normalize_chunk(self, chunk: Mapping[str, Any]) -> dict[str, Any]:
        now = self._now_iso()
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        payload = {
            "id": str(chunk.get("id") or f"mem_{uuid4().hex[:12]}"),
            "session_id": str(chunk.get("session_id") or ""),
            "source": str(chunk.get("source") or "unknown"),
            "start_at": str(chunk.get("start_at") or chunk.get("created_at") or now),
            "end_at": str(chunk.get("end_at") or chunk.get("start_at") or chunk.get("created_at") or now),
            "content": str(chunk.get("content") or ""),
            "metadata": metadata,
            "created_at": str(chunk.get("created_at") or now),
        }
        return payload

    def _write_chunk_markdown(self, payload: Mapping[str, Any]) -> None:
        CHUNKS_MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
        safe_id = str(payload.get("id") or f"mem_{uuid4().hex[:12]}")
        path = CHUNKS_MARKDOWN_DIR / f"{safe_id}.md"
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        frontmatter = {
            "id": payload.get("id"),
            "session_id": payload.get("session_id"),
            "source": payload.get("source"),
            "start_at": payload.get("start_at"),
            "end_at": payload.get("end_at"),
            "created_at": payload.get("created_at"),
            "metadata": metadata,
        }
        content = str(payload.get("content") or "")
        path.write_text(
            "---\n"
            + json.dumps(frontmatter, ensure_ascii=False, indent=2)
            + "\n---\n\n"
            + content
            + "\n",
            encoding="utf-8",
        )

    def _read_chunks(self) -> list[dict[str, Any]]:
        if not CHUNKS_JSONL_PATH.exists():
            return []
        chunks: list[dict[str, Any]] = []
        for line in CHUNKS_JSONL_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                chunks.append(item)
        return chunks

    def _context_priority(self, chunks: list[dict[str, Any]]) -> str:
        sources = {str(chunk.get("source") or "") for chunk in chunks}
        if "video_context" in sources:
            return "video_context"
        if "audio_context" in sources or "ownscribe" in sources:
            return "audio_context"
        if chunks:
            return "memory_context"
        return "empty"

    def _parse_timestamp(self, value: Any) -> datetime | None:
        if not value:
            return None
        try:
            text = str(value)
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat()


basic_memory_adapter = BasicMemoryAdapter()
