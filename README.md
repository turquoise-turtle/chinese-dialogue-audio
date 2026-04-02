# Chinese Audio Practice Generator

**[Try the live demo](https://chinese-dialogue-audio.onrender.com/)**

A lightweight web app that turns Chinese dialogue text into multi-speaker MP3 audio. Built for my own Mandarin listening practice — I'm learning from scratch and wanted a fast way to generate audio from the conversations and vocabulary I'm studying.

## Why I built this

I'm taking beginner Mandarin classes and needed a way to practice listening outside of lessons. My workflow:

1. I give an LLM (DeepSeek, ChatGPT, etc.) my lesson vocabulary and ask it to generate realistic practice conversations using only the words I know
2. I paste the dialogue into this tool
3. It generates an MP3 with different male/female voices for each speaker

This way I get unlimited listening practice that's always at my level.

## Features

- **Multi-speaker TTS** — 6 natural Chinese voices (3 male, 3 female) via Microsoft Edge TTS. Each speaker in the dialogue gets their own voice.
- **Inline pinyin** — Toggle pinyin with tone marks above every character. Tone sandhi rules are applied automatically (3rd+3rd, 一, 不) and highlighted in amber so you learn the actual spoken tones.
- **Select-to-translate** — Highlight any word or phrase in the text to see an instant English translation tooltip.
- **Speed control** — Slow down or speed up speech from -50% to +50%.
- **No API keys needed** — Everything runs locally for free.

## Quick start

Requires **Python 3.9+**. No need to install ffmpeg — it's bundled automatically.

```bash
# Clone the repo
git clone https://github.com/maxchalabi/chinese-dialogue-audio.git
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
5. Use **Show Pinyin** to see pronunciation with tone sandhi corrections.
6. **Select any text** to get an instant English translation tooltip.

Both Chinese colon (：) and ASCII colon (:) work.

### CLI batch generation

Generate MP3s for the 16 pre-built conversations in `conversations.py`:

```bash
python generate_all.py                # all conversations
python generate_all.py --rate=-15%    # slower for beginners
python generate_all.py --only=01      # just one conversation
```

Output goes to the `output/` folder.

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

## Project structure

```
├── app.py                 # Flask web server
├── tts_engine.py          # Core TTS: parsing, voice assignment, audio generation
├── conversations.py       # 16 pre-built practice dialogues (for CLI)
├── generate_all.py        # CLI batch generator
├── templates/
│   └── index.html         # Web UI (single page)
├── run.sh                 # Quick-start script
├── render.yaml            # Render deployment config
├── requirements.txt       # Pinned Python dependencies
└── output/                # Generated MP3s (gitignored)
```

## Tech stack

- **[edge-tts](https://github.com/rany2/edge-tts)** — Free Microsoft Edge text-to-speech with high-quality Chinese voices
- **[Flask](https://flask.palletsprojects.com/)** — Lightweight web framework
- **[pypinyin](https://github.com/mozillazg/python-pinyin)** — Chinese character to pinyin conversion
- **[imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg)** — Bundled ffmpeg for audio concatenation
- **Google Translate** — Used for the select-to-translate feature via the same public endpoint that translate.google.com uses (no API key). This is an unofficial endpoint and may stop working if Google changes it.

## License

MIT
