# Edge-TTS Implementation & Configuration Guide

This document describes how **Edge-TTS** is structured, configured, and implemented within this project (`pyvideotrans`), including its role in the dubbing pipeline, parameters, proxy handling, and Vietnamese language support.

---

## 1. Overview & Architecture

Edge-TTS connects to Microsoft Edge's cloud text-to-speech service over WebSockets via the `edge-tts` Python library. It is keyless and free to use, but requires an active internet connection.

In this project, Edge-TTS is handled by:
- **TTS Provider Class:** `videotrans/tts/_edgetts.py` (`EdgeTTS`)
- **Voice Catalog:** `videotrans/voicejson/edge_tts.json`
- **Voice Resolver:** `videotrans/util/help_role.py` (`get_edge_rolelist`)
- **Dubbing Pipeline Integration:** `videotrans/task/dubbing.py` and `videotrans/task/_base.py` (`_edgetts_single`)
- **UI Settings & Parameters:** `videotrans/configure/_app_settings.py`, `videotrans/ui/setini.py`, and `webui.py`

---

## 2. Current Settings & Parameters

Edge-TTS behavior is governed by settings stored in `settings.json` (managed via `_app_settings.py` / UI settings):

| Setting Key | Default Value | Description |
| :--- | :--- | :--- |
| `edgetts_max_concurrent_tasks` | `10` | Maximum concurrent async dubbing tasks. Higher values speed up segment processing, but increase the chance of Microsoft rate limiting (HTTP 429/401). |
| `edgetts_retry_nums` | `3` | Number of retry attempts when a connection or timeout failure occurs. |
| `SAVE_TIMEOUT` | `30`s | In `_edgetts.py`, sets the timeout per audio chunk save to prevent WebSocket hangs. |
| `RETRY_DELAY` | `5`s | Sleep duration between retry attempts. |
| `volume` | `0%` | Configured per dubbing task (`+N%` or `-N%`). |
| `pitch` | `0Hz` | Configured per dubbing task (`+NHz` or `-NHz`). |
| `rate` | `0%` | Voice speed rate (percentage offset). |

---

## 3. Proxy Configuration & Bypass

Edge-TTS requests can be routed through a network proxy if specified in global settings.

- **Global Proxy:** By default, `EdgeTTS` inherits `self.proxy_str` from the application settings.
- **Proxy Bypass Switch:** If your general network proxy causes connection or timeout errors with Edge-TTS, create an empty file named `edgetts-noproxy.txt` in the workspace root directory:
  ```powershell
  New-Item -ItemType File -Path "edgetts-noproxy.txt"
  ```
  When this file exists, `_edgetts.py` and `_base.py` automatically set `useproxy = None` and bypass the proxy.

---

## 4. Vietnamese Language (`vi` / `vi-VN`) Support

Edge-TTS natively supports Vietnamese. In `videotrans/voicejson/edge_tts.json`, the available voices are:

```json
"vi": {
    "NamMinh(Male/VN)": "vi-VN-NamMinhNeural",
    "HoaiMy(Female/VN)": "vi-VN-HoaiMyNeural"
}
```

### Voice Selection
When selecting Vietnamese as target language (`vi` / `vi-VN`):
- **Male Voice:** `vi-VN-NamMinhNeural` (`NamMinh(Male/VN)`)
- **Female Voice:** `vi-VN-HoaiMyNeural` (`HoaiMy(Female/VN)`)

---

## 5. Implementation Code Reference

### A. Core Generation Engine (`videotrans/tts/_edgetts.py`)

```python
import asyncio
from dataclasses import dataclass
from pathlib import Path
from edge_tts import Communicate
from videotrans.configure.config import ROOT_DIR, settings, logger
from videotrans.tts._base import BaseTTS

MAX_CONCURRENT_TASKS = int(settings.get('edgetts_max_concurrent_tasks', 10))
RETRY_NUMS = int(settings.get('edgetts_retry_nums', 3)) + 1
SAVE_TIMEOUT = 30

@dataclass
class EdgeTTS(BaseTTS):
    def __post_init__(self):
        super().__post_init__()
        # Determine whether to use proxy or bypass via edgetts-noproxy.txt
        self.useproxy = None if not self.proxy_str or Path(f'{ROOT_DIR}/edgetts-noproxy.txt').exists() else self.proxy_str

    async def _create_audio_with_retry(self, item, index, total_tasks, semaphore):
        async with semaphore:
            for attempt in range(RETRY_NUMS + 1):
                try:
                    communicate = Communicate(
                        item['text'],
                        voice=item['role'],
                        rate=self.rate,
                        volume=self.volume,
                        pitch=self.pitch,
                        proxy=self.useproxy,
                        connect_timeout=5
                    )
                    await asyncio.wait_for(
                        communicate.save(item['filename'] + ".mp3"),
                        timeout=SAVE_TIMEOUT
                    )
                    return
                except (asyncio.TimeoutError, Exception) as e:
                    if attempt < RETRY_NUMS:
                        await asyncio.sleep(5)
                    else:
                        logger.error(f"EdgeTTS failed after retries: {e}")
                        raise
```

### B. Single Audio / Full-Text Mode (`videotrans/task/_base.py`)

For text files (`.txt`) or single-pass subtitles:
```python
async def _edgetts_single(self, target_audio, kwargs):
    from edge_tts import Communicate
    proxy = None if Path(f'{ROOT_DIR}/edgetts-noproxy.txt').exists() else self.proxy_str
    communicate = Communicate(
        text=kwargs['text'],
        voice=kwargs['voice'],
        rate=kwargs.get('rate', '+0%'),
        volume=kwargs.get('volume', '+0%'),
        pitch=kwargs.get('pitch', '+0Hz'),
        proxy=proxy
    )
    await communicate.save(target_audio)
```

---

## 6. How to Use / Configure

1. **Via Desktop GUI:**
   - Go to **TTS Settings** / **Advanced Settings**.
   - Under Edge-TTS, set `Max Concurrent Tasks` (recommended: `5`–`10`) and `Retries` (default: `3`).
   - In the main interface, set **TTS Engine** to `Edge-TTS (free)`.
   - Set **Target Language** to `Vietnamese` (`vi`).
   - Choose `NamMinh(Male/VN)` or `HoaiMy(Female/VN)`.
2. **Via WebUI (`webui.py`):**
   - Configure EdgeTTS parameters (`edgetts_max_concurrent_tasks` and `edgetts_retry_nums`) directly under the TTS options.
3. **CLI / Direct Execution:**
   - Pass `--tts_type 0` (or `edge`) with `--voice_role "vi-VN-NamMinhNeural"` and `--target_language vi`.
