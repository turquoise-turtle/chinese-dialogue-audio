"""Engine tests with the network call replaced, so they run offline."""

import asyncio

import pytest
from edge_tts.exceptions import NoAudioReceived

import tts_engine
from tts_engine import (
    DEFAULT_VOICE_ROTATION,
    NARRATOR_VOICE,
    assign_default_voices,
    detect_speakers,
    generate_audio,
    parse_dialogue,
)

FRAME = tts_engine._SILENT_FRAME
SEGMENT_FRAMES = 10


@pytest.fixture
def fake_stream(monkeypatch):
    calls = []

    async def fake(text, voice, rate):
        calls.append((text, voice, rate))
        return FRAME * SEGMENT_FRAMES, [{"text": text[:1], "start": 0.05, "end": 0.1}]

    monkeypatch.setattr(tts_engine, "_stream_line", fake)
    return calls


@pytest.fixture
def no_backoff(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr(tts_engine.asyncio, "sleep", instant)


def test_parse_dialogue_handles_both_colons_and_continuations():
    text = "售货员：您好！\n\n顾客: 我要水。\n还要面包。"
    assert parse_dialogue(text) == [
        ("售货员", "您好！"),
        ("顾客", "我要水。"),
        ("顾客", "还要面包。"),
    ]


def test_lines_without_a_speaker_belong_to_the_narrator():
    assert parse_dialogue("今天是星期三。") == [("旁白", "今天是星期三。")]


def test_detect_speakers_keeps_first_appearance_order():
    lines = [("B", "1"), ("A", "2"), ("B", "3")]
    assert detect_speakers(lines) == ["B", "A"]


def test_narrator_gets_broadcast_voice_and_others_rotate():
    assert assign_default_voices(["旁白", "A", "B"]) == {
        "旁白": NARRATOR_VOICE,
        "A": DEFAULT_VOICE_ROTATION[0],
        "B": DEFAULT_VOICE_ROTATION[1],
    }


def test_pause_is_whole_frames_close_to_the_configured_length():
    assert len(FRAME) == 144
    assert tts_engine._PAUSE_S == pytest.approx(tts_engine.PAUSE_BETWEEN_LINES_MS / 1000, abs=0.024)


def test_audio_and_timing_include_segments_and_pauses(fake_stream):
    mp3, timing = generate_audio([("A", "你好"), ("B", "谢谢")], {"A": "voice-a"}, rate="-10%")

    segment_s = SEGMENT_FRAMES * tts_engine._FRAME_SECONDS
    pause_s = tts_engine._PAUSE_S
    assert mp3 == FRAME * SEGMENT_FRAMES + tts_engine._PAUSE_MP3 + FRAME * SEGMENT_FRAMES
    assert timing[0]["start"] == 0
    assert timing[0]["end"] == pytest.approx(segment_s, abs=1e-3)
    assert timing[1]["start"] == pytest.approx(segment_s + pause_s, abs=1e-3)
    assert timing[1]["words"][0]["start"] == pytest.approx(segment_s + pause_s + 0.05, abs=1e-3)
    assert sorted(fake_stream) == [
        ("你好", "voice-a", "-10%"),
        ("谢谢", DEFAULT_VOICE_ROTATION[0], "-10%"),
    ]


def test_lines_run_concurrently_up_to_the_limit(monkeypatch):
    active = peak = 0

    async def slow(text, voice, rate):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return FRAME, []

    monkeypatch.setattr(tts_engine, "_stream_line", slow)
    generate_audio([("A", str(i)) for i in range(12)], {})
    assert peak == tts_engine.MAX_CONCURRENT_LINES


def test_transient_failures_are_retried(monkeypatch, no_backoff):
    attempts = []

    async def flaky(text, voice, rate):
        attempts.append(text)
        if len(attempts) < tts_engine.MAX_ATTEMPTS:
            raise ConnectionError("dropped")
        return FRAME, []

    monkeypatch.setattr(tts_engine, "_stream_line", flaky)
    mp3, _ = generate_audio([("A", "你好")], {})
    assert mp3 == FRAME
    assert len(attempts) == tts_engine.MAX_ATTEMPTS


def test_persistent_failure_raises(monkeypatch, no_backoff):
    async def broken(text, voice, rate):
        raise ConnectionError("403")

    monkeypatch.setattr(tts_engine, "_stream_line", broken)
    with pytest.raises(ConnectionError):
        generate_audio([("A", "你好")], {})


def test_unspeakable_line_is_skipped_not_an_error(monkeypatch):
    async def no_audio(text, voice, rate):
        raise NoAudioReceived("nothing to say")

    monkeypatch.setattr(tts_engine, "_stream_line", no_audio)
    mp3, timing = generate_audio([("A", "……")], {})
    assert mp3 == b""
    assert timing[0]["end"] == 0
