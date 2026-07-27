from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

from discord.ext import commands

from ..paths import RESTART_FLAG

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("packagemanager.watcher")


class RestartWatcher(commands.Cog):
    """Background task that watches for package changes and triggers a bot restart."""

    def __init__(self, bot: "BallsDexBot") -> None:
        self.bot = bot
        self._watcher_task: asyncio.Task | None = None

    async def cog_load(self) -> None:
        self._watcher_task = asyncio.create_task(self._watch_loop())
        log.info("Restart watcher started.")

    def cog_unload(self) -> None:
        if self._watcher_task:
            self._watcher_task.cancel()
            log.info("Restart watcher stopped.")

    @commands.command()
    @commands.is_owner()
    async def reloadextra(self, ctx: commands.Context) -> None:
        """Reload the extra.toml file."""
        from ..services import import_legacy_packages

        count = import_legacy_packages()
        if count:
            log.info("Imported %d package(s) from extra.toml", count)
            await ctx.send(f"Imported {count} package(s).")
        else:
            await ctx.send("No packages imported.")

    async def _watch_loop(self) -> None:
        """Check for the restart flag every 30 seconds."""
        await self.bot.wait_until_ready()
        while True:
            try:
                if RESTART_FLAG.exists():
                    reason = RESTART_FLAG.read_text(encoding="utf-8").strip()
                    log.info(
                        "Package change detected: %s. Restarting bot...",
                        reason or "no reason specified",
                    )
                    try:
                        RESTART_FLAG.unlink()
                    except OSError:
                        pass
                    # Graceful shutdown - the process manager (systemd, Docker, etc.)
                    # will restart the bot. For manual setups, the user can use
                    # `os.execv` to re-exec.
                    await self.bot.close()
                    sys.exit(0)
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Error in restart watcher")
            await asyncio.sleep(30)
