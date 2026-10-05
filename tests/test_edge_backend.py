import unittest
from unittest.mock import patch, AsyncMock

from services.tts_service import TTSService
from services.edge_tts_backend import EdgeTTSBackend, format_percent, format_hz


class TestEdgeHelpers(unittest.TestCase):
    def test_format_percent(self):
        self.assertEqual(format_percent(1.0), "+0%")
        self.assertEqual(format_percent(1.2), "+20%")
        self.assertEqual(format_percent(0.8), "-20%")

    def test_format_hz(self):
        self.assertEqual(format_hz(0), "+0Hz")
        self.assertEqual(format_hz(5), "+5Hz")
        self.assertEqual(format_hz(-3), "-3Hz")


class TestEdgeBackend(unittest.IsolatedAsyncioTestCase):
    async def test_backend_selection(self):
        edge_service = TTSService(backend="edge", edge_voice="vi-VN-HoaiMyNeural")
        self.assertIsNotNone(edge_service.edge)
        self.assertIsNone(edge_service.capcut)
        self.assertFalse(edge_service.is_remote_backend)

    async def test_proxy_bypass_file(self):
        import tempfile, os
        backend = EdgeTTSBackend(proxy="http://127.0.0.1:7890", no_proxy_file="does-not-exist.txt")
        self.assertEqual(backend.use_proxy, "http://127.0.0.1:7890")

        with tempfile.TemporaryDirectory() as tmp:
            bypass = os.path.join(tmp, "edgetts-noproxy.txt")
            with open(bypass, "w") as f:
                f.write("")
            backend2 = EdgeTTSBackend(proxy="http://127.0.0.1:7890", no_proxy_file=bypass)
            self.assertIsNone(backend2.use_proxy)

    async def test_synthesize_dispatches_to_edge(self):
        service = TTSService(backend="edge", edge_voice="vi-VN-HoaiMyNeural")
        with patch.object(service.edge, "synthesize", new=AsyncMock(return_value=b"edge-audio")) as mock_synth:
            result = await service.synthesize("hello", voice="default", speed=1.0)
            self.assertEqual(result, b"edge-audio")
            mock_synth.assert_awaited_once()

    async def test_vietnamese_voice_catalog(self):
        backend = EdgeTTSBackend()
        catalog = await backend.list_vietnamese_voices()
        self.assertIn("vi-VN-HoaiMyNeural", catalog.values())
        self.assertIn("vi-VN-NamMinhNeural", catalog.values())


if __name__ == "__main__":
    unittest.main()
