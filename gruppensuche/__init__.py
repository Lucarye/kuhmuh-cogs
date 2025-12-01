# __init__.py
from .gruppensuche import Gruppensuche


async def setup(bot):
    """Wird von Discord.py/Red beim Laden des Cogs aufgerufen."""
    await bot.add_cog(Gruppensuche(bot))
