from __future__ import annotations

import datetime as dt
import re
from typing import Dict, List, Optional, Tuple

import discord
from discord.ext import tasks
from redbot.core import commands, Config


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
CHEER_EMOJI = "<:blackspiritcheer:1199730129476268183>"

AKVK_NORMAL = "301/385"
AKVK_SCHWER = "330/401"

WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


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
    return key


def _default_req_for(data: dict) -> str:
    cat = data.get("category")
    if cat == "muhhelfer":
        diff = data.get("difficulty", "normal")
        return AKVK_SCHWER if diff == "schwer" else AKVK_NORMAL
    if cat == "spots":
        spot = data.get("spot_key", "")
        if spot == "mirumok":
            return "350+ AP / 427+ VK"
        if spot == "gyfin":
            return "370+ AP / 440+ VK"
        return ""
    return ""


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


class Gruppenübersicht(commands.Cog):
    """Gruppenübersicht - Dashbord"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Eigene Config fuer Dashboard-Msg/Channel
        self.config = Config.get_conf(self, identifier=DASHBOARD_CONFIG_IDENTIFIER, force_registration=True)
        self.config.register_guild(
            dashboard_channel_id=None,
            dashboard_message_id=None,
        )

        self._dashboard_refresh_loop.start()

    def cog_unload(self):
        self._dashboard_refresh_loop.cancel()

    # =========================
    # Datenquelle: direkt aus Gruppensuche-Cog
    # =========================

    def _get_gruppensuche_cog(self):
        """
        Holt den Cog, der die searches besitzt.
        Passe hier nur an, falls du den Klassennamen aenderst.
        """
        # Erst Test-Cog
        c = self.bot.get_cog("GruppensucheTest")
        if c:
            return c

        # Falls spaeter der Main Cog anders heisst
        c = self.bot.get_cog("Gruppensuche")
        if c:
            return c

        return None

    async def _get_searches(self, guild: discord.Guild) -> Dict[str, dict]:
        search_cog = self._get_gruppensuche_cog()
        if not search_cog:
            return {}

        # Erwartet: search_cog.config.register_guild(searches={})
        try:
            data = await search_cog.config.guild(guild).searches()
            return data or {}
        except Exception:
            return {}

    async def _get_dashboard_target(self, guild: discord.Guild) -> Tuple[Optional[int], Optional[int]]:
        ch_id = await self.config.guild(guild).dashboard_channel_id()
        msg_id = await self.config.guild(guild).dashboard_message_id()
        try:
            return (int(ch_id) if ch_id else None, int(msg_id) if msg_id else None)
        except Exception:
            return (None, None)

    async def _set_dashboard_target(self, guild: discord.Guild, channel_id: int, message_id: int):
        await self.config.guild(guild).dashboard_channel_id.set(int(channel_id))
        await self.config.guild(guild).dashboard_message_id.set(int(message_id))

    async def _clear_dashboard_target(self, guild: discord.Guild):
        await self.config.guild(guild).dashboard_channel_id.set(None)
        await self.config.guild(guild).dashboard_message_id.set(None)

    # =========================
    # Prefix Command
    # =========================

    @commands.guild_only()
    @commands.command(name="gruppenübersicht", aliases=["gübersicht", "dashboard"])
    async def gruppenuebersicht_prefix(self, ctx: commands.Context):
        """
        Erstellt oder aktualisiert das Dashboard im aktuellen Channel.
        Aufruf: °gruppenübersicht
        """
        guild = ctx.guild
        if guild is None:
            return

        if guild.id != GUILD_ID:
            await ctx.send("Dieser Cog ist nur fuer unsere Guild vorgesehen.")
            return

        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("Bitte in einem Text-Channel ausfuehren.")
            return

        await self._ensure_dashboard_message(guild, ctx.channel)

        try:
            await ctx.message.add_reaction("✅")
        except Exception:
            pass

    async def _ensure_dashboard_message(self, guild: discord.Guild, channel: discord.TextChannel):
        embed = await self._build_dashboard_embed(guild)

        ch_id, msg_id = await self._get_dashboard_target(guild)
        if ch_id and msg_id:
            ch = guild.get_channel(int(ch_id))
            if isinstance(ch, discord.TextChannel):
                try:
                    msg = await ch.fetch_message(int(msg_id))
                    await msg.edit(embed=embed, view=None)
                    return
                except Exception:
                    pass

        msg = await channel.send(embed=embed)
        await self._set_dashboard_target(guild, channel.id, msg.id)

    # =========================
    # Sofort-Refresh via Event aus Gruppensuche
    # =========================

    @commands.Cog.listener()
    async def on_gruppensuche_updated(self, guild_id: int):
        if int(guild_id) != GUILD_ID:
            return

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return

        await self._refresh_dashboard(guild)

    async def _refresh_dashboard(self, guild: discord.Guild):
        ch_id, msg_id = await self._get_dashboard_target(guild)
        if not ch_id or not msg_id:
            return

        ch = guild.get_channel(int(ch_id))
        if not isinstance(ch, discord.TextChannel):
            return

        try:
            msg = await ch.fetch_message(int(msg_id))
        except Exception:
            try:
                await self._clear_dashboard_target(guild)
            except Exception:
                pass
            return

        try:
            embed = await self._build_dashboard_embed(guild)
            await msg.edit(embed=embed, view=None)
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

        await self._refresh_dashboard(guild)

    @_dashboard_refresh_loop.before_loop
    async def _before_dashboard_refresh_loop(self):
        await self.bot.wait_until_red_ready()
        await self.bot.wait_until_ready()

    # =========================
    # Build Dashboard
    # =========================

    async def _build_dashboard_embed(self, guild: discord.Guild) -> discord.Embed:
        searches = await self._get_searches(guild)
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
            
        if stale_message_ids:
            search_cog = self._get_gruppensuche_cog()
            if search_cog:
                try:
                    async with search_cog.config.guild(guild).searches() as s:
                        for mid in stale_message_ids:
                            s.pop(str(mid), None)
                except Exception:
                    pass


        def _sort_key(d: dict):
            day_iso = str(d.get("day_date_iso") or "")
            start_text = str(d.get("start_text") or "")
            tkey = _extract_time_sort_key(start_text)
            cat = str(d.get("category") or "")
            return (day_iso, tkey[0], tkey[1], cat)

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

        e = discord.Embed(
            title="Gruppenübersicht - Dashbord",
            description=(
                "Hier siehst du alle aktiven Gruppensuchen **ab heute**.\n"
                "Auto-Update laeuft alle 15 Minuten (und sofort bei Updates der Suche, sobald das Dashboard einmal gesetzt wurde)."
            ),
        )

        def fmt_line(d: dict) -> str:
            owner_id = int(d.get("owner_id") or 0)
            owner = guild.get_member(owner_id)
            owner_txt = owner.mention if owner else f"<@{owner_id}>"

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
            status = "🔴 Geschlossen" if is_closed else ("🔴 Voll" if is_full else "🟢 Offen")

            req_text = d.get("req_text") or ""
            req_default = _default_req_for(d)
            req = req_text or req_default or "—"

            channel_id = int(d.get("channel_id") or 0)
            message_id = int(d.get("message_id") or 0)
            jump = _jump_url(guild.id, channel_id, message_id)

            free = max(0, max_players - len(participants))

            cat = str(d.get("category") or "")
            extra = ""
            if cat == "spots":
                spot = str(d.get("spot_key") or "")
                emoji = MIRUMOK_EMOJI if spot == "mirumok" else (GYFIN_EMOJI if spot == "gyfin" else CHEER_EMOJI)
                extra = f"{emoji} {_spot_name(spot)}"
            elif cat == "pilafe":
                amount = d.get("scroll_amount") or "—"
                extra = f"{PILAFE_EMOJI} Menge: {amount}"
            else:
                diff = str(d.get("difficulty") or "normal")
                diff_label = "Schwer" if diff == "schwer" else "Normal"
                extra = f"{MUHKUH_EMOJI} {diff_label}"

            return (
                f"• **{day_str}** | Start: **{start_text}** | Dauer: **{duration_text}**\n"
                f"  {extra} | Req: **{req}** | {status} | Frei: **{free}** | Warteschlange: **{len(waitlist)}**\n"
                f"  Suchender: {owner_txt} → {jump}"
            )

        def add_section(title: str, arr: List[dict]):
            if not arr:
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
                e.add_field(name=field_name, value=ch, inline=False)

        add_section(f"{MUHKUH_EMOJI} Muhhelfer – Normal ({len(muh_normal)})", muh_normal)
        add_section(f"{MUHKUH_EMOJI} Muhhelfer – Schwer ({len(muh_schwer)})", muh_schwer)
        add_section(f"{CHEER_EMOJI} Gruppenspots ({len(spots)})", spots)
        add_section(f"{PILAFE_EMOJI} Pila Fe ({len(pilafe)})", pilafe)

        if not items:
            e.add_field(name="Keine Eintraege", value="Aktuell gibt es **keine** Gruppensuchen ab heute.", inline=False)

        e.set_footer(text=f"Aktualisiert: {_now_local().strftime('%d.%m.%Y %H:%M')} Uhr")
        e.timestamp = discord.utils.utcnow()
        return e
