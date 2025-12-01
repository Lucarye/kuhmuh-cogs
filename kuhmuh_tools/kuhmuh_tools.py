# kuhmuh_tools.py (Ausschnitt)
from redbot.core import commands

class KuhmuhTools(commands.Cog):
    """Hilfsbefehle für Kuhmuh-Setup & Updates."""

    def __init__(self, bot):
        self.bot = bot

@commands.command(name="kuhmuhupdate")
@commands.admin_or_permissions(manage_guild=True)
async def kuhmuhupdate(self, ctx: commands.Context):
    """Aktualisiert Repo 'kuhmuh', updated/reinstalled Cogs und lädt sie neu (mit Versionsanzeige)."""
    await ctx.send("🔄 **Aktualisiere Cogs aus kuhmuh …**")

    # 1️⃣ Downloader sicherstellen
    if not self.bot.get_cog("Downloader"):
        try:
            await ctx.invoke(self.bot.get_command("load"), "downloader")
        except Exception:
            await ctx.send("⚠️ Downloader konnte nicht geladen werden, fahre trotzdem fort...")

    # 2️⃣ Repo & Cogs updaten
    try:
        await ctx.invoke(self.bot.get_command("repo"), "update", "kuhmuh")
    except Exception:
        await ctx.send("⚠️ Repo-Update fehlgeschlagen (übersprungen).")

    try:
        await ctx.invoke(self.bot.get_command("cog"), "update", "kuhmuh")
    except Exception:
        await ctx.send("⚠️ Cog-Update fehlgeschlagen (übersprungen).")

    # 3️⃣ Alle Cogs aus Repo 'kuhmuh' sammeln
    reponame = "kuhmuh"
    target_cogs = set()
    dl = self.bot.get_cog("Downloader")

    try:
        rm = getattr(dl, "_repo_manager", None)
        if rm:
            repo = await rm.get_repo(reponame)
            if repo:
                for cog_meta in repo.available_cogs:
                    name = getattr(cog_meta, "name", None)
                    if name:
                        target_cogs.add(name)
    except Exception:
        pass

    # 4️⃣ Mapping Repo-Namen → tatsächlicher Cog-Name
    # -----------------------------------------------
    # Grund: Cog-Klassenname != Repo-Ordnername
    # z. B. gruppensuche (Repo) → Gruppensuche (tatsächlicher Cog-Name)
    
    name_map = {
        "gruppensuche": "Gruppensuche",
        # weitere Mappings falls nötig
    }

    mapped_cogs = set()
    for name in target_cogs:
        mapped_cogs.add(name_map.get(name, name))

    target_cogs = mapped_cogs

    # Fallback falls API nichts liefert
    if not target_cogs:
        target_cogs.update({"triggerpost", "kuhmuh_tools"})

    # 5️⃣ Installiere / Reinstalliere
    for cog in target_cogs:
        try:
            await ctx.invoke(self.bot.get_command("cog"), "install", reponame, cog, "--force")
        except Exception:
            try:
                await ctx.invoke(self.bot.get_command("cog"), "reinstall", cog)
            except Exception:
                pass

    # 6️⃣ Reload aller geladenen Cogs
    reloaded = []
    for cog in target_cogs:
        try:
            await ctx.invoke(self.bot.get_command("unload"), cog)
        except Exception:
            pass
        try:
            await ctx.invoke(self.bot.get_command("load"), cog)
            reloaded.append(cog)
        except Exception:
            pass

    # 7️⃣ Versionen ausgeben
    version_lines = []
    for cog in reloaded:
        c = self.bot.get_cog(cog)
        version = getattr(c, "__version__", "—")
        version_lines.append(f"• **{cog}** → v{version}")

    if not version_lines:
        version_lines.append("– keine Cogs geladen oder Version nicht verfügbar –")

    summary = "\n".join(version_lines)
    await ctx.send(f"Fertig.\n\n{summary}")
