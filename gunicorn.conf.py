# Shared by Render and the Docker image; gunicorn loads this file from the
# working directory automatically.
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
# Threads let one long generation run without blocking page loads and pinyin.
threads = 4
# A long dialogue can take well over gunicorn's default 30s to synthesise.
timeout = 120
# gunicorn 25.1+ opens an admin socket in the home directory by default. Nothing
# here uses it, so don't create one on the host.
control_socket_disable = True
