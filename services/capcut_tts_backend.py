import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("TTSBot.CapCutTTSBackend")

# Import the vendored CapCut SDK. The package lives in the bundled
# `capcut-tts-api-main` directory; add it to sys.path so `capcut_tts_api`
# is importable regardless of the current working directory.
try:
    from capcut_tts_api import CapCutClient, CapCutError, VoiceInfo
except ImportError:  # pragma: no cover - defensive path setup
    import sys

    _SDK_ROOT = Path(__file__).resolve().parent.parent / "capcut-tts-api-main"
    if str(_SDK_ROOT) not in sys.path:
        sys.path.insert(0, str(_SDK_ROOT))
    from capcut_tts_api import CapCutClient, CapCutError, VoiceInfo


class CapCutTTSBackend:
    """
    Async wrapper around the synchronous CapCut TTS SDK.

    The CapCut SDK performs blocking `requests` calls and sleeps while polling, so
    every call is offloaded to a worker thread to avoid blocking the Discord
    event loop.
    """

    def __init__(
        self,
        voice: str = "BV421_vivn_streaming",
        resource_id: Optional[str] = None,
        device_json: Optional[str] = None,
        timeout: float = 90.0,
    ):
        self.voice = voice
        self.resource_id = resource_id
        self.device_json = device_json
        self.timeout = timeout
        self._client: Optional[CapCutClient] = None

    def _get_client(self) -> CapCutClient:
        """Lazily build the client. Must be used from a worker thread."""
        if self._client is None:
            device: Any = self.device_json if self.device_json else None
            self._client = CapCutClient(device=device)
        return self._client

    def initialize(self) -> None:
        """Eagerly construct the client so misconfiguration surfaces at startup."""
        try:
            self._get_client()
            logger.info("CapCut TTS backend initialized (voice=%s).", self.voice)
        except Exception as e:
            logger.warning("CapCut TTS backend failed to initialize: %s", e)

    def close(self) -> None:
        self._client = None

    # ------------------------------------------------------------------
    # Blocking internals (run inside a thread)
    # ------------------------------------------------------------------
    def _download_speech(self, query_response: Dict[str, Any]) -> Optional[bytes]:
        """Extract the audio URL from a completed task and download its bytes."""
        import requests

        payload = self._extract_payload(query_response)
        subtitles = payload.get("audio_subtitles") or []
        if not subtitles:
            logger.error("CapCut response contained no audio_subtitles.")
            return None

        speech_url = subtitles[0].get("speech_url")
        if not speech_url:
            logger.error("CapCut audio subtitle missing speech_url: %s", subtitles[0])
            return None

        resp = requests.get(speech_url, timeout=60)
        resp.raise_for_status()
        return resp.content

    @staticmethod
    def _extract_payload(query_response: Dict[str, Any]) -> Dict[str, Any]:
        tasks = (query_response.get("data") or {}).get("tasks") or []
        if not tasks:
            return {}
        raw = tasks[0].get("payload", "{}")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}
        return raw or {}

    def _synthesize_blocking(self, text: str, voice: str, speed: float) -> Optional[bytes]:
        client = self._get_client()
        try:
            result = client.generate_speech(
                texts=text,
                voice=voice or self.voice,
                resource_id=self.resource_id,
                rate=f"{float(speed):.2f}",
                wait=True,
                poll_interval=1.0,
                timeout=self.timeout,
            )
        except CapCutError as e:
            logger.error("CapCut TTS task failed: %s", e)
            return None
        except Exception as e:
            logger.exception("Unexpected CapCut TTS error: %s", e)
            return None

        return self._download_speech(result)

    def list_voices_blocking(self, lang: Optional[str] = None) -> List[VoiceInfo]:
        return self._get_client().list_voices(lang=lang)

    # ------------------------------------------------------------------
    # Async public API
    # ------------------------------------------------------------------
    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        speed: float = 1.0,
        audio_format: str = "mp3",
        **kwargs: Any,
    ) -> Optional[bytes]:
        """Generate speech audio bytes via CapCut, offloading work to a thread."""
        selected_voice = self.voice if voice in (None, "", "default") else voice
        return await asyncio.to_thread(self._synthesize_blocking, text, selected_voice, speed)

    async def list_voices(self, lang: Optional[str] = None) -> List[VoiceInfo]:
        return await asyncio.to_thread(self.list_voices_blocking, lang)
