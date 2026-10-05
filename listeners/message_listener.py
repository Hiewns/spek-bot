import logging
import discord
from discord.ext import commands

logger = logging.getLogger("TTSBot.MessageListener")


class MessageListener(commands.Cog):
    """Listens for regular text messages in channels and speaks them in active voice channels."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore messages from bots (including self)
        if message.author.bot:
            return

        # Ignore DMs (TTS is guild-based)
        if not message.guild:
            return

        # Check if the message is a command
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        # Check guild settings for auto-read
        settings = self.bot.get_guild_settings(message.guild.id)
        if not settings.get("auto_read", True):
            return

        # If a specific text channel is bound, ignore others
        bound_channel_id = settings.get("bound_text_channel_id")
        if bound_channel_id and message.channel.id != bound_channel_id:
            return

        # Verify that the author is in a voice channel
        if not message.author.voice or not message.author.voice.channel:
            return

        voice_channel = message.author.voice.channel

        # If the bot is already connected to a voice channel in this guild,
        # only read if the user is in the same voice channel as the bot
        if message.guild.voice_client and message.guild.voice_client.channel:
            if message.guild.voice_client.channel.id != voice_channel.id:
                return

        # Check per-user rate limit
        if self.bot.rate_limiter.is_rate_limited(message.author.id):
            logger.debug("User %s rate limited on message auto-read.", message.author.id)
            return

        # Validate message
        is_valid, _ = self.bot.text_processor.validate(message.content)
        if not is_valid:
            return

        cleaned_text = self.bot.text_processor.clean_text(message.content)
        truncated_text = self.bot.text_processor.truncate(cleaned_text)

        if not truncated_text:
            return

        # Determine voice & speed
        voice = settings.get("voice", self.bot.default_voice)
        speed = settings.get("speed", self.bot.default_speed)

        # Prepend author display name for clarity if requested or configured
        if settings.get("speak_author_name", True):
            author_prefix = f"{message.author.display_name} says: "
            text_to_speak = f"{author_prefix} {truncated_text}"
        else:
            text_to_speak = truncated_text

        # Fetch audio
        try:
            audio_file = await self.bot.audio_handler.get_audio_file(
                text=text_to_speak,
                voice=voice,
                speed=speed,
            )

            if not audio_file:
                logger.warning("Failed to obtain audio for message %s", message.id)
                return

            await self.bot.voice_manager.enqueue_audio(
                guild=message.guild,
                voice_channel=voice_channel,
                audio_path=audio_file,
                text=text_to_speak,
                user_name=message.author.display_name,
            )
            # Add subtle reaction so user knows message was queued
            try:
                await message.add_reaction("🔊")
            except discord.HTTPException:
                pass
        except Exception as e:
            logger.exception("Error in MessageListener on_message: %s", e)


async def setup(bot):
    await bot.add_cog(MessageListener(bot))
