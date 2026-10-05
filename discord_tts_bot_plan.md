# Discord TTS Bot Development Plan

## Overview

A comprehensive guide to building a Discord bot that reads chat messages aloud through a custom TTS API.

---

## Architecture

### Bot Flow
```
Discord Server (user sends message)
    ↓
Bot Listener (captures message event)
    ↓
Text Processing (filter & validate input)
    ↓
TTS API (converts text to audio)
    ↓
Audio Handler (download & cache audio)
    ↓
Voice Manager (join VC & play audio)
    ↓
Discord Voice Channel (audio plays)
```

### Supporting Systems
- **Configuration**: API keys, voice settings
- **Error Handler**: Log & notify users
- **Rate Limiter**: Prevent API abuse
- **Cache/Database**: Store audio & metadata

---

## Phase 1: Foundation (Setup & Core Listeners)

### What You Need
- Discord bot library: `discord.py` (Python) or `discord.js` (Node.js)
- TTS API client (custom API or third-party like Google Cloud TTS, Azure, ElevenLabs)
- Voice handling library: `pyttsx3` (local) or FFmpeg (for streaming audio)
- Environment secrets: Discord token, TTS API key

### Initial Tasks
1. Create bot with `discord.py` or `discord.js`
2. Implement message event listener
3. Set up logging and error handling
4. Test bot connectivity to Discord

### Example Setup (discord.py)
```python
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    print(f"Message from {message.author}: {message.content}")
    await bot.process_commands(message)

bot.run('YOUR_DISCORD_TOKEN')
```

---

## Phase 2: Text Processing Pipeline

### Implement
- Message validation (length limits, filtering commands)
- Text normalization (remove mentions, emojis, URLs)
- Language detection (if API supports multiple languages)
- Handle special cases (links, code blocks, etc.)

### Considerations
- Discord message max is 2000 chars; TTS API may have limits
- Cache repeated phrases to avoid redundant API calls
- Queue management for multiple simultaneous requests

### Example Text Processor
```python
import re
from urllib.parse import urlparse

class TextProcessor:
    MAX_LENGTH = 500
    
    @staticmethod
    def clean_text(text):
        """Remove mentions, URLs, and excessive emojis"""
        # Remove @mentions
        text = re.sub(r'<@[\w!&]+>', '', text)
        # Remove URLs
        text = re.sub(r'http[s]?://\S+', '', text)
        # Remove markdown formatting
        text = re.sub(r'[*_~`]', '', text)
        # Remove excessive whitespace
        text = ' '.join(text.split())
        return text.strip()
    
    @staticmethod
    def truncate(text, max_length=MAX_LENGTH):
        """Truncate text and add ellipsis"""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text
    
    @staticmethod
    def validate(text):
        """Check if text is valid for TTS"""
        if not text or len(text.strip()) == 0:
            return False, "Message is empty"
        if len(text) > 2000:
            return False, "Message exceeds Discord limit"
        return True, None
```

---

## Phase 3: TTS API Integration

### Setup
- Authenticate with your custom TTS API
- Build request/response handlers
- Implement retries and fallback strategies
- Cache audio files locally or in cloud storage

### Key Features
- Voice selection (multiple voices/accents)
- Speed/pitch control
- Error handling for API downtime

### Example TTS Service
```python
import aiohttp
import asyncio
from typing import Optional

class TTSService:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key
        self.session = None
    
    async def initialize(self):
        """Initialize async session"""
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close async session"""
        if self.session:
            await self.session.close()
    
    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        speed: float = 1.0,
        max_retries: int = 3
    ) -> Optional[bytes]:
        """Convert text to speech with retry logic"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "text": text,
            "voice": voice,
            "speed": speed,
            "format": "mp3"
        }
        
        for attempt in range(max_retries):
            try:
                async with self.session.post(
                    f"{self.api_url}/synthesize",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        return await response.read()
                    elif response.status == 429:  # Rate limited
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"TTS API error: {response.status}")
                        return None
            except asyncio.TimeoutError:
                print(f"TTS API timeout (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                print(f"TTS service error: {e}")
                return None
        
        return None
```

---

## Phase 4: Audio Delivery & Voice Channel

### Implement
- Voice channel detection and auto-join
- Audio file download and formatting (PCM, MP3)
- FFmpeg integration for audio streaming
- Playback controls (stop, pause, volume)

### Edge Cases
- Bot doesn't have voice permissions
- User not in voice channel
- Audio format incompatibility

### Example Voice Manager
```python
import discord
from discord.ext import commands

class VoiceManager:
    def __init__(self, bot):
        self.bot = bot
        self.current_vc = None
    
    async def join_and_play(
        self,
        user: discord.Member,
        audio_path: str
    ) -> bool:
        """Join user's voice channel and play audio"""
        # Check if user is in a voice channel
        if not user.voice or not user.voice.channel:
            raise Exception("User is not in a voice channel")
        
        channel = user.voice.channel
        
        # Check bot permissions
        if not channel.permissions_for(channel.guild.me).connect:
            raise Exception("Bot lacks permission to join voice channel")
        
        # Connect to voice channel
        if self.current_vc is None or not self.current_vc.is_connected():
            self.current_vc = await channel.connect()
        else:
            await self.current_vc.move_to(channel)
        
        # Play audio
        try:
            audio_source = discord.FFmpegPCMAudio(audio_path)
            self.current_vc.play(audio_source)
            return True
        except Exception as e:
            print(f"Playback error: {e}")
            return False
    
    async def stop_playing(self):
        """Stop playback and disconnect"""
        if self.current_vc and self.current_vc.is_playing():
            self.current_vc.stop()
        
        if self.current_vc and self.current_vc.is_connected():
            await self.current_vc.disconnect()
            self.current_vc = None
```

---

## Phase 5: Rate Limiting & Abuse Prevention

### Add
- Per-user/per-guild rate limits
- Cooldown timers (e.g., 1 TTS request per 5 seconds)
- Blacklist/whitelist commands
- API quota tracking

### Example Rate Limiter
```python
import time
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.user_requests = defaultdict(list)
    
    def is_rate_limited(self, user_id: int) -> bool:
        """Check if user has exceeded rate limit"""
        now = time.time()
        cutoff = now - self.window_seconds
        
        # Clean old entries
        self.user_requests[user_id] = [
            ts for ts in self.user_requests[user_id] if ts > cutoff
        ]
        
        # Check limit
        if len(self.user_requests[user_id]) >= self.max_requests:
            return True
        
        self.user_requests[user_id].append(now)
        return False
    
    def get_reset_time(self, user_id: int) -> int:
        """Get seconds until rate limit resets"""
        if not self.user_requests[user_id]:
            return 0
        
        oldest_request = min(self.user_requests[user_id])
        reset_time = int(oldest_request + self.window_seconds - time.time())
        return max(0, reset_time)
```

---

## Phase 6: Configuration & User Control

### Implement
- Admin commands to set voice preferences
- Enable/disable by channel
- Custom voice profiles per guild
- User opt-out mechanism

### Example Commands
```python
@bot.command(name='tts')
@commands.has_permissions(administrator=True)
async def configure_tts(ctx, action: str, **kwargs):
    """
    Configure TTS settings
    Usage: !tts voice female
    Usage: !tts speed 1.2
    Usage: !tts disable #channel
    """
    if action == "voice":
        voice = kwargs.get('voice', 'default')
        # Save to guild config
        await ctx.send(f"✓ Voice set to: {voice}")
    
    elif action == "speed":
        speed = float(kwargs.get('speed', 1.0))
        if 0.5 <= speed <= 2.0:
            # Save to guild config
            await ctx.send(f"✓ Speed set to: {speed}x")
        else:
            await ctx.send("❌ Speed must be between 0.5 and 2.0")
    
    elif action == "disable":
        # Disable for specific channel
        await ctx.send("✓ TTS disabled for this channel")

@bot.command(name='tts_status')
async def tts_status(ctx):
    """Check current TTS settings"""
    status = {
        "voice": "female",
        "speed": "1.0x",
        "enabled": True
    }
    embed = discord.Embed(title="TTS Status", color=discord.Color.blue())
    for key, value in status.items():
        embed.add_field(name=key, value=value, inline=True)
    await ctx.send(embed=embed)
```

---

## Phase 7: Monitoring & Maintenance

### Track
- API response times
- Success/failure rates
- Cache hit ratios
- User feedback

### Example Monitoring
```python
import logging
from datetime import datetime

class Metrics:
    def __init__(self):
        self.total_requests = 0
        self.successful_tts = 0
        self.failed_tts = 0
        self.cache_hits = 0
        self.api_response_times = []
    
    def log_request(self, success: bool, response_time: float):
        """Log TTS request"""
        self.total_requests += 1
        if success:
            self.successful_tts += 1
        else:
            self.failed_tts += 1
        self.api_response_times.append(response_time)
    
    def get_stats(self) -> dict:
        """Get current metrics"""
        avg_time = sum(self.api_response_times) / len(self.api_response_times) if self.api_response_times else 0
        success_rate = (self.successful_tts / self.total_requests * 100) if self.total_requests > 0 else 0
        
        return {
            "total_requests": self.total_requests,
            "success_rate": f"{success_rate:.1f}%",
            "avg_response_time": f"{avg_time:.2f}s",
            "cache_hits": self.cache_hits,
            "cache_hit_rate": f"{self.cache_hits / self.total_requests * 100:.1f}%" if self.total_requests > 0 else "0%"
        }
```

---

## Technology Stack Recommendation

| Component | Option A | Option B |
|-----------|----------|----------|
| **Language** | Python 3.10+ | Node.js 18+ |
| **Discord Lib** | discord.py | discord.js |
| **TTS API** | Your custom API | Google Cloud TTS / ElevenLabs |
| **Storage** | Local SQLite | PostgreSQL / MongoDB |
| **Audio Codec** | FFmpeg | libopus |
| **Hosting** | Docker on VPS | AWS Lambda / Railway |

---

## Code Structure

```
discord-tts-bot/
├── config.py                 # Settings & secrets
├── bot.py                    # Main bot entry
├── listeners/
│   └── message_listener.py   # On-message handler
├── services/
│   ├── tts_service.py        # TTS API calls
│   ├── audio_handler.py      # Download & stream audio
│   └── voice_manager.py      # Voice channel logic
├── utils/
│   ├── cache.py              # Audio caching
│   ├── rate_limiter.py       # Anti-abuse
│   └── validators.py         # Input validation
├── commands/
│   ├── voice_commands.py     # Voice settings
│   └── admin_commands.py     # Server config
├── tests/
│   └── test_tts_service.py
├── requirements.txt          # Python dependencies
└── docker-compose.yml        # Docker setup
```

---

## Common Pitfalls to Avoid

### 1. No Caching
**Problem**: Every repeated phrase hits the API = slow & costly  
**Solution**: Implement audio file caching with TTL (time-to-live)

### 2. Blocking Main Loop
**Problem**: Long TTS requests freeze the bot  
**Solution**: Always use `async`/`await` for API calls

### 3. No Rate Limiting
**Problem**: Malicious users spam `/tts`, wasting API quota  
**Solution**: Implement per-user and per-guild rate limits

### 4. Poor Error Messages
**Problem**: Users don't know why it failed  
**Solution**: Return clear, actionable error messages

### 5. Missing Permissions Checks
**Problem**: Bot can't join the voice channel  
**Solution**: Verify bot has `connect` and `speak` permissions

### 6. Audio Format Mismatch
**Problem**: Discord expects specific codec (Opus)  
**Solution**: Use FFmpeg to convert audio to PCM format

### 7. No Timeout Handling
**Problem**: API takes 30s, user loses patience  
**Solution**: Set reasonable timeouts and fallback responses

---

## Dependencies (Python)

```
discord.py==2.3.0
aiohttp==3.9.0
python-dotenv==1.0.0
ffmpeg-python==0.2.1
```

Install with: `pip install -r requirements.txt`

---

## Environment Variables

```bash
DISCORD_TOKEN=your_bot_token_here
TTS_API_URL=https://your-tts-api.com
TTS_API_KEY=your_api_key_here
LOG_LEVEL=INFO
CACHE_DIR=./audio_cache
MAX_MESSAGE_LENGTH=500
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW=60
```

---

## Next Steps

1. **Choose your tech stack** (Python or Node.js)
2. **Set up the bot skeleton** with message listener
3. **Integrate with TTS API** and test audio generation
4. **Implement voice channel management** with FFmpeg
5. **Add rate limiting and caching** for production
6. **Deploy to hosting** (VPS, Docker, or cloud)
7. **Monitor and iterate** based on user feedback

---

## Useful Resources

- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [discord.js Documentation](https://discord.js.org/)
- [FFmpeg Guide](https://ffmpeg.org/)
- [Google Cloud TTS API](https://cloud.google.com/text-to-speech)
- [ElevenLabs TTS](https://elevenlabs.io/)

---

## Support

For issues or questions during implementation, consider:
- Reading Discord.py/discord.js documentation
- Testing TTS API separately before bot integration
- Using logging extensively for debugging
- Testing bot permissions in a test server first
