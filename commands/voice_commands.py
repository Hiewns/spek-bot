import discord
from discord.ext import commands
from discord import app_commands


class VoiceCommands(commands.Cog, name="Voice"):
    """Commands for controlling bot voice channel participation."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="join", description="Make the bot join your current voice channel.")
    async def join(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply("❌ You must be in a voice channel first!", ephemeral=True)
            return

        channel = ctx.author.voice.channel
        try:
            await self.bot.voice_manager.join_channel(channel)
            await ctx.reply(f"🔊 Joined voice channel: **{channel.name}**")
        except PermissionError as pe:
            await ctx.reply(f"❌ Permission error: {pe}", ephemeral=True)
        except Exception as e:
            await ctx.reply(f"❌ Failed to join voice channel: {e}", ephemeral=True)

    @commands.hybrid_command(name="leave", description="Make the bot leave the voice channel.")
    async def leave(self, ctx: commands.Context):
        if not ctx.guild.voice_client:
            await ctx.reply("ℹ️ The bot is not currently in a voice channel.", ephemeral=True)
            return

        await self.bot.voice_manager.leave(ctx.guild)
        await ctx.reply("👋 Left the voice channel.")

    @commands.hybrid_command(name="stop", description="Stop current audio playback and clear the queue.")
    async def stop(self, ctx: commands.Context):
        if not ctx.guild.voice_client:
            await ctx.reply("ℹ️ No audio is playing.", ephemeral=True)
            return

        await self.bot.voice_manager.stop(ctx.guild.id)
        await ctx.reply("⏹️ Stopped playback and cleared the audio queue.")


async def setup(bot):
    await bot.add_cog(VoiceCommands(bot))
