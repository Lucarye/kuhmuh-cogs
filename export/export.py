"""
Export Cog - Exportiert die Member-Liste als CSV.
Folgt den KUHMUH-Regelwerken fuer Slash-Commands und Guild-Scope.
"""

import csv
import io
from datetime import datetime

import discord  # pyright: ignore[reportMissingImports]
from discord import app_commands  # pyright: ignore[reportMissingImports]
from redbot.core import commands  # pyright: ignore[reportMissingImports]
from redbot.core.bot import Red  # pyright: ignore[reportMissingImports]

# ====== Server-spezifische IDs (aus RULEBOOK) ======
GUILD_ID = 1198649628787212458
OWNER_ID = 359447597427064833
ADMIN_ROLE_ID = 1198650646786736240
OFFIZIER_ROLE_ID = 1198652039312453723

MUHKUH_EMOJI = "<:muhkuh:1207038544510586890>"


class Export(commands.Cog):
    """Cog fuer CSV-Export der Memberliste."""

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self._startup_task = self.bot.loop.create_task(self._startup_guild_sync())

    async def _startup_guild_sync(self) -> None:
        """Synchronisiert den guild-scoped Slash-Command beim Start."""
        try:
            await self.bot.wait_until_red_ready()
            await self.bot.wait_until_ready()
            await self.bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        except Exception:
            pass

    def cog_unload(self) -> None:
        if self._startup_task and not self._startup_task.done():
            self._startup_task.cancel()

    def _has_export_permission(self, user: discord.User | discord.Member) -> bool:
        """Prueft, ob der Nutzer Export-Berechtigung hat."""
        if not isinstance(user, discord.Member):
            return False

        if user.id == OWNER_ID:
            return True

        return any(role.id in {ADMIN_ROLE_ID, OFFIZIER_ROLE_ID} for role in user.roles)

    def _get_member_roles_str(self, member: discord.Member) -> str:
        """Gibt eine Semikolon-getrennte Liste der Rollen zurueck."""
        roles = [role.name for role in member.roles if role.name != "@everyone"]
        return "; ".join(roles) if roles else "Keine Rollen"

    def _get_join_method(self, member: discord.Member) -> str:
        """
        Versucht, die Beitrittsmethode zu ermitteln.
        Discord stellt diese Info nicht direkt bereit; aktuell liefern wir
        daher den definierten Fallback.
        """
        _ = member
        return "Invite"

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="export", description="Exportiert die Memberliste als CSV")
    @app_commands.choices(
        format=[
            app_commands.Choice(name="CSV-Datei", value="csv"),
        ]
    )
    async def export_member(
        self,
        interaction: discord.Interaction,
        format: str = "csv",
    ) -> None:
        """
        Exportiert die Memberliste mit:
        - Nickname
        - Richtiger Discord-Name
        - Zugewiesene Rollen
        - Beitrittsdatum Server
        - Beitrittsmethode
        """
        if not interaction.guild or interaction.guild.id != GUILD_ID:
            await interaction.response.send_message(
                "❌ Dieser Command ist nur in der Kuhmuh-Guild verfuegbar.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Dieser Command kann nur innerhalb des Servers verwendet werden.",
                ephemeral=True,
            )
            return

        if format != "csv":
            await interaction.response.send_message(
                "❌ Aktuell wird nur das Format CSV unterstuetzt.",
                ephemeral=True,
            )
            return

        if not self._has_export_permission(interaction.user):
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung fuer diesen Command. "
                "Nur Admins und Offiziere koennen exportieren.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            members = guild.members
            if not members:
                await interaction.followup.send("❌ Keine Member gefunden.", ephemeral=True)
                return

            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)

            writer.writerow(
                [
                    "Nickname",
                    "Discord-Name",
                    "Zugewiesene Rollen",
                    "Beitrittsdatum Server",
                    "Beitrittsmethode",
                ]
            )

            for member in sorted(members, key=lambda m: m.joined_at or datetime.now()):
                nickname = member.display_name
                discord_name = (
                    f"{member.name}#{member.discriminator}"
                    if member.discriminator
                    else member.name
                )
                roles = self._get_member_roles_str(member)
                join_date = (
                    member.joined_at.strftime("%d.%m.%Y %H:%M:%S")
                    if member.joined_at
                    else "Unbekannt"
                )
                join_method = self._get_join_method(member)

                writer.writerow(
                    [
                        nickname,
                        discord_name,
                        roles,
                        join_date,
                        join_method,
                    ]
                )

            csv_content = csv_buffer.getvalue()
            csv_file = discord.File(
                io.BytesIO(csv_content.encode("utf-8-sig")),
                filename=f"memberliste_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            )

            embed = discord.Embed(
                title=f"{MUHKUH_EMOJI} Member-Export erfolgreich",
                description=f"**{len(members)}** Member wurden exportiert.",
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="Exportierte Felder",
                value=(
                    "• Nickname\n"
                    "• Discord-Name\n"
                    "• Rollen\n"
                    "• Beitrittsdatum\n"
                    "• Beitrittsmethode"
                ),
                inline=False,
            )
            embed.set_footer(text=f"Exportiert von {interaction.user.display_name}")

            await interaction.followup.send(
                embed=embed,
                file=csv_file,
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Fehler beim Export: {str(e)}",
                ephemeral=True,
            )
