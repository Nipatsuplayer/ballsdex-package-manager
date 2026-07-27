from typing import TYPE_CHECKING

from .cog import RestartWatcher

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


async def setup(bot: "BallsDexBot") -> None:
    await bot.add_cog(RestartWatcher(bot))
