import traceback
from redbot.core import commands

DEFAULT_REPO_ALIAS = "kuhmuh"  # passe deinen Repo-Alias hier an (°repo add <alias> ...)

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

    # ---- Helpers ----

    async def _repo_update(self, ctx: commands.Context, repo_alias: str):
        await ctx.invoke(self.bot.get_command("repo update"), repo=repo_alias)

    async def _cog_install_list(self, ctx: commands.Context, repo_alias: str):
        # nutzt vorhandenes Red-Kommando, gibt Text aus – wir parsen grob den Output nicht,
        # sondern lassen ihn anzeigen; für saubere Logik haben wir unten eigene Checks.
        await ctx.invoke(self.bot.get_command("cog list"), repo=repo_alias)

    def _is_loaded(self, cog_name: str) -> bool:
        return cog_name in self.bot.cogs

    async def _safe_reload(self, ctx: commands.Context, cog: str):
        # Wenn gelayouted ist: reload, sonst load
        if self._is_loaded(cog):
            await ctx.invoke(self.bot.get_command("reload"), module=cog)
        else:
            await ctx.invoke(self.bot.get_command("load"), module=cog)

    # ---- Commands ----

    @commands.is_owner()
    @commands.command(name="kuhmuhlist")
    async def kuhmuh_list(self, ctx: commands.Context, *, repo: str = DEFAULT_REPO_ALIAS):
        """Zeigt (aus Bot-Sicht) geladen/ungeladen für Cogs aus dem Repo an."""
        await ctx.send(f"📦 Prüfe Repo **{repo}** …")
        # Wir zeigen die bekannte Red-Ansicht an (praktisch, um zu sehen, was es gibt)
        await self._cog_install_list(ctx, repo)
        # Zusätzlich: kurze geladene/ungeladene Übersicht (nur Namen, die der Bot kennt)
        loaded = sorted(self.bot.cogs.keys())
        if loaded:
            await ctx.send("✅ Geladen: " + ", ".join(loaded))
        else:
            await ctx.send("ℹ️ Aktuell sind keine Cogs geladen (oder Red listet sie nicht unter diesem Alias).")

    @commands.is_owner()
    @commands.command(name="kuhmuhupdate")
    async def kuhmuh_update(self, ctx: commands.Context, *, repo: str = DEFAULT_REPO_ALIAS):
        """
        Aktualisiert das Repo & versucht alle installierten Cogs daraus zu updaten und reloaden.
        Nutzt Red-Kommandos: repo update -> cog update all (implizit per reload Versuch).
        """
        await ctx.send(f"🔄 Aktualisiere Repo **{repo}** …")
        try:
            await self._repo_update(ctx, repo)
        except Exception as e:
            return await ctx.send(f"❌ repo update fehlgeschlagen: `{e}`")

        # Wir kennen die exakten Cogs eines Repos nicht programmgesteuert, deshalb:
        # Strategie: Alle _geladenen_ Cogs reloaden (sicher), dazu typische aus deinem Repo benennen.
        # Du kannst hier eine Liste deiner Repo-Cogs pflegen, dann werden sie gezielt geupdated.
        known_repo_cogs = [
            "nachrichteninfo",
            "kuhmuh_tools",
            "triggerpost",  # füge hier weitere Cogs hinzu, wenn du willst
        ]

        summary = []
        for cog in known_repo_cogs:
            try:
                await ctx.send(f"♻️ Update & Reload `{cog}` …")
                # Versuch: explizites Update dieses Cogs (falls Red das repo-spezifisch erfordert)
                try:
                    await ctx.invoke(self.bot.get_command("cog update"), repo=repo, cog=cog)
                except Exception:
                    # Wenn der Manager kein spezifisches Update braucht, ignorieren.
                    pass
                await self._safe_reload(ctx, cog)
                summary.append(f"✅ {cog}")
            except Exception as e:
                summary.append(f"❌ {cog}: {e}")
                await ctx.send(f"```py\n{traceback.format_exc()}\n```")

        await ctx.send("**Fertig.**\n" + "\n".join(summary))

    @commands.is_owner()
    @commands.command(name="kuhmuhupdatecog")
    async def kuhmuh_update_cog(self, ctx: commands.Context, cog: str, *, repo: str = DEFAULT_REPO_ALIAS):
        """Aktualisiert & reloadet genau EINEN Cog (z. B. °kuhmuhupdatecog nachrichteninfo)."""
        await ctx.send(f"🔄 Aktualisiere Repo **{repo}** …")
        try:
            await self._repo_update(ctx, repo)
        except Exception as e:
            return await ctx.send(f"❌ repo update fehlgeschlagen: `{e}`")

        try:
            # Optionaler Versuch eines gezielten Updates
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
