import os
import sys
import logging
import asyncio
from typing import Dict, Any

import discord
from discord.ext import commands

import config
from utils.validators import TextProcessor
from utils.rate_limiter import RateLimiter
from utils.cache import AudioCache
from services.tts_service import TTSService
from services.audio_handler import AudioHandler
from services.voice_manager import VoiceManager

# Logging setup
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("TTSBot")


class TTSBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True

        super().__init__(
            command_prefix=config.COMMAND_PREFIX,
            intents=intents,
            help_command=commands.DefaultHelpCommand(),
        )

        # Core services and utilities
        self.text_processor = TextProcessor(max_length=config.MAX_MESSAGE_LENGTH)
        self.rate_limiter = RateLimiter(
            max_requests=config.RATE_LIMIT_REQUESTS,
            window_seconds=config.RATE_LIMIT_WINDOW,
        )
        self.audio_cache = AudioCache(
            cache_dir=config.CACHE_DIR,
            ttl_hours=config.CACHE_TTL_HOURS,
            max_size_mb=config.MAX_CACHE_SIZE_MB,
        )
        self.tts_service = TTSService(
            backend=config.TTS_BACKEND,
            api_url=config.TTS_API_URL,
            api_key=config.TTS_API_KEY,
            capcut_voice=config.CAPCUT_VOICE,
            capcut_resource_id=config.CAPCUT_RESOURCE_ID,
            capcut_device_json=config.CAPCUT_DEVICE_JSON,
            capcut_timeout=config.CAPCUT_TIMEOUT,
            edge_voice=config.EDGE_VOICE,
            edge_proxy=config.EDGE_PROXY,
            edge_retries=config.EDGE_RETRIES,
            edge_max_concurrent=config.EDGE_MAX_CONCURRENT,
            edge_volume=config.EDGE_VOLUME,
            edge_pitch=config.EDGE_PITCH,
            edge_no_proxy_file=config.EDGE_NO_PROXY_FILE,
        )
        self.audio_handler = AudioHandler(
            tts_service=self.tts_service,
            audio_cache=self.audio_cache,
        )
        self.voice_manager = VoiceManager(bot=self)

        # Defaults
        self.default_voice = config.DEFAULT_VOICE
        self.default_speed = config.DEFAULT_SPEED

        # In-memory guild settings store (can be wired to SQLite/JSON in future)
        self.guild_settings: Dict[int, Dict[str, Any]] = {}

    def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        if guild_id not in self.guild_settings:
            self.guild_settings[guild_id] = {
                "voice": self.default_voice,
                "speed": self.default_speed,
                "auto_read": True,
                "speak_author_name": False,
                "bound_text_channel_id": None,
            }
        return self.guild_settings[guild_id]

    def save_guild_settings(self, guild_id: int, settings: Dict[str, Any]) -> None:
        self.guild_settings[guild_id] = settings

    async def setup_hook(self) -> None:
        """Initialize HTTP sessions and load cogs."""
        await self.tts_service.initialize()

        # Load extension cogs
        cogs = [
            "commands.voice_commands",
            "commands.admin_commands",
            "commands.tts_commands",
            "listeners.message_listener",
            "listeners.attachment_listener",
        ]
        self.loaded_cogs = []
        for cog in cogs:
            try:
                await self.load_extension(cog)
                self.loaded_cogs.append(cog)
                logger.info("Loaded extension: %s", cog)
            except Exception as e:
                logger.error("FAILED to load extension %s: %s", cog, e, exc_info=True)

        if not self.loaded_cogs:
            logger.critical(
                "No cogs loaded. Slash commands will not appear. "
                "Check the errors above and ensure all dependencies are installed."
            )
            return

        # Sync globally (can take up to ~1 hour to propagate to clients)
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d global application (slash) commands.", len(synced))
        except Exception as e:
            logger.error("Failed to sync global application commands: %s", e)

        # Also sync per-guild for instant availability in each server
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                guild_synced = await self.tree.sync(guild=guild)
                logger.info(
                    "Synced %d application commands to guild '%s' (%s).",
                    len(guild_synced),
                    guild.name,
                    guild.id,
                )
            except Exception as e:
                logger.error("Failed to sync commands to guild %s: %s", guild.id, e)

    async def on_ready(self):
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        logger.info("Bot is ready and listening across %d guilds.", len(self.guilds))
        logger.info("Loaded cogs: %s", ", ".join(getattr(self, "loaded_cogs", [])) or "none")
        if not self.guilds:
            logger.warning(
                "The bot is not in any server yet. Use the OAuth2 invite URL "
                "(scopes: bot + applications.commands) to add it, then restart."
            )

    async def on_guild_join(self, guild: discord.Guild):
        """Sync slash commands immediately when the bot joins a new server."""
        try:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(
                "Joined guild '%s' (%s) and synced %d commands.",
                guild.name,
                guild.id,
                len(synced),
            )
        except Exception as e:
            logger.error("Failed to sync commands to newly joined guild %s: %s", guild.id, e)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Auto-disconnect if the bot is left alone in a voice channel."""
        voice_client = member.guild.voice_client
        if not voice_client or not voice_client.channel:
            return

        # Check if the channel bot is in only contains bots
        bot_channel = voice_client.channel
        human_members = [m for m in bot_channel.members if not m.bot]

        if len(human_members) == 0:
            logger.info("No humans left in voice channel %s. Leaving...", bot_channel.name)
            await self.voice_manager.leave(member.guild)

    async def close(self):
        """Cleanup upon shutdown."""
        logger.info("Shutting down bot...")
        await self.tts_service.close()
        for guild in self.guilds:
            if guild.voice_client:
                await self.voice_manager.leave(guild)
        await super().close()


def main():
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "your_bot_token_here":
        logger.warning(
            "DISCORD_TOKEN is not configured in .env. Please configure it to run the bot in production."
        )

    bot = TTSBot()
    try:
        bot.run(config.DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.critical("Invalid Discord token provided. Please update your .env file.")
    except Exception as e:
        logger.critical("Failed to start bot: %s", e)


if __name__ == "__main__":
    main()
