import discord
from discord import app_commands
from redbot.core import commands, Config
from redbot.core.bot import Red

ADMIN_ROLE_ID = 1198650646786736240
REPO_NAME = "kuhmuh"
GUILD_ID = 1198649628787212458


class Update(commands.Cog):
    """Kuhmuh Update-System (API-Version)."""

    def __init__(self, bot: Red):
        self.bot = bot

        self.config = Config.get_conf(
            self, identifier=984561237, force_registration=True
        )
        self.config.register_global(cogs=[])

        #
        #   Slash Commands
        #
        self.update_group = app_commands.Group(
            name="update", description="Kuhmuh Update-System"
        )

        self.kuhmuh_group = app_commands.Group(
            name="kuhmuh", description="Update-Funktionen für das Repo 'kuhmuh'"
        )

        self.update_group.add_command(self.kuhmuh_group)

        # --- SUBCOMMANDS ---

        @self.kuhmuh_group.command(
            name="list", description="Liste aller Cogs in deiner Update-Liste."
        )
        async def list_cmd(interaction: discord.Interaction):
            await self._cmd_list(interaction)

        @self.kuhmuh_group.command(
            name="add", description="Fügt ein Cog zur Update-Liste hinzu."
        )
        async def add_cmd(interaction: discord.Interaction, cog: str):
            await self._cmd_add(interaction, cog)

        @self.kuhmuh_group.command(
            name="remove", description="Entfernt ein Cog aus der Update-Liste."
        )
        async def remove_cmd(interaction: discord.Interaction, cog: str):
            await self._cmd_remove(interaction, cog)

        @self.kuhmuh_group.command(
            name="single", description="Updated ein einzelnes Cog."
        )
        async def single_cmd(interaction: discord.Interaction, cog: str):
            await self._cmd_single(interaction, cog)

        @self.kuhmuh_group.command(
            name="run", description="Updated alle Cogs aus der Update-Liste."
        )
        async def run_cmd(interaction: discord.Interaction):
            await self._cmd_run(interaction)

    # ---------------------------------------------------------------------
    #  Slash Commands registrieren
    # ---------------------------------------------------------------------

    async def cog_load(self):
        guild = discord.Object(id=GUILD_ID)

        # Slash-Gruppe registrieren
        self.bot.tree.add_command(self.update_group, guild=guild)

        # Nur Adminrolle darf den Befehl sehen/ausführen
        try:
            g = self.bot.get_guild(GUILD_ID)
            if g:
                permissions = [
                    discord.app_commands.AppCommandPermission(
                        id=ADMIN_ROLE_ID,
                        type=discord.AppCommandPermissionType.role,
                        permission=True,
                    )
                ]
                await g.bulk_edit_app_command_permissions(
                    commands=[self.update_group], permissions=permissions
                )
        except Exception:
            pass

        # Sync
        try:
            await self.bot.tree.sync(guild=guild)
        except Exception:
            pass

    # ---------------------------------------------------------------------
    #  LIST
    # ---------------------------------------------------------------------

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

        await interaction.response.send_message(msg)

    # ---------------------------------------------------------------------
    #  ADD
    # ---------------------------------------------------------------------

    async def _cmd_add(self, interaction: discord.Interaction, cog: str):
        cogs = await self.config.cogs()
        if cog in cogs:
            await interaction.response.send_message(
                f"⚠️ **{cog}** ist bereits in der Liste."
            )
            return

        cogs.append(cog)
        await self.config.cogs.set(cogs)

        await interaction.response.send_message(f"➕ Cog **{cog}** hinzugefügt.")

    # ---------------------------------------------------------------------
    #  REMOVE
    # ---------------------------------------------------------------------

    async def _cmd_remove(self, interaction: discord.Interaction, cog: str):
        cogs = await self.config.cogs()
        if cog not in cogs:
            await interaction.response.send_message(
                f"⚠️ **{cog}** ist nicht in der Liste."
            )
            return

        cogs.remove(cog)
        await self.config.cogs.set(cogs)

        await interaction.response.send_message(f"➖ Cog **{cog}** entfernt.")

    # ---------------------------------------------------------------------
    #  SINGLE UPDATE
    # ---------------------------------------------------------------------

    async def _cmd_single(self, interaction: discord.Interaction, cog: str):
        await interaction.response.defer()

        out = await self._update_cog(cog)

        await interaction.followup.send(out)

    # ---------------------------------------------------------------------
    #  RUN (alle Cogs)
    # ---------------------------------------------------------------------

    async def _cmd_run(self, interaction: discord.Interaction):
        await interaction.response.defer()

        cogs = await self.config.cogs()
        if not cogs:
            await interaction.followup.send("⚠️ Keine Cogs in der Liste.")
            return

        msg = "🔄 **Aktualisiere Cogs aus kuhmuh ...**\n\n"

        for cog in cogs:
            msg += await(self._update_cog(cog))

        await interaction.followup.send(msg)

    # ---------------------------------------------------------------------
    #  UPDATE PROZESS (API VERSION)
    # ---------------------------------------------------------------------

    async def _update_cog(self, cog: str):
        """Benutzt die Downloader-API für:
        – Repo-Update
        – Uninstall
        – Install
        – Reload
        """

        dl = self.bot.get_cog("Downloader")
        out = ""

        # 1️⃣ Repo aktualisieren
        try:
            await dl._repo_manager.update_repo(REPO_NAME)
        except Exception:
            pass

        # 2️⃣ Uninstall (falls installiert)
        try:
            await dl.uninstall(cog)
        except Exception:
            pass

        # 3️⃣ Install aus Repo
        try:
            await dl.install(REPO_NAME, cog)
        except Exception:
            return f"❌ Installation fehlgeschlagen für **{cog}**\n"

        # 4️⃣ Reload
        try:
            await dl.reload(cog)
        except Exception:
            out += f"♻️ Update & Reload **{cog}** (Reload Fehler – evtl. bereits aktiv)\n"
            return out

        out += f"🍀 Update & Reload **{cog}**\n"
        return out
