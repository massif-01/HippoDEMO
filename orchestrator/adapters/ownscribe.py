from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import shutil
import signal
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import ServiceStatus, now_iso


PROJECT_DIR = Path(__file__).resolve().parents[2]
OWNSCRIBE_DIR = PROJECT_DIR / "ownscribe"
OWNSCRIBE_SRC = OWNSCRIBE_DIR / "src"
DATA_DIR = PROJECT_DIR / "orchestrator" / "data" / "ownscribe"
CONFIG_PATH = PROJECT_DIR / "orchestrator" / "data" / "ownscribe_config.json"
PROVIDER_CONFIG_PATH = PROJECT_DIR / ".runtime" / "ownscribe-provider.json"
SUMMARY_PROMPT_PATH = PROJECT_DIR / "orchestrator" / "prompts" / "meeting_summary_zh.md"
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

CHILD_CODE = """\
import json
import os
import re
import subprocess
import sys
import time
import signal
from datetime import datetime, timezone
from pathlib import Path

from ownscribe.config import Config
from ownscribe.pipeline import _WAV_HEADER_SIZE, _check_audio_silence, _create_recorder

config = Config.load()
config.output.dir = sys.argv[1]
config.output.keep_recording = True
audio_source = os.environ.get("OWNSCRIBE_AUDIO_SOURCE", "system").strip().lower()
mic_device = os.environ.get("OWNSCRIBE_AUDIO_MIC_DEVICE", "").strip()
if audio_source in {"system", "system-audio", "screen", "display", "app"}:
    config.audio.backend = "coreaudio"
    config.audio.device = ""
    config.audio.mic = False
    config.audio.mic_device = ""
elif audio_source in {"both", "mixed", "system+mic", "mic+system", "all"}:
    config.audio.backend = "coreaudio"
    config.audio.device = ""
    config.audio.mic = True
    config.audio.mic_device = mic_device
elif audio_source in {"mic", "microphone", "room"}:
    config.audio.backend = "coreaudio"
    config.audio.device = ""
    config.audio.mic = True
    config.audio.mic_device = mic_device
    os.environ["OWNSCRIBE_AUDIO_MIC_ONLY"] = "1"
else:
    raise SystemExit(f"Unsupported OWNSCRIBE_AUDIO_SOURCE={audio_source!r}; use system, mic, or both.")
out_dir = Path(sys.argv[1])
out_dir.mkdir(parents=True, exist_ok=True)
audio_path = out_dir / "recording.wav"
timeline_path = out_dir / "recording_timeline.json"
recorder = _create_recorder(config)
stop_event = False
stop_requested_wall = None
stop_requested_epoch = None
stop_requested_monotonic = None

def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat()

def timeline_base():
    return {
        "schema_version": 1,
        "source": "ownscribe",
        "session_id": out_dir.name,
        "audio_source": audio_source,
        "mic_device": mic_device or None,
        "audio_path": str(audio_path),
        "alignment": {
            "offset_seconds": 0.0,
            "wall_time_field": "recording_started_at",
            "formula": "wall_time = recording_started_at + audio_offset_seconds",
        },
    }

def update_timeline(**updates):
    payload = timeline_base()
    if timeline_path.exists():
        try:
            payload.update(json.loads(timeline_path.read_text()))
        except Exception:
            pass
    payload.update(updates)
    timeline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

def audio_info(path):
    if not path.exists():
        return {}
    info = {"file_size_bytes": path.stat().st_size}
    try:
        result = subprocess.run(["afinfo", str(path)], capture_output=True, text=True, timeout=10)
    except Exception:
        return info
    if result.returncode != 0:
        return info
    text = result.stdout
    duration = re.search(r"estimated duration:\\s*([0-9.]+) sec", text)
    if duration:
        info["duration_seconds"] = float(duration.group(1))
    data_format = re.search(r"Data format:\\s*(.+)", text)
    if data_format:
        info["data_format"] = data_format.group(1).strip()
    return info

def on_interrupt(sig, frame):
    global stop_event, stop_requested_wall, stop_requested_epoch, stop_requested_monotonic
    stop_event = True
    stop_requested_wall = now_iso()
    stop_requested_epoch = time.time()
    stop_requested_monotonic = time.monotonic()

original_handler = signal.getsignal(signal.SIGINT)
signal.signal(signal.SIGINT, on_interrupt)

try:
    print(f"Starting ownscribe audio capture: {audio_path}", flush=True)
    update_timeline(
        process_started_at=now_iso(),
        process_started_epoch_seconds=time.time(),
        process_started_monotonic_seconds=time.monotonic(),
        status="starting",
    )
    start_requested_at = now_iso()
    start_requested_epoch = time.time()
    start_requested_monotonic = time.monotonic()
    update_timeline(
        recording_start_requested_at=start_requested_at,
        recording_start_requested_epoch_seconds=start_requested_epoch,
        recording_start_requested_monotonic_seconds=start_requested_monotonic,
    )
    recorder.start(audio_path)
    started_at = now_iso()
    started_epoch = time.time()
    started_monotonic = time.monotonic()
    update_timeline(
        recording_started_at=started_at,
        recording_started_epoch_seconds=started_epoch,
        recording_started_monotonic_seconds=started_monotonic,
        status="recording",
    )
    while not stop_event and recorder.is_recording:
        time.sleep(0.5)
finally:
    signal.signal(signal.SIGINT, original_handler)
    if stop_requested_wall is None:
        stop_requested_wall = now_iso()
        stop_requested_epoch = time.time()
        stop_requested_monotonic = time.monotonic()
    update_timeline(
        recording_stop_requested_at=stop_requested_wall,
        recording_stop_requested_epoch_seconds=stop_requested_epoch,
        recording_stop_requested_monotonic_seconds=stop_requested_monotonic,
        status="stopping",
    )
    recorder.stop()
    stopped_at = now_iso()
    stopped_epoch = time.time()
    stopped_monotonic = time.monotonic()
    timeline_updates = {
        "recording_stopped_at": stopped_at,
        "recording_stopped_epoch_seconds": stopped_epoch,
        "recording_stopped_monotonic_seconds": stopped_monotonic,
        "status": "stopped",
    }
    try:
        existing = json.loads(timeline_path.read_text())
        start_epoch = existing.get("recording_started_epoch_seconds")
        start_monotonic = existing.get("recording_started_monotonic_seconds")
        if isinstance(start_epoch, (int, float)):
            timeline_updates["wall_duration_seconds"] = max(0.0, stopped_epoch - float(start_epoch))
        if isinstance(start_monotonic, (int, float)):
            timeline_updates["monotonic_duration_seconds"] = max(0.0, stopped_monotonic - float(start_monotonic))
    except Exception:
        pass
    timeline_updates["audio_file"] = audio_info(audio_path)
    update_timeline(**timeline_updates)

if not audio_path.exists() or audio_path.stat().st_size <= _WAV_HEADER_SIZE:
    raise SystemExit("No audio was captured. Check audio permissions and capture backend.")

if not getattr(recorder, "silence_warning", False):
    _check_audio_silence(audio_path)

print(f"Audio saved to {audio_path}", flush=True)
"""

DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_HTTP_TIMEOUT = 300.0
OPENAI_COMPATIBLE_PROVIDERS = {"openai-compatible", "openai", "vllm"}
DEFAULT_AUDIO_SOURCE = "system"
SYSTEM_AUDIO_SOURCE_ALIASES = {"system", "system-audio", "screen", "display", "app"}
MIC_AUDIO_SOURCE_ALIASES = {"mic", "microphone", "room"}
BOTH_AUDIO_SOURCE_ALIASES = {"both", "mixed", "system+mic", "mic+system", "all"}


@dataclass
class OwnscribeResult:
    ok: bool
    session_id: str
    output_dir: str | None = None
    transcript_path: str | None = None
    summary_path: str | None = None
    audio_path: str | None = None
    detail: str | None = None
    error: str | None = None


@dataclass
class _SessionProcess:
    session_id: str
    process: subprocess.Popen[bytes]
    base_output_dir: Path
    stdout_log_path: Path
    stderr_log_path: Path
    phase: str
    started_at: str
    stopped_at: str | None = None
    result: OwnscribeResult | None = None


class OwnscribeAdapter:
    def __init__(
        self,
        *,
        stop_timeout: float = 900.0,
        terminate_timeout: float = 20.0,
        kill_timeout: float = 5.0,
    ) -> None:
        self.stop_timeout = stop_timeout
        self.terminate_timeout = terminate_timeout
        self.kill_timeout = kill_timeout
        self._sessions: dict[str, _SessionProcess] = {}
        self._lock = asyncio.Lock()

    async def status(self) -> ServiceStatus:
        async with self._lock:
            self._refresh_finished_sessions_locked()
            active = [record for record in self._sessions.values() if record.process.poll() is None]
            if active:
                processing = [record for record in active if record.phase == "processing"]
                record = self._latest_record(processing or active)
                return ServiceStatus(
                    name="ownscribe",
                    status=record.phase,
                    detail=self._record_detail(record),
                )

            completed = [record for record in self._sessions.values() if record.result is not None]
            if completed:
                record = self._latest_record(completed)
                result = record.result
                assert result is not None
                return ServiceStatus(
                    name="ownscribe",
                    status="available" if result.ok else "error",
                    detail=result.detail or result.error,
                )

            if not OWNSCRIBE_SRC.exists():
                return ServiceStatus(
                    name="ownscribe",
                    status="error",
                    detail=f"ownscribe source not found: {OWNSCRIBE_SRC}",
                )

            return ServiceStatus(
                name="ownscribe",
                status="available",
                detail=(
                    f"adapter ready; source={OWNSCRIBE_SRC}; "
                    f"audio_source={self._audio_source()}; "
                    f"mic_device={self._audio_mic_device() or 'default'}; "
                    f"asr_provider={self._asr_provider()}; asr_base_url={self._asr_base_url()}; "
                    f"asr_model={self._configured_asr_model() or 'auto'}"
                ),
            )

    def config(self) -> dict[str, Any]:
        return {
            "audio_source": self._audio_source(),
            "mic_device": self._audio_mic_device() or None,
            "audio_display": self._audio_display_enabled() == "1",
            "asr_provider": self._asr_provider(),
            "asr_base_url": self._asr_base_url(),
            "asr_model": self._configured_asr_model() or None,
            "summary_provider": self._summary_provider(),
            "summary_base_url": self._summary_base_url(),
            "summary_model": self._configured_summary_model() or None,
            "asr_api_key_configured": self._api_key_configured("asr"),
            "summary_api_key_configured": self._api_key_configured("summary"),
            "config_path": str(CONFIG_PATH),
        }

    def update_config(
        self,
        *,
        audio_source: str | None = None,
        mic_device: str | None = None,
        audio_display: bool | None = None,
        asr_provider: str | None = None,
        asr_base_url: str | None = None,
        asr_model: str | None = None,
        asr_api_key: str | None = None,
        summary_provider: str | None = None,
        summary_base_url: str | None = None,
        summary_model: str | None = None,
        summary_api_key: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        if audio_source is not None or mic_device is not None or audio_display is not None:
            config = self._read_config()
            if audio_source is not None:
                config["audio_source"] = self._normalize_audio_source(audio_source)
            if mic_device is not None:
                config["mic_device"] = mic_device.strip()
            if audio_display is not None:
                config["audio_display"] = bool(audio_display)
            self._write_config(config)

        self._update_provider_config(
            asr_provider=asr_provider,
            asr_base_url=asr_base_url,
            asr_model=asr_model,
            asr_api_key=asr_api_key,
            summary_provider=summary_provider,
            summary_base_url=summary_base_url,
            summary_model=summary_model,
            summary_api_key=summary_api_key,
            api_key=api_key,
        )
        return self.config()

    def audio_devices(self) -> dict[str, Any]:
        binary = self._ownscribe_audio_binary()
        if binary is None:
            return {
                "ok": False,
                "devices": [],
                "raw": "",
                "detail": "ownscribe-audio binary not found",
            }

        try:
            result = subprocess.run(
                [str(binary), "list-devices"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as exc:
            return {"ok": False, "devices": [], "raw": "", "detail": str(exc)}

        devices = self._parse_audio_devices(result.stdout)
        detail = result.stderr.strip() if result.returncode != 0 else ""
        return {
            "ok": result.returncode == 0,
            "devices": devices,
            "raw": result.stdout,
            "detail": detail or None,
        }

    def preflight(self, *, network: bool = False) -> dict[str, Any]:
        config = self.config()
        devices_result = self.audio_devices()
        devices = devices_result.get("devices") or []
        device_names = {str(device.get("name")) for device in devices if isinstance(device, dict)}
        selected_mic = config.get("mic_device") or ""
        latest_timeline = self._latest_recording_timeline()
        asr_endpoint_ok = self._models_endpoint_ok(self._asr_base_url(), api_key=self._api_key("asr")) if network else (
            True,
            "not checked; pass network=true to probe /v1/models",
        )
        summary_endpoint_ok = self._models_endpoint_ok(self._summary_base_url(), api_key=self._api_key("summary")) if network else (
            True,
            "not checked; pass network=true to probe /v1/models",
        )

        checks = [
            self._preflight_check(
                "ownscribe_helper",
                self._ownscribe_audio_binary() is not None,
                str(self._ownscribe_audio_binary() or "ownscribe-audio binary not found"),
            ),
            self._preflight_check(
                "audio_devices",
                bool(devices_result.get("ok")) and bool(devices),
                f"{len(devices)} input device(s) visible",
            ),
            self._preflight_check(
                "selected_microphone",
                not selected_mic or selected_mic in device_names,
                selected_mic or "system default input",
            ),
            self._preflight_check(
                "asr_model",
                bool(config.get("asr_model")),
                str(config.get("asr_model") or "ASR model is not configured"),
            ),
            self._preflight_check(
                "summary_model",
                bool(config.get("summary_model")),
                str(config.get("summary_model") or "summary model is not configured"),
            ),
            self._preflight_check(
                "asr_endpoint",
                *asr_endpoint_ok,
            ),
            self._preflight_check(
                "summary_endpoint",
                *summary_endpoint_ok,
            ),
            self._preflight_check(
                "recording_timeline",
                latest_timeline is not None,
                str(latest_timeline or "no recording_timeline.json found yet"),
            ),
        ]
        return {
            "ok": all(check["ok"] for check in checks),
            "updated_at": now_iso(),
            "config": config,
            "checks": checks,
            "network_checked": network,
            "latest_timeline_path": str(latest_timeline) if latest_timeline else None,
        }

    async def start(self, session_id: str) -> OwnscribeResult:
        validation_error = self._validate_session_id(session_id)
        if validation_error:
            return OwnscribeResult(ok=False, session_id=session_id, error=validation_error)
        if not OWNSCRIBE_SRC.exists():
            return OwnscribeResult(
                ok=False,
                session_id=session_id,
                error=f"ownscribe source not found: {OWNSCRIBE_SRC}",
            )

        async with self._lock:
            existing = self._sessions.get(session_id)
            if existing is not None:
                if existing.process.poll() is None:
                    return OwnscribeResult(
                        ok=True,
                        session_id=session_id,
                        output_dir=str(existing.base_output_dir),
                        detail=f"already {existing.phase}; {self._record_detail(existing)}",
                    )
                if existing.result is not None:
                    return existing.result

            base_output_dir = DATA_DIR / session_id
            base_output_dir.mkdir(parents=True, exist_ok=True)
            stdout_log_path = base_output_dir / "ownscribe.stdout.log"
            stderr_log_path = base_output_dir / "ownscribe.stderr.log"

            env = os.environ.copy()
            env["PYTHONPATH"] = self._pythonpath(env.get("PYTHONPATH"))
            env["OWNSCRIBE_AUDIO_SOURCE"] = self._audio_source()
            env["OWNSCRIBE_AUDIO_MIC_DEVICE"] = self._audio_mic_device()
            env["OWNSCRIBE_AUDIO_DISPLAY"] = self._audio_display_enabled()
            python = self._python_executable()
            command = [python, "-c", CHILD_CODE, str(base_output_dir)]

            try:
                with stdout_log_path.open("ab") as stdout_log, stderr_log_path.open("ab") as stderr_log:
                    popen_kwargs: dict[str, Any] = {}
                    if sys.version_info >= (3, 11):
                        popen_kwargs["process_group"] = 0
                    else:
                        popen_kwargs["start_new_session"] = True
                    process = subprocess.Popen(
                        command,
                        cwd=str(OWNSCRIBE_DIR),
                        env=env,
                        stdout=stdout_log,
                        stderr=stderr_log,
                        stdin=subprocess.DEVNULL,
                        **popen_kwargs,
                    )
            except OSError as exc:
                return OwnscribeResult(
                    ok=False,
                    session_id=session_id,
                    output_dir=str(base_output_dir),
                    error=str(exc),
                )

            record = _SessionProcess(
                session_id=session_id,
                process=process,
                base_output_dir=base_output_dir,
                stdout_log_path=stdout_log_path,
                stderr_log_path=stderr_log_path,
                phase="recording",
                started_at=now_iso(),
            )
            self._sessions[session_id] = record
            await asyncio.sleep(1.0)
            if process.poll() is not None:
                record.phase = "error"
                record.result = self._collect_result(record, returncode=process.returncode)
                return record.result
            return OwnscribeResult(
                ok=True,
                session_id=session_id,
                output_dir=str(base_output_dir),
                detail=f"recording started pid={process.pid}; {self._record_detail(record)}",
            )

    async def stop(
        self,
        session_id: str,
        stop_timeout: float | None = None,
        terminate_timeout: float | None = None,
        kill_timeout: float | None = None,
    ) -> OwnscribeResult:
        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return self._result_from_existing_output(session_id)
            if record.result is not None:
                return record.result
            if record.process.poll() is not None:
                record.result = self._collect_result(record, returncode=record.process.returncode)
                return record.result
            record.phase = "processing"
            record.stopped_at = now_iso()
            self._signal_process_group(record.process, signal.SIGINT)

        error: str | None = None
        timed_out = False
        effective_stop_timeout = self.stop_timeout if stop_timeout is None else stop_timeout
        effective_terminate_timeout = self.terminate_timeout if terminate_timeout is None else terminate_timeout
        effective_kill_timeout = self.kill_timeout if kill_timeout is None else kill_timeout
        try:
            await asyncio.to_thread(record.process.wait, effective_stop_timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            error = f"timed out after {effective_stop_timeout:.0f}s waiting for ownscribe to finish"
            self._signal_process_group(record.process, signal.SIGTERM)
            try:
                await asyncio.to_thread(record.process.wait, effective_terminate_timeout)
            except subprocess.TimeoutExpired:
                error = f"{error}; killed after terminate timeout"
                self._signal_process_group(record.process, signal.SIGKILL)
                try:
                    await asyncio.to_thread(record.process.wait, effective_kill_timeout)
                except subprocess.TimeoutExpired:
                    error = f"{error}; process group did not exit"

        if not timed_out and record.process.returncode == 0:
            try:
                asr_error = await asyncio.to_thread(self._postprocess_recording, record.base_output_dir)
                if asr_error and error is None:
                    error = asr_error
            except Exception as exc:
                if error is None:
                    error = f"remote ASR postprocess failed: {exc}"

        async with self._lock:
            record.result = self._collect_result(
                record,
                returncode=record.process.returncode,
                error=error,
                forced_failure=timed_out,
            )
            return record.result

    async def result_for_session(self, session_id: str) -> OwnscribeResult:
        validation_error = self._validate_session_id(session_id)
        if validation_error:
            return OwnscribeResult(ok=False, session_id=session_id, error=validation_error)

        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return self._result_from_existing_output(session_id)
            if record.result is not None:
                return record.result
            if record.process.poll() is None:
                return OwnscribeResult(
                    ok=False,
                    session_id=session_id,
                    output_dir=str(record.base_output_dir),
                    detail=self._record_detail(record),
                    error=f"session is still {record.phase}",
                )
            record.result = self._collect_result(record, returncode=record.process.returncode)
            return record.result

    def _postprocess_recording(self, base_output_dir: Path) -> str | None:
        audio_path = self._audio_path(base_output_dir)
        if audio_path is None:
            return "recording.wav not found after ownscribe audio capture"

        transcript_path = self._first_existing(base_output_dir, "transcript", ("md", "json"))
        if transcript_path is None:
            try:
                transcript_payload = self._transcribe_audio(self._prepare_audio_for_asr(audio_path))
            except Exception as exc:
                return f"remote ASR failed: {exc}"

            transcript_text = self._extract_transcript_text(transcript_payload)
            if not transcript_text.strip():
                return "remote ASR returned an empty transcript"

            self._write_transcript(base_output_dir, transcript_text, transcript_payload)
        else:
            transcript_text = transcript_path.read_text(errors="replace")

        if self._summary_enabled() and self._first_existing(base_output_dir, "summary", ("md", "json")) is None:
            try:
                summary_text = self._summarize_transcript(transcript_text)
                if summary_text.strip():
                    self._write_summary(base_output_dir, summary_text)
            except Exception as exc:
                (base_output_dir / "summary.error.txt").write_text(str(exc))

        return None

    def _prepare_audio_for_asr(self, audio_path: Path) -> Path:
        if os.environ.get("HIPPODEMO_ASR_SKIP_TRANSCODE", "").lower() in {"1", "true", "yes"}:
            return audio_path
        afconvert = shutil.which("afconvert")
        if not afconvert:
            return audio_path
        asr_path = audio_path.with_name(f"{audio_path.stem}.asr.wav")
        if asr_path.exists() and asr_path.stat().st_mtime >= audio_path.stat().st_mtime:
            return asr_path
        result = subprocess.run(
            [
                afconvert,
                str(audio_path),
                str(asr_path),
                "-f",
                "WAVE",
                "-d",
                "LEI16@16000",
                "-c",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return audio_path
        return asr_path

    def _transcribe_audio(self, audio_path: Path) -> dict[str, Any]:
        provider = self._asr_provider()
        self._ensure_openai_compatible_provider(provider, capability="ASR")
        base_url = self._asr_base_url()
        model = self._configured_asr_model() or self._first_model(base_url, api_key=self._api_key("asr"))
        if not model:
            raise RuntimeError(
                "set HIPPODEMO_ASR_MODEL or expose a model through the provider /v1/models endpoint"
            )

        response_format = self._env(
            "HIPPODEMO_ASR_RESPONSE_FORMAT",
            "HIPPODEMO_VLLM_ASR_RESPONSE_FORMAT",
            default="json",
        )
        fields = {
            "model": model,
            "response_format": response_format,
        }
        language = self._env("HIPPODEMO_ASR_LANGUAGE", "HIPPODEMO_VLLM_ASR_LANGUAGE")
        if language:
            fields["language"] = language
        prompt = self._env("HIPPODEMO_ASR_PROMPT", "HIPPODEMO_VLLM_ASR_PROMPT")
        if prompt:
            fields["prompt"] = prompt

        body, content_type = self._multipart_body(fields, "file", audio_path)
        data = self._request_bytes(
            "POST",
            self._join_url(base_url, "/audio/transcriptions"),
            body=body,
            headers={"Content-Type": content_type},
            timeout=self._http_timeout(),
            api_key=self._api_key("asr"),
        )
        text = data.decode("utf-8", errors="replace")
        if response_format == "text":
            return {"text": text, "model": model, "provider": provider}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {"text": text, "model": model, "provider": provider}
        if isinstance(payload, dict):
            payload.setdefault("model", model)
            payload.setdefault("provider", provider)
            return payload
        return {"text": str(payload), "model": model, "provider": provider}

    def _summarize_transcript(self, transcript_text: str) -> str:
        provider = self._summary_provider()
        self._ensure_openai_compatible_provider(provider, capability="summary")
        base_url = self._summary_base_url()
        model = self._configured_summary_model() or self._first_model(base_url, api_key=self._api_key("summary"))
        if not model:
            raise RuntimeError(
                "set HIPPODEMO_SUMMARY_MODEL or expose a model through the provider /v1/models endpoint"
            )

        system_prompt = os.environ.get(
            "HIPPODEMO_SUMMARY_SYSTEM_PROMPT",
            os.environ.get(
                "HIPPODEMO_VLLM_SUMMARY_SYSTEM_PROMPT",
                self._default_summary_system_prompt(),
            ),
        )
        user_prompt = os.environ.get(
            "HIPPODEMO_SUMMARY_USER_PROMPT",
            os.environ.get(
                "HIPPODEMO_VLLM_SUMMARY_USER_PROMPT",
                "以下是会议转写文本，请严格基于该文本生成会议纪要：\n\n{transcript}",
            ),
        ).format(transcript=transcript_text)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(
                self._env(
                    "HIPPODEMO_SUMMARY_TEMPERATURE",
                    "HIPPODEMO_VLLM_SUMMARY_TEMPERATURE",
                    default="0.2",
                )
            ),
        }
        data = self._request_bytes(
            "POST",
            self._join_url(base_url, "/chat/completions"),
            body=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=self._http_timeout(),
            api_key=self._api_key("summary"),
        )
        response = json.loads(data.decode("utf-8", errors="replace"))
        choices = response.get("choices") if isinstance(response, dict) else None
        if not choices:
            return ""
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        return str(message.get("content") or "")

    def _ensure_openai_compatible_provider(self, provider: str, *, capability: str) -> None:
        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            return
        raise NotImplementedError(
            f"{capability} provider '{provider}' is not implemented. "
            "Use HIPPODEMO_ASR_PROVIDER=openai-compatible for OpenAI-compatible APIs."
        )

    def _default_summary_system_prompt(self) -> str:
        try:
            return SUMMARY_PROMPT_PATH.read_text(encoding="utf-8")
        except OSError:
            return "你是会议纪要专家。请基于会议转写生成高密度、结构化、可执行的会议纪要。"

    def _extract_transcript_text(self, payload: dict[str, Any]) -> str:
        text = payload.get("text")
        if isinstance(text, str):
            return text
        transcript = payload.get("transcript")
        if isinstance(transcript, str):
            return transcript
        for container_key in ("data", "result", "results"):
            container = payload.get(container_key)
            if isinstance(container, dict):
                nested_text = container.get("text") or container.get("transcript")
                if isinstance(nested_text, str):
                    return nested_text
        segments = payload.get("segments")
        if isinstance(segments, list):
            parts = []
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                segment_text = segment.get("text") or segment.get("sentence") or segment.get("transcript")
                if isinstance(segment_text, str):
                    parts.append(segment_text.strip())
            return "\n".join(part for part in parts if part)
        return ""

    def _write_transcript(self, directory: Path, transcript_text: str, payload: dict[str, Any]) -> None:
        transcript_md = directory / "transcript.md"
        transcript_json = directory / "transcript.json"
        transcript_md.write_text(f"# Transcript\n\n{transcript_text.strip()}\n")
        transcript_json.write_text(
            json.dumps(
                {
                    "text": transcript_text,
                    "source": "remote-asr",
                    "provider": self._asr_provider(),
                    "payload": payload,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    def _write_summary(self, directory: Path, summary_text: str) -> None:
        summary_md = directory / "summary.md"
        summary_json = directory / "summary.json"
        summary_md.write_text(f"# Meeting Minutes\n\n{summary_text.strip()}\n")
        summary_json.write_text(
            json.dumps(
                {
                    "summary": summary_text,
                    "source": "remote-summary",
                    "provider": self._summary_provider(),
                    "model": self._configured_summary_model(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    def _request_bytes(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        api_key: str | None = None,
    ) -> bytes:
        request_headers = dict(headers or {})
        if api_key:
            request_headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout or self._http_timeout()) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            detail = self._redact_sensitive(f"{url} returned HTTP {exc.code}: {body_text[:1200]}")
            raise RuntimeError(detail) from exc
        except urllib.error.URLError as exc:
            detail = self._redact_sensitive(f"{url} is not reachable: {exc.reason}")
            raise RuntimeError(detail) from exc

    def _multipart_body(self, fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
        boundary = f"HippoDEMO-{uuid.uuid4().hex}"
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                    str(value).encode(),
                    b"\r\n",
                ]
            )
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{file_field}"; '
                    f'filename="{file_path.name}"\r\n'
                ).encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                file_path.read_bytes(),
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

    def _first_model(self, base_url: str, *, api_key: str | None = None) -> str | None:
        try:
            data = self._request_bytes(
                "GET",
                self._join_url(base_url, "/models"),
                timeout=10.0,
                api_key=api_key or self._api_key(),
            )
            payload = json.loads(data.decode("utf-8", errors="replace"))
        except Exception:
            return None
        models = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(models, list) or not models:
            return None
        first = models[0]
        if isinstance(first, dict):
            model_id = first.get("id")
            return str(model_id) if model_id else None
        return None

    def _asr_base_url(self) -> str:
        return self._normalize_base_url(
            self._provider_config_value("asr_base_url")
            or os.environ.get("HIPPODEMO_ASR_BASE_URL")
            or os.environ.get("HIPPODEMO_VLLM_ASR_BASE_URL")
            or os.environ.get("HIPPODEMO_OPENAI_COMPATIBLE_BASE_URL")
            or os.environ.get("HIPPODEMO_VLLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or DEFAULT_OPENAI_COMPATIBLE_BASE_URL
        )

    def _summary_base_url(self) -> str:
        return self._normalize_base_url(
            self._provider_config_value("summary_base_url")
            or os.environ.get("HIPPODEMO_SUMMARY_BASE_URL")
            or os.environ.get("HIPPODEMO_VLLM_SUMMARY_BASE_URL")
            or os.environ.get("HIPPODEMO_OPENAI_COMPATIBLE_BASE_URL")
            or os.environ.get("HIPPODEMO_VLLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or DEFAULT_OPENAI_COMPATIBLE_BASE_URL
        )

    def _configured_asr_model(self) -> str | None:
        return (
            self._provider_config_value("asr_model")
            or os.environ.get("HIPPODEMO_ASR_MODEL")
            or os.environ.get("HIPPODEMO_VLLM_ASR_MODEL")
        )

    def _configured_summary_model(self) -> str | None:
        return (
            self._provider_config_value("summary_model")
            or os.environ.get("HIPPODEMO_SUMMARY_MODEL")
            or os.environ.get("HIPPODEMO_VLLM_SUMMARY_MODEL")
            or os.environ.get("HIPPODEMO_VLLM_CHAT_MODEL")
        )

    def _summary_enabled(self) -> bool:
        disabled = self._env("HIPPODEMO_SUMMARY_DISABLED", "HIPPODEMO_VLLM_SUMMARY_DISABLED", default="")
        return disabled.lower() not in {"1", "true", "yes"}

    def _asr_provider(self) -> str:
        return self._provider(
            self._provider_config_value("asr_provider")
            or self._env("HIPPODEMO_ASR_PROVIDER", "HIPPODEMO_VLLM_ASR_PROVIDER"),
            vllm_markers=("HIPPODEMO_VLLM_ASR_BASE_URL", "HIPPODEMO_VLLM_ASR_MODEL", "HIPPODEMO_VLLM_BASE_URL"),
        )

    def _summary_provider(self) -> str:
        return self._provider(
            self._provider_config_value("summary_provider")
            or self._env("HIPPODEMO_SUMMARY_PROVIDER", "HIPPODEMO_VLLM_SUMMARY_PROVIDER"),
            vllm_markers=(
                "HIPPODEMO_VLLM_SUMMARY_BASE_URL",
                "HIPPODEMO_VLLM_SUMMARY_MODEL",
                "HIPPODEMO_VLLM_CHAT_MODEL",
                "HIPPODEMO_VLLM_BASE_URL",
            ),
        )

    def _provider(self, configured: str | None, *, vllm_markers: tuple[str, ...]) -> str:
        if configured:
            return configured.strip().lower()
        if any(os.environ.get(name) for name in vllm_markers):
            return "vllm"
        return "openai-compatible"

    def _api_key(self, capability: str | None = None) -> str | None:
        return self._explicit_api_key(capability) or "not-needed"

    def _explicit_api_key(self, capability: str | None = None) -> str | None:
        if capability == "asr":
            key = self._provider_config_value("asr_api_key") or self._env(
                "HIPPODEMO_ASR_API_KEY",
                "HIPPODEMO_VLLM_ASR_API_KEY",
            )
            if key:
                return key
        if capability == "summary":
            key = self._provider_config_value("summary_api_key") or self._env(
                "HIPPODEMO_SUMMARY_API_KEY",
                "HIPPODEMO_VLLM_SUMMARY_API_KEY",
            )
            if key:
                return key
        return (
            self._provider_config_value("api_key")
            or os.environ.get("HIPPODEMO_OPENAI_COMPATIBLE_API_KEY")
            or os.environ.get("HIPPODEMO_VLLM_API_KEY")
            or os.environ.get("HIPPODEMO_OPENAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )

    def _api_key_configured(self, capability: str | None = None) -> bool:
        return bool(self._explicit_api_key(capability))

    def _http_timeout(self) -> float:
        raw = self._env("HIPPODEMO_HTTP_TIMEOUT_SECONDS", "HIPPODEMO_VLLM_TIMEOUT_SECONDS")
        if not raw:
            return DEFAULT_HTTP_TIMEOUT
        try:
            return float(raw)
        except ValueError:
            return DEFAULT_HTTP_TIMEOUT

    def _audio_source(self) -> str:
        raw = (
            self._read_config().get("audio_source")
            or os.environ.get("HIPPODEMO_OWNSCRIBE_AUDIO_SOURCE")
            or DEFAULT_AUDIO_SOURCE
        )
        return self._normalize_audio_source(str(raw))

    def _normalize_audio_source(self, raw: str) -> str:
        normalized = raw.strip().lower()
        if normalized in SYSTEM_AUDIO_SOURCE_ALIASES:
            return "system"
        if normalized in MIC_AUDIO_SOURCE_ALIASES:
            return "mic"
        if normalized in BOTH_AUDIO_SOURCE_ALIASES:
            return "both"
        raise ValueError(f"unsupported ownscribe audio source: {raw!r}; use system, mic, or both")

    def _audio_mic_device(self) -> str:
        configured = self._read_config().get("mic_device")
        if configured is not None:
            return str(configured).strip()
        return os.environ.get("HIPPODEMO_OWNSCRIBE_MIC_DEVICE", "").strip()

    def _audio_display_enabled(self) -> str:
        configured = self._read_config().get("audio_display")
        if isinstance(configured, bool):
            return "1" if configured else "0"
        raw = os.environ.get("HIPPODEMO_OWNSCRIBE_AUDIO_DISPLAY")
        if raw is None:
            return "1"
        return "1" if raw.lower() in {"1", "true", "yes", "on"} else "0"

    def _read_config(self) -> dict[str, Any]:
        if not CONFIG_PATH.exists():
            return {}
        try:
            payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_config(self, payload: dict[str, Any]) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        safe_payload = {
            "audio_source": self._normalize_audio_source(str(payload.get("audio_source") or DEFAULT_AUDIO_SOURCE)),
            "mic_device": str(payload.get("mic_device") or "").strip(),
            "audio_display": bool(payload.get("audio_display", True)),
            "updated_at": now_iso(),
        }
        CONFIG_PATH.write_text(json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_provider_config(self) -> dict[str, Any]:
        if not PROVIDER_CONFIG_PATH.exists():
            return {}
        try:
            payload = json.loads(PROVIDER_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _update_provider_config(self, **updates: str | None) -> None:
        if not any(value is not None for value in updates.values()):
            return

        config = self._read_provider_config()
        for key, value in updates.items():
            if value is None:
                continue
            cleaned = value.strip()
            if cleaned:
                config[key] = cleaned
            else:
                config.pop(key, None)
        self._write_provider_config(config)

    def _write_provider_config(self, payload: dict[str, Any]) -> None:
        PROVIDER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        safe_payload: dict[str, Any] = {}

        for key in ("asr_provider", "summary_provider"):
            value = str(payload.get(key) or "").strip().lower()
            if value:
                safe_payload[key] = value

        for key in ("asr_base_url", "summary_base_url"):
            value = str(payload.get(key) or "").strip()
            if value:
                safe_payload[key] = self._normalize_base_url(value)

        for key in ("asr_model", "summary_model", "asr_api_key", "summary_api_key", "api_key"):
            value = str(payload.get(key) or "").strip()
            if value:
                safe_payload[key] = value

        safe_payload["updated_at"] = now_iso()
        PROVIDER_CONFIG_PATH.write_text(
            json.dumps(safe_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _provider_config_value(self, key: str) -> str | None:
        value = self._read_provider_config().get(key)
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    def _ownscribe_audio_binary(self) -> Path | None:
        candidates = [
            OWNSCRIBE_DIR / "bin" / "ownscribe-audio",
            Path(sys.prefix) / "bin" / "ownscribe-audio",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        found = shutil.which("ownscribe-audio")
        return Path(found) if found else None

    def _parse_audio_devices(self, output: str) -> list[dict[str, Any]]:
        devices: list[dict[str, Any]] = []
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "Input devices:":
                continue
            is_default = stripped.endswith("(default)")
            name = stripped.removesuffix("(default)").strip()
            if name:
                devices.append({"name": name, "is_default": is_default})
        return devices

    def _preflight_check(self, name: str, ok: bool, detail: str) -> dict[str, Any]:
        return {"name": name, "ok": bool(ok), "detail": detail}

    def _models_endpoint_ok(self, base_url: str, *, api_key: str | None) -> tuple[bool, str]:
        try:
            data = self._request_bytes(
                "GET",
                self._join_url(base_url, "/models"),
                timeout=10.0,
                api_key=api_key,
            )
            payload = json.loads(data.decode("utf-8", errors="replace"))
            models = payload.get("data") if isinstance(payload, dict) else None
            count = len(models) if isinstance(models, list) else 0
            return count > 0, f"{count} model(s) visible at {base_url}"
        except Exception as exc:
            return False, self._redact_sensitive(str(exc))

    def _latest_recording_timeline(self) -> Path | None:
        if not DATA_DIR.exists():
            return None
        timelines = list(DATA_DIR.glob("*/recording_timeline.json"))
        if not timelines:
            return None
        return max(timelines, key=lambda path: path.stat().st_mtime)

    def _env(self, *names: str, default: str | None = None) -> str | None:
        for name in names:
            value = os.environ.get(name)
            if value is not None and value != "":
                return value
        return default

    def _normalize_base_url(self, url: str) -> str:
        normalized = url.rstrip("/")
        if not normalized.endswith("/v1"):
            normalized = f"{normalized}/v1"
        return normalized

    def _join_url(self, base_url: str, path: str) -> str:
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    def _redact_sensitive(self, value: str) -> str:
        redacted = value
        for key in {
            self._explicit_api_key("asr"),
            self._explicit_api_key("summary"),
            self._explicit_api_key(None),
        }:
            if key:
                redacted = redacted.replace(key, "[redacted]")
        redacted = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]", redacted, flags=re.IGNORECASE)
        redacted = re.sub(r"sk-[A-Za-z0-9._-]{8,}", "sk-[redacted]", redacted)
        return redacted

    def _python_executable(self) -> str:
        override = os.environ.get("OWNSCRIBE_PYTHON")
        if override:
            return override
        local_python = OWNSCRIBE_DIR / ".venv" / "bin" / "python"
        if local_python.exists():
            return str(local_python)
        return sys.executable

    def _pythonpath(self, current: str | None) -> str:
        parts = [str(OWNSCRIBE_SRC)]
        if current:
            parts.append(current)
        return os.pathsep.join(parts)

    def _validate_session_id(self, session_id: str) -> str | None:
        if not session_id:
            return "session_id is required"
        if not SESSION_ID_RE.fullmatch(session_id):
            return "session_id may only contain letters, numbers, underscore, dash, and dot"
        return None

    def _refresh_finished_sessions_locked(self) -> None:
        for record in self._sessions.values():
            if record.result is None and record.process.poll() is not None:
                record.result = self._collect_result(record, returncode=record.process.returncode)

    def _collect_result(
        self,
        record: _SessionProcess,
        *,
        returncode: int | None,
        error: str | None = None,
        forced_failure: bool = False,
    ) -> OwnscribeResult:
        return self._collect_result_from_paths(
            session_id=record.session_id,
            base_output_dir=record.base_output_dir,
            stdout_log_path=record.stdout_log_path,
            stderr_log_path=record.stderr_log_path,
            returncode=returncode,
            error=error,
            forced_failure=forced_failure,
        )

    def _collect_result_from_paths(
        self,
        *,
        session_id: str,
        base_output_dir: Path,
        stdout_log_path: Path,
        stderr_log_path: Path,
        returncode: int | None,
        error: str | None = None,
        forced_failure: bool = False,
    ) -> OwnscribeResult:
        output_dir = self._latest_output_dir(base_output_dir)
        transcript_path = self._first_existing(output_dir, "transcript", ("md", "json")) if output_dir else None
        summary_path = self._first_existing(output_dir, "summary", ("md", "json")) if output_dir else None
        audio_path = self._audio_path(output_dir) if output_dir else None

        ok = not forced_failure and (returncode in (0, None)) and transcript_path is not None
        details = []
        if returncode is not None:
            details.append(f"rc={returncode}")
        details.append(f"base_output_dir={base_output_dir}")
        if output_dir is not None:
            details.append(f"output_dir={output_dir}")
        if transcript_path is None:
            details.append("transcript=missing")
        if summary_path is None:
            details.append("summary=missing")
        if audio_path is None:
            details.append("audio=missing")
        log_detail = self._log_detail(stdout_log_path, stderr_log_path)
        if log_detail:
            details.append(log_detail)

        result_error = error
        if result_error is None and not ok:
            if returncode not in (0, None):
                result_error = f"ownscribe exited with rc={returncode}"
            elif transcript_path is None:
                result_error = "ownscribe output did not include transcript.md or transcript.json"

        return OwnscribeResult(
            ok=ok,
            session_id=session_id,
            output_dir=str(output_dir) if output_dir else str(base_output_dir),
            transcript_path=str(transcript_path) if transcript_path else None,
            summary_path=str(summary_path) if summary_path else None,
            audio_path=str(audio_path) if audio_path else None,
            detail="; ".join(details),
            error=result_error,
        )

    def _result_from_existing_output(self, session_id: str) -> OwnscribeResult:
        validation_error = self._validate_session_id(session_id)
        if validation_error:
            return OwnscribeResult(ok=False, session_id=session_id, error=validation_error)

        base_output_dir = DATA_DIR / session_id
        if not base_output_dir.exists():
            return OwnscribeResult(
                ok=False,
                session_id=session_id,
                output_dir=str(base_output_dir),
                error="ownscribe session is unknown and has no output directory",
            )

        return self._collect_result_from_paths(
            session_id=session_id,
            base_output_dir=base_output_dir,
            stdout_log_path=base_output_dir / "ownscribe.stdout.log",
            stderr_log_path=base_output_dir / "ownscribe.stderr.log",
            returncode=None,
        )

    def _latest_output_dir(self, base_output_dir: Path) -> Path | None:
        if not base_output_dir.exists():
            return None

        candidates = []
        if self._contains_artifacts(base_output_dir):
            candidates.append(base_output_dir)
        candidates.extend(path for path in base_output_dir.iterdir() if path.is_dir())
        if not candidates:
            return base_output_dir
        return max(candidates, key=lambda path: path.stat().st_mtime)

    def _contains_artifacts(self, directory: Path) -> bool:
        return any(
            (directory / name).exists()
            for name in (
                "transcript.md",
                "transcript.json",
                "summary.md",
                "summary.json",
                "recording.wav",
            )
        )

    def _first_existing(self, directory: Path, stem: str, extensions: tuple[str, ...]) -> Path | None:
        for extension in extensions:
            path = directory / f"{stem}.{extension}"
            if path.exists():
                return path
        return None

    def _audio_path(self, directory: Path) -> Path | None:
        recording = directory / "recording.wav"
        if recording.exists():
            return recording
        wav_files = sorted(directory.glob("*.wav"), key=lambda path: path.stat().st_mtime, reverse=True)
        return wav_files[0] if wav_files else None

    def _signal_process_group(self, process: subprocess.Popen[bytes], sig: signal.Signals) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        except OSError:
            try:
                process.send_signal(sig)
            except OSError:
                return

    def _latest_record(self, records: list[_SessionProcess]) -> _SessionProcess:
        return max(records, key=lambda record: record.started_at)

    def _record_detail(self, record: _SessionProcess) -> str:
        return (
            f"session_id={record.session_id}; pid={record.process.pid}; "
            f"audio_source={self._audio_source()}; "
            f"mic_device={self._audio_mic_device() or 'default'}; "
            f"base_output_dir={record.base_output_dir}; "
            f"stdout={record.stdout_log_path}; stderr={record.stderr_log_path}"
        )

    def _log_detail(self, stdout_log_path: Path, stderr_log_path: Path) -> str:
        parts = []
        stdout_tail = self._tail(stdout_log_path)
        stderr_tail = self._tail(stderr_log_path)
        if stdout_tail:
            parts.append(f"stdout_tail={stdout_tail}")
        if stderr_tail:
            parts.append(f"stderr_tail={stderr_tail}")
        return "; ".join(parts)

    def _tail(self, path: Path, max_chars: int = 1200) -> str:
        if not path.exists():
            return ""
        try:
            data = path.read_bytes()[-max_chars:]
        except OSError:
            return ""
        return " | ".join(line.strip() for line in data.decode(errors="replace").splitlines() if line.strip())


ownscribe_adapter = OwnscribeAdapter()

__all__ = ["OwnscribeAdapter", "OwnscribeResult", "ownscribe_adapter"]
