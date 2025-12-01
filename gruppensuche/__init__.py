# __init__.py
from .GruppensucheModule import Gruppensuche


async def setup(bot):
    await bot.add_cog(Gruppensuche(bot))
