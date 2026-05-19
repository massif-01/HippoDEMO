from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PROJECT_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PROJECT_DIR / ".runtime"
LOG_DIR = RUNTIME_DIR / "logs"
ORCHESTRATOR_LOG_PATH = LOG_DIR / "orchestrator.jsonl"
DEFAULT_LOG_LEVEL = logging.DEBUG
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5
REDACTED = "[REDACTED]"

_HANDLER_MARKER = "_hippo_orchestrator_jsonl_handler"
_SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|bearer|token|secret|password|passwd|credential|cookie|set-cookie|x-api-key|extra[_-]?headers?)",
    re.IGNORECASE,
)
_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|AUTHORIZATION|EXTRA[_-]?HEADERS?)[A-Z0-9_]*)\s*=\s*([^\s,;&]+)"
)
_HEADER_RE = re.compile(
    r"(?i)\b(authorization|x-api-key|api-key|cookie|set-cookie)\s*:\s*([^\r\n,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_SK_RE = re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9._-]{8,}\b")
_URL_RE = re.compile(r"\b(?:https?|wss?)://[^\s\"'<>]+")
_SIGNED_QUERY_KEYS = {
    "signature",
    "x-amz-signature",
    "x-amz-credential",
    "x-amz-security-token",
    "x-goog-signature",
    "x-goog-credential",
    "x-goog-security-token",
    "token",
    "access_token",
    "sig",
    "expires",
    "policy",
    "key-pair-id",
    "x-oss-signature",
    "x-oss-credential",
}
_LOG_RECORD_BUILTINS = set(logging.makeLogRecord({}).__dict__.keys())


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if _SENSITIVE_KEY_RE.search(str(key)):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: str) -> str:
    text = _ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}={REDACTED}", value)
    text = _HEADER_RE.sub(lambda match: f"{match.group(1)}: {REDACTED}", text)
    text = _BEARER_RE.sub(f"Bearer {REDACTED}", text)
    text = _SK_RE.sub(REDACTED, text)
    return _URL_RE.sub(_redact_url_match, text)


def _redact_url_match(match: re.Match[str]) -> str:
    url = match.group(0)
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    if not parsed.query:
        return url
    query = []
    changed = False
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in _SIGNED_QUERY_KEYS:
            query.append((key, REDACTED))
            changed = True
        else:
            query.append((key, value))
    if not changed:
        return url
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


class JsonlFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).astimezone().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _LOG_RECORD_BUILTINS and not key.startswith("_")
        }
        if extras:
            payload.update(redact(extras))
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(
    *,
    log_path: Path | str = ORCHESTRATOR_LOG_PATH,
    level: int | str | None = None,
) -> Path:
    path = Path(log_path)
    resolved_level = _level_from_env() if level is None else level

    logger = logging.getLogger("orchestrator")
    logger.setLevel(resolved_level)
    logger.propagate = False

    for handler in logger.handlers:
        if getattr(handler, _HANDLER_MARKER, False) and Path(getattr(handler, "baseFilename", "")) == path:
            handler.setLevel(resolved_level)
            return path

    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = RotatingFileHandler(
            path,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        handler = logging.NullHandler()
    setattr(handler, _HANDLER_MARKER, True)
    handler.setLevel(resolved_level)
    handler.setFormatter(JsonlFormatter())
    logger.addHandler(handler)
    return path


def _level_from_env() -> int:
    raw = os.environ.get("HIPPODEMO_LOG_LEVEL", "").strip().upper()
    if not raw:
        return DEFAULT_LOG_LEVEL
    return getattr(logging, raw, DEFAULT_LOG_LEVEL)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    extra = {"event": event}
    for key, value in fields.items():
        safe_key = f"field_{key}" if key in _LOG_RECORD_BUILTINS or key in {"message", "asctime"} else key
        extra[safe_key] = value
    logger.info(event, extra=extra)


def tail_log(path: Path | str, *, limit: int = 200) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 1000))
    log_path = Path(path)
    if not log_path.exists():
        return []
    try:
        lines = _tail_lines(log_path, safe_limit)
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = {"message": line}
        entries.append(redact(payload))
    return entries


def _tail_lines(path: Path, limit: int) -> list[str]:
    block_size = 8192
    chunks: list[bytes] = []
    line_count = 0
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        while position > 0 and line_count <= limit:
            read_size = min(block_size, position)
            position -= read_size
            handle.seek(position)
            chunk = handle.read(read_size)
            chunks.append(chunk)
            line_count += chunk.count(b"\n")
    text = b"".join(reversed(chunks)).decode("utf-8", errors="replace")
    return [line.rstrip("\n") for line in text.splitlines()[-limit:] if line.strip()]
