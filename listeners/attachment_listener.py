import asyncio
import logging
import re
from typing import Optional
import discord
from discord.ext import commands

logger = logging.getLogger("TTSBot.AttachmentListener")


class AttachmentListener(commands.Cog):
    """Watches for uploaded Markdown script files and replies with the extracted column text."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if not message.attachments:
            return

        # Check if the message is a command
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        for attachment in message.attachments:
            if not self._is_markdown(attachment):
                continue
            try:
                raw = await attachment.read()
            except discord.HTTPException as e:
                logger.error("Failed to download attachment %s: %s", attachment.filename, e)
                continue

            try:
                content = raw.decode("utf-8", errors="replace")
            except Exception as e:
                logger.error("Failed to decode attachment %s: %s", attachment.filename, e)
                continue

            lines = self.parse_column(content)
            if not lines:
                continue

            await self._send_lines(message, lines)

    @staticmethod
    def _is_markdown(attachment: discord.Attachment) -> bool:
        name = (attachment.filename or "").lower()
        return name.endswith((".md", ".markdown", ".txt"))

    @staticmethod
    def parse_column(content: str) -> list:
        """Parse a Markdown table and return the last column value per data row, prefixed by the row number.

        Handles the `| Frame | Script | Visual Description |` layout: every row
        becomes `N. <last column>`, ignoring the header and separator rows.
        """
        results = []
        counter = 0

        for line in content.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue

            cells = [c.strip() for c in line.strip("|").split("|")]
            if not cells:
                continue

            # Skip separator rows like |---|---|
            if all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells if c != ""):
                continue

            first = cells[0].lower()

            # Skip the header row
            if first in ("frame", "index", "#", "no", "no."):
                continue

            # Skip the title row (`| Frame | Script | Visual Description |` style header already caught,
            # but the document title uses a single-cell row spanning without pipes)
            last = cells[-1]
            if not last:
                continue

            counter += 1
            results.append(f"{counter}. {last}")

        return results

    async def _send_lines(self, message: discord.Message, lines: list) -> None:
        """Send results in Discord-safe 2000-char chunks."""
        header = f"📄 Extracted {len(lines)} rows from **{message.attachments[0].filename}**:\n"
        buffer = header

        for line in lines:
            if len(buffer) + len(line) + 1 > 1900:
                await message.reply(buffer)
                buffer = ""
            buffer += line + "\n"

        if buffer.strip():
            await message.reply(buffer)


async def setup(bot):
    await bot.add_cog(AttachmentListener(bot))
