# Discord TTS Bot

A modular Discord TTS (Text-to-Speech) bot built with `discord.py`, asynchronous audio handling, sliding-window rate limiting, and local disk audio caching. It ships with the bundled **CapCut TTS API** SDK so it works out of the box without a separate TTS server.

## Features
- **Multiple TTS Backends**: `edge` (default, free & keyless Microsoft voices via `edge-tts`), `capcut` (bundled CapCut SDK), or `http` (custom endpoint).
- **Vietnamese & Multi-Language**: Curated Vietnamese voices (`vi-VN-HoaiMyNeural`, `vi-VN-NamMinhNeural`) plus 300+ Edge voices in many languages.
- **Resilient Edge-TTS**: Automatic retries, concurrent-task limiting, and an `edgetts-noproxy.txt` proxy bypass.
- **Local Audio Caching**: SHA256 hashed audio caching with TTL and automatic size eviction to minimize API calls and latency.
- **Voice Management**: Queue-based sequential playback per guild using `discord.FFmpegPCMAudio`.
- **Text Normalization**: Strips URLs, mentions, emojis, markdown, and code blocks before synthesis.
- **Anti-Abuse Rate Limiter**: Configurable sliding window limits per user.
- **Slash & Prefix Commands**:
  - `/join`, `/leave`, `/stop`
  - `/speak text:<str> [voice] [speed]`
  - `/voices [language]` — list available voices
  - `/tts_config voice <voice>`
  - `/tts_config speed <0.5-2.0>`
  - `/tts_config bind [channel]`
  - `/tts_config unbind`
  - `/tts_status`
- **Auto-Read Text Messages**: Automatically reads incoming messages when users are in voice channels.

## Setup Instructions

### 1. Requirements
- Python 3.10+
- FFmpeg installed and in PATH
- Discord Bot Token with `Message Content`, `Voice States`, and `Guilds` intents enabled

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` and configure your credentials:
```bash
cp .env.example .env
```
Fill in:
- `DISCORD_TOKEN`: Your Discord bot token from the Discord Developer Portal
- `TTS_BACKEND`: `edge` (default, free/keyless), `capcut`, or `http`
- `EDGE_VOICE`: Edge voice name, e.g. `vi-VN-HoaiMyNeural` (list via `/voices`)
- `TTS_API_URL` / `TTS_API_KEY`: only needed when `TTS_BACKEND=http`

#### Edge-TTS notes
- No API key or server required — uses Microsoft Edge cloud voices (needs internet).
- Tuning: `EDGE_RETRIES`, `EDGE_MAX_CONCURRENT`, `EDGE_VOLUME`, `EDGE_PITCH`. Speech speed is controlled at runtime via `/tts_config speed` or the `speed` option of `/speak`.
- If a network proxy breaks Edge-TTS, set `EDGE_PROXY` or create an empty `edgetts-noproxy.txt` file in the project root to bypass it.

### 4. Running the Bot
```bash
python bot.py
```

### 5. Running with Docker
```bash
docker compose up -d --build
```

### 6. Running Tests
```bash
python -m unittest discover -s tests
```
