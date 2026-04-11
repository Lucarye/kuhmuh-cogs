from redbot.core.bot import Red # pyright: ignore[reportMissingImports]
from .GruppensucheModule import GruppensucheTest

async def setup(bot: Red) -> None:
    await bot.add_cog(GruppensucheTest(bot))
