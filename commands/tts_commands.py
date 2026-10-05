import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional


class TTSCommands(commands.Cog, name="TTS"):
    """Commands for direct TTS requests."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="speak", description="Synthesize and speak custom text in your voice channel.")
    @app_commands.describe(
        text="The text you want the bot to say",
        voice="Optional voice override",
        speed="Optional speed override between 0.5 and 2.0"
    )
    async def speak(
        self,
        ctx: commands.Context,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ):
        is_slash = ctx.interaction is not None

        if not ctx.author.voice or not ctx.author.voice.channel:
            if is_slash:
                await ctx.reply("❌ You must be in a voice channel first!", ephemeral=True)
            else:
                await ctx.reply("❌ You must be in a voice channel first!")
            return

        # Check rate limit
        if self.bot.rate_limiter.is_rate_limited(ctx.author.id):
            reset = self.bot.rate_limiter.get_reset_time(ctx.author.id)
            msg = f"⏳ You are sending requests too fast! Please wait {reset}s."
            await (ctx.reply(msg, ephemeral=True) if is_slash else ctx.reply(msg))
            return

        # Clean and validate
        is_valid, err = self.bot.text_processor.validate(text)
        if not is_valid:
            msg = f"❌ {err}"
            await (ctx.reply(msg, ephemeral=True) if is_slash else ctx.reply(msg))
            return

        cleaned_text = self.bot.text_processor.clean_text(text)
        truncated_text = self.bot.text_processor.truncate(cleaned_text)

        # Defer interaction if slash command to avoid timeout
        if is_slash:
            await ctx.defer(ephemeral=True)

        guild_settings = self.bot.get_guild_settings(ctx.guild.id)
        selected_voice = voice or guild_settings.get("voice", self.bot.default_voice)
        selected_speed = speed if (speed is not None and 0.5 <= speed <= 2.0) else guild_settings.get("speed", self.bot.default_speed)

        audio_file = await self.bot.audio_handler.get_audio_file(
            text=truncated_text,
            voice=selected_voice,
            speed=selected_speed,
        )

        if not audio_file:
            msg = "❌ Failed to synthesize audio. The TTS service may be unavailable."
            if is_slash:
                await ctx.followup.send(msg, ephemeral=True)
            else:
                await ctx.reply(msg)
            return

        try:
            await self.bot.voice_manager.enqueue_audio(
                guild=ctx.guild,
                voice_channel=ctx.author.voice.channel,
                audio_path=audio_file,
                text=truncated_text,
                user_name=ctx.author.display_name,
            )
            confirmation = f"🗣️ Queued: \"{truncated_text}\""
            if is_slash:
                await ctx.followup.send(confirmation, ephemeral=True)
            else:
                await ctx.message.add_reaction("🔊")
        except PermissionError as pe:
            msg = f"❌ Permission error: {pe}"
            if is_slash:
                await ctx.followup.send(msg, ephemeral=True)
            else:
                await ctx.reply(msg)
        except Exception as e:
            msg = f"❌ Error queuing audio: {e}"
            if is_slash:
                await ctx.followup.send(msg, ephemeral=True)
            else:
                await ctx.reply(msg)


    @commands.hybrid_command(name="voices", description="List available TTS voices for the active backend.")
    @app_commands.describe(language="Optional language filter, e.g. vi-VN or en-US (defaults to vi-VN for Edge-TTS)")
    async def voices(self, ctx: commands.Context, language: Optional[str] = None):
        is_slash = ctx.interaction is not None
        if is_slash:
            await ctx.defer(ephemeral=True)

        backend = getattr(self.bot.tts_service, "backend", "unknown")
        if language is None and backend == "edge":
            language = "vi-VN"

        voice_list = await self.bot.tts_service.list_voices(lang=language)

        if not voice_list:
            msg = "ℹ️ No voice catalog available. The active backend does not expose a voice list."
            if is_slash:
                await ctx.followup.send(msg, ephemeral=True)
            else:
                await ctx.reply(msg)
            return

        lines = [f"• `{v}`" for v in voice_list[:40]]
        if len(voice_list) > 40:
            lines.append(f"... and {len(voice_list) - 40} more.")

        embed = discord.Embed(
            title="🎙️ Available Voices",
            description="\n".join(lines),
            color=discord.Color.green(),
        )
        embed.set_footer(text="Set a voice with /tts_config voice <voice_name>")

        if is_slash:
            await ctx.followup.send(embed=embed, ephemeral=True)
        else:
            await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(TTSCommands(bot))
