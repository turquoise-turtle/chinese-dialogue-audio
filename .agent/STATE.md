# State

Last updated 2026-10-27.

## Goal

Keep this fork working for the teacher who uses it, with little effort. The owner does a monthly check from a calendar event, following [MAINTENANCE.md](../MAINTENANCE.md).

## Current state

- Live at https://chinese-audio-practice.onrender.com (Render free tier, Blueprint from `render.yaml`, auto-deploys from `main`). The Render build log confirmed Python 3.14.8 on 2026-10-16.
- `APP_PASSCODE` is not set, so the site is open to anyone.
- Verified 2026-10-27: `scripts/smoke_test.py` passes every check against the live site, 29 offline tests pass, and the live `-m live` test passes.
- Added 2026-10-27: `tests/`, `pytest.ini`, `scripts/`, `MAINTENANCE.md`. Tests run locally only; there is no CI.

## Open items

- gunicorn 26.2.0 is available; the pin is 23.0.0. Not upgraded yet: it's a major jump, so read the release notes first.
- The Hugging Face Spaces deployment (`Dockerfile`) has never been tested.
- pypinyin 0.55.0 uses `codecs.open()`, which Python 3.14 deprecates (warning filtered in `pytest.ini`).

## Decided against for now

- A daily automated check of the live site (scheduled GitHub Actions job), Dependabot pull requests, and running the tests in GitHub Actions. On 2026-10-27 the owner chose a manual monthly check instead. Revisit if monthly checks get skipped or a breakage goes unnoticed. Adding a workflow file needs the `workflow` scope on the GitHub CLI token (`gh auth refresh -h github.com -s workflow`).

## Gotchas

- Render doesn't apply changes to existing environment variables in `render.yaml` until someone clicks **Manual Sync** on the Blueprint (if needed) and approves them.
- Commits use the owner's GitHub noreply address (set in global git config). Never commit with a personal email.

## Next steps

- Monthly checks per `MAINTENANCE.md`.
