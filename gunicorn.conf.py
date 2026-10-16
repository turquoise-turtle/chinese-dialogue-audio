# Shared by Render and the Docker image; gunicorn loads this file from the
# working directory automatically.
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
# Threads let one long generation run without blocking page loads and pinyin.
threads = 4
# A long dialogue can take well over gunicorn's default 30s to synthesize.
timeout = 120
