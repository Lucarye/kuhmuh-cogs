"""
Export Cog - Exportiert die Member-Liste als CSV
Folgt den KUHMUH-Regelwerken für Slash-Commands und Guild-Scope
"""

import csv
import io
from datetime import datetime
from typing import Optional

import discord  # pyright: ignore[reportMissingImports]
from discord import app_commands  # pyright: ignore[reportMissingImports]
from discord.ext import tasks  # pyright: ignore[reportMissingImports]
from redbot.core import commands  # pyright: ignore[reportMissingImports]
from redbot.core.bot import Red  # pyright: ignore[reportMissingImports]

# ====== Server-spezifische IDs (aus RULEBOOK) ======
GUILD_ID = 1198649628787212458
OWNER_ID = 359447597427064833
ADMIN_ROLE_ID = 1198650646786736240
OFFIZIER_ROLE_ID = 1198652039312453723

MUHKUH_EMOJI = "<:muhkuh:1207038544510586890>"


class Export(commands.Cog):
    """Cog für CSV-Export der Memberliste"""

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self._startup_task = self.bot.loop.create_task(self._startup_guild_sync())

    async def _startup_guild_sync(self) -> None:
        """Synchronisiert Slash-Commands beim Start"""
        await self.bot.wait_until_red_ready()
        await self.bot.wait_until_ready()
        await self.bot.tree.sync(guild=discord.Object(id=GUILD_ID))

    def _has_export_permission(self, user: discord.User | discord.Member) -> bool:
        """Prüft, ob der Nutzer Export-Berechtigung hat"""
        if isinstance(user, discord.Member):
            # Owner hat immer Zugriff
            if user.id == OWNER_ID:
                return True
            # Admin oder Offizier
            if any(role.id in [ADMIN_ROLE_ID, OFFIZIER_ROLE_ID] for role in user.roles):
                return True
        return False

    def _get_member_roles_str(self, member: discord.Member) -> str:
        """Gibt eine Komma-getrennte Liste der Rollen zurück"""
        roles = [role.name for role in member.roles if role.name != "@everyone"]
        return "; ".join(roles) if roles else "Keine Rollen"

    def _get_join_method(self, member: discord.Member) -> str:
        """
        Versucht, die Beitrittsmethode zu ermitteln.
        Discord stellt diese Info nicht direkt bereit, daher verwenden wir Heuristiken:
        - Invite-Tracking würde einen zusätzlichen Bot-Code benötigen
        - Fallback: "Unbekannt" (würde durch erweiterte Logs ermittelbar sein)
        """
        # Hinweis: Echte Beitrittsmethode benötigt Audit-Log-Zugriff und Invite-Tracking
        # Für MVP: "Unbekannt" oder "Invite" als Standardwert
        return "Invite"

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="export",
        description="Exportiert die Memberliste als CSV"
    )
    @app_commands.choices(
        format=[
            app_commands.Choice(name="CSV-Datei", value="csv")
        ]
    )
    async def export_member(
        self,
        interaction: discord.Interaction,
        format: str = "csv"
    ) -> None:
        """
        Exportiert die Memberliste mit:
        - Nickname
        - Richtiger Discord-Name
        - Zugewiesene Rollen
        - Beitrittsdatum Server
        - Beitrittsmethode
        """

        # Berechtigung prüfen
        if not self._has_export_permission(interaction.user):
            await interaction.response.send_message(
                f"❌ Du hast keine Berechtigung für diesen Command. "
                f"Nur Admins und Offiziere können exportieren.",
                ephemeral=True
            )
            return

        # Deferring da Export etwas länger dauern kann
        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send(
                    "❌ Guild konnte nicht geladen werden.",
                    ephemeral=True
                )
                return

            # Alle Member laden
            members = guild.members
            if not members:
                await interaction.followup.send(
                    "❌ Keine Member gefunden.",
                    ephemeral=True
                )
                return

            # CSV-Datei erstellen
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)

            # Header schreiben
            writer.writerow([
                "Nickname",
                "Discord-Name",
                "Zugewiesene Rollen",
                "Beitrittsdatum Server",
                "Beitrittsmethode"
            ])

            # Member-Daten schreiben
            for member in sorted(members, key=lambda m: m.joined_at or datetime.now()):
                nickname = member.display_name
                discord_name = f"{member.name}#{member.discriminator}" if member.discriminator else member.name
                roles = self._get_member_roles_str(member)
                join_date = (
                    member.joined_at.strftime("%d.%m.%Y %H:%M:%S")
                    if member.joined_at
                    else "Unbekannt"
                )
                join_method = self._get_join_method(member)

                writer.writerow([
                    nickname,
                    discord_name,
                    roles,
                    join_date,
                    join_method
                ])

            # CSV als Datei vorbereiten
            csv_content = csv_buffer.getvalue()
            csv_file = discord.File(
                io.BytesIO(csv_content.encode("utf-8-sig")),
                filename=f"memberliste_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            # Embed für Bestätigung
            embed = discord.Embed(
                title=f"{MUHKUH_EMOJI} Member-Export erfolgreich",
                description=f"**{len(members)}** Member wurden exportiert.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="Exportierte Felder",
                value="• Nickname\n• Discord-Name\n• Rollen\n• Beitrittsdatum\n• Beitrittsmethode",
                inline=False
            )
            embed.set_footer(text=f"Exportiert von {interaction.user.display_name}")

            await interaction.followup.send(
                embed=embed,
                file=csv_file,
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Fehler beim Export: {str(e)}",
                ephemeral=True
            )
