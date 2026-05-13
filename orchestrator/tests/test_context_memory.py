from __future__ import annotations

import asyncio
import json
import wave
from pathlib import Path

from orchestrator import store as store_module
from orchestrator.adapters import ownscribe
from orchestrator.adapters.basic_memory import BasicMemoryAdapter
from orchestrator.adapters.ownscribe import OwnscribeAdapter
from orchestrator.models import ContextFragment
from orchestrator.store import OrchestratorStore


def run(coro):
    return asyncio.run(coro)


def _write_test_wav(path: Path, *, duration_seconds: float = 2.0, sample_rate: int = 16_000) -> None:
    frames = int(duration_seconds * sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(sample_rate)
        file.writeframes(b"\x01\x00" * frames)


def test_context_fragment_store_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "CONTEXT_DIR", tmp_path / "context")
    store = OrchestratorStore()
    fragment = ContextFragment(
        id="context_test",
        session_id="session_test",
        modality="voice",
        source="ownscribe",
        text="hello context",
        started_at="2026-05-14T10:00:00+08:00",
        ended_at="2026-05-14T10:00:20+08:00",
        sequence=1,
    )

    run(store.save_context_fragment(fragment))

    loaded = store.get_context_fragment("context_test")
    assert loaded.text == "hello context"
    recent = store.list_context_fragments(session_id="session_test", modality="voice", limit=10)
    assert [item.id for item in recent] == ["context_test"]


def test_context_write_note_uses_context_ledger_key(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "BASIC_MEMORY_DIR", tmp_path / "basic_memory")

    class FakeAdapter(BasicMemoryAdapter):
        def _read_ledger(self):
            return {
                "context:context_123": {
                    "identifier": "hippo/context/voice/chunks/hippo-voice-context-123",
                    "path": "hippo/context/voice/chunks/Hippo Voice Context 123.md",
                    "status": "synced",
                }
            }

        async def _ensure_setup(self):
            raise AssertionError("setup should not run when context ledger already has the source")

    result = run(
        FakeAdapter().write_note(
            kind="context_voice",
            source_id="context_123",
            title="Hippo Voice Context 123",
            folder="hippo/context/voice/chunks",
            content="# Hippo Voice Context 123",
        )
    )

    assert result["status"] == "already_synced"
    assert result["identifier"] == "hippo/context/voice/chunks/hippo-voice-context-123"


def test_ownscribe_creates_valid_wav_segment(tmp_path, monkeypatch):
    monkeypatch.setattr(ownscribe, "DATA_DIR", tmp_path)
    session_dir = tmp_path / "session_test"
    audio_path = session_dir / "recording.wav"
    _write_test_wav(audio_path, duration_seconds=2.0)

    segment_path = OwnscribeAdapter().create_audio_segment(
        "session_test",
        sequence=0,
        start_offset_seconds=0.5,
        end_offset_seconds=1.0,
    )

    assert segment_path.exists()
    with wave.open(str(segment_path), "rb") as file:
        assert file.getnchannels() == 1
        assert file.getframerate() == 16_000
        assert 7_900 <= file.getnframes() <= 8_100


def test_ownscribe_timeline_timestamp_alignment(tmp_path, monkeypatch):
    monkeypatch.setattr(ownscribe, "DATA_DIR", tmp_path)
    session_dir = tmp_path / "session_test"
    session_dir.mkdir(parents=True)
    (session_dir / "recording_timeline.json").write_text(
        json.dumps(
            {
                "recording_started_epoch_seconds": 1_779_360_000,
                "recording_started_at": "2026-05-14T10:00:00+08:00",
            }
        ),
        encoding="utf-8",
    )

    payload = OwnscribeAdapter().recording_timeline("session_test")

    assert payload["recording_started_epoch_seconds"] == 1_779_360_000
