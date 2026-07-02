from __future__ import annotations

import contextlib
import datetime as dt
import logging
from typing import Any, Dict, List, Optional, Sequence

from zoneinfo import ZoneInfo
import discord  # pyright: ignore[reportMissingImports]
from discord import app_commands
from discord.ext import tasks
from redbot.core import commands, Config  # pyright: ignore[reportMissingImports]
from redbot.core.bot import Red  # pyright: ignore[reportMissingImports]

GUILD_ID = 1198649628787212458
ADMIN_ROLE_ID = 1198650646786736240
OFFICIER_ROLE_ID = 1198652039312453723

DEFAULT_GUILD = {
    "standard_days": [],
    "boss_days": [],
    "start_time": "12:00",
    "repost_interval_minutes": 120,
    "participant_allowed_roles": [],
    "participant_allowed_members": [],
    "status_allowed_roles": [],
    "status_allowed_members": [],
    "session_active": False,
    "session_date": None,
    "session_channel_id": None,
    "session_started_by": None,
    "session_auto_started": False,
    "message_ids": [],
    "latest_message_id": None,
    "anmeldung_erfolgt": False,
    "platoon_erstellt": False,
    "captains": [],
    "sailors": [],
    "own_ships": [],
    "last_post_at": None,
    "next_post_at": None,
}

WEEKDAY_LABELS = {
    "mo": "Montag",
    "di": "Dienstag",
    "mi": "Mittwoch",
    "do": "Donnerstag",
    "fr": "Freitag",
    "sa": "Samstag",
    "so": "Sonntag",
}

DAY_ALIASES = {
    "montag": "mo",
    "monday": "mo",
    "mo": "mo",
    "dienstag": "di",
    "di": "di",
    "tuesday": "di",
    "mittwoch": "mi",
    "mi": "mi",
    "wednesday": "mi",
    "donnerstag": "do",
    "do": "do",
    "thursday": "do",
    "freitag": "fr",
    "fr": "fr",
    "friday": "fr",
    "samstag": "sa",
    "sa": "sa",
    "saturday": "sa",
    "sonntag": "so",
    "so": "so",
    "sunday": "so",
}

BERLIN_TZ = ZoneInfo("Europe/Berlin")
logger = logging.getLogger("red.kuhmuh.blaues_schlachtfeld")


def _normalize_day_token(token: str) -> Optional[str]:
    normalized = token.strip().lower()
    return DAY_ALIASES.get(normalized)


def _normalize_day_list(value: str) -> List[str]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    days: List[str] = []
    for part in parts:
        code = _normalize_day_token(part)
        if code and code not in days:
            days.append(code)
    return days


def _format_day_list(days: Sequence[str]) -> str:
    if not days:
        return "(keine)"
    return ", ".join(WEEKDAY_LABELS.get(day, day) for day in days)


def _parse_clock(value: str) -> Optional[str]:
    raw = str(value or "").strip()
    parts = raw.replace(".", ":").split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def _parse_positive_int(value: Any) -> Optional[int]:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    if result <= 0:
        return None
    return result


def _berlin_now() -> dt.datetime:
    return dt.datetime.now(tz=BERLIN_TZ)


def _berlin_date_string(dt_value: dt.datetime) -> str:
    return dt_value.date().isoformat()


def _to_utc_iso(dt_value: dt.datetime) -> str:
    return dt_value.astimezone(dt.timezone.utc).isoformat()


def _from_iso(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_bool(value: bool) -> str:
    return "✅ Ja" if value else "❌ Nein"


class BlauesSchlachtfeldView(discord.ui.View):
    def __init__(self, cog: "BlauesSchlachtfeldCog") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    async def _update_state_and_embed(self, interaction: discord.Interaction, update_func) -> None:
        guild = interaction.guild
        if not guild or not interaction.user:
            await interaction.response.send_message("⚠️ Nur auf dem Server nutzbar.", ephemeral=True)
            return
        updated = await update_func(interaction)
        if updated is False:
            return
        await self.cog._refresh_session_embed(guild)

    async def _button_permission_check(self, interaction: discord.Interaction, allowed_roles_key: str, allowed_members_key: str) -> bool:
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            await interaction.response.send_message("⚠️ Nur auf dem Server nutzbar.", ephemeral=True)
            return False
        user = interaction.user
        if await self.cog._is_admin_or_officer(user):
            return True
        guild_config = self.cog.config.guild(interaction.guild)
        allowed_roles = await getattr(guild_config, allowed_roles_key)() or []
        allowed_members = await getattr(guild_config, allowed_members_key)() or []
        if any(role.id in allowed_roles for role in user.roles):
            return True
        if user.id in allowed_members:
            return True
        await interaction.response.send_message("❌ Du hast hierfür keine Berechtigung.", ephemeral=True)
        return False

    @discord.ui.button(label="Anmeldung erfolgt", style=discord.ButtonStyle.secondary, custom_id="bf_status_anmeldung", row=1)
    async def anmeldung_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        async def update(interaction: discord.Interaction) -> bool:
            if not await self._button_permission_check(interaction, "status_allowed_roles", "status_allowed_members"):
                return False
            guild_config = self.cog.config.guild(interaction.guild)
            current = await guild_config.anmeldung_erfolgt()
            await guild_config.anmeldung_erfolgt.set(not current)
            await interaction.response.send_message(
                f"✅ Anmeldung erfolgt auf {'Ein' if not current else 'Aus'} gesetzt.",
                ephemeral=True,
            )
            return True

        await self._update_state_and_embed(interaction, update)

    @discord.ui.button(label="Platoon erstellt", style=discord.ButtonStyle.secondary, custom_id="bf_status_platoon", row=1)
    async def platoon_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        async def update(interaction: discord.Interaction) -> bool:
            if not await self._button_permission_check(interaction, "status_allowed_roles", "status_allowed_members"):
                return False
            guild_config = self.cog.config.guild(interaction.guild)
            current = await guild_config.platoon_erstellt()
            await guild_config.platoon_erstellt.set(not current)
            await interaction.response.send_message(
                f"✅ Platoon erstellt auf {'Ein' if not current else 'Aus'} gesetzt.",
                ephemeral=True,
            )
            return True

        await self._update_state_and_embed(interaction, update)

    @discord.ui.button(label="Kapitän der Galeere", style=discord.ButtonStyle.primary, custom_id="bf_part_captain", row=0)
    async def captain_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._participant_toggle(interaction, "captains")

    @discord.ui.button(label="Matrose", style=discord.ButtonStyle.primary, custom_id="bf_part_sailor", row=0)
    async def sailor_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._participant_toggle(interaction, "sailors")

    @discord.ui.button(label="Eigenes Schiff vorhanden", style=discord.ButtonStyle.primary, custom_id="bf_part_own_ship", row=0)
    async def own_ship_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._participant_toggle(interaction, "own_ships")

    @discord.ui.button(label="Abmelden", style=discord.ButtonStyle.danger, custom_id="bf_part_remove", row=1)
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._button_permission_check(interaction, "participant_allowed_roles", "participant_allowed_members"):
            return
        guild_config = self.cog.config.guild(interaction.guild)
        user_id = interaction.user.id
        await guild_config.captains.set([uid for uid in await guild_config.captains() if uid != user_id])
        await guild_config.sailors.set([uid for uid in await guild_config.sailors() if uid != user_id])
        await guild_config.own_ships.set([uid for uid in await guild_config.own_ships() if uid != user_id])
        await interaction.response.send_message("✅ Du wurdest aus allen Teilnehmer-Kategorien entfernt.", ephemeral=True)
        await self.cog._refresh_session_embed(interaction.guild)

    async def _participant_toggle(self, interaction: discord.Interaction, key: str) -> None:
        if not await self._button_permission_check(interaction, "participant_allowed_roles", "participant_allowed_members"):
            return
        guild_config = self.cog.config.guild(interaction.guild)
        user_id = interaction.user.id
        current = await getattr(guild_config, key)()
        if user_id in current:
            current = [uid for uid in current if uid != user_id]
            action = "entfernt"
        else:
            current.append(user_id)
            action = "hinzugefügt"
        await getattr(guild_config, key).set(current)
        await interaction.response.send_message(f"✅ Du wurdest '{key}' {action}.", ephemeral=True)
        await self.cog._refresh_session_embed(interaction.guild)


class BlauesSchlachtfeldCog(commands.Cog):
    blaues_group = app_commands.Group(
        name="blaues",
        description="Blaues Schlachtfeld Aktionen.",
        guild_ids=[GUILD_ID],
    )

    bf_group = app_commands.Group(
        name="bf",
        description="Blaues Schlachtfeld Admin-Konfiguration.",
        guild_ids=[GUILD_ID],
    )

    config_group = app_commands.Group(
        name="config",
        description="Konfiguration des Blauen Schlachtfeldes.",
        parent=bf_group,
    )

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0x0B1C2D3E, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)
        self._view = BlauesSchlachtfeldView(self)
        with contextlib.suppress(Exception):
            self.bot.add_view(self._view)
        self._scheduler_loop.start()
        self._startup_task = self.bot.loop.create_task(self._startup_guild_sync())

    async def cog_load(self) -> None:
        guild_obj = discord.Object(id=GUILD_ID)
        with contextlib.suppress(Exception):
            self.bot.tree.remove_command("blaues", guild=guild_obj)
            self.bot.tree.remove_command("bf", guild=guild_obj)
        with contextlib.suppress(Exception):
            self.bot.tree.add_command(self.blaues_group, guild=guild_obj)
            self.bot.tree.add_command(self.bf_group, guild=guild_obj)

    async def cog_unload(self) -> None:
        self._scheduler_loop.cancel()
        self._startup_task.cancel()
        guild_obj = discord.Object(id=GUILD_ID)
        with contextlib.suppress(Exception):
            self.bot.tree.remove_command("blaues", guild=guild_obj)
            self.bot.tree.remove_command("bf", guild=guild_obj)

    async def _startup_guild_sync(self) -> None:
        try:
            await self.bot.wait_until_red_ready()
            await self.bot.wait_until_ready()
            guild_obj = discord.Object(id=GUILD_ID)
            await self.bot.tree.sync(guild=guild_obj)
            await self._restore_session_state()
        except Exception:
            pass

    async def _restore_session_state(self) -> None:
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return
        async with self.config.guild(guild).all() as data:
            if not data.get("session_active"):
                return
            today = _berlin_date_string(_berlin_now())
            session_date = data.get("session_date")
            if session_date != today:
                await self._reset_session(guild)

    def _active_session_for_today(self, guild: discord.Guild, data: Dict[str, Any]) -> bool:
        if not data.get("session_active"):
            return False
        session_date = data.get("session_date")
        return session_date == _berlin_date_string(_berlin_now())

    def _create_embed(self, guild: discord.Guild, data: Dict[str, Any]) -> discord.Embed:
        event_note = "" if not data.get("session_active") else ""
        boss_today = self._is_boss_today(data)
        if boss_today:
            event_note = "⚠️ Boss-Tag: Zur gleichen Zeit laufen mögliche Gildenbosse."

        participants = self._unique_participant_count(data)
        overflow = participants - 20
        participant_text = f"{participants} / 20"
        if overflow > 0:
            participant_text += f" (+{overflow})"

        next_post = _from_iso(data.get('next_post_at'))
        next_post_text = "–"
        if next_post is not None:
            next_post_text = next_post.astimezone(BERLIN_TZ).strftime("%d.%m.%Y %H:%M %Z")

        embed = discord.Embed(
            title="Blaues Schlachtfeld",
            description=(
                "**Uhrzeit:** 20:00 – 21:00 Uhr\n"
                "**Server:** Odylita-1\n"
                f"**Teilnehmer:** {participant_text}\n"
                f"**Anmeldung erfolgt:** {_format_bool(data.get('anmeldung_erfolgt', False))}\n"
                f"**Platoon erstellt:** {_format_bool(data.get('platoon_erstellt', False))}\n"
                f"**Nächster Auto-Post:** {next_post_text}"
            ),
            color=discord.Color.blue(),
        )
        if event_note:
            embed.add_field(name="Hinweis", value=event_note, inline=False)

        def mention_block(key: str, title: str) -> str:
            ids = data.get(key, []) or []
            if not ids:
                return "– aktuell niemand –"
            parts: List[str] = []
            for user_id in ids:
                member = guild.get_member(user_id)
                if member:
                    parts.append(member.mention)
                else:
                    parts.append(f"<@{user_id}>")
            return "\n".join(parts)

        embed.add_field(name="Kapitän der Galeere", value=mention_block("captains", "Kapitän der Galeere"), inline=False)
        embed.add_field(name="Matrosen / Gildengaleere", value=mention_block("sailors", "Matrosen"), inline=False)
        embed.add_field(name="Eigenes Schiff vorhanden / Jäger mit eigenen Schiffen", value=mention_block("own_ships", "Eigenes Schiff vorhanden"), inline=False)
        embed.set_footer(text="Blaues Schlachtfeld Reminder")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def _refresh_session_embed(self, guild: discord.Guild) -> None:
        data = await self.config.guild(guild).all()
        if not self._active_session_for_today(guild, data):
            return
        message_id = data.get("latest_message_id")
        channel_id = data.get("session_channel_id")
        if not message_id or not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return
        try:
            message = await channel.fetch_message(message_id)
        except Exception:
            return
        embed = self._create_embed(guild, data)
        with contextlib.suppress(Exception):
            await message.edit(embed=embed)

    def _is_boss_today(self, data: Dict[str, Any]) -> bool:
        today = _berlin_date_string(_berlin_now())
        weekday = self._current_weekday_code()
        return weekday in (data.get("boss_days") or [])

    def _current_weekday_code(self) -> str:
        weekdays = ["mo", "di", "mi", "do", "fr", "sa", "so"]
        return weekdays[_berlin_now().weekday()]

    def _unique_participant_count(self, data: Dict[str, Any]) -> int:
        ids = set((data.get("captains") or []) + (data.get("sailors") or []) + (data.get("own_ships") or []))
        return len(ids)

    async def _post_reminder(self, guild: discord.Guild, channel: discord.TextChannel, *, auto_started: bool, started_by: Optional[int] = None) -> None:
        async with self.config.guild(guild).all() as data:
            if not data.get("session_active"):
                data["session_active"] = True
                data["session_date"] = _berlin_date_string(_berlin_now())
                data["session_channel_id"] = channel.id
                data["session_auto_started"] = auto_started
                data["session_started_by"] = started_by if not auto_started else None
                data["message_ids"] = data.get("message_ids") or []

            latest_id = data.get("latest_message_id")
            if latest_id:
                old_channel = guild.get_channel(data.get("session_channel_id") or 0)
                if isinstance(old_channel, discord.TextChannel):
                    with contextlib.suppress(Exception):
                        old_msg = await old_channel.fetch_message(latest_id)
                        await old_msg.delete()

            data["latest_message_id"] = None
            data["last_post_at"] = _to_utc_iso(dt.datetime.now(tz=dt.timezone.utc))
            interval = data.get("repost_interval_minutes") or 120
            next_post = _berlin_now() + dt.timedelta(minutes=int(interval))
            data["next_post_at"] = _to_utc_iso(next_post)

            embed = self._create_embed(guild, data)
            message = await channel.send(
                embed=embed,
                view=self._view,
            )
            logger.debug("Blaues Schlachtfeld Reminder gepostet: message=%s channel=%s", message.id, channel.id)
            data["message_ids"].append(message.id)
            data["latest_message_id"] = message.id

    async def _session_cleanup(self, guild: discord.Guild) -> None:
        data = await self.config.guild(guild).all()
        if not data.get("session_active"):
            return
        channel_id = data.get("session_channel_id")
        message_ids = list(data.get("message_ids") or [])
        if channel_id:
            channel = guild.get_channel(channel_id)
            if isinstance(channel, discord.abc.Messageable):
                for message_id in message_ids:
                    with contextlib.suppress(Exception):
                        message = await channel.fetch_message(message_id)
                        await message.delete()
        await self._reset_session(guild)

    async def _restore_session_message(self, guild: discord.Guild, channel: discord.TextChannel) -> None:
        data = await self.config.guild(guild).all()
        if not data.get("session_active"):
            return
        embed = self._create_embed(guild, data)
        message = await channel.send(
            content="Blaues Schlachtfeld Reminder",
            embed=embed,
            view=self._view,
        )
        logger.warning("Blaues Schlachtfeld Reminder wurde wiederhergestellt: message=%s channel=%s", message.id, channel.id)
        data["message_ids"].append(message.id)
        data["latest_message_id"] = message.id

    async def _reset_session(self, guild: discord.Guild) -> None:
        data = await self.config.guild(guild).all()
        await self.config.guild(guild).set({
            "standard_days": data.get("standard_days", []),
            "boss_days": data.get("boss_days", []),
            "start_time": data.get("start_time", "12:00"),
            "repost_interval_minutes": data.get("repost_interval_minutes", 120),
            "participant_allowed_roles": data.get("participant_allowed_roles", []),
            "participant_allowed_members": data.get("participant_allowed_members", []),
            "status_allowed_roles": data.get("status_allowed_roles", []),
            "status_allowed_members": data.get("status_allowed_members", []),
            "session_active": False,
            "session_date": None,
            "session_channel_id": None,
            "session_started_by": None,
            "session_auto_started": False,
            "message_ids": [],
            "latest_message_id": None,
            "anmeldung_erfolgt": False,
            "platoon_erstellt": False,
            "captains": [],
            "sailors": [],
            "own_ships": [],
            "last_post_at": None,
            "next_post_at": None,
        })

    async def _start_session(self, interaction: discord.Interaction, manual: bool) -> bool:
        guild = interaction.guild
        channel = interaction.channel
        if not guild or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("⚠️ Dieser Command muss in einem Text-Channel ausgeführt werden.", ephemeral=True)
            return False
        if self._current_weekday_code() == "sa":
            await interaction.response.send_message("⚠️ Samstag ist ausgeschlossen. Start blockiert.", ephemeral=True)
            return False
        data = await self.config.guild(guild).all()
        if not await self._participant_allowed(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Berechtigung, das Event zu starten.", ephemeral=True)
            return False
        if self._active_session_for_today(guild, data):
            await self._post_reminder(guild, channel, auto_started=False, started_by=interaction.user.id)
            await interaction.response.send_message("✅ Session ist aktiv; Reminder wurde erneut gepostet.", ephemeral=True)
            return True
        if not self._day_is_allowed(data):
            await interaction.response.send_message(
                "⚠️ Heute ist kein konfigurierter Standard- oder Boss-Tag. Keine automatische Session möglich.",
                ephemeral=True,
            )
            return False
        await self._post_reminder(guild, channel, auto_started=not manual, started_by=interaction.user.id)
        await interaction.response.send_message(
            "✅ Blaues Schlachtfeld gestartet und Reminder gepostet.", ephemeral=True,
        )
        return True

    def _day_is_allowed(self, data: Dict[str, Any]) -> bool:
        weekday = self._current_weekday_code()
        return weekday in (data.get("standard_days") or []) or weekday in (data.get("boss_days") or [])

    async def _check_scheduler(self) -> None:
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return
        data = await self.config.guild(guild).all()
        now = _berlin_now()
        weekday = self._current_weekday_code()
        if data.get("session_active") and data.get("session_date") == _berlin_date_string(now):
            next_post_at = _from_iso(data.get("next_post_at"))
            if next_post_at and now.astimezone(dt.timezone.utc) >= next_post_at.astimezone(dt.timezone.utc):
                channel = guild.get_channel(data.get("session_channel_id") or 0)
                if isinstance(channel, discord.TextChannel):
                    await self._post_reminder(guild, channel, auto_started=False)
                    return
            latest_id = data.get("latest_message_id")
            channel = guild.get_channel(data.get("session_channel_id") or 0)
            message_missing = False
            if isinstance(channel, discord.TextChannel) and latest_id:
                try:
                    await channel.fetch_message(latest_id)
                except Exception:
                    message_missing = True
            if not latest_id or not isinstance(channel, discord.TextChannel) or message_missing:
                default = self._find_default_channel(guild)
                if default:
                    await self._restore_session_message(guild, default)
                    return
        if not data.get("session_active") and weekday in (data.get("standard_days") or []):
            start_time = _parse_clock(data.get("start_time") or "12:00")
            if start_time:
                start_ts = self._today_time(now, start_time)
                if start_ts <= now < (start_ts + dt.timedelta(minutes=1)):
                    channel = self._find_default_channel(guild)
                    if channel:
                        await self._post_reminder(guild, channel, auto_started=True)

    def _today_time(self, now: dt.datetime, clock: str) -> dt.datetime:
        hour, minute = map(int, clock.split(":"))
        return dt.datetime(year=now.year, month=now.month, day=now.day, hour=hour, minute=minute, tzinfo=BERLIN_TZ)

    def _find_default_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                return channel
        return None

    @tasks.loop(seconds=60.0)
    async def _scheduler_loop(self) -> None:
        await self._check_scheduler()

    @_scheduler_loop.before_loop
    async def before_scheduler_loop(self) -> None:
        await self.bot.wait_until_red_ready()
        await self.bot.wait_until_ready()

    async def _is_admin_or_officer(self, member: discord.Member) -> bool:
        if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
            return True
        if ADMIN_ROLE_ID:
            role = member.guild.get_role(ADMIN_ROLE_ID)
            if role in member.roles:
                return True
        if OFFICIER_ROLE_ID:
            role = member.guild.get_role(OFFICIER_ROLE_ID)
            if role in member.roles:
                return True
        return False

    async def _participant_allowed(self, member: discord.Member) -> bool:
        if await self._is_admin_or_officer(member):
            return True
        guild_config = self.config.guild(member.guild)
        allowed_roles = await guild_config.participant_allowed_roles() or []
        allowed_members = await guild_config.participant_allowed_members() or []
        if any(role.id in allowed_roles for role in member.roles):
            return True
        if member.id in allowed_members:
            return True
        return False

    async def _require_admin(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Dieser Command ist nur innerhalb der Guild verfügbar.", ephemeral=True)
            return False
        if interaction.guild.id != GUILD_ID:
            await interaction.response.send_message("❌ Dieser Command ist nur in der Ziel-Guild verfügbar.", ephemeral=True)
            return False
        if await self._is_admin_or_officer(interaction.user):
            return True
        await interaction.response.send_message("❌ Du hast keine Admin-Berechtigung.", ephemeral=True)
        return False

    @blaues_group.command(name="schlachtfeld", description="Starte oder reposte das Blaue Schlachtfeld Event.")
    async def start_blaues_schlachtfeld(self, interaction: discord.Interaction) -> None:
        if not await self._start_session(interaction, manual=True):
            return

    @config_group.command(name="standardtage", description="Standardtage anzeigen oder setzen.")
    async def config_standardtage(self, interaction: discord.Interaction, days: Optional[str] = None) -> None:
        if not await self._require_admin(interaction):
            return
        guild_config = self.config.guild(interaction.guild)
        if not days:
            current = await guild_config.standard_days()
            await interaction.response.send_message(f"**Standardtage:** {_format_day_list(current)}", ephemeral=True)
            return
        normalized = _normalize_day_list(days)
        await guild_config.standard_days.set(normalized)
        await interaction.response.send_message(f"✅ Standardtage gesetzt auf: {_format_day_list(normalized)}", ephemeral=True)

    @config_group.command(name="bosstage", description="Boss-Tage anzeigen oder setzen.")
    async def config_bosstage(self, interaction: discord.Interaction, days: Optional[str] = None) -> None:
        if not await self._require_admin(interaction):
            return
        guild_config = self.config.guild(interaction.guild)
        if not days:
            current = await guild_config.boss_days()
            await interaction.response.send_message(f"**Boss-Tage:** {_format_day_list(current)}", ephemeral=True)
            return
        normalized = _normalize_day_list(days)
        await guild_config.boss_days.set(normalized)
        await interaction.response.send_message(f"✅ Boss-Tage gesetzt auf: {_format_day_list(normalized)}", ephemeral=True)

    @config_group.command(name="startzeit", description="Startzeit im Europe/Berlin-Format anzeigen oder setzen.")
    async def config_startzeit(self, interaction: discord.Interaction, time: Optional[str] = None) -> None:
        if not await self._require_admin(interaction):
            return
        guild_config = self.config.guild(interaction.guild)
        if not time:
            current = await guild_config.start_time()
            await interaction.response.send_message(f"**Startzeit:** {current}", ephemeral=True)
            return
        normalized = _parse_clock(time)
        if not normalized:
            await interaction.response.send_message("⚠️ Ungültiges Zeitformat. Bitte HH:MM verwenden.", ephemeral=True)
            return
        await guild_config.start_time.set(normalized)
        await interaction.response.send_message(f"✅ Startzeit gesetzt auf {normalized} (Europe/Berlin)", ephemeral=True)

    @config_group.command(name="repost_intervall", description="Neu-Post-Intervall anzeigen oder setzen.")
    async def config_repost_interval(self, interaction: discord.Interaction, minutes: Optional[int] = None) -> None:
        if not await self._require_admin(interaction):
            return
        guild_config = self.config.guild(interaction.guild)
        if minutes is None:
            current = await guild_config.repost_interval_minutes()
            await interaction.response.send_message(f"**Neu-Post-Intervall:** {current} Minuten", ephemeral=True)
            return
        normalized = _parse_positive_int(minutes)
        if normalized is None:
            await interaction.response.send_message("⚠️ Bitte eine positive ganze Zahl eingeben.", ephemeral=True)
            return
        await guild_config.repost_interval_minutes.set(normalized)
        await interaction.response.send_message(f"✅ Neu-Post-Intervall gesetzt auf {normalized} Minuten", ephemeral=True)

    @config_group.command(name="participant_role", description="Teilnehmer-Rollen hinzufügen/entfernen/anzeigen.")
    @app_commands.choices(action=[
        app_commands.Choice(name="anzeigen", value="show"),
        app_commands.Choice(name="hinzufügen", value="add"),
        app_commands.Choice(name="entfernen", value="remove"),
    ])
    async def config_participant_role(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        role: Optional[discord.Role] = None,
    ) -> None:
        if not await self._require_admin(interaction):
            return
        guild_config = self.config.guild(interaction.guild)
        current = await guild_config.participant_allowed_roles()
        if action.value == "show":
            mentions = [f"<@&{role_id}>" for role_id in current]
            await interaction.response.send_message(f"**Teilnehmer-Rollen:** {', '.join(mentions) if mentions else '(keine)'}", ephemeral=True)
            return
        if not role:
            await interaction.response.send_message("⚠️ Bitte eine Rolle angeben.", ephemeral=True)
            return
        if action.value == "add":
            if role.id in current:
                await interaction.response.send_message("⚠️ Rolle ist bereits erlaubt.", ephemeral=True)
                return
            current.append(role.id)
            await guild_config.participant_allowed_roles.set(current)
            await interaction.response.send_message(f"✅ Rolle {role.mention} als Teilnehmer erlaubt.", ephemeral=True)
            return
        if action.value == "remove":
            if role.id not in current:
                await interaction.response.send_message("⚠️ Rolle war nicht hinterlegt.", ephemeral=True)
                return
            current.remove(role.id)
            await guild_config.participant_allowed_roles.set(current)
            await interaction.response.send_message(f"✅ Rolle {role.mention} entfernt.", ephemeral=True)
            return

    @config_group.command(name="participant_member", description="Teilnehmer-Member hinzufügen/entfernen/anzeigen.")
    @app_commands.choices(action=[
        app_commands.Choice(name="anzeigen", value="show"),
        app_commands.Choice(name="hinzufügen", value="add"),
        app_commands.Choice(name="entfernen", value="remove"),
    ])
    async def config_participant_member(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        member: Optional[discord.Member] = None,
    ) -> None:
        if not await self._require_admin(interaction):
            return
        guild_config = self.config.guild(interaction.guild)
        current = await guild_config.participant_allowed_members()
        if action.value == "show":
            mentions = [f"<@{member_id}>" for member_id in current]
            await interaction.response.send_message(f"**Teilnehmer-Member:** {', '.join(mentions) if mentions else '(keine)'}", ephemeral=True)
            return
        if not member:
            await interaction.response.send_message("⚠️ Bitte ein Member angeben.", ephemeral=True)
            return
        if action.value == "add":
            if member.id in current:
                await interaction.response.send_message("⚠️ Member ist bereits erlaubt.", ephemeral=True)
                return
            current.append(member.id)
            await guild_config.participant_allowed_members.set(current)
            await interaction.response.send_message(f"✅ Member {member.mention} als Teilnehmer erlaubt.", ephemeral=True)
            return
        if action.value == "remove":
            if member.id not in current:
                await interaction.response.send_message("⚠️ Member war nicht hinterlegt.", ephemeral=True)
                return
            current.remove(member.id)
            await guild_config.participant_allowed_members.set(current)
            await interaction.response.send_message(f"✅ Member {member.mention} entfernt.", ephemeral=True)
            return

    @config_group.command(name="status_role", description="Status-/Orga-Rollen hinzufügen/entfernen/anzeigen.")
    @app_commands.choices(action=[
        app_commands.Choice(name="anzeigen", value="show"),
        app_commands.Choice(name="hinzufügen", value="add"),
        app_commands.Choice(name="entfernen", value="remove"),
    ])
    async def config_status_role(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        role: Optional[discord.Role] = None,
    ) -> None:
        if not await self._require_admin(interaction):
            return
        guild_config = self.config.guild(interaction.guild)
        current = await guild_config.status_allowed_roles()
        if action.value == "show":
            mentions = [f"<@&{role_id}>" for role_id in current]
            await interaction.response.send_message(f"**Status-Rollen:** {', '.join(mentions) if mentions else '(keine)'}", ephemeral=True)
            return
        if not role:
            await interaction.response.send_message("⚠️ Bitte eine Rolle angeben.", ephemeral=True)
            return
        if action.value == "add":
            if role.id in current:
                await interaction.response.send_message("⚠️ Rolle ist bereits erlaubt.", ephemeral=True)
                return
            current.append(role.id)
            await guild_config.status_allowed_roles.set(current)
            await interaction.response.send_message(f"✅ Rolle {role.mention} als Status/Orga erlaubt.", ephemeral=True)
            return
        if action.value == "remove":
            if role.id not in current:
                await interaction.response.send_message("⚠️ Rolle war nicht hinterlegt.", ephemeral=True)
                return
            current.remove(role.id)
            await guild_config.status_allowed_roles.set(current)
            await interaction.response.send_message(f"✅ Rolle {role.mention} entfernt.", ephemeral=True)
            return

    @config_group.command(name="status_member", description="Status-/Orga-Member hinzufügen/entfernen/anzeigen.")
    @app_commands.choices(action=[
        app_commands.Choice(name="anzeigen", value="show"),
        app_commands.Choice(name="hinzufügen", value="add"),
        app_commands.Choice(name="entfernen", value="remove"),
    ])
    async def config_status_member(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        member: Optional[discord.Member] = None,
    ) -> None:
        if not await self._require_admin(interaction):
            return
        guild_config = self.config.guild(interaction.guild)
        current = await guild_config.status_allowed_members()
        if action.value == "show":
            mentions = [f"<@{member_id}>" for member_id in current]
            await interaction.response.send_message(f"**Status-Member:** {', '.join(mentions) if mentions else '(keine)'}", ephemeral=True)
            return
        if not member:
            await interaction.response.send_message("⚠️ Bitte ein Member angeben.", ephemeral=True)
            return
        if action.value == "add":
            if member.id in current:
                await interaction.response.send_message("⚠️ Member ist bereits erlaubt.", ephemeral=True)
                return
            current.append(member.id)
            await guild_config.status_allowed_members.set(current)
            await interaction.response.send_message(f"✅ Member {member.mention} als Status/Orga erlaubt.", ephemeral=True)
            return
        if action.value == "remove":
            if member.id not in current:
                await interaction.response.send_message("⚠️ Member war nicht hinterlegt.", ephemeral=True)
                return
            current.remove(member.id)
            await guild_config.status_allowed_members.set(current)
            await interaction.response.send_message(f"✅ Member {member.mention} entfernt.", ephemeral=True)
            return

    @config_group.command(name="session", description="Aktive Session anzeigen.")
    async def config_session(self, interaction: discord.Interaction) -> None:
        if not await self._require_admin(interaction):
            return
        data = await self.config.guild(interaction.guild).all()
        if not data.get("session_active"):
            await interaction.response.send_message("ℹ️ Es gibt aktuell keine aktive Session.", ephemeral=True)
            return
        session_date = data.get("session_date")
        started_by = data.get("session_started_by")
        auto_started = data.get("session_auto_started")
        await interaction.response.send_message(
            "**Aktive Session**\n"
            f"Datum: {session_date}\n"
            f"Auto gestartet: {_format_bool(auto_started)}\n"
            f"Gestartet von: {f'<@{started_by}>' if started_by else 'System'}\n"
            f"Nachrichten: {len(data.get('message_ids') or [])}\n"
            f"Anmeldung erfolgt: {_format_bool(data.get('anmeldung_erfolgt', False))}\n"
            f"Platoon erstellt: {_format_bool(data.get('platoon_erstellt', False))}",
            ephemeral=True,
        )

    @config_group.command(name="stop", description="Aktive Session stoppen und Cleanup ausführen.")
    async def config_stop(self, interaction: discord.Interaction) -> None:
        if not await self._require_admin(interaction):
            return
        await self._session_cleanup(interaction.guild)
        await interaction.response.send_message("✅ Die aktive Session wurde gestoppt und aufgeräumt.", ephemeral=True)
