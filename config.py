import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Discord Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

# TTS Backend Configuration: "edge" (free, keyless), "capcut", or "http" (custom API)
TTS_BACKEND = os.getenv("TTS_BACKEND", "edge").strip().lower()

# Custom HTTP TTS API Configuration (used when TTS_BACKEND=http)
TTS_API_URL = os.getenv("TTS_API_URL", "https://your-tts-api.com").rstrip("/")
TTS_API_KEY = os.getenv("TTS_API_KEY", "")

# CapCut TTS Configuration (used when TTS_BACKEND=capcut)
CAPCUT_VOICE = os.getenv("CAPCUT_VOICE", "BV421_vivn_streaming")
CAPCUT_RESOURCE_ID = os.getenv("CAPCUT_RESOURCE_ID") or None
CAPCUT_DEVICE_JSON = os.getenv("CAPCUT_DEVICE_JSON") or None
CAPCUT_TIMEOUT = float(os.getenv("CAPCUT_TIMEOUT", "90"))

# Edge-TTS Configuration (used when TTS_BACKEND=edge)
EDGE_VOICE = os.getenv("EDGE_VOICE", "vi-VN-HoaiMyNeural")
EDGE_PROXY = os.getenv("EDGE_PROXY") or None
EDGE_RETRIES = int(os.getenv("EDGE_RETRIES", "3"))
EDGE_MAX_CONCURRENT = int(os.getenv("EDGE_MAX_CONCURRENT", "10"))
EDGE_VOLUME = os.getenv("EDGE_VOLUME", "+0%")
EDGE_PITCH = os.getenv("EDGE_PITCH", "+0Hz")
EDGE_NO_PROXY_FILE = os.getenv("EDGE_NO_PROXY_FILE", "edgetts-noproxy.txt")

# Resolve backend-specific default voice
_BACKEND_VOICE_DEFAULTS = {
    "edge": EDGE_VOICE,
    "capcut": CAPCUT_VOICE,
}
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", _BACKEND_VOICE_DEFAULTS.get(TTS_BACKEND, "default"))
DEFAULT_SPEED = float(os.getenv("DEFAULT_SPEED", "1.0"))

# Validation and limits
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "500"))
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# Cache settings
CACHE_DIR = BASE_DIR / os.getenv("CACHE_DIR", "audio_cache")
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))
MAX_CACHE_SIZE_MB = int(os.getenv("MAX_CACHE_SIZE_MB", "500"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
