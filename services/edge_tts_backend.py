import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("TTSBot.EdgeTTSBackend")

# Per-chunk save timeout to prevent WebSocket hangs (see EDGE_TTS_INSTRUCTION).
SAVE_TIMEOUT = 30
# Sleep between retry attempts.
RETRY_DELAY = 5

# Curated Vietnamese voices (from the voice catalog in the instruction doc).
VIETNAMESE_VOICES: Dict[str, str] = {
    "NamMinh (Male/VN)": "vi-VN-NamMinhNeural",
    "HoaiMy (Female/VN)": "vi-VN-HoaiMyNeural",
}


def format_percent(value: float) -> str:
    """Format a numeric speed/volume offset as an edge-tts percentage string.

    edge-tts expects strings like "+0%", "+20%", "-10%". A value of 1.0 is
    neutral, so 1.2 -> "+20%" and 0.8 -> "-20%".
    """
    offset = int(round((float(value) - 1.0) * 100))
    return f"{offset:+d}%"


def format_hz(value: float) -> str:
    """Format a pitch value (in Hz) as an edge-tts string like '+0Hz'."""
    return f"{int(round(float(value))):+d}Hz"


class EdgeTTSBackend:
    """
    Keyless, free TTS backend using Microsoft Edge's cloud voices via `edge-tts`.

    Mirrors the retry / proxy-bypass behavior documented for the `pyvideotrans`
    project: retries transient failures, honors an `edgetts-noproxy.txt` bypass
    file, and supports rate/volume/pitch tuning.
    """

    def __init__(
        self,
        voice: str = "vi-VN-HoaiMyNeural",
        proxy: Optional[str] = None,
        retries: int = 3,
        max_concurrent_tasks: int = 10,
        volume: str = "+0%",
        pitch: str = "+0Hz",
        no_proxy_file: str = "edgetts-noproxy.txt",
    ):
        self.voice = voice
        self.proxy = proxy
        self.retries = max(0, int(retries))
        self.max_concurrent_tasks = max(1, int(max_concurrent_tasks))
        self.volume = volume or "+0%"
        self.pitch = pitch or "+0Hz"
        self.no_proxy_file = no_proxy_file
        self._semaphore: Optional[asyncio.Semaphore] = None

    @property
    def use_proxy(self) -> Optional[str]:
        """Proxy to use, unless the bypass file exists (creates/uses no proxy)."""
        if not self.proxy:
            return None
        if Path(self.no_proxy_file).exists():
            logger.info("'%s' found: bypassing proxy for Edge-TTS.", self.no_proxy_file)
            return None
        return self.proxy

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent_tasks)
        return self._semaphore

    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        speed: float = 1.0,
        audio_format: str = "mp3",
        rate: Optional[str] = None,
        volume: Optional[str] = None,
        pitch: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[bytes]:
        """Generate speech audio bytes using edge-tts, with retries."""
        try:
            from edge_tts import Communicate
        except ImportError:
            logger.error("The 'edge-tts' package is required. Run 'pip install edge-tts'.")
            return None

        selected_voice = self.voice if voice in (None, "", "default") else voice
        rate_str = rate or format_percent(speed)
        volume_str = volume or self.volume
        pitch_str = pitch or self.pitch
        proxy = self.use_proxy

        async with self._get_semaphore():
            for attempt in range(self.retries + 1):
                try:
                    communicate = Communicate(
                        text,
                        voice=selected_voice,
                        rate=rate_str,
                        volume=volume_str,
                        pitch=pitch_str,
                        proxy=proxy,
                        connect_timeout=5,
                    )
                    audio = bytearray()
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio.extend(chunk["data"])

                    if not audio:
                        raise RuntimeError("edge-tts returned no audio data.")

                    return bytes(audio)

                except Exception as e:
                    if attempt < self.retries:
                        logger.warning(
                            "Edge-TTS attempt %d/%d failed (%s). Retrying in %ds...",
                            attempt + 1,
                            self.retries + 1,
                            e,
                            RETRY_DELAY,
                        )
                        await asyncio.sleep(RETRY_DELAY)
                    else:
                        logger.error("Edge-TTS failed after %d attempts: %s", self.retries + 1, e)
                        return None

        return None

    async def list_voices(self, lang: Optional[str] = None) -> List[Dict[str, str]]:
        """Return available edge-tts voices, optionally filtered by locale prefix."""
        try:
            import edge_tts
        except ImportError:
            logger.error("The 'edge-tts' package is required. Run 'pip install edge-tts'.")
            return []

        try:
            voices = await edge_tts.list_voices()
        except Exception as e:
            logger.error("Failed to fetch edge-tts voice list: %s", e)
            return []

        results: List[Dict[str, str]] = []
        lang_prefix = (lang or "").lower()
        for v in voices:
            short_name = v.get("ShortName", "")
            locale = v.get("Locale", "")
            if lang_prefix and not (
                locale.lower().startswith(lang_prefix) or short_name.lower().startswith(lang_prefix)
            ):
                continue
            results.append({"short_name": short_name, "locale": locale, "gender": v.get("Gender", "")})
        return results

    async def list_vietnamese_voices(self) -> Dict[str, str]:
        """Return the curated Vietnamese voice catalog."""
        return dict(VIETNAMESE_VOICES)
