from __future__ import annotations

import asyncio
import io
import os
import re
from typing import Optional

import edge_tts
from edge_tts.exceptions import NoAudioReceived

VOICES = {
    "zh-CN-XiaoxiaoNeural": "Xiaoxiao (female, natural)",
    "zh-CN-XiaoyiNeural": "Xiaoyi (female, young)",
    "zh-CN-YunxiNeural": "Yunxi (male, natural)",
    "zh-CN-YunyangNeural": "Yunyang (male, broadcast)",
    "zh-CN-YunjianNeural": "Yunjian (male, sporty)",
    "zh-CN-YunxiaNeural": "Yunxia (male, boyish)",
}

DEFAULT_VOICE_ROTATION = [
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-XiaoyiNeural",
    "zh-CN-YunyangNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-YunxiaNeural",
]

NARRATOR_VOICE = "zh-CN-YunyangNeural"

PAUSE_BETWEEN_LINES_MS = 900


# edge-tts always returns constant-bitrate MP3 (24 kHz, 48 kbps, mono), so a
# segment's duration is its byte length divided by the byte rate, and segments
# can be joined by concatenating bytes. No ffmpeg needed.
_MP3_BYTES_PER_SECOND = 48_000 // 8
_FRAME_SECONDS = 576 / 24_000  # one MPEG-2 Layer III frame

# A silent frame in the same format: the header edge-tts emits, followed by
# zeroed side info and main data, which decodes to silence.
_SILENT_FRAME = b"\xff\xf3\x64\xc4" + bytes(140)

_PAUSE_MP3 = _SILENT_FRAME * round(PAUSE_BETWEEN_LINES_MS / 1000 / _FRAME_SECONDS)
_PAUSE_S = len(_PAUSE_MP3) / _MP3_BYTES_PER_SECOND

MAX_CONCURRENT_LINES = 5
MAX_ATTEMPTS = 3


def parse_dialogue(text: str) -> list[tuple[str, str]]:
    """Split pasted text into [(speaker, line), ...].

    Accepts both Chinese full-width colon and ASCII colon.
    Blank lines are skipped.  Lines without a colon are treated as
    continuation of the previous speaker.
    """
    lines: list[tuple[str, str]] = []
    prev_speaker = "旁白"

    for raw in text.strip().splitlines():
        raw = raw.strip()
        if not raw:
            continue

        m = re.match(r"^(.+?)\s*[：:]\s*(.+)$", raw)
        if m:
            speaker = m.group(1).strip()
            content = m.group(2).strip()
            prev_speaker = speaker
        else:
            speaker = prev_speaker
            content = raw

        if content:
            lines.append((speaker, content))

    return lines


def detect_speakers(lines: list[tuple[str, str]]) -> list[str]:
    """Return unique speaker names in order of first appearance."""
    seen: set[str] = set()
    result: list[str] = []
    for speaker, _ in lines:
        if speaker not in seen:
            seen.add(speaker)
            result.append(speaker)
    return result


def assign_default_voices(speakers: list[str]) -> dict[str, str]:
    """Assign voices to speakers using the default rotation.

    The narrator (旁白) always gets the broadcast voice.
    """
    voice_map: dict[str, str] = {}
    rotation_idx = 0

    for speaker in speakers:
        if speaker == "旁白":
            voice_map[speaker] = NARRATOR_VOICE
        else:
            voice_map[speaker] = DEFAULT_VOICE_ROTATION[
                rotation_idx % len(DEFAULT_VOICE_ROTATION)
            ]
            rotation_idx += 1

    return voice_map


async def _stream_line(
    text: str, voice: str, rate: str,
) -> tuple[bytes, list[dict]]:
    """Generate MP3 bytes and word-boundary timing for a single line."""
    communicate = edge_tts.Communicate(
        text, voice, rate=rate, boundary="WordBoundary",
        connect_timeout=10, receive_timeout=30,
    )
    buffer = io.BytesIO()
    word_boundaries: list[dict] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            offset_s = chunk["offset"] / 10_000_000
            duration_s = chunk["duration"] / 10_000_000
            word_boundaries.append({
                "text": chunk["text"],
                "start": round(offset_s, 3),
                "end": round(offset_s + duration_s, 3),
            })
    return buffer.getvalue(), word_boundaries


async def _synthesize_line(
    text: str, voice: str, rate: str,
) -> tuple[bytes, list[dict]]:
    """Like _stream_line, retrying transient failures with backoff."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return await _stream_line(text, voice, rate)
        except NoAudioReceived:
            # Nothing speakable in the line (e.g. only punctuation).
            return b"", []
        except Exception:
            if attempt == MAX_ATTEMPTS:
                raise
            await asyncio.sleep(0.5 * 2 ** (attempt - 1))
    raise AssertionError("unreachable")


async def _generate_audio_async(
    lines: list[tuple[str, str]],
    voice_map: dict[str, str],
    rate: str = "+0%",
) -> tuple[bytes, list[dict]]:
    """Generate a combined MP3 from dialogue lines.

    Lines are synthesized concurrently. Returns (mp3_bytes, timing) where
    timing is a list of per-line dicts with word-level start/end times
    relative to the combined audio.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LINES)

    async def synthesize(speaker: str, text: str) -> tuple[bytes, list[dict]]:
        voice = voice_map.get(speaker, DEFAULT_VOICE_ROTATION[0])
        async with semaphore:
            return await _synthesize_line(text, voice, rate)

    results = await asyncio.gather(*(synthesize(s, t) for s, t in lines))

    parts: list[bytes] = []
    timing: list[dict] = []
    cumulative_offset = 0.0

    for i, ((speaker, text), (mp3_bytes, word_boundaries)) in enumerate(
        zip(lines, results)
    ):
        if i > 0:
            parts.append(_PAUSE_MP3)
            cumulative_offset += _PAUSE_S
        parts.append(mp3_bytes)
        seg_duration = len(mp3_bytes) / _MP3_BYTES_PER_SECOND

        timing.append({
            "line": i,
            "speaker": speaker,
            "text": text,
            "start": round(cumulative_offset, 3),
            "end": round(cumulative_offset + seg_duration, 3),
            "words": [
                {
                    "text": wb["text"],
                    "start": round(cumulative_offset + wb["start"], 3),
                    "end": round(cumulative_offset + wb["end"], 3),
                }
                for wb in word_boundaries
            ],
        })
        cumulative_offset += seg_duration

    return b"".join(parts), timing


def generate_audio(
    lines: list[tuple[str, str]],
    voice_map: dict[str, str],
    rate: str = "+0%",
    output_path: Optional[str] = None,
) -> tuple[bytes, list[dict]]:
    """Synchronous wrapper that generates combined MP3 audio.

    If *output_path* is given the MP3 is also written to disk.
    Returns (mp3_bytes, timing) where timing carries per-line word offsets.
    """
    mp3_bytes, timing = asyncio.run(_generate_audio_async(lines, voice_map, rate))

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(mp3_bytes)

    return mp3_bytes, timing
