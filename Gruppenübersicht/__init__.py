from .gruppenuebersicht import Gruppenuebersicht

async def setup(bot):
    await bot.add_cog(Gruppenuebersicht(bot))
