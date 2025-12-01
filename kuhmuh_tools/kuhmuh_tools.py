from redbot.core import commands


class KuhmuhTools(commands.Cog):
    """Hilfsbefehle für Kuhmuh-Setup & Updates."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="kuhmuhupdate")
    @commands.admin_or_permissions(manage_guild=True)
    async def kuhmuhupdate(self, ctx: commands.Context):
        """Aktualisiert Repo 'kuhmuh', updated/reinstalled Cogs und lädt sie neu."""
        await ctx.send("🔄 **Starte Update aller Cogs aus 'kuhmuh'…**")

        # 1️⃣ Downloader sicherstellen
        if not self.bot.get_cog("Downloader"):
            try:
                await ctx.invoke(self.bot.get_command("load"), "downloader")
            except Exception:
                await ctx.send("⚠️ Downloader konnte nicht geladen werden, fahre trotzdem fort…")

        # 2️⃣ Repo-Update
        try:
            await ctx.invoke(self.bot.get_command("repo"), "update", "kuhmuh")
        except Exception:
            await ctx.send("⚠️ Repo-Update fehlgeschlagen (übersprungen).")

        # 3️⃣ Cog-Update
        try:
            await ctx.invoke(self.bot.get_command("cog"), "update", "kuhmuh")
        except Exception:
            await ctx.send("⚠️ Cog-Update fehlgeschlagen (übersprungen).")

        # 4️⃣ Cogs aus Repo holen
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

        # 5️⃣ Repo → tatsächliche Cog-Namen mappen
        name_map = {
            "gruppensuche": "Gruppensuche",
            # weitere Cogs falls Struktur abweicht
        }

        mapped = set()
        for name in target_cogs:
            mapped.add(name_map.get(name, name))

        target_cogs = mapped

        # Falls Repo leer → kurze Fallbackliste
        if not target_cogs:
            target_cogs.update({"triggerpost", "kuhmuh_tools"})

        # 6️⃣ Installieren / Reinstallieren
        for cog in target_cogs:
            try:
                await ctx.send(f"🔧 Installiere/Reinstalliere **{cog}**…")
                await ctx.invoke(self.bot.get_command("cog"), "install", reponame, cog, "--force")
            except Exception:
                try:
                    await ctx.invoke(self.bot.get_command("cog"), "reinstall", cog)
                except Exception:
                    await ctx.send(f"⚠️ Konnte {cog} weder installieren noch reinstallen.")

        # 7️⃣ Reload
        reloaded = []
        for cog in target_cogs:
            try:
                await ctx.send(f"♻️ Reload: **{cog}**…")
                await ctx.invoke(self.bot.get_command("unload"), cog)
            except Exception:
                pass
            try:
                await ctx.invoke(self.bot.get_command("load"), cog)
                reloaded.append(cog)
            except Exception:
                await ctx.send(f"⚠️ {cog} konnte nicht neu geladen werden.")

        # 8️⃣ Versionen ausgeben
        version_lines = []
        for cog in reloaded:
            c = self.bot.get_cog(cog)
            version = getattr(c, "__version__", "—")
            version_lines.append(f"• **{cog}** → v{version}")

        if not version_lines:
            version_lines.append("– keine Cogs geladen oder Version nicht verfügbar –")

        await ctx.send("✅ **Update abgeschlossen.**\n\n" + "\n".join(version_lines))


# 🔚 Setup-Funktion MUSS vorhanden sein
async def setup(bot):
    """Erforderlich, damit Red das Cog laden kann."""
    await bot.add_cog(KuhmuhTools(bot))
