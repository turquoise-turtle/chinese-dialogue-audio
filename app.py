import base64
import hashlib
import hmac
import html
import json
import os
import random
import re
import secrets
import urllib.parse
import urllib.request

from flask import Flask, g, jsonify, redirect, render_template, request, url_for
from pypinyin import pinyin, Style
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from tts_engine import (
    parse_dialogue,
    detect_speakers,
    assign_default_voices,
    generate_audio,
    VOICES,
)
from conversation_library import LIBRARY

app = Flask(__name__)
# Render and Hugging Face terminate HTTPS at a proxy; trust its X-Forwarded-Proto
# so request.is_secure is accurate.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)

# Optional passcode gate. When APP_PASSCODE is unset, the app is open to anyone.
PASSCODE = os.environ.get("APP_PASSCODE", "")
_AUTH_COOKIE = "auth"
_AUTH_MAX_AGE = 30 * 24 * 3600
_OPEN_ENDPOINTS = {"login", "healthz", "static"}

_RATE_RE = re.compile(r"^[+-]\d{1,2}%$")
_MAX_RATE = 50


def _auth_token() -> str:
    """Cookie value proving the passcode was entered; changes with the passcode."""
    return hmac.new(PASSCODE.encode(), b"chinese-dialogue-audio", hashlib.sha256).hexdigest()


def _csp_nonce() -> str:
    if "csp_nonce" not in g:
        g.csp_nonce = secrets.token_urlsafe(16)
    return g.csp_nonce


app.jinja_env.globals["csp_nonce"] = _csp_nonce


@app.before_request
def require_passcode():
    if not PASSCODE or request.endpoint in _OPEN_ENDPOINTS:
        return None
    if hmac.compare_digest(request.cookies.get(_AUTH_COOKIE, ""), _auth_token()):
        return None
    if request.method == "GET" and request.endpoint == "index":
        return redirect(url_for("login"))
    return jsonify({"error": "Passcode required"}), 401


@app.after_request
def security_headers(resp):
    nonce = g.get("csp_nonce")
    script_src = f"'nonce-{nonce}'" if nonce else "'none'"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src {script_src}; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "media-src 'self' blob:; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        # Hugging Face Spaces shows the app in an iframe on huggingface.co.
        "frame-ancestors 'self' https://huggingface.co"
    )
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


@app.errorhandler(HTTPException)
def http_error(e):
    return jsonify({"error": e.description}), e.code


def _json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _text_field(data: dict) -> str:
    text = data.get("text", "")
    return text if isinstance(text, str) else ""


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/login", methods=["GET", "POST"])
def login():
    if not PASSCODE:
        return redirect(url_for("index"))
    if request.method == "POST":
        entered = request.form.get("passcode", "").encode()
        if hmac.compare_digest(entered, PASSCODE.encode()):
            resp = redirect(url_for("index"))
            # SameSite=None lets the cookie work inside the Hugging Face iframe.
            resp.set_cookie(
                _AUTH_COOKIE, _auth_token(), max_age=_AUTH_MAX_AGE, httponly=True,
                secure=request.is_secure,
                samesite="None" if request.is_secure else "Lax",
            )
            return resp
        return render_template("login.html", error="Wrong passcode"), 401
    return render_template("login.html", error=None)


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
    text = _text_field(_json_body())
    lines = parse_dialogue(text)
    speakers = detect_speakers(lines)
    defaults = assign_default_voices(speakers)
    return jsonify({"speakers": speakers, "defaults": defaults})


@app.route("/generate", methods=["POST"])
def generate():
    data = _json_body()
    text = _text_field(data)
    voice_map = data.get("voice_map") or {}
    rate = data.get("rate", "+0%")

    if not isinstance(voice_map, dict) or not all(
        isinstance(v, str) and v in VOICES for v in voice_map.values()
    ):
        return jsonify({"error": "Unknown voice"}), 400
    if not isinstance(rate, str) or not _RATE_RE.match(rate) or abs(int(rate[:-1])) > _MAX_RATE:
        return jsonify({"error": f"Rate must be between -{_MAX_RATE}% and +{_MAX_RATE}%"}), 400

    lines = parse_dialogue(text)
    if not lines:
        return jsonify({"error": "No dialogue lines found"}), 400

    try:
        mp3_bytes, timing = generate_audio(lines, voice_map, rate=rate)
    except Exception:
        app.logger.exception("Audio generation failed")
        return jsonify({"error": "The speech service failed, please try again"}), 502

    # Audio travels in the response itself, so no server-side storage is needed
    # and any worker can serve any request.
    return jsonify({
        "audio": base64.b64encode(mp3_bytes).decode("ascii"),
        "timing": timing,
    })


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
            result.append(html.escape(t["c"]))
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
    text = _text_field(_json_body())
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
    text = _text_field(_json_body())
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    translated = []
    for line in lines:
        try:
            translated.append(_google_translate(line))
        except Exception:
            translated.append(line)
    return jsonify({"lines": translated})


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
        port=int(os.environ.get("PORT", "5000")),
    )
