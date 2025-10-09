from .triggerpost import TriggerPost

async def setup(bot):
    await bot.add_cog(TriggerPost(bot))
