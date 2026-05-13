import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI()

VLLM_BASE = os.environ.get("VLLM_BASE_URL", "http://localhost:58000")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "RM-01 VLM")

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _resolve_ffmpeg() -> str | None:
    env_path = os.environ.get("HIPPODEMO_FFMPEG_PATH")
    if env_path and Path(env_path).expanduser().exists():
        return str(Path(env_path).expanduser())
    system_path = shutil.which("ffmpeg")
    if system_path:
        return system_path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _resolve_ffprobe() -> str | None:
    env_path = os.environ.get("HIPPODEMO_FFPROBE_PATH")
    if env_path and Path(env_path).expanduser().exists():
        return str(Path(env_path).expanduser())
    return shutil.which("ffprobe")


def _ffmpeg_command() -> str:
    return _resolve_ffmpeg() or "ffmpeg"


def _probe_video_duration(video_path: str, fallback: float = 0) -> float:
    ffprobe = _resolve_ffprobe()
    if ffprobe:
        try:
            probe = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    video_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if probe.stdout.strip():
                return float(probe.stdout.strip())
        except Exception:
            pass

    try:
        probe = subprocess.run(
            [_ffmpeg_command(), "-i", video_path],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
        output = (probe.stderr or "") + "\n" + (probe.stdout or "")
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
        if match:
            hours, minutes, seconds = match.groups()
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except Exception:
        pass
    return fallback


STORAGE_MODE = os.environ.get("HIPPODEMO_VLMAC_STORAGE", "basic-memory-local")
PROJECT_DIR_CONFIGURED = bool(os.environ.get("HIPPODEMO_BASIC_MEMORY_PROJECT_DIR"))
PROJECT_DIR = Path(
    os.environ.get(
        "HIPPODEMO_BASIC_MEMORY_PROJECT_DIR",
        str(Path(__file__).resolve().parent / "data" / "basic_memory_project"),
    )
).expanduser()
VIDEO_CONTEXT_DIR = PROJECT_DIR / "hippo" / "context" / "video"
VIDEO_CHUNKS_DIR = VIDEO_CONTEXT_DIR / "chunks"
VIDEO_SUMMARIES_DIR = VIDEO_CONTEXT_DIR / "summaries"
ROLLING_CONTEXT_MD = VIDEO_CONTEXT_DIR / "rolling_context.md"
ROLLING_CONTEXT_JSONL = VIDEO_CONTEXT_DIR / "rolling_context.jsonl"
TEXT_EXTENSIONS = {".md", ".json", ".jsonl", ".txt"}
BLOCKED_READ_PARTS = {"chunks"}
IGNORE_PATTERNS = [
    "hippo/context/video/chunks/**/*.webm",
    "hippo/context/video/chunks/**/*.mp4",
    "hippo/context/video/chunks/**/*.mov",
    "hippo/context/video/chunks/**/*.mkv",
    "hippo/context/video/chunks/**/*.jpg",
    "hippo/context/video/chunks/**/*.jpeg",
    "hippo/context/video/chunks/**/*.png",
    "hippo/context/video/chunks/**/*.tmp",
]


def _system_timestamp() -> dict:
    now = datetime.now().astimezone()
    offset = now.strftime("%z")
    timezone_offset = f"{offset[:3]}:{offset[3:]}" if offset else ""
    return {
        "system_time_iso": now.isoformat(timespec="seconds"),
        "epoch_ms": int(now.timestamp() * 1000),
        "timezone": timezone_offset or str(now.tzinfo or ""),
    }


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return cleaned.strip(".-") or "unknown"


def _safe_timestamp(system_time_iso: str) -> str:
    return _safe_component(system_time_iso.replace(":", "-"))


def _storage_ready() -> bool:
    return STORAGE_MODE == "basic-memory-local" and PROJECT_DIR_CONFIGURED and PROJECT_DIR.exists()


def _ensure_storage_dirs() -> None:
    if not PROJECT_DIR_CONFIGURED:
        raise RuntimeError("HIPPODEMO_BASIC_MEMORY_PROJECT_DIR is required for vlmac local storage")
    if not PROJECT_DIR.exists():
        raise RuntimeError(f"Basic Memory project path does not exist: {PROJECT_DIR}")
    VIDEO_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_ignore_rules()


def _ensure_ignore_rules() -> None:
    _append_ignore_patterns(PROJECT_DIR / ".gitignore", "HippoDEMO vlmac binary evidence chunks")
    _append_ignore_patterns(PROJECT_DIR / ".bmignore", "HippoDEMO vlmac binary evidence chunks")


def _append_ignore_patterns(ignore_path: Path, label: str) -> None:
    existing = ignore_path.read_text(encoding="utf-8") if ignore_path.exists() else ""
    additions = [pattern for pattern in IGNORE_PATTERNS if pattern not in existing.splitlines()]
    if not additions:
        return
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    section = f"\n# {label}\n" + "\n".join(additions) + "\n"
    ignore_path.write_text(existing + prefix + section, encoding="utf-8")


def _relative_to_project(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_DIR))
    except ValueError:
        return str(path)


def _unique_stem(base_dir: Path, stem: str, suffixes: list[str]) -> str:
    candidate = stem
    index = 1
    while any((base_dir / f"{candidate}{suffix}").exists() for suffix in suffixes):
        index += 1
        candidate = f"{stem}-{index}"
    return candidate


def _storage_entry(
    *,
    source_id: str,
    prompt: str,
    answer: str,
    duration_seconds: float,
    frames_used: int,
    activity_events_count: int,
    chunk_paths: list[str],
    kind: str,
) -> dict:
    _ensure_storage_dirs()
    stamp = _system_timestamp()
    safe_source = _safe_component(source_id)
    safe_ts = _safe_timestamp(stamp["system_time_iso"])
    summary_dir = VIDEO_SUMMARIES_DIR / safe_source
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_stem = _unique_stem(summary_dir, safe_ts, [".md", ".json"])
    summary_md = summary_dir / f"{summary_stem}.md"
    summary_json = summary_dir / f"{summary_stem}.json"
    rel_summary_md = _relative_to_project(summary_md)
    rel_summary_json = _relative_to_project(summary_json)
    rel_chunks = [_relative_to_project(Path(path)) for path in chunk_paths]
    payload = {
        **stamp,
        "source_type": "video",
        "source_id": source_id,
        "kind": kind,
        "prompt": prompt,
        "answer": answer,
        "duration_seconds": round(float(duration_seconds or 0), 3),
        "frames_used": int(frames_used or 0),
        "summary_path": rel_summary_md,
        "summary_json_path": rel_summary_json,
        "chunk_paths": rel_chunks,
        "activity_events_count": int(activity_events_count or 0),
    }
    summary_md.write_text(
        "\n".join(
            [
                f"# VLMac Video Summary {stamp['system_time_iso']}",
                "",
                "## Source",
                f"- source_id: `{source_id}`",
                f"- kind: {kind}",
                f"- system_time: {stamp['system_time_iso']}",
                f"- epoch_ms: {stamp['epoch_ms']}",
                f"- duration_seconds: {payload['duration_seconds']}",
                f"- frames_used: {payload['frames_used']}",
                f"- activity_events_count: {payload['activity_events_count']}",
                "",
                "## Prompt",
                prompt,
                "",
                "## Summary",
                answer.strip(),
                "",
                "## Evidence Chunks",
                *(f"- `{path}`" for path in rel_chunks),
                "",
            ]
        ),
        encoding="utf-8",
    )
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    rolling_section = (
        f"## {stamp['system_time_iso']} [video:{source_id}]\n\n"
        f"- epoch_ms: {stamp['epoch_ms']}\n"
        f"- timezone: {stamp['timezone']}\n"
        f"- duration_seconds: {payload['duration_seconds']}\n"
        f"- frames_used: {payload['frames_used']}\n"
        f"- activity_events_count: {payload['activity_events_count']}\n"
        f"- summary_path: `{rel_summary_md}`\n"
        f"- chunk_paths: {', '.join(f'`{path}`' for path in rel_chunks) if rel_chunks else 'none'}\n\n"
        f"{answer.strip()}\n\n---\n\n"
    )
    with ROLLING_CONTEXT_MD.open("a", encoding="utf-8") as handle:
        handle.write(rolling_section)
    with ROLLING_CONTEXT_JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


def _save_video_chunk(source_id: str, video_bytes: bytes, ext: str, metadata: dict | None = None) -> Path:
    _ensure_storage_dirs()
    stamp = _system_timestamp()
    safe_source = _safe_component(source_id)
    safe_ts = _safe_timestamp(stamp["system_time_iso"])
    chunk_dir = VIDEO_CHUNKS_DIR / safe_source
    chunk_dir.mkdir(parents=True, exist_ok=True)
    safe_ext = _safe_component(ext.lstrip(".") or "webm")
    chunk_stem = _unique_stem(chunk_dir, safe_ts, [f".{safe_ext}"])
    chunk_path = chunk_dir / f"{chunk_stem}.{safe_ext}"
    chunk_path.write_bytes(video_bytes)
    manifest = {
        **stamp,
        "source_id": source_id,
        "chunk_path": _relative_to_project(chunk_path),
        "size_bytes": len(video_bytes),
        **(metadata or {}),
    }
    with (chunk_dir / "manifest.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, ensure_ascii=False) + "\n")
    return chunk_path


def _list_storage(kind: str, limit: int) -> list[dict]:
    if not PROJECT_DIR.exists():
        return []
    if kind == "video_chunk":
        roots = [VIDEO_CHUNKS_DIR]
        patterns = ["*.webm", "*.mp4", "*.mov", "*.mkv", "manifest.jsonl"]
    elif kind == "rolling_context":
        roots = [VIDEO_CONTEXT_DIR]
        patterns = ["rolling_context.md", "rolling_context.jsonl"]
    else:
        roots = [VIDEO_SUMMARIES_DIR]
        patterns = ["*.md", "*.json"]
    items: list[dict] = []
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            for path in root.rglob(pattern):
                if not path.is_file():
                    continue
                stat = path.stat()
                items.append(
                    {
                        "name": _relative_to_project(path),
                        "path": _relative_to_project(path),
                        "size": stat.st_size,
                        "last_modified": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                    }
                )
    items.sort(key=lambda item: item["last_modified"], reverse=True)
    return items[: max(1, min(int(limit), 500))]


def _safe_text_path(path_value: str) -> Path:
    candidate = (PROJECT_DIR / path_value).resolve()
    project_root = PROJECT_DIR.resolve()
    context_root = (PROJECT_DIR / "hippo" / "context").resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("Access denied") from exc
    try:
        candidate.relative_to(context_root)
    except ValueError as exc:
        raise ValueError("Only hippo/context text files can be read") from exc
    rel_parts = set(candidate.relative_to(project_root).parts)
    if rel_parts & BLOCKED_READ_PARTS:
        raise ValueError("Reading binary chunk storage is not allowed")
    if candidate.suffix.lower() not in TEXT_EXTENSIONS:
        raise ValueError("Only text storage files can be read")
    return candidate


@app.get("/api/storage/status")
async def api_storage_status():
    return {
        "ok": _storage_ready(),
        "storage": STORAGE_MODE,
        "project_path_configured": PROJECT_DIR_CONFIGURED,
        "project_path": str(PROJECT_DIR),
        "video_context_path": str(VIDEO_CONTEXT_DIR),
        "rolling_context_md": str(ROLLING_CONTEXT_MD),
        "rolling_context_jsonl": str(ROLLING_CONTEXT_JSONL),
    }


@app.get("/api/storage/list")
async def api_storage_list(kind: str = "video_summary", limit: int = 50):
    return {"objects": _list_storage(kind, limit), "kind": kind}


@app.get("/api/storage/read")
async def api_storage_read(path: str):
    try:
        text_path = _safe_text_path(path)
        return {"path": _relative_to_project(text_path), "content": text_path.read_text(encoding="utf-8", errors="replace")}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/storage/stats")
async def api_storage_stats():
    objects = _list_storage("video_summary", 500) + _list_storage("rolling_context", 500)
    total_size = sum(int(item.get("size") or 0) for item in objects)
    return {"count": len(objects), "total_size": total_size, "project_path": str(PROJECT_DIR)}


@app.get("/api/minio/list")
async def api_minio_list(limit: int = 50):
    """Compatibility alias for the legacy /api/minio/list route."""
    return await api_storage_list(kind="video_summary", limit=limit)


@app.get("/api/minio/read")
async def api_minio_read(path: str):
    """Compatibility alias for the legacy /api/minio/read route."""
    return await api_storage_read(path)


@app.get("/api/minio/stats")
async def api_minio_stats():
    """Compatibility alias for the legacy /api/minio/stats route."""
    return await api_storage_stats()


# ---- Capture manager (shared per device) ----
class CaptureManager:
    """Shared capture instance per device. Multiple tasks reference the same manager."""
    def __init__(self, device: str, resolution: str, bitrate: str):
        self.device = device
        self.resolution = resolution
        self.bitrate = bitrate
        self.ref_count = 0
        self.video_path = f"/tmp/vlmac_capture_{device.replace('/', '_')}_{os.getpid()}.webm"

    async def capture_segment(self, duration: int) -> bytes | None:
        """Capture a video segment using ffmpeg from V4L2 device."""
        w, h = self.resolution.split("x")
        cmd = [
            _ffmpeg_command(), "-y",
            "-f", "v4l2",
            "-video_size", f"{w}x{h}",
            "-i", self.device,
            "-t", str(duration),
            "-c:v", "libvpx-vp9",
            "-b:v", self.bitrate,
            "-an",
            self.video_path,
            "-loglevel", "error",
        ]
        loop = asyncio.get_event_loop()
        try:
            proc = await loop.run_in_executor(None, lambda: subprocess.run(
                cmd, capture_output=True, timeout=duration + 30,
                stdin=subprocess.DEVNULL,
            ))
            if proc.returncode != 0:
                print(f"[capture:{self.device}] ffmpeg error: {proc.stderr.decode()[:300]}")
                return None
            with open(self.video_path, "rb") as f:
                return f.read()
        except Exception as e:
            print(f"[capture:{self.device}] Error: {e}")
            return None


# Global capture managers: device_path → CaptureManager
capture_managers: dict[str, CaptureManager] = {}


def get_capture_manager(device: str, resolution: str, bitrate: str) -> CaptureManager:
    """Get or create a shared CaptureManager for a device."""
    if device not in capture_managers:
        capture_managers[device] = CaptureManager(device, resolution, bitrate)
    cm = capture_managers[device]
    cm.ref_count += 1
    return cm


def release_capture_manager(device: str):
    """Decrement ref count; remove if no tasks reference it."""
    if device in capture_managers:
        cm = capture_managers[device]
        cm.ref_count -= 1
        if cm.ref_count <= 0:
            del capture_managers[device]
            print(f"[capture:{device}] Released (no more tasks)")


DEFAULT_SYSTEM_PROMPT = (
    "你是一个敏锐的视觉观察助手。你会收到一段连续视频流中按时间顺序排列的帧截图。"
    "每帧标注了时间戳和前端检测到的画面像素变化区域及比例。\n"
    "请你特别注意：\n"
    "1. 前后帧之间的具体视觉差异（内容变化、位移、出现/消失的元素等）\n"
    "2. 人物的动作和表情变化\n"
    "3. 画面中元素的任何状态变化\n"
    "注意：帧标注仅描述像素层面的变化范围，不代表具体操作类型。"
    "请根据你自己的视觉分析来判断实际发生了什么。"
)


class TaskState:
    """Lightweight per-task config — shares capture with other tasks on same device."""
    def __init__(self, task_id: str, device: str, resolution: str = "1920x1080",
                 bitrate: str = "1M", interval: int = 30,
                 scene_threshold: float = 0.05, min_interval: float = 3.0,
                 timer_prompt: str = "请描述当前画面中的内容和变化。",
                 system_prompt: str = ""):
        self.task_id = task_id
        self.device = device
        self.resolution = resolution
        self.bitrate = bitrate
        self.interval = interval
        self.scene_threshold = scene_threshold
        self.min_interval = min_interval
        self.timer_prompt = timer_prompt
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.running = False
        self.created_at = datetime.now(timezone.utc)
        self.session_filename = f"task_{task_id}.md"
        self.query_count = 0
        self.results: list[dict] = []
        self.timer_task: asyncio.Task | None = None
        self.capture: CaptureManager | None = None


# Global task registry
tasks: dict[str, TaskState] = {}


class CreateTaskRequest(BaseModel):
    device: str = Field("", description="V4L2 device path, e.g. /dev/video0")
    resolution: str = Field("1920x1080", description="Capture resolution WxH")
    interval: int = Field(30, description="Timer interval in seconds", ge=5, le=3600)
    scene_threshold: float = Field(0.05, description="Scene change detection threshold (0-1)", ge=0.01, le=1.0)
    min_interval: float = Field(3.0, description="Baseline sampling interval in seconds", ge=0.5, le=60.0)
    bitrate: str = Field("1M", description="Video encoding bitrate, e.g. 500K, 1M, 2M")
    timer_prompt: str = Field("请描述当前画面中的内容和变化。", description="Prompt sent each interval")
    system_prompt: str = Field("", description="System prompt (empty = use default)")


def list_v4l2_devices() -> list[dict]:
    """List available V4L2 video capture devices."""
    devices = []
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--list-devices"],
            capture_output=True, text=True, timeout=5,
        )
        current_name = ""
        for line in result.stdout.splitlines():
            line = line.rstrip()
            if not line:
                continue
            if not line.startswith("\t"):
                current_name = line.rstrip(":")
            else:
                dev_path = line.strip()
                if dev_path.startswith("/dev/video"):
                    devices.append({"name": current_name, "path": dev_path})
    except Exception as e:
        print(f"[v4l2] Error listing devices: {e}")
    return devices


@app.get("/api/devices")
async def api_devices():
    """List available UVC/V4L2 video devices."""
    return {"devices": list_v4l2_devices()}


@app.get("/api/tasks")
async def api_tasks():
    """List all tasks."""
    result = []
    for t in tasks.values():
        result.append({
            "task_id": t.task_id,
            "running": t.running,
            "device": t.device,
            "resolution": t.resolution,
            "interval": t.interval,
            "scene_threshold": t.scene_threshold,
            "min_interval": t.min_interval,
            "bitrate": t.bitrate,
            "timer_prompt": t.timer_prompt,
            "system_prompt": t.system_prompt[:200],
            "results_count": len(t.results),
            "query_count": t.query_count,
            "created_at": t.created_at.isoformat(),
            "session_filename": t.session_filename,
        })
    return {"tasks": result}


@app.get("/api/tasks/{task_id}")
async def api_task_detail(task_id: str):
    """Get details of a specific task."""
    t = tasks.get(task_id)
    if not t:
        return {"error": "Task not found"}
    return {
        "task_id": t.task_id,
        "running": t.running,
        "device": t.device,
        "resolution": t.resolution,
        "interval": t.interval,
        "scene_threshold": t.scene_threshold,
        "min_interval": t.min_interval,
        "bitrate": t.bitrate,
        "timer_prompt": t.timer_prompt,
        "system_prompt": t.system_prompt[:200],
        "results_count": len(t.results),
        "query_count": t.query_count,
        "created_at": t.created_at.isoformat(),
        "session_filename": t.session_filename,
    }


@app.post("/api/tasks")
async def api_create_task(req: CreateTaskRequest):
    """Create and start a new task."""
    device = req.device
    if not device:
        devs = list_v4l2_devices()
        if not devs:
            return {"error": "No V4L2 devices found"}
        device = devs[0]["path"]

    task_id = uuid.uuid4().hex[:8]
    task = TaskState(
        task_id=task_id,
        device=device,
        resolution=req.resolution,
        bitrate=req.bitrate,
        interval=req.interval,
        scene_threshold=req.scene_threshold,
        min_interval=req.min_interval,
        timer_prompt=req.timer_prompt,
        system_prompt=req.system_prompt,
    )
    task.capture = get_capture_manager(device, req.resolution, req.bitrate)
    task.running = True
    tasks[task_id] = task

    # Start the task loop
    task.timer_task = asyncio.create_task(_task_loop(task_id))

    return {
        "task_id": task_id,
        "status": "started",
        "device": device,
        "resolution": task.resolution,
        "interval": task.interval,
        "scene_threshold": task.scene_threshold,
        "min_interval": task.min_interval,
        "bitrate": task.bitrate,
    }


@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: str):
    """Stop and remove a task."""
    task = tasks.get(task_id)
    if not task:
        return {"error": "Task not found"}

    task.running = False
    if task.timer_task:
        task.timer_task.cancel()
        try:
            await task.timer_task
        except asyncio.CancelledError:
            pass
        task.timer_task = None

    if task.device:
        release_capture_manager(task.device)

    del tasks[task_id]
    return {"status": "stopped", "task_id": task_id}


@app.get("/api/tasks/{task_id}/results")
async def api_task_results(task_id: str, limit: int = 10):
    """Get recent results for a task."""
    task = tasks.get(task_id)
    if not task:
        return {"error": "Task not found"}
    return {"results": task.results[-limit:]}


# ---- Backward compat: /api/status, /api/start, /api/stop, /api/results ----
@app.get("/api/status")
async def api_status():
    """Get summary status of all tasks."""
    running = [t for t in tasks.values() if t.running]
    return {
        "running": len(running) > 0,
        "tasks_count": len(tasks),
        "running_count": len(running),
        "tasks": [{"task_id": t.task_id, "device": t.device, "interval": t.interval} for t in running],
    }


@app.post("/api/start")
async def api_start_compat(req: CreateTaskRequest):
    """Create a task (backward compatible)."""
    return await api_create_task(req)


@app.post("/api/stop")
async def api_stop_compat():
    """Stop all running tasks (backward compatible)."""
    stopped = []
    for task_id in list(tasks.keys()):
        result = await api_delete_task(task_id)
        stopped.append(result)
    return {"status": "stopped", "stopped": stopped}


@app.get("/api/results")
async def api_results(limit: int = 10):
    """Get recent results from all tasks (backward compatible)."""
    all_results = []
    for t in tasks.values():
        for r in t.results:
            r_copy = dict(r)
            r_copy["task_id"] = t.task_id
            all_results.append(r_copy)
    all_results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"results": all_results[:limit]}


async def _task_loop(task_id: str):
    """Main loop for a task: capture video → extract frames → query VLM → save to local Hippo context."""
    task = tasks.get(task_id)
    if not task or not task.capture:
        return
    client = httpx.AsyncClient()
    try:
        while task.running:
            print(f"[task:{task_id}] Capturing {task.interval}s from {task.device}...")

            video_bytes = await task.capture.capture_segment(task.interval)
            if not video_bytes:
                print(f"[task:{task_id}] No video captured, retrying in 5s...")
                await asyncio.sleep(5)
                continue

            print(f"[task:{task_id}] Captured {len(video_bytes)/1024/1024:.1f}MB")
            source_id = f"task_{task_id}"
            chunk_path = _save_video_chunk(
                source_id,
                video_bytes,
                "webm",
                {
                    "kind": "headless_task",
                    "device": task.device,
                    "duration_seconds": task.interval,
                },
            )

            # Extract frames
            frames, annotations, stats = await extract_frames_from_bytes(
                video_bytes, "webm",
                scene_threshold=task.scene_threshold,
                min_interval=task.min_interval,
                activity_events=[], video_duration=task.interval,
            )

            if not frames:
                print(f"[task:{task_id}] No frames extracted, retrying...")
                await asyncio.sleep(5)
                continue

            actual_dur = stats.get("actual_duration", task.interval)
            n_sub = stats.get("submitted", len(frames))

            # Build VLM messages
            messages = [{"role": "system", "content": task.system_prompt}]
            content_parts = []
            header = f"[以下是从最近 {round(actual_dur)}秒 视频流中提取的 {n_sub} 个关键帧。]"
            content_parts.append({"type": "text", "text": header})
            for i, fb64 in enumerate(frames):
                ann = annotations[i] if i < len(annotations) else f"[帧{i+1}/{len(frames)}]"
                content_parts.append({"type": "text", "text": ann})
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{fb64}"},
                })
            content_parts.append({"type": "text", "text": task.timer_prompt})
            messages.append({"role": "user", "content": content_parts})

            # Call VLM (non-streaming for headless)
            print(f"[task:{task_id}] Querying VLM with {len(frames)} frames...")
            try:
                resp = await client.post(
                    f"{VLLM_BASE}/v1/chat/completions",
                    json={
                        "model": VLLM_MODEL,
                        "messages": messages,
                        "max_tokens": 2048,
                        "temperature": 0.7,
                    },
                    timeout=120.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data["choices"][0]["message"]["content"]
                else:
                    answer = f"[VLM error {resp.status_code}]: {resp.text[:300]}"
                    print(f"[task:{task_id}] {answer}")
            except Exception as e:
                answer = f"[VLM error]: {e}"
                print(f"[task:{task_id}] {answer}")

            # Save to local Basic Memory project context.
            task.query_count += 1
            storage_payload = {}
            try:
                storage_payload = _storage_entry(
                    source_id=source_id,
                    prompt=task.timer_prompt,
                    answer=answer,
                    duration_seconds=actual_dur,
                    frames_used=n_sub,
                    activity_events_count=0,
                    chunk_paths=[str(chunk_path)],
                    kind="headless_task",
                )
                print(f"[task:{task_id}] Result saved: {storage_payload.get('summary_path')}")
            except Exception as e:
                print(f"[task:{task_id}] storage save error: {e}")

            result = {
                "timestamp": storage_payload.get("system_time_iso") or datetime.now().astimezone().isoformat(timespec="seconds"),
                "frames": n_sub,
                "duration": round(actual_dur, 1),
                "answer": answer[:500],
                "summary_path": storage_payload.get("summary_path", ""),
                "chunk_paths": storage_payload.get("chunk_paths", []),
            }
            task.results.append(result)
            if len(task.results) > 100:
                task.results = task.results[-100:]

            print(f"[task:{task_id}] Cycle complete. Answer: {answer[:100]}...")

    except asyncio.CancelledError:
        print(f"[task:{task_id}] Task cancelled")
    except Exception as e:
        print(f"[task:{task_id}] Loop error: {e}")
    finally:
        await client.aclose()
        task.running = False


async def stream_vlm_response(
    client: httpx.AsyncClient,
    messages: list[dict],
    ws: WebSocket,
    req_id: str,
):
    """Send messages to vLLM and stream tokens back via WebSocket."""
    payload = {
        "model": VLLM_MODEL,
        "messages": messages,
        "max_tokens": 2048,
        "stream": True,
        "temperature": 0.7,
    }

    full_text = ""
    try:
        async with client.stream(
            "POST",
            f"{VLLM_BASE}/v1/chat/completions",
            json=payload,
            timeout=120.0,
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                await ws.send_json(
                    {"type": "error", "id": req_id, "text": f"vLLM error {resp.status_code}: {body.decode()[:500]}"}
                )
                return ""

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0]["delta"]
                    token = delta.get("content", "")
                    if token:
                        full_text += token
                        await ws.send_json({"type": "token", "id": req_id, "text": token})
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    except httpx.ReadTimeout:
        await ws.send_json({"type": "error", "id": req_id, "text": "vLLM request timed out"})
    except Exception as e:
        await ws.send_json({"type": "error", "id": req_id, "text": str(e)})

    await ws.send_json({"type": "done", "id": req_id})
    return full_text


# ---- Activity event helpers ----

MAX_FRAMES = 50  # Hard cap — VLM can't handle hundreds of images


def _smart_downsample(
    total: int, max_n: int,
    activity_events: list[dict] | None,
    video_duration: float,
) -> list[int]:
    """Pick up to max_n indices from [0..total), prioritising event-adjacent frames."""
    if total <= max_n:
        return list(range(total))

    # Score each frame by proximity to activity events
    scores = [0.0] * total
    if activity_events and video_duration > 0:
        for ev in activity_events:
            t = ev.get("t", 0)
            idx = int(t / video_duration * total)
            idx = max(0, min(total - 1, idx))
            intensity = ev.get("intensity", 5)
            for offset in range(-2, 3):
                j = idx + offset
                if 0 <= j < total:
                    scores[j] += intensity / (1 + abs(offset))

    # Always keep first and last
    selected = {0, total - 1}

    # Greedily pick highest-scored frames, enforcing min gap
    min_gap = max(1, total // max_n)
    ranked = sorted(range(total), key=lambda i: scores[i], reverse=True)
    for i in ranked:
        if len(selected) >= max_n:
            break
        if all(abs(i - s) >= min_gap for s in selected):
            selected.add(i)

    # Fill remaining slots uniformly
    if len(selected) < max_n:
        step = total / (max_n - len(selected) + 1)
        pos = step
        while len(selected) < max_n and pos < total:
            idx = int(pos)
            if idx not in selected:
                selected.add(idx)
            pos += step

    return sorted(selected)


def _annotate_frames(
    indices: list[int],
    total_extracted: int,
    activity_events: list[dict] | None,
    video_duration: float,
) -> list[str]:
    """Create text annotations for each selected frame."""
    n = len(indices)
    annotations = []
    for rank, idx in enumerate(indices):
        # Estimate timestamp from position
        t = video_duration * idx / max(total_extracted - 1, 1) if video_duration > 0 else 0
        label = f"[帧{rank+1}/{n} @{t:.1f}s"
        if activity_events:
            nearby = sorted(
                [e for e in activity_events if abs(e.get("t", 0) - t) <= 1.5],
                key=lambda e: abs(e.get("t", 0) - t),
            )
            if nearby:
                descs, seen = [], set()
                for e in nearby[:3]:
                    d = e.get("desc", e.get("type", ""))
                    if d and d not in seen:
                        descs.append(d)
                        seen.add(d)
                if descs:
                    label += f" — {'; '.join(descs)}"
        label += "]"
        annotations.append(label)
    return annotations


async def extract_frames_from_bytes(
    video_bytes: bytes, ext: str,
    scene_threshold: float = 0.05,
    min_interval: float = 3.0,
    activity_events: list[dict] | None = None,
    video_duration: float = 0,
) -> tuple[list[str], list[str], dict]:
    """Extract key frames via scene detection + activity-event-driven selection.

    When activity events exist: frames are extracted near event timestamps
    (content-driven), with a sparse gap-filler for quiet sections.
    When no events: very sparse periodic baseline (scene detection primary).

    Returns (frames_b64, annotations, stats).
    """
    loop = asyncio.get_event_loop()

    def _extract():
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, f"input.{ext}")
            with open(video_path, "wb") as f:
                f.write(video_bytes)
            size_mb = len(video_bytes) / 1024 / 1024
            n_events = len(activity_events) if activity_events else 0

            actual_duration = _probe_video_duration(video_path, video_duration)

            print(f"[extract] Video: {size_mb:.1f}MB, ext={ext}, "
                  f"threshold={scene_threshold}, interval={min_interval}s, "
                  f"events={n_events}, duration={actual_duration:.1f}s")

            # ---- Adaptive select filter ----
            # Cluster activity event timestamps (merge within 2s)
            event_times: list[float] = []
            if activity_events and actual_duration > 0:
                raw = sorted(set(round(ev.get("t", 0), 1) for ev in activity_events))
                for t in raw:
                    if event_times and t - event_times[-1] < 2.0:
                        continue
                    event_times.append(t)
                event_times = event_times[:20]  # Cap filter complexity

            select_parts = [f"eq(n\\,0)", f"gt(scene\\,{scene_threshold})"]

            if event_times:
                # Event-driven mode: extract frames near detected changes
                for t in event_times:
                    lo = max(0, t - 0.5)
                    hi = t + 0.5
                    select_parts.append(f"between(t\\,{lo:.1f}\\,{hi:.1f})")
                # Sparse gap-filler for quiet sections
                gap_fill = max(min_interval * 3, 15.0)
                select_parts.append(f"gte(t-prev_selected_t\\,{gap_fill:.1f})")
                print(f"[extract] Event-driven mode: {len(event_times)} event clusters, "
                      f"gap-fill={gap_fill:.0f}s")
            else:
                # No events (static scene): very sparse periodic baseline
                sparse = max(min_interval * 2, 8.0)
                if actual_duration > 0:
                    sparse = max(sparse, actual_duration / 4)
                select_parts.append(f"gte(t-prev_selected_t\\,{sparse:.1f})")
                print(f"[extract] Sparse periodic mode: interval={sparse:.1f}s (no events)")

            select_expr = "+".join(select_parts)
            vf = (
                f"select='{select_expr}',"
                f"scale='min(1024,iw)':'-1'"
            )
            out_pattern = os.path.join(tmpdir, "key_%06d.jpg")
            cmd = [
                _ffmpeg_command(), "-i", video_path,
                "-vf", vf, "-vsync", "vfr",
                "-q:v", "3", out_pattern,
                "-y", "-loglevel", "error",
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=600,
                                    stdin=subprocess.DEVNULL)
            if result.returncode != 0:
                print(f"[extract] ffmpeg error: {result.stderr.decode()[:500]}")

            key_files = sorted(
                f for f in os.listdir(tmpdir)
                if f.startswith("key_") and f.endswith(".jpg")
            )
            total_extracted = len(key_files)
            print(f"[extract] Scene+event extracted {total_extracted} frames"
                  f" ({len(event_times)} event clusters)")

            # Fallback: 0.5fps if nothing extracted
            if total_extracted == 0:
                fb_pattern = os.path.join(tmpdir, "fb_%06d.jpg")
                fb_cmd = [
                    _ffmpeg_command(), "-i", video_path, "-vf",
                    "fps=0.5,scale='min(1024,iw)':'-1'",
                    "-q:v", "3",
                    fb_pattern, "-y", "-loglevel", "error",
                ]
                subprocess.run(fb_cmd, capture_output=True, timeout=300,
                               stdin=subprocess.DEVNULL)
                key_files = sorted(
                    f for f in os.listdir(tmpdir)
                    if f.startswith("fb_") and f.endswith(".jpg")
                )
                total_extracted = len(key_files)
                print(f"[extract] Fallback 0.5fps: {total_extracted} frames")

            # Smart downsample: prefer frames near activity events
            selected_indices = _smart_downsample(
                total_extracted, MAX_FRAMES,
                activity_events, actual_duration,
            )
            selected_files = [key_files[i] for i in selected_indices]
            capped = total_extracted > MAX_FRAMES

            annotations = _annotate_frames(
                selected_indices, total_extracted,
                activity_events, actual_duration,
            )

            frames = []
            for fname in selected_files:
                with open(os.path.join(tmpdir, fname), "rb") as f:
                    frames.append(base64.b64encode(f.read()).decode())

            stats = {
                "total_extracted": total_extracted,
                "submitted": len(frames),
                "capped": capped,
                "activity_events": n_events,
                "actual_duration": round(actual_duration, 1),
            }
            if capped:
                print(f"[extract] Downsampled {total_extracted} → {len(frames)} "
                      f"(prioritised {n_events} events)")
            print(f"[extract] Submitting {len(frames)} frames")
            return frames, annotations, stats

    try:
        return await loop.run_in_executor(None, _extract)
    except Exception as e:
        print(f"[extract_frames] Error: {e}")
        return [], [], {"error": str(e)}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    # Session-level local storage source id.
    session_start = datetime.now(timezone.utc)
    session_source_id = f"session_{session_start.strftime('%Y%m%d_%H%M%S')}"
    session_query_count = 0

    # Video stream accumulation: raw bytes from MediaRecorder chunks
    video_chunks: list[bytes] = []
    video_start_time: float = 0
    video_mime: str = "video/webm"

    # Activity events pushed from frontend diff engine
    server_activity_events: list[dict] = []

    # Conversation history (text only, images not repeated)
    history: list[dict] = []
    max_history = 20

    # Lock to prevent concurrent VLM queries
    query_lock = asyncio.Lock()

    client = httpx.AsyncClient()

    # Per-connection timed tasks (share video_chunks buffer)
    ws_tasks: dict[str, asyncio.Task] = {}
    ws_task_configs: dict[str, dict] = {}  # task_id → config

    async def _take_buffer_snapshot():
        """Take a snapshot of the current video buffer and reset it. Returns (bytes, ext, duration, events)."""
        nonlocal video_chunks, video_start_time, server_activity_events
        if not video_chunks:
            return None, "video/webm", 0, []
        video_bytes = b"".join(video_chunks)
        ext = "webm" if "webm" in video_mime else "mp4"
        duration = time.time() - video_start_time if video_start_time else 0
        events = server_activity_events[:]
        video_chunks.clear()
        video_start_time = 0
        server_activity_events.clear()
        return video_bytes, ext, duration, events

    async def _ws_task_loop(task_id: str):
        """Per-connection task loop: periodically consume video buffer and query VLM."""
        nonlocal session_query_count
        cfg = ws_task_configs.get(task_id)
        if not cfg:
            return
        task_query_count = 0
        try:
            while task_id in ws_task_configs:
                await asyncio.sleep(cfg["interval"])
                if task_id not in ws_task_configs:
                    break
                if not video_chunks:
                    continue

                video_bytes, ext, duration, events = await _take_buffer_snapshot()
                if not video_bytes:
                    continue
                await ws.send_json({"type": "stream_reset"})

                print(f"[ws_task:{task_id}] Processing {len(video_bytes)/1024:.0f}KB, {duration:.1f}s, {len(events)} events")
                source_id = f"ws_task_{task_id}"
                chunk_path = _save_video_chunk(
                    source_id,
                    video_bytes,
                    ext,
                    {
                        "kind": "ws_timed_task",
                        "duration_seconds": duration,
                        "activity_events_count": len(events),
                    },
                )

                frames, annotations, stats = await extract_frames_from_bytes(
                    video_bytes, ext,
                    scene_threshold=cfg.get("scene_threshold", 0.05),
                    min_interval=cfg.get("min_interval", 3.0),
                    activity_events=events, video_duration=duration)

                if not frames:
                    continue

                actual_dur = stats.get("actual_duration", duration)
                n_sub = stats.get("submitted", len(frames))

                # Build VLM messages
                messages = [{"role": "system", "content": cfg.get("system_prompt", DEFAULT_SYSTEM_PROMPT)}]
                content_parts = []
                header = f"[以下是从最近 {round(actual_dur)}秒 视频流中提取的 {n_sub} 个关键帧。]"
                content_parts.append({"type": "text", "text": header})
                for i, fb64 in enumerate(frames):
                    ann = annotations[i] if i < len(annotations) else f"[帧{i+1}/{len(frames)}]"
                    content_parts.append({"type": "text", "text": ann})
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{fb64}"},
                    })
                content_parts.append({"type": "text", "text": cfg["prompt"]})
                messages.append({"role": "user", "content": content_parts})

                # Notify frontend
                req_id = f"task_{task_id}_{task_query_count}"
                await ws.send_json({
                    "type": "task_start", "task_id": task_id, "id": req_id,
                    "frames_used": len(frames),
                    "video_duration": round(actual_dur, 1),
                    "activity_events": len(events),
                })

                # Stream response via WS
                response_text = await stream_vlm_response(client, messages, ws, req_id)
                task_query_count += 1

                # Save to local Basic Memory project context.
                if response_text:
                    try:
                        session_query_count += 1
                        _storage_entry(
                            source_id=source_id,
                            prompt=cfg["prompt"],
                            answer=response_text,
                            duration_seconds=actual_dur,
                            frames_used=n_sub,
                            activity_events_count=len(events),
                            chunk_paths=[str(chunk_path)],
                            kind="ws_timed_task",
                        )
                    except Exception as e:
                        print(f"[ws_task:{task_id}] storage error: {e}")

                await ws.send_json({
                    "type": "task_result", "task_id": task_id, "id": req_id,
                    "query_count": task_query_count,
                })
                print(f"[ws_task:{task_id}] Query {task_query_count} done: {response_text[:80]}...")

        except asyncio.CancelledError:
            print(f"[ws_task:{task_id}] Cancelled")
        except Exception as e:
            print(f"[ws_task:{task_id}] Error: {e}")
            try:
                await ws.send_json({"type": "task_error", "task_id": task_id, "text": str(e)})
            except Exception:
                pass

    async def _handle_query(msg):
        """Process buffered video from browser, extract frames, query VLM, stream response."""
        nonlocal video_chunks, video_start_time, session_query_count

        user_text = msg.get("text", "请分析视频内容")
        system_prompt = msg.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        req_id = msg.get("id", str(time.time()))
        scene_threshold = msg.get("scene_threshold", 0.05)
        min_interval_val = msg.get("min_interval", 3.0)
        activity_events = msg.get("activity_events", [])
        no_history = msg.get("no_history", False)

        frames = []
        annotations = []
        video_duration = 0
        extract_stats = {}
        merged_events = activity_events
        chunk_path: Path | None = None

        snapshot_bytes, ext, video_duration, snapshot_events = await _take_buffer_snapshot()
        if snapshot_bytes:
            await ws.send_json({"type": "stream_reset"})

            if ext == "webm" and snapshot_bytes[:4] != b'\x1a\x45\xdf\xa3':
                print(f"[extract] WARNING: WebM EBML header unexpected "
                      f"({len(snapshot_bytes)} bytes, first 8: {snapshot_bytes[:8].hex()})")

            # Merge client-sent events with server-accumulated events
            merged_events = activity_events + snapshot_events
            chunk_path = _save_video_chunk(
                session_source_id,
                snapshot_bytes,
                ext,
                {
                    "kind": "ws_manual_query",
                    "duration_seconds": video_duration,
                    "activity_events_count": len(merged_events),
                },
            )
            frames, annotations, extract_stats = await extract_frames_from_bytes(
                snapshot_bytes, ext, scene_threshold, min_interval_val,
                activity_events=merged_events, video_duration=video_duration)

        # Build VLM request
        messages_list = [{"role": "system", "content": system_prompt}]
        if not no_history:
            messages_list.extend(history[-max_history:])

        content_parts = []
        if frames:
            actual_dur = extract_stats.get("actual_duration", video_duration)
            n_sub = extract_stats.get("submitted", len(frames))
            n_total = extract_stats.get("total_extracted", n_sub)
            header = f"[以下是从最近 {round(actual_dur)}秒 视频流中提取的 {n_sub} 个关键帧"
            if n_total > n_sub:
                header += f"（从 {n_total} 帧中智能采样）"
            header += "。]"
            content_parts.append({"type": "text", "text": header})
            for i, fb64 in enumerate(frames):
                ann = annotations[i] if i < len(annotations) else f"[帧{i+1}/{len(frames)}]"
                content_parts.append({"type": "text", "text": ann})
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{fb64}"},
                })
        content_parts.append({"type": "text", "text": user_text})
        messages_list.append({"role": "user", "content": content_parts})

        await ws.send_json({"type": "start", "id": req_id,
                            "frames_used": len(frames),
                            "total_extracted": extract_stats.get("total_extracted", 0),
                            "video_duration": round(extract_stats.get("actual_duration", video_duration), 1),
                            "activity_events": len(merged_events) if merged_events else 0})
        response_text = await stream_vlm_response(client, messages_list, ws, req_id)

        if not no_history:
            history.append({"role": "user", "content": user_text})
            if response_text:
                history.append({"role": "assistant", "content": response_text})

        # Save result to local Basic Memory project context.
        if response_text:
            try:
                session_query_count += 1
                actual_dur = extract_stats.get("actual_duration", video_duration)
                _storage_entry(
                    source_id=session_source_id,
                    prompt=user_text,
                    answer=response_text,
                    duration_seconds=actual_dur,
                    frames_used=len(frames),
                    activity_events_count=len(merged_events),
                    chunk_paths=[str(chunk_path)] if chunk_path else [],
                    kind="ws_manual_query",
                )
            except Exception as e:
                print(f"[ws] storage save error: {e}")

    async def _query_wrapper(msg):
        """Wrapper that acquires the lock and handles errors."""
        async with query_lock:
            try:
                await _handle_query(msg)
            except Exception as e:
                req_id = msg.get("id", "unknown")
                print(f"[query] Error: {e}")
                try:
                    await ws.send_json({"type": "error", "id": req_id, "text": str(e)})
                    await ws.send_json({"type": "done", "id": req_id})
                except Exception:
                    pass

    try:
        while True:
            message = await ws.receive()

            if message["type"] == "websocket.disconnect":
                break

            # Binary message = video chunk from MediaRecorder
            if "bytes" in message and message["bytes"]:
                chunk_data = message["bytes"]

                # First chunk must have EBML header for valid WebM
                if not video_chunks and "webm" in video_mime:
                    if chunk_data[:4] != b'\x1a\x45\xdf\xa3':
                        # Stale chunk from old recorder before restart — discard
                        continue

                video_chunks.append(chunk_data)
                if not video_start_time:
                    video_start_time = time.time()
                    print(f"[ws] First video chunk received: {len(chunk_data)} bytes")

                total_size = sum(len(c) for c in video_chunks)
                duration = time.time() - video_start_time
                await ws.send_json({
                    "type": "stream_status",
                    "chunks": len(video_chunks),
                    "size_kb": total_size // 1024,
                    "duration": round(duration, 1),
                })
                continue

            # Text message = JSON command
            if "text" not in message or not message["text"]:
                continue

            msg = json.loads(message["text"])
            print(f"[ws] Received message type={msg.get('type')}, video_chunks={len(video_chunks)}")

            if msg["type"] == "set_mime":
                video_mime = msg.get("mime", "video/webm")
                video_chunks.clear()
                video_start_time = 0
                server_activity_events.clear()
                print(f"[ws] set_mime={video_mime}, buffer cleared")

            elif msg["type"] == "query":
                if query_lock.locked():
                    print(f"[ws] Query skipped — previous query still running")
                    await ws.send_json({"type": "error", "id": msg.get("id", ""),
                                        "text": "上一个查询仍在处理中，请稍候"})
                    await ws.send_json({"type": "done", "id": msg.get("id", "")})
                else:
                    asyncio.create_task(_query_wrapper(msg))

            elif msg["type"] == "clear_history":
                history.clear()
                video_chunks.clear()
                video_start_time = 0
                server_activity_events.clear()
                await ws.send_json({"type": "history_cleared"})
                await ws.send_json({"type": "stream_reset"})

            elif msg["type"] == "reset_stream":
                video_chunks.clear()
                video_start_time = 0
                await ws.send_json({"type": "stream_reset"})

            elif msg["type"] == "activity_event":
                ev = msg.get("event")
                if ev and isinstance(ev, dict):
                    server_activity_events.append(ev)

            elif msg["type"] == "ping":
                await ws.send_json({"type": "pong"})

            elif msg["type"] == "create_task":
                task_id = uuid.uuid4().hex[:8]
                cfg = {
                    "interval": max(5, min(3600, msg.get("interval", 30))),
                    "prompt": msg.get("prompt", "请描述当前画面中的内容和变化。"),
                    "system_prompt": msg.get("system_prompt", ""),
                    "scene_threshold": msg.get("scene_threshold", 0.05),
                    "min_interval": msg.get("min_interval", 3.0),
                }
                ws_task_configs[task_id] = cfg
                ws_tasks[task_id] = asyncio.create_task(_ws_task_loop(task_id))
                await ws.send_json({
                    "type": "task_created", "task_id": task_id,
                    "interval": cfg["interval"], "prompt": cfg["prompt"],
                })
                print(f"[ws] Task {task_id} created: interval={cfg['interval']}s")

            elif msg["type"] == "delete_task":
                task_id = msg.get("task_id", "")
                if task_id in ws_tasks:
                    ws_task_configs.pop(task_id, None)
                    ws_tasks[task_id].cancel()
                    try:
                        await ws_tasks[task_id]
                    except asyncio.CancelledError:
                        pass
                    del ws_tasks[task_id]
                    await ws.send_json({"type": "task_deleted", "task_id": task_id})
                    print(f"[ws] Task {task_id} deleted")

            elif msg["type"] == "list_tasks":
                task_list = []
                for tid, cfg in ws_task_configs.items():
                    task_list.append({
                        "task_id": tid,
                        "interval": cfg["interval"],
                        "prompt": cfg["prompt"][:50],
                        "running": tid in ws_tasks and not ws_tasks[tid].done(),
                    })
                await ws.send_json({"type": "task_list", "tasks": task_list})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "text": str(e)})
        except Exception:
            pass
    finally:
        # Cancel all WS tasks on disconnect
        for tid, t in ws_tasks.items():
            t.cancel()
        for tid, t in ws_tasks.items():
            try:
                await t
            except asyncio.CancelledError:
                pass
        ws_tasks.clear()
        ws_task_configs.clear()
        await client.aclose()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=59092)
