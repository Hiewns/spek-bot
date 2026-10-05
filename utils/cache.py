import os
import time
import hashlib
from pathlib import Path
from typing import Optional, Union


class AudioCache:
    """Caches synthesized audio files locally by hash of text, voice, and speed."""

    def __init__(
        self,
        cache_dir: Union[str, Path] = "./audio_cache",
        ttl_hours: int = 24,
        max_size_mb: int = 500,
    ):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_hours * 3600
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _generate_cache_key(self, text: str, voice: str, speed: float, audio_format: str = "mp3") -> str:
        unique_string = f"{voice}_{speed:.2f}_{audio_format}_{text}"
        digest = hashlib.sha256(unique_string.encode("utf-8")).hexdigest()
        return f"{digest}.{audio_format}"

    def get_cache_path(self, text: str, voice: str, speed: float, audio_format: str = "mp3") -> Path:
        return self.cache_dir / self._generate_cache_key(text, voice, speed, audio_format)

    def get(self, text: str, voice: str, speed: float, audio_format: str = "mp3") -> Optional[Path]:
        """Return cached audio file Path if it exists and is not expired, else None."""
        file_path = self.get_cache_path(text, voice, speed, audio_format)
        if not file_path.exists():
            return None

        # Check expiration
        mtime = file_path.stat().st_mtime
        if time.time() - mtime > self.ttl_seconds:
            try:
                file_path.unlink()
            except OSError:
                pass
            return None

        return file_path

    def save(self, text: str, voice: str, speed: float, audio_bytes: bytes, audio_format: str = "mp3") -> Path:
        """Save audio bytes to cache and enforce max cache size constraint."""
        self._enforce_size_limit()
        file_path = self.get_cache_path(text, voice, speed, audio_format)
        file_path.write_bytes(audio_bytes)
        return file_path

    def _enforce_size_limit(self) -> None:
        """Evicts oldest files if directory size exceeds max_size_bytes."""
        try:
            files = list(self.cache_dir.glob("*.*"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())

            if total_size <= self.max_size_bytes:
                return

            # Sort by access / modification time (oldest first)
            files.sort(key=lambda f: f.stat().st_mtime)

            for f in files:
                if total_size <= self.max_size_bytes * 0.8:
                    break
                try:
                    size = f.stat().st_size
                    f.unlink()
                    total_size -= size
                except OSError:
                    pass
        except Exception:
            pass

    def clear(self) -> int:
        """Remove all files from the cache directory."""
        count = 0
        for f in self.cache_dir.glob("*.*"):
            try:
                if f.is_file():
                    f.unlink()
                    count += 1
            except OSError:
                pass
        return count
