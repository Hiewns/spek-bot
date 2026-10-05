import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional, Union
import discord
from discord.ext import commands

logger = logging.getLogger("TTSBot.VoiceManager")


class AudioItem:
    def __init__(self, audio_path: Union[str, Path], text: str, user_name: str):
        self.audio_path = str(audio_path)
        self.text = text
        self.user_name = user_name


class GuildVoiceState:
    """Manages playback queue and connection for a specific guild."""

    def __init__(self, bot: commands.Bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.queue: asyncio.Queue[AudioItem] = asyncio.Queue()
        self.voice_client: Optional[discord.VoiceClient] = None
        self.current_item: Optional[AudioItem] = None
        self.play_task: Optional[asyncio.Task] = None
        self._stopped = False

    async def worker(self) -> None:
        """Background queue processor for the guild voice client."""
        while not self._stopped:
            try:
                item = await self.queue.get()
                if self._stopped:
                    break

                self.current_item = item
                if not self.voice_client or not self.voice_client.is_connected():
                    logger.warning("Voice client disconnected while processing queue for guild %s", self.guild_id)
                    self.queue.task_done()
                    continue

                finished = asyncio.Event()

                def after_playing(err: Optional[Exception]):
                    if err:
                        logger.error("Error during playback in guild %s: %s", self.guild_id, err)
                    self.bot.loop.call_soon_threadsafe(finished.set)

                audio_source = discord.FFmpegPCMAudio(item.audio_path)
                # Volume control wrapper
                transformed_source = discord.PCMVolumeTransformer(audio_source, volume=1.0)

                self.voice_client.play(transformed_source, after=after_playing)
                await finished.wait()

                self.current_item = None
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Unexpected error in GuildVoiceState worker: %s", e)
                await asyncio.sleep(0.5)

    def start(self) -> None:
        self._stopped = False
        if self.play_task is None or self.play_task.done():
            self.play_task = self.bot.loop.create_task(self.worker())

    def stop(self) -> None:
        self._stopped = True
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
        if self.play_task and not self.play_task.done():
            self.play_task.cancel()

        # Drain queue
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except Exception:
                break


class VoiceManager:
    """Manages voice channel connections and audio playback queues per guild."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild_states: Dict[int, GuildVoiceState] = {}

    def get_guild_state(self, guild_id: int) -> GuildVoiceState:
        if guild_id not in self.guild_states:
            self.guild_states[guild_id] = GuildVoiceState(self.bot, guild_id)
        return self.guild_states[guild_id]

    async def join_channel(self, channel: discord.VoiceChannel) -> discord.VoiceClient:
        """Connects or moves the bot to the specified voice channel."""
        guild = channel.guild
        state = self.get_guild_state(guild.id)

        # Check bot permissions
        permissions = channel.permissions_for(guild.me)
        if not permissions.connect:
            raise PermissionError("Bot lacks 'Connect' permission for voice channel.")
        if not permissions.speak:
            raise PermissionError("Bot lacks 'Speak' permission for voice channel.")

        if guild.voice_client is None:
            state.voice_client = await channel.connect()
        else:
            if guild.voice_client.channel.id != channel.id:
                await guild.voice_client.move_to(channel)
            state.voice_client = guild.voice_client

        state.start()
        return state.voice_client

    async def enqueue_audio(
        self,
        guild: discord.Guild,
        voice_channel: discord.VoiceChannel,
        audio_path: Union[str, Path],
        text: str,
        user_name: str,
    ) -> None:
        """Ensures voice connection and enqueues audio file for playback."""
        state = self.get_guild_state(guild.id)
        if not state.voice_client or not state.voice_client.is_connected() or state.voice_client.channel.id != voice_channel.id:
            await self.join_channel(voice_channel)

        item = AudioItem(audio_path=audio_path, text=text, user_name=user_name)
        await state.queue.put(item)

    async def stop(self, guild_id: int) -> None:
        """Stops current playback and clears queue for guild."""
        if guild_id in self.guild_states:
            self.guild_states[guild_id].stop()

    async def leave(self, guild: discord.Guild) -> None:
        """Stops playback, drains queue, and leaves voice channel."""
        await self.stop(guild.id)
        if guild.voice_client and guild.voice_client.is_connected():
            await guild.voice_client.disconnect(force=True)
        if guild.id in self.guild_states:
            del self.guild_states[guild.id]

    def is_connected(self, guild_id: int) -> bool:
        state = self.guild_states.get(guild_id)
        return bool(state and state.voice_client and state.voice_client.is_connected())

    def get_queue_size(self, guild_id: int) -> int:
        state = self.guild_states.get(guild_id)
        return state.queue.qsize() if state else 0
