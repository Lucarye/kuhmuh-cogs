# __init__.py
from redbot.core.bot import Red
from .GruppensucheModule import Gruppensuche


async def setup(bot: Red) -> None:
    await bot.add_cog(Gruppensuche(bot))
