# State

Last updated 2026-11-07.

## Goal

Keep this fork working for the teacher who uses it, with little effort. The owner does a monthly check from a calendar event, following [MAINTENANCE.md](../MAINTENANCE.md).

## Current state

- Live at https://chinese-audio-practice.onrender.com (Render free tier, Blueprint from `render.yaml`). The Render build log confirmed Python 3.14.8 on 2026-10-16.
- `APP_PASSCODE` is not set, so the site is open to anyone.
- Monthly check 2026-11-03: all dependencies up to date (edge-tts 7.3.1, flask 3.1.3, gunicorn 26.2.0, pypinyin 0.55.0); Python 3.14 supported until 2030-10-31. 29 offline tests and the live test pass. Smoke test passed every check except Google translation, which got a one-off HTTP 429; a retry 20 seconds later returned 200. In the browser, audio generated (35 s) and played, pinyin and highlighting rendered, and translation worked. Render dashboard (MAINTENANCE.md step 4) not checked by the agent.
- Added 2026-10-27: `tests/`, `pytest.ini`, `scripts/`, `MAINTENANCE.md`. Tests run locally only; there is no CI.

## Open items

- Deploys: the Render GitHub app isn't installed (the owner doesn't want it), so Render's auto-deploy never fired. Every deploy before 2026-11-06 came from a Blueprint sync or a manual deploy, and smoke tests after pushes were checking the old build. On 2026-11-06 the owner added a GitHub repo webhook that calls the service's Render deploy hook; its test ping started a deploy of `d465466` ("Triggered via Deploy Hook"). Verified 2026-11-07: pushing `cb6dad8` started a deploy through the hook and it went live (owner checked in Render). A push to any branch or tag redeploys `main`; harmless while `main` is the only branch.
- gunicorn upgrade 23.0.0 → 26.2.0 (newest on PyPI; 26.2.1/26.2.2 are GitHub-only HTTP/2 and ASGI fixes that don't affect the gthread worker used here): pushed to `main` on 2026-10-30, with `control_socket_disable = True` added to `gunicorn.conf.py`. Release notes 24–26 reviewed: the only breaking change is the removed eventlet worker, which isn't used. Verified locally 2026-10-28: 29 offline tests, the live test and the smoke test against a local gunicorn 26.2.0 server all pass, and other requests stay fast during a long generation. Deploy of `d465466` started 2026-11-06 through the deploy hook; afterwards the live smoke test passed everything except Google translation (another intermittent 429 from this machine; retries returned 200). Superseded by `cb6dad8`, which is live, so gunicorn 26.2.0 is now running in production.
- Fixed after the 2026-11-07 review: `/generate` rejects dialogues over 4,000 characters (owner's choice, raised from a proposed 2,500) and request bodies over 64 KB. A real 3,933-character, 253-line dialogue took 67 s locally and made 16 min of audio (5.9 MB MP3), so the limit leaves less than 2x headroom under gunicorn's 120 s timeout; lower it if long generations time out on Render. `scripts/smoke_test.py` now reports FAIL instead of crashing on connection errors, empty audio or timing, and non-JSON replies. `scripts/check_updates.py` reports PyPI errors per package instead of crashing. Verified: 32 offline tests pass; smoke test passes against local gunicorn and fails cleanly against an unreachable host and a junk server; check_updates tested with the network blocked.
- The Hugging Face Spaces deployment (`Dockerfile`) has never been tested.
- Google translation in the smoke test got intermittent HTTP 429s on 2026-11-03 and 2026-11-06 (passes on retry). If it keeps happening, consider making the smoke test retry once.
- pypinyin 0.55.0 uses `codecs.open()`, which Python 3.14 deprecates (warning filtered in `pytest.ini`).

## Decided against for now

- A daily automated check of the live site (scheduled GitHub Actions job), Dependabot pull requests, and running the tests in GitHub Actions. On 2026-10-27 the owner chose a manual monthly check instead. Revisit if monthly checks get skipped or a breakage goes unnoticed. Adding a workflow file needs the `workflow` scope on the GitHub CLI token (`gh auth refresh -h github.com -s workflow`).

## Gotchas

- Render doesn't apply changes to existing environment variables in `render.yaml` until someone clicks **Manual Sync** on the Blueprint (if needed) and approves them.
- Commits use the owner's GitHub noreply address (set in global git config). Never commit with a personal email.

## Next steps

- Monthly checks per `MAINTENANCE.md`.
