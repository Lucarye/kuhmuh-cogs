from .update import Update

async def setup(bot):
    await bot.add_cog(Update(bot))
