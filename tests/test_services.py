import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import shutil

from services.tts_service import TTSService
from services.audio_handler import AudioHandler
from utils.cache import AudioCache


class TestServices(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_cache_dir = Path("test_services_cache")
        self.cache = AudioCache(cache_dir=self.test_cache_dir)
        self.tts_service = TTSService(api_url="http://mock-tts.local", api_key="secret-key")
        self.handler = AudioHandler(tts_service=self.tts_service, audio_cache=self.cache)

    async def asyncTearDown(self):
        await self.tts_service.close()
        if self.test_cache_dir.exists():
            shutil.rmtree(self.test_cache_dir)

    async def test_audio_handler_cache_flow(self):
        fake_bytes = b"MPEG-audio-stream"

        # Mock synthesize on TTSService
        with patch.object(self.tts_service, "synthesize", new_callable=AsyncMock) as mock_synth:
            mock_synth.return_value = fake_bytes

            # 1. First fetch -> Cache miss, calls synthesize
            file_path = await self.handler.get_audio_file("Hello there", voice="default", speed=1.0)
            self.assertIsNotNone(file_path)
            self.assertTrue(file_path.exists())
            self.assertEqual(file_path.read_bytes(), fake_bytes)
            mock_synth.assert_called_once()

            # 2. Second fetch -> Cache hit, should NOT call synthesize again
            mock_synth.reset_mock()
            file_path_2 = await self.handler.get_audio_file("Hello there", voice="default", speed=1.0)
            self.assertEqual(file_path, file_path_2)
            mock_synth.assert_not_called()

            stats = self.handler.get_stats()
            self.assertEqual(stats["total_requests"], 2)
            self.assertEqual(stats["cache_hits"], 1)


if __name__ == "__main__":
    unittest.main()
