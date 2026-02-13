from __future__ import annotations

import datetime as dt
import re
from typing import Dict, List, Optional, Tuple
import asyncio
import hashlib
import json


import discord
from discord.ext import tasks
from redbot.core import commands, Config
from discord import app_commands


# =========================
# FIX: Nur fuer eure Guild
# =========================
GUILD_ID = 1198649628787212458

# Eigene Dashboard-Config (separat)
DASHBOARD_CONFIG_IDENTIFIER = 935771234124

# Update-Intervall
DASHBOARD_REFRESH_MINUTES = 15

# Emojis
MUHKUH_EMOJI = "<:muhkuh:1207038544510586890>"
PILAFE_EMOJI = "<:pilafe:1450051653297504368>"
MIRUMOK_EMOJI = "<:Mirumok:1461101498954940428>"
GYFIN_EMOJI = "<:Gyfin:1461102103266066502>"
OLUN_EMOJI = "<:olun:1471826612394655857>"
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
        # Optional: Dehkia optisch gleich lassen oder später eigenes Emoji je Tier
        return OLUN_EMOJI

    return CHEER_EMOJI


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
        return self.bot.get_cog("Gruppensuche")

    def _get_gruppensuche_cog_test(self):
        return self.bot.get_cog("GruppensucheTest")

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
            return

        try:
            msg = await ch.fetch_message(int(msg_id))
        except Exception:
            try:
                await self._clear_dashboard_target(guild, which)
            except Exception:
                pass
            return

        lock = self._dash_locks.get(which)
        if lock is None:
            lock = asyncio.Lock()
            self._dash_locks[which] = lock

        async with lock:
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
        stale_message_ids: List[int] = []

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
                    stale_message_ids.append(int(message_id))
                    continue

                try:
                    await ch.fetch_message(int(message_id))
                except Exception:
                    stale_message_ids.append(int(message_id))
                    continue

                items.append(d2)
            except Exception:
                continue

        # stale Einträge löschen (nur in der passenden Quelle!)
        if stale_message_ids:
            search_cog = self._get_gruppensuche_cog_live(
            ) if which == "live" else self._get_gruppensuche_cog_test()
            if search_cog:
                try:
                    async with search_cog.config.guild(guild).searches() as s:
                        for mid in stale_message_ids:
                            s.pop(str(mid), None)
                except Exception:
                    pass

        SPOT_ORDER = ["mirumok", "gyfin", "olun", "newspot"]

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

            # Spots: extra sort nach Spot (miru -> gyfin -> neu)
            if cat == "spots":
                spot = str(d.get("spot_key") or "")
                return (day_iso, tkey[0], tkey[1], 0, _spot_order_key(spot))

            return (day_iso, tkey[0], tkey[1], 1, cat)

        items.sort(key=_sort_key)

        muh_normal: List[dict] = []
        muh_schwer: List[dict] = []
        spots: List[dict] = []
        pilafe: List[dict] = []

        for d in items:
            cat = str(d.get("category") or "")
            if cat == "muhhelfer":
                diff = str(d.get("difficulty") or "normal")
                if diff == "schwer":
                    muh_schwer.append(d)
                else:
                    muh_normal.append(d)
            elif cat == "spots":
                spots.append(d)
            elif cat == "pilafe":
                pilafe.append(d)

        title = "Gruppenübersicht - LIVE" if which == "live" else "Gruppenübersicht - TEST"

        e = discord.Embed(
            title=title,
            description="Hier siehst du alle aktiven Gruppensuchen.\n✉️ Button: DM Reminders an/aus.",
        )

        def fmt_line(d: dict) -> str:
            day_iso = str(d.get("day_date_iso") or "")
            try:
                day_d = dt.date.fromisoformat(day_iso)
                day_str = _format_day(day_d)
            except Exception:
                day_str = day_iso or "—"

            start_text = d.get("start_text") or "—"
            duration_text = d.get("duration_text") or "—"

            max_players = int(d.get("max_players") or 2)
            participants = list(d.get("participants") or [])
            waitlist = list(d.get("waitlist") or [])

            is_closed = bool(d.get("is_closed", False))
            is_full = len(participants) >= max_players
            status = "🔴 Geschlossen" if is_closed else (
                "🔴 Voll" if is_full else "🟢 Offen")

            req_text = d.get("req_text") or ""
            req_default = _default_req_for(d)
            req = req_text or req_default or "—"

            channel_id = int(d.get("channel_id") or 0)
            message_id = int(d.get("message_id") or 0)
            jump = _jump_url(guild.id, channel_id, message_id)

            # 3/5 Anzeige
            count = f"{len(participants)}/{max_players}"

            # Warteschlange nur wenn > 0
            wl = f" | WL: {len(waitlist)}" if len(waitlist) > 0 else ""

            cat = str(d.get("category") or "")
            spot_key = str(d.get("spot_key") or "")
            olun_tier = str(d.get("olun_tier") or "")
            spot_icon = _spot_emoji(
                spot_key, olun_tier=olun_tier) if cat == "spots" else ""

            prefix = f"{spot_icon} " if spot_icon else ""
            return (
                f"• **{day_str}** | **{start_text}** | {duration_text} | Req: **{req}**\n"
                f"  {status} | {count}{wl} → {jump}"
            )

        def add_section(title: str, arr: List[dict], empty_text: str = "—"):
            if not arr:
                e.add_field(name=title, value=empty_text, inline=False)
                return

            lines = [fmt_line(x) for x in arr]

            chunk = ""
            chunks: List[str] = []
            for line in lines:
                if len(chunk) + len(line) + 1 > 1000:
                    chunks.append(chunk)
                    chunk = line
                else:
                    chunk = f"{chunk}\n{line}".strip()
            if chunk:
                chunks.append(chunk)

            for idx, ch in enumerate(chunks):
                field_name = title if idx == 0 else f"{title} (weiter)"
                # ⬇️ am Ende einen unsichtbaren Abstand anhängen
                spaced_value = ch + "\n\u200b"

                e.add_field(
                    name=field_name,
                    value=spaced_value,
                    inline=False
                )

        add_section(
            f"{MUHKUH_EMOJI} Muhhelfer – Normal ({len(muh_normal)})", muh_normal)
        add_section(
            f"{MUHKUH_EMOJI} Muhhelfer – Schwer ({len(muh_schwer)})", muh_schwer)

        # --- Gruppenspots nach Spot aufteilen ---
        spots_miru: List[dict] = []
        spots_gyfin: List[dict] = []

        spots_olun_normal: List[dict] = []
        spots_olun_d1: List[dict] = []
        spots_olun_d2: List[dict] = []

        spots_other: List[dict] = []

        for d in spots:
            sk = _norm_spot_key(d.get("spot_key"))

            if sk == "mirumok":
                spots_miru.append(d)

            elif sk == "gyfin":
                spots_gyfin.append(d)

            elif sk == "olun":
                tier = str(d.get("olun_tier") or "normal").strip().lower()
                if tier == "dehkia2":
                    spots_olun_d2.append(d)
                elif tier == "dehkia1":
                    spots_olun_d1.append(d)
                else:
                    spots_olun_normal.append(d)

            else:
                spots_other.append(d)

        add_section(
            f"{MIRUMOK_EMOJI} Gruppenspots – Mirumok ({len(spots_miru)})",
            spots_miru
        )

        add_section(
            f"{GYFIN_EMOJI} Gruppenspots – Gyfin ({len(spots_gyfin)})",
            spots_gyfin
        )

        add_section(
            f"{OLUN_EMOJI} Gruppenspots – Olun Normal ({len(spots_olun_normal)})",
            spots_olun_normal
        )

        add_section(
            f"{OLUN_EMOJI} Gruppenspots – Olun Dehkia 1 ({len(spots_olun_d1)})",
            spots_olun_d1
        )

        add_section(
            f"{OLUN_EMOJI} Gruppenspots – Olun Dehkia 2 ({len(spots_olun_d2)})",
            spots_olun_d2
        )

        if spots_other:
            add_section(
                f"{CHEER_EMOJI} Gruppenspots – Sonstige ({len(spots_other)})",
                spots_other
            )

        add_section(f"{PILAFE_EMOJI} Pila Fe ({len(pilafe)})", pilafe)

        # Letztes echtes Update (datengetrieben) statt "immer jetzt"
        last_ts = 0
        for d in items:
            try:
                last_ts = max(last_ts, int(d.get("updated_at") or 0))
            except Exception:
                pass

        if not items:
            e.add_field(name="Keine Eintraege",
                        value="Aktuell gibt es **keine** Gruppensuchen ab heute.", inline=False)

        if last_ts > 0:
            t = dt.datetime.fromtimestamp(last_ts)
            e.set_footer(
                text=f"Aktualisiert: {t.strftime('%d.%m.%Y %H:%M')} Uhr")
        else:
            e.set_footer(text="Aktualisiert: —")
        return e
