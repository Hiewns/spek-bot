import aiohttp
import asyncio
import logging
from typing import Any, Dict, List, Optional

from services.capcut_tts_backend import CapCutTTSBackend
from services.edge_tts_backend import EdgeTTSBackend, VIETNAMESE_VOICES

logger = logging.getLogger("TTSBot.TTSService")


class TTSService:
    """
    Facade over the configured TTS backend.

    Supported backends:
      - "edge":   keyless Microsoft Edge cloud voices via `edge-tts` (default).
      - "capcut": bundled CapCut TTS API SDK.
      - "http":   posts to a custom `POST {api_url}/synthesize` endpoint.
    """

    def __init__(
        self,
        api_url: str = "",
        api_key: str = "",
        backend: str = "edge",
        capcut_voice: str = "BV421_vivn_streaming",
        capcut_resource_id: Optional[str] = None,
        capcut_device_json: Optional[str] = None,
        capcut_timeout: float = 90.0,
        edge_voice: str = "vi-VN-HoaiMyNeural",
        edge_proxy: Optional[str] = None,
        edge_retries: int = 3,
        edge_max_concurrent: int = 10,
        edge_volume: str = "+0%",
        edge_pitch: str = "+0Hz",
        edge_no_proxy_file: str = "edgetts-noproxy.txt",
    ):
        self.backend = (backend or "http").strip().lower()
        self.api_url = (api_url or "").rstrip("/")
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.capcut: Optional[CapCutTTSBackend] = None
        self.edge: Optional[EdgeTTSBackend] = None

        if self.backend == "capcut":
            self.capcut = CapCutTTSBackend(
                voice=capcut_voice,
                resource_id=capcut_resource_id,
                device_json=capcut_device_json,
                timeout=capcut_timeout,
            )
        elif self.backend == "edge":
            self.edge = EdgeTTSBackend(
                voice=edge_voice,
                proxy=edge_proxy,
                retries=edge_retries,
                max_concurrent_tasks=edge_max_concurrent,
                volume=edge_volume,
                pitch=edge_pitch,
                no_proxy_file=edge_no_proxy_file,
            )

    @property
    def is_remote_backend(self) -> bool:
        return self.backend not in ("capcut", "edge")

    async def initialize(self) -> None:
        """Create HTTP session (remote backend) and warm up the selected backend."""
        if self.backend == "capcut":
            if self.capcut:
                await asyncio.to_thread(self.capcut.initialize)
            return

        if self.backend == "edge":
            if self.edge:
                try:
                    import edge_tts  # noqa: F401
                    logger.info("Edge-TTS backend initialized (voice=%s).", self.edge.voice)
                except ImportError:
                    logger.warning("Edge-TTS backend selected but 'edge-tts' is not installed.")
            return

        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        """Close aiohttp session and release backend resources."""
        if self.capcut:
            self.capcut.close()
        if self.session and not self.session.closed:
            await self.session.close()

    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        speed: float = 1.0,
        audio_format: str = "mp3",
        max_retries: int = 3,
        timeout_seconds: int = 20,
    ) -> Optional[bytes]:
        """Convert text to speech audio bytes using the selected backend."""
        if self.backend == "capcut":
            if self.capcut is None:
                logger.error("CapCut backend requested but not configured.")
                return None
            return await self.capcut.synthesize(
                text=text,
                voice=voice,
                speed=speed,
                audio_format=audio_format,
            )

        if self.backend == "edge":
            if self.edge is None:
                logger.error("Edge-TTS backend requested but not configured.")
                return None
            return await self.edge.synthesize(
                text=text,
                voice=voice,
                speed=speed,
                audio_format=audio_format,
            )

        return await self._synthesize_http(
            text=text,
            voice=voice,
            speed=speed,
            audio_format=audio_format,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )

    async def list_voices(self, lang: Optional[str] = None) -> List[str]:
        """Return a list of selectable voice identifiers for the active backend."""
        if self.backend == "capcut" and self.capcut:
            voices = await self.capcut.list_voices(lang=lang)
            return [f"{v.display_name} ({v.voice_type})" for v in voices]

        if self.backend == "edge" and self.edge:
            # Prefer the curated Vietnamese catalog when a vi filter is requested.
            if lang and lang.lower().startswith("vi"):
                catalog = await self.edge.list_vietnamese_voices()
                return [f"{name} -> {code}" for name, code in catalog.items()]

            voices = await self.edge.list_voices(lang=lang)
            return [f"{v['short_name']} ({v['locale']}/{v['gender']})" for v in voices]

        return []

    async def _synthesize_http(
        self,
        text: str,
        voice: str,
        speed: float,
        audio_format: str,
        max_retries: int,
        timeout_seconds: int,
    ) -> Optional[bytes]:
        """Custom HTTP TTS endpoint integration with retry and backoff."""
        if not self.api_url:
            logger.error("TTS_API_URL is not configured for the HTTP backend.")
            return None

        if self.session is None or self.session.closed:
            await self.initialize()

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: Dict[str, Any] = {
            "text": text,
            "voice": voice,
            "speed": speed,
            "format": audio_format,
        }

        endpoint = f"{self.api_url}/synthesize"

        for attempt in range(max_retries):
            try:
                assert self.session is not None
                async with self.session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout_seconds),
                ) as response:
                    if response.status == 200:
                        return await response.read()

                    if response.status == 429:
                        backoff = 2**attempt
                        logger.warning(
                            "TTS API rate limit hit (attempt %d/%d). Backing off %d seconds.",
                            attempt + 1,
                            max_retries,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue

                    error_body = await response.text()
                    logger.error(
                        "TTS API error status %d on attempt %d: %s",
                        response.status,
                        attempt + 1,
                        error_body,
                    )
                    if response.status >= 500:
                        await asyncio.sleep(2**attempt)
                        continue
                    return None

            except asyncio.TimeoutError:
                logger.warning(
                    "TTS API timeout on attempt %d/%d for endpoint %s",
                    attempt + 1,
                    max_retries,
                    endpoint,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
            except aiohttp.ClientError as e:
                logger.error(
                    "TTS client network error on attempt %d/%d: %s",
                    attempt + 1,
                    max_retries,
                    e,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
            except Exception as e:
                logger.exception("Unexpected error in TTSService.synthesize: %s", e)
                return None

        logger.error("TTS synthesis failed after %d retries.", max_retries)
        return None
