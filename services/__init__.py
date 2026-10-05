"""Services package for Discord TTS Bot."""
from .capcut_tts_backend import CapCutTTSBackend
from .edge_tts_backend import EdgeTTSBackend, VIETNAMESE_VOICES
from .tts_service import TTSService
from .audio_handler import AudioHandler
from .voice_manager import VoiceManager

__all__ = [
    "CapCutTTSBackend",
    "EdgeTTSBackend",
    "VIETNAMESE_VOICES",
    "TTSService",
    "AudioHandler",
    "VoiceManager",
]
