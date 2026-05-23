from __future__ import annotations

import contextlib
import datetime as dt
import logging
from typing import Any, Dict, List, Optional

from zoneinfo import ZoneInfo
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

BERLIN_TZ = ZoneInfo("Europe/Berlin")
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


def _berlin_now() -> dt.datetime:
    return dt.datetime.now(tz=BERLIN_TZ)


class MuhInfoMessageModal(discord.ui.Modal):
    def __init__(
        self,
        cog: "MuhInfoCog",
        title: str,
        entry_name: str,
        channel: discord.TextChannel,
        days: List[str],
        time: str,
        current_message: str = "",
        mode: str = "add",
    ) -> None:
        super().__init__(title=title)
        self.cog = cog
        self.entry_name = entry_name
        self.channel = channel
        self.days = days
        self.time = time
        self.mode = mode
        self.message_input = discord.ui.TextInput(
            label="Nachricht",
            style=discord.TextStyle.paragraph,
            required=True,
            default=current_message,
            placeholder="Text hier einfügen. Zeilenumbrüche bleiben erhalten.",
            max_length=2000,
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or interaction.guild.id != GUILD_ID:
            await interaction.response.send_message("Dieser Command ist nur für unsere Guild vorgesehen.", ephemeral=True)
            return

        message = self.message_input.value.strip()
        if not message:
            await interaction.response.send_message("⚠️ Bitte gib eine Nachricht ein.", ephemeral=True)
            return

        if self.mode == "add":
            entries = await self.cog.config.guild(interaction.guild).muhinfo_entries()
            name_clean = _normalize_name(self.entry_name)
            if any(_normalize_name(entry.get("name", "")) == name_clean for entry in entries):
                await interaction.response.send_message("⚠️ Ein Eintrag mit diesem Namen existiert bereits.", ephemeral=True)
                return

            entry = {
                "id": _next_entry_id(entries),
                "name": self.entry_name.strip(),
                "message": message,
                "channel_id": self.channel.id,
                "days": self.days,
                "time": self.time,
                "last_posted_at": None,
            }
            entries.append(entry)
            await self.cog.config.guild(interaction.guild).muhinfo_entries.set(entries)
            await interaction.response.send_message(
                f"✅ Muhinfo-Eintrag erstellt: **{entry['name']}**\n"
                f"Channel: {self.channel.mention}\n"
                f"Zeitplan: {_format_schedule(entry)} (Berlin-Zeit)",
                ephemeral=True,
            )
            return

        if self.mode == "edit":
            entries = await self.cog.config.guild(interaction.guild).muhinfo_entries()
            name_clean = _normalize_name(self.entry_name)
            entry = next((entry for entry in entries if _normalize_name(entry.get("name", "")) == name_clean), None)
            if not entry:
                await interaction.response.send_message("⚠️ Kein Muhinfo-Eintrag mit diesem Namen gefunden.", ephemeral=True)
                return

            entry["message"] = message
            await self.cog.config.guild(interaction.guild).muhinfo_entries.set(entries)
            await interaction.response.send_message(
                f"✅ Muhinfo-Nachricht für **{entry['name']}** wurde aktualisiert.",
                ephemeral=True,
            )
            return


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


class MuhInfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0x0A1B2C3D, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)
        self._scheduled_post_loop.start()

    async def _ac_muhinfo_name(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        entries = []
        if interaction.guild and interaction.guild.id == GUILD_ID:
            entries = await self.config.guild(interaction.guild).muhinfo_entries()
        current_lower = (current or "").strip().lower()
        choices: List[app_commands.Choice[str]] = []
        for entry in entries:
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            if not current_lower or current_lower in name.lower():
                choices.append(app_commands.Choice(name=name, value=name))
                if len(choices) >= 25:
                    break
        return choices

    @app_commands.command(name="muhinfo", description="Verwaltet automatisierte Muhinfo-Nachrichten.")
    @app_commands.autocomplete(name=_ac_muhinfo_name)
    @app_commands.choices(
        operation=[
            app_commands.Choice(name="Info", value="info"),
            app_commands.Choice(name="Add", value="add"),
            app_commands.Choice(name="Update", value="update"),
            app_commands.Choice(name="Remove", value="remove"),
        ],
        weekday=[
            app_commands.Choice(name="Täglich", value="daily"),
            app_commands.Choice(name="Montag", value="mo"),
            app_commands.Choice(name="Dienstag", value="di"),
            app_commands.Choice(name="Mittwoch", value="mi"),
            app_commands.Choice(name="Donnerstag", value="do"),
            app_commands.Choice(name="Freitag", value="fr"),
            app_commands.Choice(name="Samstag", value="sa"),
            app_commands.Choice(name="Sonntag", value="so"),
        ],
    )
    @app_commands.describe(
        operation="Gewünschte Muhinfo-Aktion",
        name="Name des Eintrags",
        channel="Ziel-Channel für Erstellung oder Aktualisierung",
        weekday="Wochentag für die geplante Nachricht",
        time="Uhrzeit im Format HH:MM",
    )
    async def muinfo(
        self,
        interaction: discord.Interaction,
        operation: app_commands.Choice[str],
        name: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None,
        weekday: Optional[app_commands.Choice[str]] = None,
        time: Optional[str] = None,
    ) -> None:
        if not interaction.guild or interaction.guild.id != GUILD_ID:
            await interaction.response.send_message("Dieser Command ist nur für unsere Guild vorgesehen.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Dieser Command kann nur von Mitgliedern im Server ausgeführt werden.", ephemeral=True)
            return
        if not _is_admin_or_officer(interaction.user):
            await interaction.response.send_message("🚫 Nur Admins und Offiziere dürfen diesen Befehl verwenden.", ephemeral=True)
            return

        op = operation.value
        entries = await self.config.guild(interaction.guild).muhinfo_entries()

        if op == "info":
            await interaction.response.defer(ephemeral=True)
            embed = _build_entry_embed(entries, interaction.guild)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if op == "add":
            if not name or not channel or not weekday or not time:
                await interaction.response.send_message("⚠️ Für `add` bitte `name`, `channel`, `weekday` und `time` angeben.", ephemeral=True)
                return
            name_clean = _normalize_name(name)
            if not name_clean:
                await interaction.response.send_message("⚠️ Bitte gib einen gültigen Eintragsnamen an.", ephemeral=True)
                return
            if any(_normalize_name(entry.get("name", "")) == name_clean for entry in entries):
                await interaction.response.send_message("⚠️ Ein Eintrag mit diesem Namen existiert bereits.", ephemeral=True)
                return
            parsed_time = _parse_time(time)
            if parsed_time is None:
                await interaction.response.send_message("⚠️ Bitte gib eine gültige Uhrzeit im Format `HH:MM` an.", ephemeral=True)
                return
            await interaction.response.send_modal(
                MuhInfoMessageModal(
                    cog=self,
                    title="Muhinfo-Nachricht eingeben",
                    entry_name=name,
                    channel=channel,
                    days=[weekday.value],
                    time=parsed_time,
                    current_message="",
                    mode="add",
                )
            )
            return

        if op == "update":
            if not name:
                await interaction.response.send_message("⚠️ Für `update` bitte den Eintragsnamen angeben.", ephemeral=True)
                return
            entry = next((entry for entry in entries if _normalize_name(entry.get("name", "")) == _normalize_name(name)), None)
            if not entry:
                await interaction.response.send_message("⚠️ Kein Muhinfo-Eintrag mit diesem Namen gefunden.", ephemeral=True)
                return
            if channel is None and weekday is None and time is None:
                channel_obj = interaction.guild.get_channel(entry.get("channel_id"))
                if not isinstance(channel_obj, discord.TextChannel):
                    await interaction.response.send_message("⚠️ Ziel-Channel für diesen Eintrag konnte nicht gefunden werden.", ephemeral=True)
                    return
                await interaction.response.send_modal(
                    MuhInfoMessageModal(
                        cog=self,
                        title="Muhinfo-Nachricht bearbeiten",
                        entry_name=name,
                        channel=channel_obj,
                        days=entry.get("days", []),
                        time=entry.get("time", "00:00"),
                        current_message=entry.get("message", ""),
                        mode="edit",
                    )
                )
                return
            if channel is not None:
                entry["channel_id"] = channel.id
            if weekday is not None:
                entry["days"] = [weekday.value]
            if time is not None:
                parsed_time = _parse_time(time)
                if parsed_time is None:
                    await interaction.response.send_message("⚠️ Bitte gib eine gültige Uhrzeit im Format `HH:MM` an.", ephemeral=True)
                    return
                entry["time"] = parsed_time
            await self.config.guild(interaction.guild).muhinfo_entries.set(entries)
            await interaction.response.send_message(
                f"✅ Muhinfo-Eintrag aktualisiert: **{entry['name']}**\n"
                f"Neuer Zeitplan: {_format_schedule(entry)} (Berlin-Zeit)\n"
                f"Channel: <#{entry['channel_id']}>",
                ephemeral=True,
            )
            return

        if op == "remove":
            if not name:
                await interaction.response.send_message("⚠️ Für `remove` bitte den Eintragsnamen angeben.", ephemeral=True)
                return
            remaining = [entry for entry in entries if _normalize_name(entry.get("name", "")) != _normalize_name(name)]
            if len(remaining) == len(entries):
                await interaction.response.send_message("⚠️ Kein Muhinfo-Eintrag mit diesem Namen gefunden.", ephemeral=True)
                return
            await self.config.guild(interaction.guild).muhinfo_entries.set(remaining)
            await interaction.response.send_message(f"🗑️ Muhinfo-Eintrag gelöscht: **{name.strip()}**", ephemeral=True)
            return

        await interaction.response.send_message("⚠️ Unbekannte Aktion.", ephemeral=True)

    async def cog_load(self) -> None:
        guild_obj = discord.Object(id=GUILD_ID)
        with contextlib.suppress(Exception):
            self.bot.tree.remove_command("muhinfo", guild=guild_obj)
        try:
            self.bot.tree.add_command(self.muhinfo, guild=guild_obj)
            with contextlib.suppress(Exception):
                await self.bot.tree.sync(guild=guild_obj)
        except Exception:
            logger.exception("Fehler beim Registrieren des /muhinfo-Befehls.")

    async def cog_unload(self) -> None:
        try:
            self.bot.tree.remove_command("muhinfo", guild=discord.Object(id=GUILD_ID))
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
        now = _berlin_now()
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
