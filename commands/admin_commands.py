import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional


class AdminCommands(commands.Cog, name="Admin"):
    """Commands for server administrators to configure TTS behavior."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="tts_config", description="Configure TTS settings for this server.")
    @commands.has_permissions(administrator=True)
    async def tts_config(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.reply("Use `/tts_config voice`, `/tts_config speed`, or `/tts_config bind` to configure TTS settings.", ephemeral=True)

    @tts_config.command(name="voice", description="Set the default voice for this server.")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(voice_name="Voice identifier or name")
    async def set_voice(self, ctx: commands.Context, voice_name: str):
        settings = self.bot.get_guild_settings(ctx.guild.id)
        settings["voice"] = voice_name
        self.bot.save_guild_settings(ctx.guild.id, settings)
        await ctx.reply(f"✅ Guild TTS voice set to: `{voice_name}`")

    @tts_config.command(name="speed", description="Set the speech speed (0.5 to 2.0).")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(speed="Speed multiplier between 0.5 and 2.0")
    async def set_speed(self, ctx: commands.Context, speed: float):
        if not (0.5 <= speed <= 2.0):
            await ctx.reply("❌ Speed must be between 0.5 and 2.0.", ephemeral=True)
            return

        settings = self.bot.get_guild_settings(ctx.guild.id)
        settings["speed"] = speed
        self.bot.save_guild_settings(ctx.guild.id, settings)
        await ctx.reply(f"✅ Guild TTS speed set to: `{speed:.2f}x`")

    @tts_config.command(name="bind", description="Bind TTS reader to a specific text channel (or current if omitted).")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="Text channel to bind to (leave empty for current channel)")
    async def bind_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        target_channel = channel or ctx.channel
        settings = self.bot.get_guild_settings(ctx.guild.id)
        settings["bound_text_channel_id"] = target_channel.id
        self.bot.save_guild_settings(ctx.guild.id, settings)
        await ctx.reply(f"✅ TTS will now listen to messages from {target_channel.mention}.")

    @tts_config.command(name="unbind", description="Allow TTS in any channel where users speak or disable auto-read.")
    @commands.has_permissions(administrator=True)
    async def unbind_channel(self, ctx: commands.Context):
        settings = self.bot.get_guild_settings(ctx.guild.id)
        settings["bound_text_channel_id"] = None
        self.bot.save_guild_settings(ctx.guild.id, settings)
        await ctx.reply("✅ Bound channel removed. TTS messages can come from any channel.")

    @commands.hybrid_command(name="tts_status", description="Display current TTS configuration for this server.")
    async def tts_status(self, ctx: commands.Context):
        settings = self.bot.get_guild_settings(ctx.guild.id)
        bound_id = settings.get("bound_text_channel_id")
        bound_channel = ctx.guild.get_channel(bound_id) if bound_id else None
        bound_str = bound_channel.mention if bound_channel else "None (All channels)"

        queue_size = self.bot.voice_manager.get_queue_size(ctx.guild.id)
        is_connected = self.bot.voice_manager.is_connected(ctx.guild.id)

        stats = self.bot.audio_handler.get_stats()

        embed = discord.Embed(title="🎙️ TTS Configuration & Status", color=discord.Color.blurple())
        embed.add_field(name="Default Voice", value=f"`{settings.get('voice', self.bot.default_voice)}`", inline=True)
        embed.add_field(name="Speed", value=f"`{settings.get('speed', self.bot.default_speed):.2f}x`", inline=True)
        embed.add_field(name="Auto-Read", value="`Enabled`" if settings.get("auto_read", True) else "`Disabled`", inline=True)
        embed.add_field(name="Bound Channel", value=bound_str, inline=False)
        embed.add_field(name="Voice Connected", value="`Yes`" if is_connected else "`No`", inline=True)
        embed.add_field(name="Audio Queue Size", value=f"`{queue_size}`", inline=True)
        embed.add_field(name="Cache Hits", value=f"`{stats['cache_hits']}` ({stats['cache_hit_rate']})", inline=True)

        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
