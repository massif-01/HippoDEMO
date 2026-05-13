import asyncio
import base64
import io
import json
import os
import re
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
from minio import Minio
from pydantic import BaseModel, Field

app = FastAPI()

def load_local_env():
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_local_env()
VLLM_BASE = os.environ.get("VLLM_BASE_URL", "http://localhost:58000")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "RM-01 VLM")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY", "")
VLLM_TEMPERATURE = float(os.environ.get("VLLM_TEMPERATURE", "0.7"))
VLLM_MAX_TOKENS = int(os.environ.get("VLLM_MAX_TOKENS", "2048"))
VLLM_TIMEOUT_SECONDS = float(os.environ.get("VLLM_TIMEOUT_SECONDS", "120"))

STATIC_DIR = Path(__file__).parent / "static"

# ---- MinIO config ----
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "rm01")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "rm01rm01")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "rm01")
MINIO_PREFIX = os.environ.get("MINIO_PREFIX", "context")

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)


def vlm_headers() -> dict[str, str]:
    if not VLLM_API_KEY:
        return {}
    return {"Authorization": f"Bearer {VLLM_API_KEY}"}

# Ensure bucket exists
if not minio_client.bucket_exists(MINIO_BUCKET):
    minio_client.make_bucket(MINIO_BUCKET)
    print(f"[minio] Created bucket: {MINIO_BUCKET}")
else:
    print(f"[minio] Bucket exists: {MINIO_BUCKET}")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def save_to_minio(content: str, filename: str | None = None) -> str:
    """Save text content to MinIO and return the object path."""
    if not filename:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}.md"
    object_name = f"{MINIO_PREFIX}/{filename}"
    data = content.encode("utf-8")
    minio_client.put_object(
        MINIO_BUCKET, object_name,
        io.BytesIO(data), len(data),
        content_type="text/markdown; charset=utf-8",
    )
    print(f"[minio] Saved: {MINIO_BUCKET}/{object_name} ({len(data)} bytes)")
    return object_name


def append_to_minio(filename: str, section: str) -> str:
    """Append a section to an existing MinIO file, or create it."""
    object_name = f"{MINIO_PREFIX}/{filename}"
    existing = ""
    try:
        resp = minio_client.get_object(MINIO_BUCKET, object_name)
        existing = resp.read().decode("utf-8")
        resp.close()
        resp.release_conn()
    except Exception:
        pass  # file doesn't exist yet

    new_content = existing + section
    data = new_content.encode("utf-8")
    minio_client.put_object(
        MINIO_BUCKET, object_name,
        io.BytesIO(data), len(data),
        content_type="text/markdown; charset=utf-8",
    )
    print(f"[minio] Appended to {MINIO_BUCKET}/{object_name} ({len(data)} bytes total)")
    return object_name


@app.get("/api/minio/list")
async def api_minio_list(limit: int = 50):
    """List objects in the context directory."""
    loop = asyncio.get_event_loop()
    def _list():
        objects = []
        for obj in minio_client.list_objects(MINIO_BUCKET, prefix=f"{MINIO_PREFIX}/", recursive=True):
            objects.append({
                "name": obj.object_name,
                "size": obj.size,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
            })
        objects.sort(key=lambda x: x["last_modified"] or "", reverse=True)
        return objects[:limit]
    return {"objects": await loop.run_in_executor(None, _list)}


@app.get("/api/minio/read")
async def api_minio_read(path: str):
    """Read a text object from MinIO."""
    if not path.startswith(f"{MINIO_PREFIX}/"):
        return {"error": "Access denied"}
    loop = asyncio.get_event_loop()
    def _read():
        resp = minio_client.get_object(MINIO_BUCKET, path)
        try:
            return resp.read().decode("utf-8")
        finally:
            resp.close()
            resp.release_conn()
    try:
        content = await loop.run_in_executor(None, _read)
        return {"path": path, "content": content}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/minio/stats")
async def api_minio_stats():
    """Get storage stats."""
    loop = asyncio.get_event_loop()
    def _stats():
        total_size = 0
        count = 0
        for obj in minio_client.list_objects(MINIO_BUCKET, prefix=f"{MINIO_PREFIX}/", recursive=True):
            total_size += obj.size or 0
            count += 1
        return {"count": count, "total_size": total_size}
    return await loop.run_in_executor(None, _stats)


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
            "ffmpeg", "-y",
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
    """Main loop for a task: capture video → extract frames → query VLM → save to MinIO."""
    task = tasks.get(task_id)
    if not task or not task.capture:
        return
    client = httpx.AsyncClient()
    # Reset context.md at task start
    save_to_minio(
        f"# VLMac 当前上下文\n\n"
        f"**任务**: {task_id}\n"
        f"**会话**: {task.session_filename}\n"
        f"**启动时间**: {task.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"**设备**: {task.device}\n\n---\n\n",
        "context.md",
    )
    try:
        while task.running:
            print(f"[task:{task_id}] Capturing {task.interval}s from {task.device}...")

            video_bytes = await task.capture.capture_segment(task.interval)
            if not video_bytes:
                print(f"[task:{task_id}] No video captured, retrying in 5s...")
                await asyncio.sleep(5)
                continue

            print(f"[task:{task_id}] Captured {len(video_bytes)/1024/1024:.1f}MB")

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
                    headers=vlm_headers(),
                    json={
                        "model": VLLM_MODEL,
                        "messages": messages,
                        "max_tokens": VLLM_MAX_TOKENS,
                        "temperature": VLLM_TEMPERATURE,
                    },
                    timeout=VLLM_TIMEOUT_SECONDS,
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

            # Save to MinIO (append to session file)
            ts = datetime.now(timezone.utc)
            task.query_count += 1
            section = ""
            if task.query_count == 1:
                section += (
                    f"# VLMac 任务 {task_id} — {task.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                    f"**设备**: {task.device}\n"
                    f"**分辨率**: {task.resolution}\n"
                    f"**采集间隔**: {task.interval}s\n"
                    f"**灵敏度**: {task.scene_threshold}\n"
                    f"**提示词**: {task.timer_prompt}\n\n"
                    f"---\n\n"
                )
            section += (
                f"## 查询 {task.query_count} — {ts.strftime('%H:%M:%S')}\n\n"
                f"**视频时长**: {round(actual_dur)}s\n"
                f"**提取帧数**: {n_sub}\n\n"
                f"{answer}\n\n"
                f"---\n\n"
            )
            try:
                obj_path = append_to_minio(task.session_filename, section)
                print(f"[task:{task_id}] Result appended to MinIO: {obj_path}")
                # Append to context.md
                ctx_section = (
                    f"## [{task_id}] 查询 {task.query_count} — {ts.strftime('%H:%M:%S')}\n\n"
                    f"**视频时长**: {round(actual_dur)}s | **提取帧数**: {n_sub}\n\n"
                    f"{answer}\n\n---\n\n"
                )
                append_to_minio("context.md", ctx_section)
            except Exception as e:
                print(f"[task:{task_id}] MinIO save error: {e}")
                obj_path = ""

            result = {
                "timestamp": ts.isoformat(),
                "frames": n_sub,
                "duration": round(actual_dur, 1),
                "answer": answer[:500],
                "minio_path": obj_path,
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
        "max_tokens": VLLM_MAX_TOKENS,
        "stream": True,
        "temperature": VLLM_TEMPERATURE,
    }

    full_text = ""
    try:
        async with client.stream(
            "POST",
            f"{VLLM_BASE}/v1/chat/completions",
            headers=vlm_headers(),
            json=payload,
            timeout=VLLM_TIMEOUT_SECONDS,
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

            # Get actual video duration via ffprobe
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries",
                     "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                     video_path],
                    capture_output=True, text=True, timeout=30)
                actual_duration = float(probe.stdout.strip()) if probe.stdout.strip() else video_duration
            except Exception:
                actual_duration = video_duration

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
                "ffmpeg", "-i", video_path,
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
                    "ffmpeg", "-i", video_path, "-vf",
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

    # Session-level MinIO file
    session_start = datetime.now(timezone.utc)
    session_filename = f"session_{session_start.strftime('%Y%m%d_%H%M%S')}.md"
    session_query_count = 0
    # Reset context.md at session start
    loop_init = asyncio.get_event_loop()
    await loop_init.run_in_executor(
        None, save_to_minio,
        f"# VLMac 当前上下文\n\n"
        f"**会话**: {session_filename}\n"
        f"**启动时间**: {session_start.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n---\n\n",
        "context.md",
    )

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
        task_session_file = f"ws_task_{task_id}.md"
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

                # Save to MinIO
                if response_text:
                    try:
                        session_query_count += 1
                        ts = datetime.now(timezone.utc)
                        section = ""
                        if task_query_count == 1:
                            section += (
                                f"# 定时任务 {task_id}\n\n"
                                f"**间隔**: {cfg['interval']}s\n"
                                f"**提示词**: {cfg['prompt']}\n\n---\n\n"
                            )
                        section += (
                            f"## 查询 {task_query_count} — {ts.strftime('%H:%M:%S')}\n\n"
                            f"**视频时长**: {round(actual_dur)}s | **帧数**: {n_sub}\n\n"
                            f"{response_text}\n\n---\n\n"
                        )
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, append_to_minio, task_session_file, section)
                        ctx_section = (
                            f"## [任务{task_id}] 查询 {task_query_count} — {ts.strftime('%H:%M:%S')}\n\n"
                            f"{response_text}\n\n---\n\n"
                        )
                        await loop.run_in_executor(None, append_to_minio, "context.md", ctx_section)
                    except Exception as e:
                        print(f"[ws_task:{task_id}] MinIO error: {e}")

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

        snapshot_bytes, ext, video_duration, snapshot_events = await _take_buffer_snapshot()
        if snapshot_bytes:
            await ws.send_json({"type": "stream_reset"})

            if ext == "webm" and snapshot_bytes[:4] != b'\x1a\x45\xdf\xa3':
                print(f"[extract] WARNING: WebM EBML header unexpected "
                      f"({len(snapshot_bytes)} bytes, first 8: {snapshot_bytes[:8].hex()})")

            # Merge client-sent events with server-accumulated events
            merged_events = activity_events + snapshot_events
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

        # Save result to MinIO (append to session file)
        if response_text:
            try:
                session_query_count += 1
                ts = datetime.now(timezone.utc)
                actual_dur = extract_stats.get("actual_duration", video_duration)
                section = ""
                if session_query_count == 1:
                    section += f"# VLMac 会话记录 — {session_start.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                section += (
                    f"## 查询 {session_query_count} — {ts.strftime('%H:%M:%S')}\n\n"
                    f"**提问**: {user_text}\n"
                    f"**视频时长**: {round(actual_dur)}s\n"
                    f"**提取帧数**: {len(frames)}\n\n"
                    f"{response_text}\n\n"
                    f"---\n\n"
                )
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, append_to_minio, session_filename, section)
                ctx_section = (
                    f"## 查询 {session_query_count} — {ts.strftime('%H:%M:%S')}\n\n"
                    f"**提问**: {user_text}\n"
                    f"**视频时长**: {round(actual_dur)}s | **提取帧数**: {len(frames)}\n\n"
                    f"{response_text}\n\n---\n\n"
                )
                await loop.run_in_executor(None, append_to_minio, "context.md", ctx_section)
            except Exception as e:
                print(f"[ws] MinIO save error: {e}")

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
