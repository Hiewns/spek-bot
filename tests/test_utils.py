import unittest
import time
import shutil
from pathlib import Path
from utils.validators import TextProcessor
from utils.rate_limiter import RateLimiter
from utils.cache import AudioCache


class TestTextProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = TextProcessor(max_length=50)

    def test_clean_text(self):
        text = "Hello <@123456789>! Check out https://example.com/audio and #general <#987654>!"
        cleaned = self.processor.clean_text(text)
        self.assertEqual(cleaned, "Hello! Check out and general!")

    def test_clean_markdown_and_code(self):
        text = "Here is ```python print('secret')``` and `inline code` and **bold** *italic*."
        cleaned = self.processor.clean_text(text)
        self.assertEqual(cleaned, "Here is and and bold italic.")

    def test_truncate(self):
        text = "This is a very long string that should be cut off."
        truncated = self.processor.truncate(text, max_length=20)
        self.assertTrue(len(truncated) <= 23)
        self.assertTrue(truncated.endswith("..."))

    def test_validate(self):
        valid, _ = self.processor.validate("Hello world!")
        self.assertTrue(valid)

        invalid_empty, _ = self.processor.validate("   ")
        self.assertFalse(invalid_empty)

        invalid_links_only, _ = self.processor.validate("https://google.com <@123456>")
        self.assertFalse(invalid_links_only)


class TestRateLimiter(unittest.TestCase):
    def test_rate_limiting(self):
        limiter = RateLimiter(max_requests=3, window_seconds=2)
        user_id = 1001

        self.assertFalse(limiter.is_rate_limited(user_id))
        self.assertFalse(limiter.is_rate_limited(user_id))
        self.assertFalse(limiter.is_rate_limited(user_id))
        # 4th request should be limited
        self.assertTrue(limiter.is_rate_limited(user_id))
        self.assertGreater(limiter.get_reset_time(user_id), 0)

        # Clear or wait
        limiter.clear(user_id)
        self.assertFalse(limiter.is_rate_limited(user_id))


class TestAudioCache(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_audio_cache")
        self.cache = AudioCache(cache_dir=self.test_dir, ttl_hours=1, max_size_mb=1)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_cache_save_and_retrieve(self):
        dummy_audio = b"ID3fakeaudiobytes"
        saved = self.cache.save("hello world", "en-us", 1.0, dummy_audio)
        self.assertTrue(saved.exists())

        retrieved = self.cache.get("hello world", "en-us", 1.0)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.read_bytes(), dummy_audio)

        # Miss case
        miss = self.cache.get("different text", "en-us", 1.0)
        self.assertIsNone(miss)


if __name__ == "__main__":
    unittest.main()
