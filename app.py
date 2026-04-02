import io
import json
import os
import random
import threading
import time
import urllib.parse
import urllib.request
import uuid

from flask import Flask, render_template, request, jsonify, send_file, abort
from pypinyin import pinyin, Style

from tts_engine import (
    parse_dialogue,
    detect_speakers,
    assign_default_voices,
    generate_audio,
    VOICES,
)
from conversation_library import LIBRARY

app = Flask(__name__)

_audio_store: dict[str, tuple[bytes, float]] = {}
_AUDIO_TTL = 300  # seconds
_store_lock = threading.Lock()


def _store_audio(mp3_bytes: bytes) -> str:
    """Store MP3 bytes under a UUID and return the key."""
    key = uuid.uuid4().hex
    with _store_lock:
        _audio_store[key] = (mp3_bytes, time.time())
        expired = [k for k, (_, ts) in _audio_store.items() if time.time() - ts > _AUDIO_TTL]
        for k in expired:
            del _audio_store[k]
    return key


@app.route("/")
def index():
    conv = random.choice(LIBRARY)
    return render_template("index.html", voices=VOICES, default_text=conv["text"])


@app.route("/random-conversation")
def random_conversation():
    conv = random.choice(LIBRARY)
    return jsonify({"title": conv["title"], "text": conv["text"]})


@app.route("/parse", methods=["POST"])
def parse():
    text = request.json.get("text", "")
    lines = parse_dialogue(text)
    speakers = detect_speakers(lines)
    defaults = assign_default_voices(speakers)
    return jsonify({"speakers": speakers, "defaults": defaults})


@app.route("/generate", methods=["POST"])
def generate():
    text = request.json.get("text", "")
    voice_map = request.json.get("voice_map", {})
    rate = request.json.get("rate", "+0%")

    lines = parse_dialogue(text)
    if not lines:
        return jsonify({"error": "No dialogue lines found"}), 400

    mp3_bytes, timing = generate_audio(lines, voice_map, rate=rate)
    audio_id = _store_audio(mp3_bytes)

    return jsonify({"id": audio_id, "timing": timing})


@app.route("/audio/<audio_id>")
def serve_audio(audio_id):
    with _store_lock:
        entry = _audio_store.get(audio_id)
    if not entry:
        abort(404)
    mp3_bytes, _ = entry
    return send_file(
        io.BytesIO(mp3_bytes),
        mimetype="audio/mpeg",
        as_attachment=False,
        download_name="dialogue.mp3",
    )


_TONE_MARKS = {
    "a": "āáǎà", "e": "ēéěè", "i": "īíǐì",
    "o": "ōóǒò", "u": "ūúǔù", "ü": "ǖǘǚǜ",
}


def _tone_num(py3: str) -> int:
    """Tone number from TONE3 string (e.g. 'ni3' -> 3). 0 = neutral."""
    return int(py3[-1]) if py3 and py3[-1] in "12345" else 0


def _set_tone(py3: str, tone: int) -> str:
    if py3 and py3[-1] in "12345":
        return py3[:-1] + str(tone)
    return py3


def _py3_to_display(py3: str) -> str:
    """Convert TONE3 ('ni3') to display form ('nǐ')."""
    if not py3 or py3[-1] not in "1234":
        return py3.rstrip("05") if py3 else py3
    ti = int(py3[-1]) - 1
    base = py3[:-1]
    for i, c in enumerate(base):
        if c in ("a", "e"):
            return base[:i] + _TONE_MARKS[c][ti] + base[i + 1:]
    if "ou" in base:
        i = base.index("o")
        return base[:i] + _TONE_MARKS["o"][ti] + base[i + 1:]
    for i in range(len(base) - 1, -1, -1):
        if base[i] in _TONE_MARKS:
            return base[:i] + _TONE_MARKS[base[i]][ti] + base[i + 1:]
    return base


def _annotate_pinyin(text: str) -> str:
    """Return HTML with ruby pinyin annotations and tone sandhi applied."""
    tokens = []
    for char in text:
        if "\u4e00" <= char <= "\u9fff":
            py3 = pinyin(char, style=Style.TONE3)[0][0]
            tokens.append({"c": char, "py3": py3, "zh": True, "sandhi": False})
        else:
            tokens.append({"c": char, "zh": False})

    zh_idx = [i for i, t in enumerate(tokens) if t.get("zh")]

    # Group into contiguous runs (punctuation / spaces break runs)
    runs = []
    cur = []
    for idx in zh_idx:
        if cur and idx != cur[-1] + 1:
            runs.append(cur)
            cur = []
        cur.append(idx)
    if cur:
        runs.append(cur)

    for run in runs:
        # 3rd-tone sandhi: consecutive 3rd tones -> first becomes 2nd
        for j in range(len(run) - 1):
            t, t_next = tokens[run[j]], tokens[run[j + 1]]
            if _tone_num(t["py3"]) == 3 and _tone_num(t_next["py3"]) == 3:
                t["py3"] = _set_tone(t["py3"], 2)
                t["sandhi"] = True

        # 一 sandhi: 4th tone before 4th → 2nd; before 1st/2nd/3rd → 4th
        for j in range(len(run)):
            t = tokens[run[j]]
            if t["c"] == "\u4e00" and j + 1 < len(run):
                nt = _tone_num(tokens[run[j + 1]]["py3"])
                if nt == 4:
                    t["py3"], t["sandhi"] = "yi2", True
                elif nt in (1, 2, 3):
                    t["py3"], t["sandhi"] = "yi4", True

        # 不 sandhi: before 4th tone → 2nd tone
        for j in range(len(run)):
            t = tokens[run[j]]
            if t["c"] == "\u4e0d" and j + 1 < len(run):
                if _tone_num(tokens[run[j + 1]]["py3"]) == 4:
                    t["py3"], t["sandhi"] = "bu2", True

    result = []
    for t in tokens:
        if not t.get("zh"):
            result.append(t["c"])
            continue
        display = _py3_to_display(t["py3"])
        if t["sandhi"]:
            result.append(
                f'<ruby>{t["c"]}<rp>(</rp>'
                f'<rt class="sandhi">{display}</rt><rp>)</rp></ruby>'
            )
        else:
            result.append(
                f'<ruby>{t["c"]}<rp>(</rp><rt>{display}</rt><rp>)</rp></ruby>'
            )
    return "".join(result)


@app.route("/pinyin", methods=["POST"])
def add_pinyin():
    text = request.json.get("text", "")
    lines = text.strip().splitlines()
    annotated = []
    for line in lines:
        annotated.append(_annotate_pinyin(line))
    return jsonify({"html": "<br>".join(annotated)})


def _google_translate(text: str, src: str = "zh-CN", tgt: str = "en") -> str:
    """Call the same Google Translate endpoint the website uses."""
    url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode({
        "client": "gtx", "sl": src, "tl": tgt, "dt": "t", "q": text,
    })
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
    return "".join(seg[0] for seg in data[0] if seg[0])


@app.route("/translate", methods=["POST"])
def translate():
    text = request.json.get("text", "")
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    translated = []
    for line in lines:
        try:
            translated.append(_google_translate(line))
        except Exception:
            translated.append(line)
    return jsonify({"lines": translated})


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", port=5000)
