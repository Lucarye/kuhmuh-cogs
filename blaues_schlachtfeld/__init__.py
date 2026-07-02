from redbot.core.bot import Red
from .blaues_schlachtfeld import BlauesSchlachtfeldCog


async def setup(bot: Red) -> None:
    await bot.add_cog(BlauesSchlachtfeldCog(bot))
