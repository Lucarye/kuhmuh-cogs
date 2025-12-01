import discord
from discord import app_commands
from redbot.core import commands, Config
from redbot.core.bot import Red


ADMIN_ROLE_ID = 1198650646786736240
REPO_NAME = "kuhmuh"


class Update(commands.Cog):
    """SMART-Update-System für das Repo 'kuhmuh'."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=982374982374, force_registration=True)
        self.config.register_global(cogs=[])

        # Slash Command Groups
        self.update_group = app_commands.Group(
            name="update",
            description="Kuhmuh Update-System"
        )

        self.kuhmuh_group = app_commands.Group(
            name="kuhmuh",
            description="Update-Funktionen für das Kuhmuh-Repo"
        )

        # Subcommands registrieren
        self.update_group.add_command(self.kuhmuh_group)

        # KUHMUH: LIST
        @self.kuhmuh_group.command(
            name="list",
            description="Zeigt Status aller Cogs im Repo."
        )
        async def list_cmd(interaction: discord.Interaction):
            await self._cmd_list(interaction)

        # KUHMUH: ADD
        @self.kuhmuh_group.command(
            name="add",
            description="Fügt ein Cog zur Update-Liste hinzu."
        )
        async def add_cmd(interaction: discord.Interaction, name: str):
            await self._cmd_add(interaction, name)

        # KUHMUH: REMOVE
        @self.kuhmuh_group.command(
            name="remove",
            description="Entfernt ein Cog aus der Update-Liste."
        )
        async def remove_cmd(interaction: discord.Interaction, name: str):
            await self._cmd_remove(interaction, name)

        # KUHMUH: RUN (alle)
        @self.kuhmuh_group.command(
            name="run",
            description="SMART-Update aller gespeicherten Cogs."
        )
        async def run_cmd(interaction: discord.Interaction):
            await self._cmd_run_all(interaction)

        # KUHMUH: SINGLE
        @self.kuhmuh_group.command(
            name="single",
            description="SMART-Update eines einzelnen Cogs."
        )
        async def single_cmd(interaction: discord.Interaction, name: str):
            await self._cmd_run_single(interaction, name)

    # ------------------------------------------------------------
    # Slash-Command-Registrierung
    # ------------------------------------------------------------

async def cog_load(self):
    guild = discord.Object(id=1198649628787212458)

    # Command hinzufügen
    self.bot.tree.add_command(self.update_group, guild=guild)

    # Visibility auf Adminrolle beschränken
    try:
        perms = {
            discord.Object(id=ADMIN_ROLE_ID): discord.Permissions(administrator=True)
        }
        await self.bot.get_guild(1198649628787212458).set_app_commands_permissions(permissions=perms)
    except Exception:
        pass

    # FORCE SYNC (wichtig!)
    await self.bot.tree.sync(guild=guild)
    # ------------------------------------------------------------
    # KUHMUH-COMMANDS (INTERN)
    # ------------------------------------------------------------

    async def _cmd_list(self, interaction: discord.Interaction):
        repo_cogs = await self._fetch_repo_cogs()
        loaded_cogs = list(self.bot.cogs.keys())
        saved_cogs = await self.config.cogs()

        missing_in_repo = [c for c in saved_cogs if c not in repo_cogs]
        not_loaded = [c for c in repo_cogs if c not in loaded_cogs]

        msg = (
            "📦 **Repo-Cogs:**\n" +
            ("\n".join(f"• {c}" for c in repo_cogs) if repo_cogs else "– keine –") +
            "\n\n🔧 **Cogs in deiner Update-Liste:**\n" +
            ("\n".join(f"• {c}" for c in saved_cogs) if saved_cogs else "– leer –") +
            "\n\n🟢 **Geladene Cogs:**\n" +
            ("\n".join(f"• {c}" for c in loaded_cogs) if loaded_cogs else "– keine –") +
            "\n\n🔴 **Nicht geladene Repo-Cogs:**\n" +
            ("\n".join(f"• {c}" for c in not_loaded) if not_loaded else "– keine –")
        )

        if missing_in_repo:
            msg += (
                "\n\n⚠️ **Cogs in deiner Liste, aber nicht im Repo:**\n" +
                "\n".join(f"• {c}" for c in missing_in_repo)
            )

        await interaction.response.send_message(msg, ephemeral=False)

    # ------------------------------------------------------------

    async def _cmd_add(self, interaction: discord.Interaction, name: str):
        cogs = await self.config.cogs()
        if name in cogs:
            await interaction.response.send_message(f"⚠️ **{name}** ist bereits in der Liste.", ephemeral=False)
            return

        cogs.append(name)
        await self.config.cogs.set(cogs)

        await interaction.response.send_message(
            f"➕ Cog **{name}** wurde zur Update-Liste hinzugefügt.", ephemeral=False
        )

    # ------------------------------------------------------------

    async def _cmd_remove(self, interaction: discord.Interaction, name: str):
        cogs = await self.config.cogs()
        if name not in cogs:
            await interaction.response.send_message(f"⚠️ **{name}** ist nicht in der Liste.", ephemeral=False)
            return

        cogs.remove(name)
        await self.config.cogs.set(cogs)

        await interaction.response.send_message(
            f"➖ Cog **{name}** wurde entfernt.", ephemeral=False
        )

    # ------------------------------------------------------------

    async def _cmd_run_all(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        saved_cogs = await self.config.cogs()
        repo_cogs = await self._fetch_repo_cogs()

        result = await self._smart_update(saved_cogs, repo_cogs)

        await interaction.followup.send(result, ephemeral=False)

    # ------------------------------------------------------------

    async def _cmd_run_single(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=False)

        repo_cogs = await self._fetch_repo_cogs()
        result = await self._smart_update([name], repo_cogs)

        await interaction.followup.send(result, ephemeral=False)

    # ------------------------------------------------------------
    # HELPER
    # ------------------------------------------------------------

    async def _fetch_repo_cogs(self):
        """Liest verfügbare Cogs aus dem Repo."""
        dl = self.bot.get_cog("Downloader")
        if not dl:
            return []

        try:
            rm = getattr(dl, "_repo_manager", None)
            repo = await rm.get_repo(REPO_NAME)
            return [c.name for c in repo.available_cogs]
        except Exception:
            return []

    # ------------------------------------------------------------

    async def _smart_update(self, list_cogs, repo_cogs):
        updated = []
        unchanged = []
        failed = []

        # Repo updaten:
        try:
            await self.bot.get_command("repo update").callback(self.bot, REPO_NAME)
        except Exception:
            pass

        for cog in list_cogs:
            if cog not in repo_cogs:
                failed.append((cog, "nicht im Repo"))
                continue

            try:
                await self.bot.get_command("cog install").callback(
                    self.bot, REPO_NAME, cog, "--force"
                )
            except Exception:
                pass

            try:
                await self.bot.get_command("reload").callback(self.bot, cog)
                updated.append(cog)
            except Exception:
                unchanged.append(cog)

        msg = "🔄 **Update abgeschlossen**\n\n"

        if updated:
            msg += "🟢 **Aktualisiert:**\n" + "\n".join(f"• {c}" for c in updated) + "\n\n"

        if unchanged:
            msg += "⚪ **Keine Änderung:**\n" + "\n".join(f"• {c}" for c in unchanged) + "\n\n"

        if failed:
            msg += "🔴 **Fehler / nicht im Repo:**\n" + "\n".join(f"• {c}: {r}" for c, r in failed)

        return msg

