import unittest
from unittest.mock import patch, MagicMock
import json

from services.tts_service import TTSService
from services.capcut_tts_backend import CapCutTTSBackend


class TestCapCutBackend(unittest.IsolatedAsyncioTestCase):
    async def test_extract_payload(self):
        payload = {"audio_subtitles": [{"speech_url": "https://example.com/a.mp3"}]}
        response = {"data": {"tasks": [{"payload": json.dumps(payload)}]}}
        extracted = CapCutTTSBackend._extract_payload(response)
        self.assertEqual(extracted, payload)

    async def test_backend_selection(self):
        capcut_service = TTSService(backend="capcut", capcut_voice="BV421_vivn_streaming")
        self.assertIsNotNone(capcut_service.capcut)
        self.assertFalse(capcut_service.is_remote_backend)

        http_service = TTSService(backend="http", api_url="https://tts.example.com")
        self.assertIsNone(http_service.capcut)
        self.assertTrue(http_service.is_remote_backend)

    async def test_synthesize_dispatches_to_capcut(self):
        service = TTSService(backend="capcut", capcut_voice="BV421_vivn_streaming")
        backend = service.capcut
        self.assertIsNotNone(backend)

        with patch.object(backend, "synthesize", new=unittest.mock.AsyncMock(return_value=b"audio-bytes")) as mock_synth:
            result = await service.synthesize("hello", voice="default", speed=1.0)
            self.assertEqual(result, b"audio-bytes")
            mock_synth.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
