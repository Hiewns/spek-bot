import logging
from pathlib import Path
from typing import Optional
from utils.cache import AudioCache
from services.tts_service import TTSService

logger = logging.getLogger("TTSBot.AudioHandler")


class AudioHandler:
    """Coordinates fetching synthesized audio from cache or TTSService, saving to disk."""

    def __init__(self, tts_service: TTSService, audio_cache: AudioCache):
        self.tts_service = tts_service
        self.cache = audio_cache
        self.cache_hits = 0
        self.total_requests = 0

    async def get_audio_file(
        self,
        text: str,
        voice: str = "default",
        speed: float = 1.0,
        audio_format: str = "mp3",
    ) -> Optional[Path]:
        """Check cache first; synthesize and save if cache miss."""
        self.total_requests += 1

        cached_file = self.cache.get(text, voice, speed, audio_format)
        if cached_file and cached_file.exists():
            self.cache_hits += 1
            logger.debug("Cache hit for text: %s", text[:30])
            return cached_file

        logger.debug("Cache miss for text: %s. Synthesizing...", text[:30])
        audio_bytes = await self.tts_service.synthesize(
            text=text,
            voice=voice,
            speed=speed,
            audio_format=audio_format,
        )

        if not audio_bytes:
            logger.error("Failed to generate audio bytes for text: %s", text[:30])
            return None

        # Save to cache
        saved_file = self.cache.save(text, voice, speed, audio_bytes, audio_format)
        return saved_file

    def get_stats(self) -> dict:
        hit_rate = (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": f"{hit_rate:.1f}%",
        }
