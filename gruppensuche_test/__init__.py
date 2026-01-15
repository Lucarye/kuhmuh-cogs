from redbot.core.bot import Red
from .GruppensucheModule import GruppensucheTest

async def setup(bot: Red) -> None:
    await bot.add_cog(GruppensucheTest(bot))
