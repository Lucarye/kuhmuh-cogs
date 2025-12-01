import discord
from discord import app_commands
from redbot.core import commands, Config
from redbot.core.bot import Red


ADMIN_ROLE_ID = 1198650646786736240
REPO_NAME = "kuhmuh"
GUILD_ID = 1198649628787212458


class Update(commands.Cog):
    """Einfache Update-Funktionen für Cogs aus dem Repo 'kuhmuh'."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789, force_registration=True)
        self.config.register_global(cogs=[])

        # Hauptgruppe /update
        self.update_group = app_commands.Group(
            name="update",
            description="Kuhmuh Update-System"
        )

        # Untergruppe /update kuhmuh
        self.kuhmuh_group = app_commands.Group(
            name="kuhmuh",
            description="Update-Funktionen für das Repo 'kuhmuh'"
        )

        self.update_group.add_command(self.kuhmuh_group)

        # ------------------ SUBCOMMANDS ------------------

        @self.kuhmuh_group.command(name="list", description="Zeigt alle hinzugefügten Cogs.")
        async def list_cmd(interaction: discord.Interaction):
            await self._cmd_list(interaction)

        @self.kuhmuh_group.command(name="add", description="Fügt ein Cog zur Updateliste hinzu.")
        async def add_cmd(interaction: discord.Interaction, cog: str):
            await self._cmd_add(interaction, cog)

        @self.kuhmuh_group.command(name="remove", description="Entfernt ein Cog aus der Updateliste.")
        async def remove_cmd(interaction: discord.Interaction, cog: str):
            await self._cmd_remove(interaction, cog)

        @self.kuhmuh_group.command(name="single", description="Updated ein einzelnes Cog.")
        async def single_cmd(interaction: discord.Interaction, cog: str):
            await self._cmd_single(interaction, cog)

        @self.kuhmuh_group.command(name="run", description="Updated alle Cogs aus der Liste.")
        async def run_cmd(interaction: discord.Interaction):
            await self._cmd_run(interaction)

    # ------------------------------------------------------------
    # Slash Commands registrieren
    # ------------------------------------------------------------

    async def cog_load(self):
        guild = discord.Object(id=GUILD_ID)

        # Commands nur für diese Guild sichtbar
        self.bot.tree.add_command(self.update_group, guild=guild)

        # Sichtbarkeit nur für Adminrolle
        try:
            g = self.bot.get_guild(GUILD_ID)
            if g:
                perms = {
                    discord.Object(id=ADMIN_ROLE_ID): discord.Permissions(administrator=True)
                }
                await g.set_app_commands_permissions(permissions=perms)
        except Exception:
            pass

        # FORCE SYNC → sofort sichtbar machen
        try:
            await self.bot.tree.sync(guild=guild)
        except Exception:
            pass

    # ------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------

    async def _cmd_list(self, interaction: discord.Interaction):
        cogs = await self.config.cogs()

        loaded = list(self.bot.cogs.keys())

        msg = "📦 **Cogs in deiner Liste:**\n"

        if not cogs:
            msg += "– keine –"
        else:
            for c in cogs:
                if c in loaded:
                    msg += f"🟢 {c} (geladen)\n"
                else:
                    msg += f"🔴 {c} (nicht geladen)\n"

        await interaction.response.send_message(msg, ephemeral=False)

    # ------------------------------------------------------------
    # ADD
    # ------------------------------------------------------------

    async def _cmd_add(self, interaction: discord.Interaction, cog: str):
        cogs = await self.config.cogs()
        if cog in cogs:
            await interaction.response.send_message(f"⚠️ **{cog}** ist bereits in der Liste.", ephemeral=False)
            return

        cogs.append(cog)
        await self.config.cogs.set(cogs)

        await interaction.response.send_message(f"➕ Cog **{cog}** hinzugefügt.", ephemeral=False)

    # ------------------------------------------------------------
    # REMOVE
    # ------------------------------------------------------------

    async def _cmd_remove(self, interaction: discord.Interaction, cog: str):
        cogs = await self.config.cogs()
        if cog not in cogs:
            await interaction.response.send_message(f"⚠️ **{cog}** ist nicht in der Liste.", ephemeral=False)
            return

        cogs.remove(cog)
        await self.config.cogs.set(cogs)

        await interaction.response.send_message(f"➖ Cog **{cog}** entfernt.", ephemeral=False)

    # ------------------------------------------------------------
    # SINGLE UPDATE
    # ------------------------------------------------------------

    async def _cmd_single(self, interaction: discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral=False)

        msg = await self._update_cog(cog)

        await interaction.followup.send(msg, ephemeral=False)

    # ------------------------------------------------------------
    # UPDATE ALL
    # ------------------------------------------------------------

    async def _cmd_run(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        cogs = await self.config.cogs()
        if not cogs:
            await interaction.followup.send("⚠️ Keine Cogs in der Liste.", ephemeral=False)
            return

        output = "🔄 **Aktualisiere Cogs aus kuhmuh ...**\n\n"

        for cog in cogs:
            output += await self._update_cog(cog)

        await interaction.followup.send(output, ephemeral=False)

    # ------------------------------------------------------------
    # UPDATE LOGIK (1:1 wie du gewohnt bist)
    # ------------------------------------------------------------

    async def _update_cog(self, cog: str):
        """Führt aus:
        repo update kuhmuh
        cog uninstall <cog>
        cog install kuhmuh <cog>
        reload <cog>
        """
        out = ""

        # repo update
        try:
            repo_cmd = self.bot.get_command("repo")
            ctx = await self._fake_ctx(f"repo update {REPO_NAME}")
            await ctx.invoke(repo_cmd, "update", REPO_NAME)
        except Exception:
            pass

        # uninstall
        try:
            uninstall_cmd = self.bot.get_command("cog")
            ctx = await self._fake_ctx(f"cog uninstall {cog}")
            await ctx.invoke(uninstall_cmd, "uninstall", cog)
        except Exception:
            pass

        # install
        try:
            install_cmd = self.bot.get_command("cog")
            ctx = await self._fake_ctx(f"cog install {REPO_NAME} {cog}")
            await ctx.invoke(install_cmd, "install", REPO_NAME, cog)
        except Exception:
            out += f"❌ Installation fehlgeschlagen für **{cog}**\n"
            return out

        # reload
        try:
            reload_cmd = self.bot.get_command("reload")
            ctx = await self._fake_ctx(f"reload {cog}")
            await ctx.invoke(reload_cmd, cog)
        except Exception:
            out += f"♻️ Update & Reload **{cog}** (Reload fehlgeschlagen – evtl. schon aktiv)\n"
            return out

        out += f"🍀 Update & Reload **{cog}**\n"
        return out

    # ------------------------------------------------------------
    # Fake-CTX → um bestehende Prefix-Commands zu nutzen
    # ------------------------------------------------------------

    async def _fake_ctx(self, content: str):
        """Baut einen Fake-Context, um bestehende Textbefehle mit ctx.invoke nutzen zu können."""
        guild = self.bot.get_guild(GUILD_ID)
        channel = guild.text_channels[0]

        message = discord.Object(id=0)
        message.content = content
        message.channel = channel
        message.guild = guild
        message.author = self.bot.user

        return await self.bot.get_context(message)
