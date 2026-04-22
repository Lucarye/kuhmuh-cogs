from redbot.core.bot import Red
from .export import Export


async def setup(bot: Red) -> None:
    await bot.add_cog(Export(bot))
