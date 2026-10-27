"""Calls Microsoft's speech service for real. Skipped by default; run with -m live.

Run this after upgrading edge-tts, before pushing.
"""

import pytest

import tts_engine

pytestmark = pytest.mark.live

FRAME_BYTES = len(tts_engine._SILENT_FRAME)
FRAME_HEADER = tts_engine._SILENT_FRAME[:4]


def test_edge_tts_still_returns_the_mp3_format_the_engine_assumes():
    mp3, timing = tts_engine.generate_audio(
        [("售货员", "您好！您要什么？"), ("顾客", "我要两瓶水。")], {}, rate="-10%",
    )

    # Durations and joins are byte arithmetic, so every frame must be this
    # exact constant-bitrate format. If this fails, Microsoft changed it.
    assert len(mp3) % FRAME_BYTES == 0
    assert all(mp3[i:i + 4] == FRAME_HEADER for i in range(0, len(mp3), FRAME_BYTES))
    assert timing[-1]["end"] == pytest.approx(len(mp3) / tts_engine._MP3_BYTES_PER_SECOND, abs=1e-3)
    assert all(line["words"] for line in timing)
