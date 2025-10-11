import traceback
from redbot.core import commands

DEFAULT_REPO_ALIAS = "kuhmuh"  # Dein Repo-Alias aus: °repo add kuhmuh <URL>

class KuhmuhTools(commands.Cog):
    """
    :muhkuh: Kuhmuh Tools – Owner-Utilities für schnelle Repo-Updates (nur Prefix-Befehle).
    
    Befehle:
      °kuhmuhupdate [repo=<alias>]           -> Update+Reload aller Cogs aus Repo
      °kuhmuhupdatecog <cog> [repo=<alias>]  -> Update+Reload eines Cogs
      °kuhmuhlist [repo=<alias>]             -> zeigt installierte/verfügbare Cogs
    """

    def __init__(self, bot):
        self.bot = bot

        # Diese Liste enthält alle Cogs, die automatisch mit °kuhmuhupdate aktualisiert & neu geladen werden.
        self.known_repo_cogs = [
            "nachrichteninfo",
            "triggerpost",
            "kuhmuh_tools",
        ]

    # ---- Hilfsfunktionen ----

    async def _repo_update(self, ctx: commands.Context, repo_alias: str):
        await ctx.invoke(self.bot.get_command("repo update"), repo=repo_alias)

    async def _cog_list(self, ctx: commands.Context, repo_alias: str):
        await ctx.invoke(self.bot.get_command("cog list"), repo=repo_alias)

    def _is_loaded(self, cog_name: str) -> bool:
        return cog_name in self.bot.cogs

    async def _safe_reload(self, ctx: commands.Context, cog: str):
        if self._is_loaded(cog):
            await ctx.invoke(self.bot.get_command("reload"), module=cog)
        else:
            await ctx.invoke(self.bot.get_command("load"), module=cog)

    # ---- Befehle ----

    @commands.is_owner()
    @commands.command(name="kuhmuhlist")
    async def kuhmuh_list(self, ctx: commands.Context, *, repo: str = DEFAULT_REPO_ALIAS):
        """Zeigt installierte/verfügbare Cogs und aktuell geladene an."""
        await ctx.send(f"📦 Prüfe Repo **{repo}** …")
        await self._cog_list(ctx, repo)

        loaded = sorted(self.bot.cogs.keys())
        if loaded:
            await ctx.send("✅ Geladen: " + ", ".join(loaded))
        else:
            await ctx.send("ℹ️ Keine Cogs geladen oder Red listet sie nicht unter diesem Alias.")

    @commands.is_owner()
    @commands.command(name="kuhmuhupdate")
    async def kuhmuh_update(self, ctx: commands.Context, *, repo: str = DEFAULT_REPO_ALIAS):
        """Aktualisiert das Repo und lädt alle bekannten Cogs neu."""
        await ctx.send(f"🔄 Aktualisiere Repo **{repo}** …")

        try:
            await self._repo_update(ctx, repo)
        except Exception as e:
            return await ctx.send(f"❌ Repo-Update fehlgeschlagen: `{e}`")

        summary = []
        for cog in self.known_repo_cogs:
            try:
                await ctx.send(f"♻️ Update & Reload `{cog}` …")
                try:
                    await ctx.invoke(self.bot.get_command("cog update"), repo=repo, cog=cog)
                except Exception:
                    pass  # nicht schlimm, wenn cog update nicht unterstützt wird
                await self._safe_reload(ctx, cog)
                summary.append(f"✅ {cog}")
            except Exception as e:
                summary.append(f"❌ {cog}: {e}")
                await ctx.send(f"```py\n{traceback.format_exc()}\n```")

        await ctx.send("**Fertig.**\n" + "\n".join(summary))

    @commands.is_owner()
    @commands.command(name="kuhmuhupdatecog")
    async def kuhmuh_update_cog(self, ctx: commands.Context, cog: str, *, repo: str = DEFAULT_REPO_ALIAS):
        """Aktualisiert & reloadet genau einen Cog (z. B. °kuhmuhupdatecog nachrichteninfo)."""
        await ctx.send(f"🔄 Aktualisiere Repo **{repo}** …")

        try:
            await self._repo_update(ctx, repo)
        except Exception as e:
            return await ctx.send(f"❌ Repo-Update fehlgeschlagen: `{e}`")

        try:
            try:
                await ctx.invoke(self.bot.get_command("cog update"), repo=repo, cog=cog)
            except Exception:
                pass
            await self._safe_reload(ctx, cog)
            await ctx.send(f"✅ `{cog}` aktualisiert & neu geladen.")
        except Exception as e:
            await ctx.send(f"❌ `{cog}` fehlgeschlagen: `{e}`")
            await ctx.send(f"```py\n{traceback.format_exc()}\n```")

async def setup(bot):
    await bot.add_cog(KuhmuhTools(bot))
