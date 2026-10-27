# Maintenance

The live site is https://chinese-audio-practice.onrender.com, deployed on Render's free tier from `main` on GitHub.

The app depends on two free services it has no agreement with: Microsoft's Edge read-aloud voices (through `edge-tts`) and Google Translate's public endpoint. Either can change without notice, and nothing alerts you when they do. These checks exist to catch that before the teacher does.

All commands run from the repository root. They need [uv](https://docs.astral.sh/uv/) and nothing else.

## Monthly (about 15 minutes)

1. Check the live site end to end. Every line should say `PASS`. The first request can take 30 seconds while the free instance wakes.

   ```bash
   uv run scripts/smoke_test.py
   ```

   If the site has a passcode, set `APP_PASSCODE` in your shell before running it.

2. Check for dependency updates.

   ```bash
   uv run scripts/check_updates.py
   ```

   For each update: change the version in `requirements.txt`, run the offline and live tests (see [Running the tests](#running-the-tests)), push to `main`, wait about four minutes for Render to deploy, then run the smoke test again. Update one package at a time so a failure points at its cause. Read the release notes before a major-version jump (for example gunicorn 23 → 26).

3. Open the site in a browser and use it: generate audio, play it, toggle **Show Pinyin** and **Highlight Words**, and select some Chinese text to see a translation.

4. In the Render dashboard, check that the latest deploy succeeded and that the Blueprint has no sync waiting for approval.


## Quarterly (add about 15 minutes)

- See what the original author has changed since this fork:

  ```bash
  git fetch upstream
  git log --oneline main..upstream/main
  ```

  Merge anything worth having, such as new conversations in `conversation_library.py`. This fork has diverged a lot in `app.py`, `tts_engine.py` and `templates/index.html`, so expect conflicts there and run the tests after merging.

- Ask the teacher whether anything has been slow, broken or missing.

## Every six months (add about 15 minutes)

- Check dependencies for known vulnerabilities:

  ```bash
  uvx pip-audit -r requirements.txt
  ```

- Skim the service's logs in the Render dashboard for repeated errors.

## Annually, each October (add about an hour)

New Python versions come out in October.

- `scripts/check_updates.py` shows how long the current Python version has left. Upgrade when convenient, and before it has less than a year left:
  1. Change the version in `render.yaml` (`PYTHON_VERSION`) and `Dockerfile` (`FROM python:…-slim`).
  2. Run the tests locally with the new version, changing `--python` in the commands under [Running the tests](#running-the-tests) and in the README.
  3. Push to `main`.
  4. In Render, open the Blueprint, click **Manual Sync** if no sync is waiting, and approve the environment variable change. Render doesn't apply a change to an existing environment variable until someone approves it, so until then it keeps building with the old Python.
  5. Check the new build log says `Using Python version …` with the version you chose.
- Re-read Render's free-tier terms in case they have changed.
- Deploy once to Hugging Face Spaces (see the README) to prove the backup host still works. This has never been tested.
- `pypinyin` 0.55.0 calls `codecs.open()`, which Python 3.14 deprecates. Check whether a newer pypinyin has fixed it, or whether the new Python removes `codecs.open()`. Removal would break pinyin.

## When something breaks

### Audio generation fails

The page shows "The speech service failed, please try again", and the Render logs show a `403` from `speech.platform.bing.com` or a `WSServerHandshakeError`.

This almost always means Microsoft changed something and `edge-tts` needs upgrading:

1. Run `uv run scripts/check_updates.py` to see the latest `edge-tts`.
2. Update it in `requirements.txt` and run the live test: `uv run --python 3.14 --no-project --with-requirements requirements.txt --with pytest pytest -m live`.
3. If it passes, push to `main` and run the smoke test once Render has deployed.

If even the newest `edge-tts` fails, look for an open issue at https://github.com/rany2/edge-tts/issues. Fixes usually arrive within days.

If the live test fails on its MP3 format assertions, Microsoft changed the audio format. The engine computes durations and joins clips by byte arithmetic, which only works for that exact format. The previous ffmpeg-based engine is in git history (commit `acd9b5e`) if it needs bringing back.

### The translation tooltip says "(translation failed)"

Visitors' browsers call Google directly. The smoke test checks the same call from your machine. If Google has changed or closed its public endpoint, select-to-translate needs a different free translation source. Nothing else in the app depends on it.

### The site is down or very slow

Check Render's status page and the service's events in the dashboard. A sleeping free instance taking about 30 seconds to wake is normal. If Render's free tier stops being usable, deploy to Hugging Face Spaces instead (see the README).

### A change to `render.yaml` has no effect

Open the Blueprint in Render, click **Manual Sync** if no sync is waiting, and approve the changes. Changes to existing environment variables always need this approval.

## Running the tests

```bash
# Offline tests
uv run --python 3.14 --no-project --with-requirements requirements.txt --with pytest pytest

# Live test: calls Microsoft's speech service. Run after upgrading edge-tts.
uv run --python 3.14 --no-project --with-requirements requirements.txt --with pytest pytest -m live
```

## Accounts and settings

- **Code:** https://github.com/turquoise-turtle/chinese-dialogue-audio (`origin`), forked from https://github.com/maxchalabi/chinese-dialogue-audio (`upstream`).
- **Hosting:** the Render service `chinese-audio-practice` is managed by a Blueprint built from `render.yaml`. Pushes to `main` deploy automatically.
- **Environment variables:** `PYTHON_VERSION` comes from `render.yaml`. `APP_PASSCODE` is optional and set only in the Render dashboard. When it's unset, the site is open to anyone. Never write its value in this repository.
