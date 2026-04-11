from .gruppenübersicht import Gruppenübersicht


async def setup(bot):
    await bot.add_cog(Gruppenübersicht(bot))