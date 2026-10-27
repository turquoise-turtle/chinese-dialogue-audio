---
title: Chinese Audio Practice
emoji: 🎧
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Chinese Audio Practice Generator

**[Try the live demo](https://chinese-audio-practice.onrender.com/)**

Forked from [maxchalabi/chinese-dialogue-audio](https://github.com/maxchalabi/chinese-dialogue-audio).

A lightweight web app that turns Chinese dialogue text into multi-speaker MP3 audio. Built for my own Mandarin listening practice — I'm learning from scratch and wanted a fast way to generate audio from the conversations and vocabulary I'm studying.

## Why I built this

I'm taking beginner Mandarin classes and needed a way to practice listening outside of lessons. My workflow:

1. I give an LLM (DeepSeek, ChatGPT, etc.) my lesson vocabulary and ask it to generate realistic practice conversations using only the words I know
2. I paste the dialogue into this tool
3. It generates an MP3 with different male/female voices for each speaker

This way I get unlimited listening practice that's always at my level.

## Features

- **Multi-speaker TTS** — 6 natural Chinese voices (3 male, 3 female) via Microsoft Edge TTS. Each speaker in the dialogue gets their own voice.
- **Highlight Words** — Toggle character-by-character highlighting that follows along as the audio plays, so you can read along in real time. Works with or without pinyin.
- **Inline pinyin** — Toggle pinyin with tone marks above every character. Tone sandhi rules are applied automatically (3rd+3rd, 一, 不) and highlighted in amber so you learn the actual spoken tones.
- **Select-to-translate** — Highlight any word or phrase in the text to see an instant English translation tooltip.
- **Conversation library** — 45 built-in practice texts (dialogues and short single-speaker passages) covering shopping, greetings, currency exchange, and more. Hit **Shuffle** to load a random one.
- **Speed control** — Slow down or speed up speech from -50% to +50%.
- **No API keys needed** — Free to run locally or on a free hosting tier.

## Quick start

Requires **Python 3.9+**. No ffmpeg or other system packages needed.

```bash
# Clone the repo
git clone https://github.com/turquoise-turtle/chinese-dialogue-audio.git
cd chinese-dialogue-audio

# Create a virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the app
./run.sh
# Or manually: python app.py
```

Open **http://localhost:5000** in your browser.

## How to use

### Web UI

1. Paste a dialogue in `Speaker：Text` format (one line per turn):
   ```
   售货员：您好！您要什么？
   顾客：我要两件T恤，一顶帽子。
   售货员：一共三百四十九块。
   ```
2. Speakers are auto-detected. Assign voices in the sidebar.
3. Adjust speed if needed (negative = slower, great for beginners).
4. Click **Generate Audio** — listen inline or download the MP3.
5. Toggle **Highlight Words** to see character-by-character highlighting synced with audio playback.
6. Use **Show Pinyin** to see pronunciation with tone sandhi corrections (combines with highlighting).
7. **Select any text** to get an instant English translation tooltip.

Both Chinese colon (：) and ASCII colon (:) work.

## Generating practice conversations

I use LLMs to create conversations tailored to my current level. Here's a sample prompt I give to DeepSeek:

> I'm a beginner Mandarin learner. Here are the words and structures I know: [paste vocabulary list]. Generate 3 short shopping dialogues using ONLY these words. Format each line as Speaker：Text.

The tool then turns those dialogues into audio I can listen to on repeat.

## Available voices

| Voice | Gender | Style |
|-------|--------|-------|
| zh-CN-XiaoxiaoNeural | Female | Natural |
| zh-CN-XiaoyiNeural | Female | Young |
| zh-CN-YunxiNeural | Male | Natural |
| zh-CN-YunyangNeural | Male | Broadcast |
| zh-CN-YunjianNeural | Male | Sporty |
| zh-CN-YunxiaNeural | Male | Boyish |

## Deployment

The app runs under gunicorn using the settings in `gunicorn.conf.py` (4 threads, 120s timeout). `GET /healthz` returns `{"status": "ok"}` for host health checks.

### Render (free tier)

`render.yaml` is a Blueprint: in the Render dashboard choose **New → Blueprint** and point it at your GitHub repo. Pushes to the main branch redeploy automatically. The free tier sleeps after 15 minutes idle, so the first request after that takes about 30 seconds.

### Hugging Face Spaces

Create a Space with the **Docker** SDK and push this repo to it. The front matter at the top of this README tells Spaces to build the `Dockerfile` and serve port 7860. Use the direct `https://<user>-<space>.hf.space` URL if your browser blocks the passcode cookie inside the huggingface.co page.

### Passcode (optional)

Set the `APP_PASSCODE` environment variable (on Render: the service's **Environment** tab; on Spaces: **Settings → Variables and secrets**, as a secret) to require a passcode before the app can be used. Visitors enter it once and stay signed in for 30 days. Leave it unset to keep the app open.

### If audio generation starts failing

edge-tts talks to an unofficial Microsoft endpoint that occasionally changes. A `403` from `speech.platform.bing.com` in the logs usually means `edge-tts` needs upgrading: bump its version in `requirements.txt` and redeploy.

## Maintenance and tests

[MAINTENANCE.md](MAINTENANCE.md) has the monthly, quarterly and yearly checklists, and what to do when something breaks. In short:

```bash
uv run scripts/smoke_test.py      # check the live site end to end
uv run scripts/check_updates.py   # newer dependencies and Python support dates
uv run --python 3.14 --no-project --with-requirements requirements.txt --with pytest pytest   # offline tests
```

## Project structure

```
├── app.py                     # Flask web server
├── tts_engine.py              # Core TTS: parsing, voice assignment, audio generation
├── conversation_library.py    # 45 built-in practice texts (used by web UI shuffle)
├── templates/
│   ├── index.html             # Web UI (single page)
│   └── login.html             # Passcode page (only used when APP_PASSCODE is set)
├── gunicorn.conf.py           # Production server settings (Render and Docker)
├── render.yaml                # Render deployment config
├── Dockerfile                 # Hugging Face Spaces deployment
├── run.sh                     # Quick-start script
├── requirements.txt           # Pinned Python dependencies
├── tests/                     # pytest suite (offline by default; -m live calls Microsoft)
├── pytest.ini                 # pytest settings
├── scripts/
│   ├── smoke_test.py          # End-to-end check of the deployed site
│   └── check_updates.py       # Dependency and Python support check
└── MAINTENANCE.md             # Maintenance checklists and fixes
```

## Tech stack

- **[edge-tts](https://github.com/rany2/edge-tts)** — Free Microsoft Edge text-to-speech with high-quality Chinese voices
- **[Flask](https://flask.palletsprojects.com/)** — Lightweight web framework
- **[pypinyin](https://github.com/mozillazg/python-pinyin)** — Chinese character to pinyin conversion
- **Google Translate** — Used for the select-to-translate feature via the same public endpoint that translate.google.com uses (no API key). The browser calls it directly, because Google blocks it from cloud hosts like Render. This is an unofficial endpoint and may stop working if Google changes it.

## License

MIT
