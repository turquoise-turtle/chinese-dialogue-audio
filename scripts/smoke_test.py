# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check the deployed site end to end, the way a visitor uses it.

    uv run scripts/smoke_test.py [URL]

If the site has a passcode, set APP_PASSCODE in your shell first.
Exits non-zero if any check fails.
"""

import base64
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "https://chinese-audio-practice.onrender.com"
# A sleeping free Render instance takes about 30 s to wake.
TIMEOUT = 120
DIALOGUE = "售货员：您好！您要什么？\n顾客：我要两瓶水。\n售货员：一共四块。"

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
failures = []


def fetch(url, json_body=None, form=None):
    if json_body is not None:
        data, ctype = json.dumps(json_body).encode(), "application/json"
    elif form is not None:
        data, ctype = urllib.parse.urlencode(form).encode(), "application/x-www-form-urlencoded"
    else:
        data, ctype = None, None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": ctype} if ctype else {})
    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{f'  ({detail})' if detail else ''}")
    if not ok:
        failures.append(name)


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL).rstrip("/")
    print(f"Checking {base} (first request may take ~30 s while the site wakes)\n")

    status, _, body = fetch(f"{base}/healthz")
    check("health check", status == 200 and json.loads(body) == {"status": "ok"}, f"HTTP {status}")

    passcode = os.environ.get("APP_PASSCODE")
    if passcode:
        status, _, _ = fetch(f"{base}/login", form={"passcode": passcode})
        check("passcode login", status == 200, f"HTTP {status}")

    status, headers, _ = fetch(f"{base}/")
    csp = headers.get("Content-Security-Policy") or ""
    if "nonce-" not in csp:
        # Only the main page carries a script nonce; anything else means a redirect to /login.
        check("home page", False, "got the passcode page; set APP_PASSCODE and rerun")
        return
    check("home page and security headers", status == 200 and "translate.googleapis.com" in csp, f"HTTP {status}")

    status, _, body = fetch(f"{base}/generate", json_body={"text": DIALOGUE, "voice_map": {}, "rate": "-10%"})
    if status == 200:
        data = json.loads(body)
        mp3 = base64.b64decode(data["audio"])
        check(
            "audio generation (Microsoft speech service)",
            mp3[:2] == b"\xff\xf3" and len(data["timing"]) == 3,
            f"{len(mp3)} bytes, {data['timing'][-1]['end']} s",
        )
    else:
        check("audio generation (Microsoft speech service)", False, f"HTTP {status}: {body[:200]!r}")

    status, _, body = fetch(f"{base}/pinyin", json_body={"text": "你好"})
    check("pinyin", status == 200 and "hǎo" in json.loads(body).get("html", ""), f"HTTP {status}")

    # Visitors' browsers call Google directly, so test from this machine, not the server.
    params = urllib.parse.urlencode({"client": "gtx", "sl": "zh-CN", "tl": "en", "dt": "t", "q": "我要两瓶水"})
    status, _, body = fetch(f"https://translate.googleapis.com/translate_a/single?{params}")
    english = "".join(seg[0] or "" for seg in json.loads(body)[0]) if status == 200 else ""
    check("Google translation", "water" in english.lower(), english or f"HTTP {status}")

    print(f"\n{'All checks passed.' if not failures else f'{len(failures)} check(s) failed. See MAINTENANCE.md.'}")


main()
sys.exit(1 if failures else 0)
