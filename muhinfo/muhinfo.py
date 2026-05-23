from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Dict, List, Optional

import discord  # pyright: ignore[reportMissingImports]
from discord import app_commands  # pyright: ignore[reportMissingImports]
from discord.ext import tasks  # pyright: ignore[reportMissingImports]
from redbot.core import commands, Config  # pyright: ignore[reportMissingImports]

GUILD_ID = 1198649628787212458
ADMIN_ROLE_ID = 1198650646786736240
OFFIZIER_ROLE_ID = 1198652039312453723

DEFAULT_GUILD = {
    "muhinfo_entries": [],
}

WEEKDAY_LABELS = {
    "daily": "Täglich",
    "mo": "Montag",
    "di": "Dienstag",
    "mi": "Mittwoch",
    "do": "Donnerstag",
    "fr": "Freitag",
    "sa": "Samstag",
    "so": "Sonntag",
}

logger = logging.getLogger("red.kuhmuh.muhinfo")


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _parse_time(value: str) -> Optional[str]:
    value = str(value or "").strip()
    if not value:
        return None
    try:
        parts = value.replace(".", ":").split(":")
        if len(parts) != 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return f"{hour:02d}:{minute:02d}"
    except ValueError:
        return None


def _format_schedule(entry: Dict[str, Any]) -> str:
    days = entry.get("days", [])
    if not days:
        return "—"
    if days == ["daily"]:
        day_text = "Täglich"
    else:
        day_text = ", ".join(WEEKDAY_LABELS.get(day, day) for day in days)
    return f"{day_text} um {entry.get('time', '??:??')}"


def _build_entry_embed(entries: List[Dict[str, Any]], guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        title="Muhinfo: Geplante Nachrichten",
        color=discord.Color.blue(),
    )
    if not entries:
        embed.description = "Keine geplanten Muhinfo-Einträge gefunden."
        return embed

    lines: List[str] = []
    for entry in entries:
        channel = guild.get_channel(entry.get("channel_id"))
        channel_name = channel.mention if isinstance(channel, discord.TextChannel) else f"<#{entry.get('channel_id')}>"
        lines.append(
            f"**{entry.get('name')}** (ID `{entry.get('id')}`)\n"
            f"Channel: {channel_name}\n"
            f"Zeitplan: {_format_schedule(entry)}\n"
            f"Nachricht: {entry.get('message')}"
        )
    embed.description = "\n\n".join(lines)
    return embed


def _is_admin_or_officer(member: discord.Member) -> bool:
    if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
        return True
    return any(role.id in {ADMIN_ROLE_ID, OFFIZIER_ROLE_ID} for role in getattr(member, "roles", []))


def _next_entry_id(entries: List[Dict[str, Any]]) -> int:
    return max((int(entry.get("id", 0)) for entry in entries), default=0) + 1


def _is_entry_due(entry: Dict[str, Any], now: dt.datetime) -> bool:
    scheduled_time = entry.get("time")
    if not scheduled_time:
        return False
    if scheduled_time != now.strftime("%H:%M"):
        return False

    days = entry.get("days", [])
    if not days:
        return False
    if days == ["daily"]:
        return True
    weekday_map = ["mo", "di", "mi", "do", "fr", "sa", "so"]
    today = weekday_map[now.weekday()]
    return today in days


class MuhInfoGroup(app_commands.Group):
    def __init__(self, cog: "MuhInfoCog"):
        super().__init__(name="muhinfo", description="Verwaltet automatisierte Muhinfo-Nachrichten.")
        self.cog = cog

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="info", description="Zeigt alle aktuellen Muhinfo-Einträge mit Tagen und Uhrzeiten.")
    async def info(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or interaction.guild.id != GUILD_ID:
            await interaction.followup.send("Dieser Command ist nur für unsere Guild vorgesehen.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            return
        entries = await self.cog.config.guild(interaction.guild).muhinfo_entries()
        embed = _build_entry_embed(entries, interaction.guild)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="add", description="Fügt eine neue zeitgesteuerte Muhinfo-Nachricht hinzu.")
    @app_commands.choices(
        weekday=[
            app_commands.Choice(name="Täglich", value="daily"),
            app_commands.Choice(name="Montag", value="mo"),
            app_commands.Choice(name="Dienstag", value="di"),
            app_commands.Choice(name="Mittwoch", value="mi"),
            app_commands.Choice(name="Donnerstag", value="do"),
            app_commands.Choice(name="Freitag", value="fr"),
            app_commands.Choice(name="Samstag", value="sa"),
            app_commands.Choice(name="Sonntag", value="so"),
        ]
    )
    async def add(
        self,
        interaction: discord.Interaction,
        name: str,
        message: str,
        channel: discord.TextChannel,
        weekday: app_commands.Choice[str],
        time: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or interaction.guild.id != GUILD_ID:
            await interaction.followup.send("Dieser Command ist nur für unsere Guild vorgesehen.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            return
        if not _is_admin_or_officer(interaction.user):
            await interaction.followup.send("🚫 Nur Admins und Offiziere dürfen diesen Befehl verwenden.", ephemeral=True)
            return

        name_clean = _normalize_name(name)
        if not name_clean:
            await interaction.followup.send("⚠️ Bitte gib einen gültigen Eintragsnamen an.", ephemeral=True)
            return

        parsed_time = _parse_time(time)
        if parsed_time is None:
            await interaction.followup.send("⚠️ Bitte gib eine gültige Uhrzeit im Format `HH:MM` an.", ephemeral=True)
            return

        entries = await self.cog.config.guild(interaction.guild).muhinfo_entries()
        if any(_normalize_name(entry.get("name", "")) == name_clean for entry in entries):
            await interaction.followup.send("⚠️ Ein Eintrag mit diesem Namen existiert bereits.", ephemeral=True)
            return

        days = [weekday.value]
        entry = {
            "id": _next_entry_id(entries),
            "name": name.strip(),
            "message": message.strip(),
            "channel_id": channel.id,
            "days": days,
            "time": parsed_time,
            "last_posted_at": None,
        }
        entries.append(entry)
        await self.cog.config.guild(interaction.guild).muhinfo_entries.set(entries)

        await interaction.followup.send(
            f"✅ Muhinfo-Eintrag erstellt: **{entry['name']}**\n"
            f"Channel: {channel.mention}\n"
            f"Zeitplan: {_format_schedule(entry)}",
            ephemeral=True,
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="update", description="Ändert einen bestehenden Muhinfo-Eintrag.")
    @app_commands.choices(
        weekday=[
            app_commands.Choice(name="Täglich", value="daily"),
            app_commands.Choice(name="Montag", value="mo"),
            app_commands.Choice(name="Dienstag", value="di"),
            app_commands.Choice(name="Mittwoch", value="mi"),
            app_commands.Choice(name="Donnerstag", value="do"),
            app_commands.Choice(name="Freitag", value="fr"),
            app_commands.Choice(name="Samstag", value="sa"),
            app_commands.Choice(name="Sonntag", value="so"),
        ]
    )
    async def update(
        self,
        interaction: discord.Interaction,
        name: str,
        message: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None,
        weekday: Optional[app_commands.Choice[str]] = None,
        time: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or interaction.guild.id != GUILD_ID:
            await interaction.followup.send("Dieser Command ist nur für unsere Guild vorgesehen.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            return
        if not _is_admin_or_officer(interaction.user):
            await interaction.followup.send("🚫 Nur Admins und Offiziere dürfen diesen Befehl verwenden.", ephemeral=True)
            return

        entries = await self.cog.config.guild(interaction.guild).muhinfo_entries()
        name_clean = _normalize_name(name)
        entry = next((entry for entry in entries if _normalize_name(entry.get("name", "")) == name_clean), None)
        if not entry:
            await interaction.followup.send("⚠️ Kein Muhinfo-Eintrag mit diesem Namen gefunden.", ephemeral=True)
            return

        if message is not None:
            entry["message"] = message.strip()
        if channel is not None:
            entry["channel_id"] = channel.id
        if weekday is not None:
            entry["days"] = [weekday.value]
        if time is not None:
            parsed_time = _parse_time(time)
            if parsed_time is None:
                await interaction.followup.send("⚠️ Bitte gib eine gültige Uhrzeit im Format `HH:MM` an.", ephemeral=True)
                return
            entry["time"] = parsed_time

        if message is None and channel is None and weekday is None and time is None:
            await interaction.followup.send("⚠️ Bitte gib mindestens ein Feld an, das aktualisiert werden soll.", ephemeral=True)
            return

        await self.cog.config.guild(interaction.guild).muhinfo_entries.set(entries)
        await interaction.followup.send(
            f"✅ Muhinfo-Eintrag aktualisiert: **{entry['name']}**\n"
            f"Neuer Zeitplan: {_format_schedule(entry)}\n"
            f"Channel: <#{entry['channel_id']}>",
            ephemeral=True,
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="remove", description="Löscht einen bestehenden Muhinfo-Eintrag.")
    async def remove(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or interaction.guild.id != GUILD_ID:
            await interaction.followup.send("Dieser Command ist nur für unsere Guild vorgesehen.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            return
        if not _is_admin_or_officer(interaction.user):
            await interaction.followup.send("🚫 Nur Admins und Offiziere dürfen diesen Befehl verwenden.", ephemeral=True)
            return

        entries = await self.cog.config.guild(interaction.guild).muhinfo_entries()
        name_clean = _normalize_name(name)
        remaining = [entry for entry in entries if _normalize_name(entry.get("name", "")) != name_clean]
        if len(remaining) == len(entries):
            await interaction.followup.send("⚠️ Kein Muhinfo-Eintrag mit diesem Namen gefunden.", ephemeral=True)
            return

        await self.cog.config.guild(interaction.guild).muhinfo_entries.set(remaining)
        await interaction.followup.send(f"🗑️ Muhinfo-Eintrag gelöscht: **{name.strip()}**", ephemeral=True)


class MuhInfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0x0A1B2C3D, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)
        self.group = MuhInfoGroup(self)
        self._scheduled_post_loop.start()

    async def cog_load(self) -> None:
        try:
            self.bot.tree.add_command(self.group, guild=discord.Object(id=GUILD_ID))
        except Exception:
            logger.exception("Fehler beim Registrieren des /muhinfo-Befehls.")

    async def cog_unload(self) -> None:
        try:
            self.bot.tree.remove_command("muhinfo", type=discord.AppCommandType.chat_input)
        except Exception:
            pass
        self._scheduled_post_loop.cancel()

    async def _send_entry(self, guild: discord.Guild, entry: Dict[str, Any]) -> None:
        channel = guild.get_channel(entry.get("channel_id"))
        if not isinstance(channel, discord.TextChannel):
            logger.warning("Muhinfo: Ziel-Channel %s nicht gefunden in Guild %s", entry.get("channel_id"), guild.id)
            return

        try:
            await channel.send(entry.get("message", ""))
        except Exception as exc:
            logger.exception("Fehler beim Senden der Muhinfo-Nachricht %s: %s", entry.get("name"), exc)

    @tasks.loop(seconds=60.0)
    async def _scheduled_post_loop(self) -> None:
        now = dt.datetime.now()
        current_minute = now.strftime("%Y-%m-%d %H:%M")

        for guild in self.bot.guilds:
            if guild.id != GUILD_ID:
                continue
            entries = await self.config.guild(guild).muhinfo_entries()
            modified = False
            for entry in entries:
                if not _is_entry_due(entry, now):
                    continue
                if entry.get("last_posted_at") == current_minute:
                    continue
                await self._send_entry(guild, entry)
                entry["last_posted_at"] = current_minute
                modified = True
            if modified:
                await self.config.guild(guild).muhinfo_entries.set(entries)

    @_scheduled_post_loop.before_loop
    async def before_scheduled_post_loop(self) -> None:
        await self.bot.wait_until_ready()
