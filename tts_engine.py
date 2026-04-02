from __future__ import annotations

import asyncio
import io
import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional

import edge_tts

# Locate ffmpeg binary: prefer imageio-ffmpeg bundle, then system ffmpeg.
_FFMPEG = shutil.which("ffmpeg")
try:
    import imageio_ffmpeg
    _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    pass

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


async def _synthesize_line(text: str, voice: str, rate: str) -> bytes:
    """Generate MP3 bytes for a single line using edge-tts."""
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    return buffer.getvalue()


def _make_silence_mp3(duration_ms: int, tmpdir: str) -> str:
    """Create a short silent MP3 file and return its path."""
    path = os.path.join(tmpdir, "_silence.mp3")
    if os.path.exists(path):
        return path
    duration_s = duration_ms / 1000.0
    subprocess.run(
        [
            _FFMPEG, "-y", "-f", "lavfi",
            "-i", f"anullsrc=r=24000:cl=mono",
            "-t", str(duration_s),
            "-c:a", "libmp3lame", "-b:a", "48k",
            path,
        ],
        capture_output=True,
        check=True,
    )
    return path


def _concat_mp3_files(file_paths: list[str], output_path: str) -> None:
    """Concatenate MP3 files using ffmpeg's concat demuxer."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in file_paths:
            f.write(f"file '{p}'\n")
        list_path = f.name

    try:
        subprocess.run(
            [
                _FFMPEG, "-y", "-f", "concat", "-safe", "0",
                "-i", list_path,
                "-c:a", "libmp3lame", "-b:a", "48k",
                output_path,
            ],
            capture_output=True,
            check=True,
        )
    finally:
        os.unlink(list_path)


async def _generate_audio_async(
    lines: list[tuple[str, str]],
    voice_map: dict[str, str],
    rate: str = "+0%",
) -> bytes:
    """Generate a combined MP3 from dialogue lines, returning raw bytes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        silence_path = _make_silence_mp3(PAUSE_BETWEEN_LINES_MS, tmpdir)
        segment_paths: list[str] = []

        for i, (speaker, text) in enumerate(lines):
            voice = voice_map.get(speaker, DEFAULT_VOICE_ROTATION[0])
            mp3_bytes = await _synthesize_line(text, voice, rate)

            seg_path = os.path.join(tmpdir, f"line_{i:04d}.mp3")
            with open(seg_path, "wb") as f:
                f.write(mp3_bytes)
            segment_paths.append(seg_path)

            if i < len(lines) - 1:
                segment_paths.append(silence_path)

        out_path = os.path.join(tmpdir, "combined.mp3")
        _concat_mp3_files(segment_paths, out_path)

        with open(out_path, "rb") as f:
            return f.read()


def generate_audio(
    lines: list[tuple[str, str]],
    voice_map: dict[str, str],
    rate: str = "+0%",
    output_path: Optional[str] = None,
) -> bytes:
    """Synchronous wrapper that generates combined MP3 audio.

    If *output_path* is given the MP3 is also written to disk.
    Returns the raw MP3 bytes either way.
    """
    mp3_bytes = asyncio.run(_generate_audio_async(lines, voice_map, rate))

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(mp3_bytes)

    return mp3_bytes
