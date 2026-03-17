from __future__ import annotations

import datetime as dt
import re
from typing import Dict, List, Optional, Tuple
import asyncio
import hashlib
import json
import logging


import discord
from discord.ext import tasks
from redbot.core import commands, Config
from discord import app_commands

log = logging.getLogger("red.kuhmuh.dashboard")

# =========================
# FIX: Nur fuer eure Guild
# =========================
GUILD_ID = 1198649628787212458

# Eigene Dashboard-Config (separat)
DASHBOARD_CONFIG_IDENTIFIER = 935771234124

# Update-Intervall
DASHBOARD_REFRESH_MINUTES = 1

# Emojis
MUHKUH_EMOJI = "<:muhkuh:1207038544510586890>"
PILAFE_EMOJI = "<:pilafe:1450051653297504368>"
MIRUMOK_EMOJI = "<:Mirumok:1461101498954940428>"
GYFIN_EMOJI = "<:Gyfin:1461102103266066502>"
OLUN_EMOJI = "<:olun:1471826612394655857>"
EDANIA_EMOJI = "<:edania:1483216698625753088>"
CHEER_EMOJI = "<:blackspiritcheer:1199730129476268183>"

AKVK_NORMAL = "301/385"
AKVK_SCHWER = "330/401"

WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# =========================
# DM Opt-Out Rollen (Reverse)
# =========================
ROLE_NO_DM_ID_LIVE = 1466752408779751509  # Gruppensuche DM-Funktion (Live)
ROLE_NO_DM_ID_TEST = 1466761625158684817  # Gruppensuche DM-Funktion TEST

# =========================
# Rechte (optional: wenn du per Rolle prüfen willst)
# =========================
ADMIN_ROLE_ID: Optional[int] = 1452050940952838214
OFFIZIER_ROLE_ID: Optional[int] = 1198652039312453723


def _now_local() -> dt.datetime:
    return dt.datetime.now()


def _format_day(d: dt.date) -> str:
    wd = WEEKDAYS_DE[d.weekday()]
    return f"{wd}, {d.day:02d}.{d.month:02d}."


def _spot_name(key: str) -> str:
    if key == "mirumok":
        return "Mirumok"
    if key == "gyfin":
        return "Gyfin"
    if key == "olun":
        return "Olun"
    return key


def _default_req_for(data: dict) -> str:
    cat = data.get("category")
    if cat == "muhhelfer":
        diff = data.get("difficulty", "normal")
        return AKVK_SCHWER if diff == "schwer" else AKVK_NORMAL
    if cat == "spots":
        spot = data.get("spot_key", "")
        if spot == "mirumok":
            return "350/427"
        if spot == "gyfin":
            return "370/440"
        if spot == "edania":
            return "385/450"
        return ""
    return ""


def _norm_spot_key(val: object) -> str:
    return str(val or "").strip().lower()


def _jump_url(guild_id: int, channel_id: int, message_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"


def _extract_time_sort_key(start_text: str) -> Tuple[int, int]:
    """
    Sortiert fixe Uhrzeiten vor "jetzt/spaeter/nach absprache".
    Wenn keine Uhrzeit erkannt wird => (99, 99)
    """
    t = (start_text or "").strip().lower()

    # 20:30
    m = re.search(r"\b([01]?\d|2[0-3])[:.]\s*([0-5]\d)\b", t)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    # 20 uhr / 20uhr / 20
    m = re.search(r"\b([01]?\d|2[0-3])\s*(uhr)?\b", t)
    if m:
        return (int(m.group(1)), 0)

    return (99, 99)


def _fmt_day(day_iso: str) -> str:
    """
    Kompat: wird vom Dashboard genutzt.
    Erwartet ISO-String (YYYY-MM-DD) und gibt formatierten Tag zurück.
    """
    day_iso = str(day_iso or "").strip()
    if not day_iso:
        return "—"
    try:
        day_d = dt.date.fromisoformat(day_iso)
        # Nutze vorhandene Formatierung, falls vorhanden
        try:
            return _format_day(day_d)  # type: ignore[name-defined]
        except Exception:
            # Fallback, falls _format_day nicht existiert
            return day_d.strftime("%a, %d.%m.")
    except Exception:
        return day_iso


def _jump_link(d: dict) -> str:
    """
    Kompat: wird vom Dashboard genutzt.
    Baut einen Jump-Link zur Nachricht.
    Erwartet mindestens channel_id + message_id (guild_id optional).
    """
    guild_id = int(d.get("guild_id") or 0)
    channel_id = int(d.get("channel_id") or 0)
    message_id = int(d.get("message_id") or 0)

    if not channel_id or not message_id:
        return "—"

    # Wenn _jump_url existiert -> verwenden
    try:
        # type: ignore[name-defined]
        return _jump_url(guild_id, channel_id, message_id)
    except Exception:
        # Fallback: klassischer Jump-URL
        if not guild_id:
            return "—"
        return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"


def _has_role(member: discord.Member, role_id: Optional[int]) -> bool:
    if not role_id:
        return False
    return any(r.id == int(role_id) for r in getattr(member, "roles", []))


def _can_post_dashboard(member: discord.Member) -> bool:
    # Posten nur Admin
    return _has_role(member, ADMIN_ROLE_ID)


def _can_refresh_dashboard(member: discord.Member) -> bool:
    # Refresh Admin + Offizier
    return _has_role(member, ADMIN_ROLE_ID) or _has_role(member, OFFIZIER_ROLE_ID)


def _spot_emoji(spot_key: str, *, olun_tier: str = "") -> str:
    sk = str(spot_key or "").strip().lower()
    tier = str(olun_tier or "").strip().lower()

    if sk == "mirumok":
        return MIRUMOK_EMOJI
    if sk == "gyfin":
        return GYFIN_EMOJI
    if sk == "olun":
        return OLUN_EMOJI
    if sk == "edania":
        return EDANIA_EMOJI

    return CHEER_EMOJI


def _normalize_atoraxxion_runs(data: dict) -> List[str]:
    """
    Liefert eine normalisierte Liste der gewählten Atoraxxion-Dungeons.
    Erwartet 'atoraxxion_runs' als Liste (neu) oder 'atoraxxion_run' als String (alt).
    Ergebnis-Keys: vahmalkea, sycrakea, yolunakea, orzekea
    """
    # Neu: Liste
    raw = data.get("atoraxxion_runs")

    runs: List[str] = []
    if isinstance(raw, list):
        runs = [str(x).strip().lower() for x in raw if str(x).strip()]

    # Alt: einzelner String
    if not runs:
        one = data.get("atoraxxion_run")
        if one:
            runs = [str(one).strip().lower()]

    allowed = {"vahmalkea", "sycrakea", "yolunakea", "orzekea"}
    runs = [r for r in runs if r in allowed]

    # Stabil / deterministisch sortieren (UI + Dashboard konsistent)
    order = ["vahmalkea", "sycrakea", "yolunakea", "orzekea"]
    runs.sort(key=lambda x: order.index(x) if x in order else 999)
    return runs


class DMOptButton(discord.ui.Button):
    def __init__(self, which: str):
        super().__init__(
            label="DM Reminders: An/Aus",
            emoji="✉️",
            style=discord.ButtonStyle.secondary,
            custom_id=f"gsdash:dmopt:{which}",
        )
        self.which = which

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return

        member: discord.Member = interaction.user
        role_id = ROLE_NO_DM_ID_LIVE if self.which == "live" else ROLE_NO_DM_ID_TEST
        role = interaction.guild.get_role(int(role_id))
        if not role:
            await interaction.response.send_message("Rolle nicht gefunden.", ephemeral=True)
            return

        try:
            if role in member.roles:
                await member.remove_roles(role, reason="DM Opt-Out deaktiviert (wieder DMs)")
                await interaction.response.send_message("✅ Du bekommst wieder **DM-Reminders**.", ephemeral=True)
            else:
                await member.add_roles(role, reason="DM Opt-Out aktiviert (keine DMs)")
                await interaction.response.send_message("✅ Du bekommst **keine DM-Reminders** mehr.", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ Konnte Rolle nicht ändern (Rechte?).", ephemeral=True)


class DashboardDMView(discord.ui.View):
    def __init__(self, which: str):
        super().__init__(timeout=None)
        self.add_item(DMOptButton(which))


class Gruppenübersicht(commands.Cog):
    """Gruppenübersicht - Dashboard"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Eigene Config fuer Dashboard-Msg/Channel
        self.config = Config.get_conf(
            self, identifier=DASHBOARD_CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            dashboard_live_channel_id=None,
            dashboard_live_message_id=None,
            dashboard_test_channel_id=None,
            dashboard_test_message_id=None,
        )

        # --- Anti-RateLimit Schutz ---
        self._dash_locks: Dict[str, asyncio.Lock] = {
            "live": asyncio.Lock(),
            "test": asyncio.Lock(),
        }
        self._last_sig: Dict[str, Optional[str]] = {
            "live": None,
            "test": None,
        }

    def _log_info(self, category: str, message: str, **fields):
        parts = [f"{k}={v}" for k, v in fields.items()]
        suffix = f" | {' '.join(parts)}" if parts else ""
        log.info(f"[Kuhmuh-Dashboard][{category}] {message}{suffix}")

    def _log_warning(self, category: str, message: str, **fields):
        parts = [f"{k}={v}" for k, v in fields.items()]
        suffix = f" | {' '.join(parts)}" if parts else ""
        log.warning(f"[Kuhmuh-Dashboard][{category}] {message}{suffix}")

    def _log_console(self, level: str, module: str, event: str, **kwargs):
        base = f"[KUHMUH][{module.upper()}][{event.upper()}][{level.upper()}]"
        if kwargs:
            details = " ".join(f"{k}={v}" for k, v in kwargs.items())
            getattr(log, level.lower(), log.info)(f"{base} {details}")
        else:
            getattr(log, level.lower(), log.info)(base)

    async def _log_event(
        self,
        guild: discord.Guild,
        level: str,
        module: str,
        event: str,
        description: str,
        *,
        channel: Optional[discord.TextChannel] = None,
    ):
        self._log_console(level, module, event, guild_id=guild.id)

        ch = guild.get_channel(LOG_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            return

        emoji_map = {
            "info": "ℹ️",
            "warn": "⚠️",
            "error": "❌",
        }
        emoji = emoji_map.get(level.lower(), "ℹ️")

        embed = discord.Embed(
            title=f"{emoji} Kuhmuh System Log",
            description=description + "\n\nTechnische Details siehe Serverkonsole.",
            color=discord.Color.orange() if level.lower() != "error" else discord.Color.red(),
        )

        embed.add_field(name="Modul", value=module, inline=True)
        embed.add_field(name="Event", value=event, inline=True)
        embed.add_field(name="Server", value=guild.name, inline=True)

        if channel:
            embed.add_field(name="Channel", value=channel.mention, inline=True)

        embed.set_footer(text="Kuhmuh Bot • Systemmeldung")

        content = None
        if level.lower() == "error" and DEV_ROLE_ID:
            content = f"<@&{DEV_ROLE_ID}>"

        try:
            await ch.send(
                content=content,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        except Exception:
            pass

    async def force_refresh_all(self, guild_id: int):
        if int(guild_id) != GUILD_ID:
            return
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return
        await self._refresh_dashboard(guild, which="live")
        await self._refresh_dashboard(guild, which="test")

    async def cog_load(self):
        # 1) Persistent Views registrieren
        try:
            self.bot.add_view(DashboardDMView("live"))
            self.bot.add_view(DashboardDMView("test"))
        except Exception:
            pass

        # 2) Commands explizit in den Tree hängen (Red-sicher)
        gobj = discord.Object(id=GUILD_ID)
        try:
            self.bot.tree.add_command(self.dashboard_command, guild=gobj)
        except Exception:
            pass

        # 3) Danach syncen
        try:
            await self.bot.tree.sync(guild=gobj)
        except Exception:
            pass
        if not self._dashboard_refresh_loop.is_running():
            self._dashboard_refresh_loop.start()

    def cog_unload(self):
        # Loop stoppen
        try:
            self._dashboard_refresh_loop.cancel()
        except Exception:
            pass

        # Command entfernen (wichtig bei reload)
        try:
            self.bot.tree.remove_command(
                "dashboard", type=discord.AppCommandType.chat_input)
        except Exception:
            pass

    # =========================
    # Datenquelle: direkt aus Gruppensuche-Cog
    # =========================

    def _get_gruppensuche_cog_live(self):
        # Robust gegen unterschiedliche Cog-Namen (Test/Live/Umbenennung)
        return (
            self.bot.get_cog("Gruppensuche")
            or self.bot.get_cog("GruppensucheTest")
            or self.bot.get_cog("Gruppensuche_test")
        )

    def _get_gruppensuche_cog_test(self):
        # Robust gegen unterschiedliche Cog-Namen (Test/Live/Umbenennung)
        return (
            self.bot.get_cog("Gruppensuche_test")
            or self.bot.get_cog("GruppensucheTest")
            or self.bot.get_cog("Gruppensuche")
        )

    async def _get_searches_from(self, guild: discord.Guild, source: str) -> Dict[str, dict]:
        cog = self._get_gruppensuche_cog_live(
        ) if source == "live" else self._get_gruppensuche_cog_test()
        if not cog:
            return {}
        try:
            data = await cog.config.guild(guild).searches()
            return data or {}
        except Exception:
            return {}

    async def _get_dashboard_target(self, guild: discord.Guild, which: str) -> Tuple[Optional[int], Optional[int]]:
        if which == "live":
            ch_id = await self.config.guild(guild).dashboard_live_channel_id()
            msg_id = await self.config.guild(guild).dashboard_live_message_id()
        else:
            ch_id = await self.config.guild(guild).dashboard_test_channel_id()
            msg_id = await self.config.guild(guild).dashboard_test_message_id()

        try:
            return (int(ch_id) if ch_id else None, int(msg_id) if msg_id else None)
        except Exception:
            return (None, None)

    async def _set_dashboard_target(self, guild: discord.Guild, which: str, channel_id: int, message_id: int):
        if which == "live":
            await self.config.guild(guild).dashboard_live_channel_id.set(int(channel_id))
            await self.config.guild(guild).dashboard_live_message_id.set(int(message_id))
        else:
            await self.config.guild(guild).dashboard_test_channel_id.set(int(channel_id))
            await self.config.guild(guild).dashboard_test_message_id.set(int(message_id))

    async def _clear_dashboard_target(self, guild: discord.Guild, which: str):
        if which == "live":
            await self.config.guild(guild).dashboard_live_channel_id.set(None)
            await self.config.guild(guild).dashboard_live_message_id.set(None)
        else:
            await self.config.guild(guild).dashboard_test_channel_id.set(None)
            await self.config.guild(guild).dashboard_test_message_id.set(None)

    # =========================
    # Slash Command: NUR 1 Command mit Optionen
    # =========================

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="dashboard", description="Dashboard posten/verschieben oder refreshen.")
    @app_commands.choices(
        bereich=[
            app_commands.Choice(name="LIVE", value="live"),
            app_commands.Choice(name="TEST", value="test"),
        ],
        aktion=[
            app_commands.Choice(name="Posten / Verschieben", value="post"),
            app_commands.Choice(name="Refresh", value="refresh"),
        ],
    )
    async def dashboard_command(
        self,
        interaction: discord.Interaction,
        bereich: app_commands.Choice[str],
        aktion: app_commands.Choice[str],
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if not guild or guild.id != GUILD_ID:
            await interaction.followup.send("Dieser Command ist nur für unsere Guild vorgesehen.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member):
            return

        which = bereich.value  # "live" | "test"

        if aktion.value == "post":
            if not _can_post_dashboard(interaction.user):
                await interaction.followup.send("Nur Admins dürfen das Dashboard posten/verschieben.", ephemeral=True)
                return
            if not isinstance(interaction.channel, discord.TextChannel):
                await interaction.followup.send("Bitte in einem Text-Channel ausführen.", ephemeral=True)
                return

            await self._ensure_dashboard_message(guild, interaction.channel, which=which)
            await interaction.followup.send(f"✅ {which.upper()} Dashboard gesetzt/aktualisiert.", ephemeral=True)
            return

        # refresh
        if not _can_refresh_dashboard(interaction.user):
            await interaction.followup.send("Nur Admin/Offizier dürfen refreshen.", ephemeral=True)
            return

        await self._refresh_dashboard(guild, which=which)
        await interaction.followup.send(f"🔄 {which.upper()} Dashboard refreshed.", ephemeral=True)

    async def _ensure_dashboard_message(self, guild: discord.Guild, channel: discord.TextChannel, which: str):
        embed = await self._build_dashboard_embed(guild, which=which)
        view = DashboardDMView(which)

        ch_id, msg_id = await self._get_dashboard_target(guild, which)

        # Wenn es ein altes Dashboard gibt:
        if ch_id and msg_id:
            old_ch = guild.get_channel(int(ch_id))

            # ✅ Wenn der Command in einem ANDEREN Channel ausgeführt wird -> wirklich "verschieben"
            if isinstance(old_ch, discord.TextChannel) and old_ch.id != channel.id:
                # optional: altes Dashboard löschen
                try:
                    old_msg = await old_ch.fetch_message(int(msg_id))
                    await old_msg.delete()
                except Exception:
                    pass

                # neues Dashboard im aktuellen Channel posten
                new_msg = await channel.send(embed=embed, view=view)
                await self._set_dashboard_target(guild, which, channel.id, new_msg.id)
                return

            # ✅ gleicher Channel -> editieren
            if isinstance(old_ch, discord.TextChannel):
                try:
                    msg = await old_ch.fetch_message(int(msg_id))
                    await msg.edit(embed=embed, view=view)
                    return
                except Exception:
                    # Wenn fetch/edit fehlschlägt: fallback -> neu posten
                    pass

        # Kein gültiges Target -> neu posten
        new_msg = await channel.send(embed=embed, view=view)
        await self._set_dashboard_target(guild, which, channel.id, new_msg.id)

    # =========================
    # Sofort-Refresh via Event aus Gruppensuche
    # =========================

    async def _refresh_dashboard(self, guild: discord.Guild, which: str):
        ch_id, msg_id = await self._get_dashboard_target(guild, which)
        if not ch_id or not msg_id:
            return

        ch = guild.get_channel(int(ch_id))
        if not isinstance(ch, discord.TextChannel):
            try:
                await self._clear_dashboard_target(guild, which)
            except Exception:
                pass

            try:
                await self._log_event(
                    guild,
                    "warn",
                    "Dashboard",
                    "Target Channel Missing",
                    (
                        f"Das {which.upper()}-Dashboard konnte nicht aktualisiert werden.\n\n"
                        "Der gespeicherte Dashboard-Channel ist nicht mehr verfügbar.\n"
                        "Das Dashboard konnte nicht automatisch repariert werden.\n\n"
                        "Bitte `/dashboard` neu ausführen."
                    ),
                )
            except Exception:
                pass
            return

        lock = self._dash_locks.get(which)
        if lock is None:
            lock = asyncio.Lock()
            self._dash_locks[which] = lock

        async with lock:
            try:
                msg = await ch.fetch_message(int(msg_id))
            except Exception:
                try:
                    await self._clear_dashboard_target(guild, which)
                except Exception:
                    pass

                try:
                    await self._log_event(
                        guild,
                        "warn",
                        "Dashboard",
                        "Message Fetch Failed",
                        (
                            f"Das {which.upper()}-Dashboard konnte nicht aktualisiert werden.\n\n"
                            "Die gespeicherte Dashboard-Nachricht konnte nicht geladen werden.\n"
                            "Das Dashboard konnte nicht automatisch repariert werden.\n\n"
                            "Bitte `/dashboard` neu ausführen."
                        ),
                        channel=ch,
                    )
                except Exception:
                    pass
                return

            try:
                embed = await self._build_dashboard_embed(guild, which=which)
                view = DashboardDMView(which)

                # --- Signatur: nur patchen wenn wirklich anders ---
                payload = {
                    "embed": embed.to_dict(),
                    # view bleibt konstant (ein Button), reicht i.d.R. embed-sig
                }
                raw = json.dumps(payload, sort_keys=True,
                                 ensure_ascii=False).encode("utf-8")
                sig = hashlib.sha256(raw).hexdigest()

                if self._last_sig.get(which) == sig:
                    return  # kein Edit nötig

                await msg.edit(embed=embed, view=view)
                self._last_sig[which] = sig

            except Exception:
                try:
                    await self._clear_dashboard_target(guild, which)
                except Exception:
                    pass

                try:
                    await self._log_event(
                        guild,
                        "error",
                        "Dashboard",
                        "Message Edit Failed",
                        (
                            f"Das {which.upper()}-Dashboard konnte nicht aktualisiert werden.\n\n"
                            "Die bestehende Dashboard-Nachricht konnte nicht bearbeitet werden.\n"
                            "Das Dashboard konnte nicht automatisch repariert werden.\n\n"
                            "Bitte `/dashboard` neu ausführen."
                        ),
                        channel=ch,
                    )
                except Exception:
                    pass
                return

    # =========================
    # Auto Refresh Loop (15 min)
    # =========================

    @tasks.loop(minutes=DASHBOARD_REFRESH_MINUTES)
    async def _dashboard_refresh_loop(self):
        await self.bot.wait_until_red_ready()
        await self.bot.wait_until_ready()

        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        await self._refresh_dashboard(guild, which="live")
        await self._refresh_dashboard(guild, which="test")

    @_dashboard_refresh_loop.before_loop
    async def _before_dashboard_refresh_loop(self):
        await self.bot.wait_until_red_ready()
        await self.bot.wait_until_ready()

    # =========================
    # Build Dashboard
    # =========================

    async def _build_dashboard_embed(self, guild: discord.Guild, which: str) -> discord.Embed:
        searches = await self._get_searches_from(guild, source=which)
        today = _now_local().date()

        items: List[dict] = []
        skipped_message_ids: List[int] = []

        for mid_str, data in (searches or {}).items():
            try:
                day_iso = data.get("day_date_iso")
                if not day_iso:
                    continue

                day_d = dt.date.fromisoformat(str(day_iso))
                if day_d < today:
                    continue

                d2 = dict(data)
                d2["message_id"] = int(d2.get("message_id") or int(mid_str))

                channel_id = int(data.get("channel_id") or 0)
                message_id = int(data.get("message_id") or 0) or int(mid_str)

                ch = guild.get_channel(channel_id)
                if not isinstance(ch, discord.TextChannel):
                    skipped_message_ids.append(int(message_id))
                    self._log_warning(
                        "FETCH",
                        "dashboard skipped post because channel is unavailable",
                        message_id=message_id,
                        channel_id=channel_id,
                    )
                    continue

                try:
                    await ch.fetch_message(int(message_id))
                except Exception:
                    skipped_message_ids.append(int(message_id))
                    self._log_warning(
                        "FETCH",
                        "dashboard skipped post because fetch_message failed",
                        message_id=message_id,
                        channel_id=channel_id,
                    )
                    continue

                items.append(d2)

            except Exception:
                continue

        SPOT_ORDER = ["mirumok", "gyfin", "olun", "edania"]

        def _spot_order_key(spot_key: str) -> int:
            try:
                return SPOT_ORDER.index(spot_key)
            except ValueError:
                return 999

        def _sort_key(d: dict):
            day_iso = str(d.get("day_date_iso") or "")
            start_text = str(d.get("start_text") or "")
            tkey = _extract_time_sort_key(start_text)
            cat = str(d.get("category") or "")

            # Spots: extra sort nach Spot
            if cat == "spots":
                spot = str(d.get("spot_key") or "")
                return (day_iso, tkey[0], tkey[1], 0, _spot_order_key(spot))

            return (day_iso, tkey[0], tkey[1], 1, cat)

        items.sort(key=_sort_key)

        muh_normal: List[dict] = []
        muh_schwer: List[dict] = []

        # Spots getrennt
        spots_miru: List[dict] = []
        spots_gyfin: List[dict] = []
        spots_olun_normal: List[dict] = []
        spots_olun_d1: List[dict] = []
        spots_olun_d2: List[dict] = []
        spots_edania: List[dict] = []

        pilafe: List[dict] = []
        atoraxxion: List[dict] = []
        altar: List[dict] = []

        for d in items:
            cat = str(d.get("category") or "")

            if cat == "muhhelfer":
                diff = str(d.get("difficulty") or "normal")
                if diff == "schwer":
                    muh_schwer.append(d)
                else:
                    muh_normal.append(d)

            elif cat == "spots":
                sk = str(d.get("spot_key") or "").strip().lower()

                if sk == "mirumok":
                    spots_miru.append(d)

                elif sk == "gyfin":
                    spots_gyfin.append(d)

                elif sk == "olun":
                    tier = str(d.get("olun_tier") or "").strip().lower()

                    if tier in ("", "normal", "base"):
                        spots_olun_normal.append(d)
                    elif tier in ("dehkia1", "dehkia_1", "d1", "1"):
                        spots_olun_d1.append(d)
                    elif tier in ("dehkia2", "dehkia_2", "d2", "2"):
                        spots_olun_d2.append(d)
                    else:
                        spots_olun_normal.append(d)

                elif sk == "edania":
                    spots_edania.append(d)

                else:
                    spots_miru.append(d)

            elif cat == "pilafe":
                pilafe.append(d)

            elif cat == "atoraxxion":
                atoraxxion.append(d)

            elif cat == "altar":
                altar.append(d)

        title = "Gruppenübersicht - LIVE" if which == "live" else "Gruppenübersicht - TEST"

        e = discord.Embed(
            title=title,
            description="Hier siehst du alle aktiven Gruppensuchen.\n✉️ Button: DM Reminders an/aus.",
        )

        def fmt_line(d: dict, include_day: bool = True) -> str:
            # --- Helper ---
            def _clean(val: object) -> Optional[str]:
                s = str(val or "").strip()
                if not s or s == "—":
                    return None
                return s

            # --- Grunddaten ---
            max_players = int(d.get("max_players", 2) or 2)
            participants = list(d.get("participants") or [])
            is_closed = bool(d.get("is_closed", False))
            is_full = len(participants) >= max_players

            status_icon = "🔴" if is_closed else ("🔴" if is_full else "🟢")
            status_label = "Geschlossen" if is_closed else (
                "Voll" if is_full else "Offen")

            chan_name = d.get("channel_name") or "—"
            jump = _jump_link(d)

            # --- Meta-Daten zuerst sauber setzen (verhindert UnboundLocalError) ---
            day_str = _fmt_day(d.get("day_date_iso")) if include_day else None
            start_text = _clean(d.get("start_text"))
            duration_text = _clean(d.get("duration_text"))
            req = _clean(d.get("req_text"))

            cat = str(d.get("category") or "").lower()

            pilafe_extra = None
            if cat == "pilafe":
                amount = _clean(d.get("scroll_amount"))
                if amount:
                    pilafe_extra = f"Menge: {amount}"

            atorun_extra = None
            if cat == "atoraxxion":
                runs = _normalize_atoraxxion_runs(d)
                all_keys = {"vahmalkea", "sycrakea", "yolunakea", "orzekea"}
                if set(runs) == all_keys:
                    atorun_extra = "🏛️ Run: Kompletter Run (4/4)"
                elif runs:
                    atorun_extra = f"🏛️ Run: Teil-Run ({len(runs)}/4)"

            # --- Meta in EINER Zeile bündeln ---
            meta_parts: list[str] = []

            if day_str:
                meta_parts.append(day_str)
            if start_text:
                meta_parts.append(start_text)
            if duration_text:
                meta_parts.append(duration_text)
            if req:
                meta_parts.append(f"Req: {req}")
            if pilafe_extra:
                meta_parts.append(pilafe_extra)
            if atorun_extra:
                meta_parts.append(atorun_extra)

            meta = " | ".join(meta_parts)
            meta = f" — {meta}" if meta else ""

            # WICHTIG: Kein Spot-Emoji hier (steht bereits im Category-Header)
            return f"{status_icon} **{status_label} | {len(participants)}/{max_players}**{meta} ➜ #{chan_name} {jump}"

        def _section_sort_key(d: dict) -> tuple:
            """
            Sortierung innerhalb einer Section:
            1) Tag (day_date_iso) primär
            2) Uhrzeit aus start_text als Tie-Breaker (wenn parsebar)
            """
            day_iso = str(d.get("day_date_iso") or "")
            try:
                day = dt.date.fromisoformat(day_iso)
            except Exception:
                day = dt.date.max  # unparsebar -> ans Ende

            start_text = str(d.get("start_text") or "").strip().lower()
            minutes = 24 * 60 + 1  # default: ganz ans Ende innerhalb des Tages

            # "15:30" / "15.30"
            m = re.search(r"\b(\d{1,2})\s*[:.]\s*(\d{2})\b", start_text)
            if m:
                h = int(m.group(1))
                mm = int(m.group(2))
                if 0 <= h <= 23 and 0 <= mm <= 59:
                    minutes = h * 60 + mm
            else:
                # "15 Uhr"
                m = re.search(r"\b(\d{1,2})\s*uhr\b", start_text)
                if m:
                    h = int(m.group(1))
                    if 0 <= h <= 23:
                        minutes = h * 60

            return (day, minutes)

        def _day_key(d: dict) -> tuple:
            """
            Sort-Key: echte Datumssortierung, Unbekannt nach hinten.
            """
            iso = d.get("day_date_iso")
            try:
                if iso:
                    dd = dt.date.fromisoformat(str(iso))
                    return (0, dd.toordinal(), str(iso))
            except Exception:
                pass
            return (1, 99999999, "unknown")

        def _day_label(d: dict) -> str:
            return _fmt_day(d.get("day_date_iso"))

        # =========================
        # 7-Tage-Layout (immer anzeigen)
        # =========================

        # --- flache Liste bauen: (day_iso, category_title, item_dict) ---
        entries: list[tuple[str, str, dict]] = []

        def add_entries(cat_title: str, arr: list[dict]):
            for x in arr:
                day_iso = str(x.get("day_date_iso") or "").strip()
                if not day_iso:
                    continue
                entries.append((day_iso, cat_title, x))

        # Nur Listen hinzufügen (leer ist ok)
        add_entries(f"{MUHKUH_EMOJI} Muhhelfer – Normal", muh_normal)
        add_entries(f"{MUHKUH_EMOJI} Muhhelfer – Schwer", muh_schwer)

        add_entries(f"{MIRUMOK_EMOJI} Gruppenspots – Mirumok", spots_miru)
        add_entries(f"{GYFIN_EMOJI} Gruppenspots – Gyfin", spots_gyfin)
        add_entries(f"{OLUN_EMOJI} Gruppenspots – Olun Normal",
                    spots_olun_normal)
        add_entries(
            f"{OLUN_EMOJI} Gruppenspots – Olun Dehkia 1", spots_olun_d1)
        add_entries(
            f"{OLUN_EMOJI} Gruppenspots – Olun Dehkia 2", spots_olun_d2)
        add_entries(f"{EDANIA_EMOJI} Gruppenspots – Edania", spots_edania)

        add_entries(f"{PILAFE_EMOJI} Pila Fe", pilafe)
        add_entries("🏛️ Atoraxxion", atoraxxion)
        add_entries("🩸 Altar des Blutes", altar)

        # --- sort: nach Datum, dann nach Uhrzeit (über items selbst) ---
        def _day_key_iso(day_iso: str) -> tuple:
            try:
                dd = dt.date.fromisoformat(day_iso)
                return (0, dd.toordinal(), day_iso)
            except Exception:
                return (1, 99999999, day_iso)

        entries_sorted = sorted(entries, key=lambda t: _day_key_iso(t[0]))

        # --- group by day_iso ---
        by_day: dict[str, list[tuple[str, dict]]] = {}
        for day_iso, cat_title, item in entries_sorted:
            by_day.setdefault(day_iso, []).append((cat_title, item))

        # --- render: immer heute..heute+6 ---
        day_range = [today + dt.timedelta(days=i) for i in range(7)]

        chunks: list[str] = []

        info_prefix = (
            "ℹ️ **Info**\n"
            "• 🟢 Offen  • 🔴 Voll/Geschlossen\n"
            "• „➜ #channel …“ ist der Jump-Link zum Post\n"
            "• Anzeige immer für die nächsten **7 Tage**\n\n"
        )

        for day_d in day_range:
            day_iso = day_d.isoformat()
            day_label = _format_day(day_d)

            chunks.append(f"### {day_label}")

            day_items = by_day.get(day_iso, [])

            if not day_items:
                chunks.append("_Keine Gruppensuchen_")
                chunks.append("")  # Leerzeile zwischen Tagen
                continue

            # innerhalb des Tages: nach Kategorie gruppieren
            # innerhalb des Tages: nach Kategorie gruppieren
            cat_map: dict[str, list[dict]] = {}
            for cat_title, item in day_items:
                cat_map.setdefault(cat_title, []).append(item)

            # ---------- Status Sort Key (einmal definieren) ----------

            def _status_sort_key(x: dict) -> tuple:
                max_players = int(x.get("max_players", 2) or 2)
                participants = list(x.get("participants") or [])
                is_closed = bool(x.get("is_closed", False))
                is_full = len(participants) >= max_players

                # Reihenfolge:
                # 0 = Offen
                # 1 = Voll
                # 2 = Geschlossen
                if is_closed:
                    state = 2
                elif is_full:
                    state = 1
                else:
                    state = 0

                # Zeit als Zweitsortierung
                start_text = str(x.get("start_text") or "")
                tkey = _extract_time_sort_key(start_text)

                return (state, tkey[0], tkey[1])

            # ---------- Rendering ----------
            for cat_title, items_cat in cat_map.items():

                # 🔹 Sortierung hier — jetzt existiert items_cat garantiert
                items_cat.sort(key=_status_sort_key)

                chunks.append(f"__{cat_title} ({len(items_cat)})__")

                lines = [fmt_line(x, include_day=False) for x in items_cat]

                for ln in lines:
                    if sum(len(s) + 1 for s in chunks) + len(ln) + 1 > 3800:
                        chunks.append("… (gekürzt)")
                        break
                    chunks.append(ln)

        e.description = info_prefix + \
            "\n".join([c for c in chunks if c is not None])

        # Letztes echtes Update (datengetrieben) statt "immer jetzt"
        last_ts = 0
        for d in items:
            try:
                last_ts = max(last_ts, int(d.get("updated_at") or 0))
            except Exception:
                pass

        if last_ts > 0:
            t = dt.datetime.fromtimestamp(last_ts)
            e.set_footer(
                text=f"Aktualisiert: {t.strftime('%d.%m.%Y %H:%M')} Uhr")
        else:
            e.set_footer(text="Aktualisiert: —")
        return e
