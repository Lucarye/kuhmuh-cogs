from .willkommen import Willkommen


async def setup(bot):
    await bot.add_cog(Willkommen(bot))
