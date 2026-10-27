# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Show pinned dependencies with newer releases, and how long the Python version is supported.

    uv run scripts/check_updates.py
"""

import datetime
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_json(url):
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp)


def main():
    print("Pinned dependencies (requirements.txt):")
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+)==(\S+)", line.strip())
        if not m:
            continue
        name, pinned = m.groups()
        latest = get_json(f"https://pypi.org/pypi/{name}/json")["info"]["version"]
        note = "up to date" if latest == pinned else f"UPDATE AVAILABLE: {latest}"
        print(f"  {name:<10} {pinned:<10} {note}")

    render = re.search(r'PYTHON_VERSION\s*\n\s*value:\s*"([\d.]+)"', (ROOT / "render.yaml").read_text())
    docker = re.search(r"^FROM python:([\d.]+)", (ROOT / "Dockerfile").read_text(), re.M)
    render_v, docker_v = render.group(1) if render else "?", docker.group(1) if docker else "?"
    print(f"\nPython: render.yaml {render_v}, Dockerfile {docker_v}")
    if render_v != docker_v:
        print("  MISMATCH: keep both on the same version.")

    try:
        cycles = get_json("https://endoflife.date/api/python.json")
    except OSError as e:
        print(f"  Could not reach endoflife.date: {e}")
        return
    newest = cycles[0]["cycle"]
    current = next((c for c in cycles if c["cycle"] == render_v), None)
    if current:
        eol = datetime.date.fromisoformat(current["eol"])
        days = (eol - datetime.date.today()).days
        print(f"  {render_v} gets security fixes until {eol} ({days} days); newest release is {newest}.")
        if days < 365:
            print("  Under a year left: plan the upgrade (see MAINTENANCE.md).")


main()
