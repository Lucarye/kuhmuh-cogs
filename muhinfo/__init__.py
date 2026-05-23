from .muhinfo import MuhInfoCog

async def setup(bot):
    await bot.add_cog(MuhInfoCog(bot))
