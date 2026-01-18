from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional, Tuple

import discord
from discord.ext import tasks
from redbot.core import commands, Config


# ============
# WICHTIG:
# - Dieser Cog liest die "searches" aus dem anderen Cog (Gruppensuche)
# - Dafür muss die IDENTIFIER-ID gleich sein, damit wir auf dieselbe Config-Datei zeigen.
# ============
GRUPPENSUCHE_CONFIG_IDENTIFIER = 935771234123  # muss exakt gleich sein wie im Gruppensuche-Cog

# Eigene Dashboard-Config (separat, damit nichts kollidiert)
DASHBOARD_CONFIG_IDENTIFIER = 935771234124

# Update-Intervall
DASHBOARD_REFRESH_MINUTES = 15

# Emojis (optional – kann man später angleichen)
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


class Gruppenübersicht(commands.Cog):
    """Gruppenübersicht - Dashbord"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Lesen aus Gruppensuche-Config (shared via identifier)
        self.search_config = Config.get_conf(
            self, identifier=GRUPPENSUCHE_CONFIG_IDENTIFIER, force_registration=True
        )
        self.search_config.register_guild(searches={})

        # Eigene Config für Dashboard-Msg/Channel
        self.config = Config.get_conf(
            self, identifier=DASHBOARD_CONFIG_IDENTIFIER, force_registration=True
        )
        self.config.register_guild(
            dashboard_channel_id=None,
            dashboard_message_id=None,
        )

        self._dashboard_refresh_loop.start()

    def cog_unload(self):
        self._dashboard_refresh_loop.cancel()

    async def _get_searches(self, guild: discord.Guild) -> Dict[str, dict]:
        data = await self.search_config.guild(guild).searches()
        return data or {}

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

        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("Bitte in einem Text-Channel ausführen.")
            return

        embed = await self._build_dashboard_embed(guild)

        # Versuche vorhandenes Dashboard zu editieren
        ch_id, msg_id = await self._get_dashboard_target(guild)
        if ch_id and msg_id:
            ch = guild.get_channel(int(ch_id))
            if isinstance(ch, discord.TextChannel):
                try:
                    msg = await ch.fetch_message(int(msg_id))
                    await msg.edit(embed=embed, view=None)
                    try:
                        await ctx.message.add_reaction("✅")
                    except Exception:
                        pass
                    return
                except Exception:
                    # message weg -> neu erstellen
                    pass

        # Neu erstellen im aktuellen Channel
        msg = await ctx.channel.send(embed=embed)
        await self._set_dashboard_target(guild, ctx.channel.id, msg.id)

        try:
            await ctx.message.add_reaction("✅")
        except Exception:
            pass

    # =========================
    # Auto Refresh Loop
    # =========================

    @tasks.loop(minutes=DASHBOARD_REFRESH_MINUTES)
    async def _dashboard_refresh_loop(self):
        await self.bot.wait_until_red_ready()
        await self.bot.wait_until_ready()

        for guild in self.bot.guilds:
            # Wenn Dashboard nicht gesetzt ist, skip
            ch_id, msg_id = await self._get_dashboard_target(guild)
            if not ch_id or not msg_id:
                continue

            ch = guild.get_channel(int(ch_id))
            if not isinstance(ch, discord.TextChannel):
                continue

            try:
                msg = await ch.fetch_message(int(msg_id))
            except Exception:
                # Dashboard wurde gelöscht -> Target resetten
                try:
                    await self._clear_dashboard_target(guild)
                except Exception:
                    pass
                continue

            try:
                embed = await self._build_dashboard_embed(guild)
                await msg.edit(embed=embed, view=None)
            except Exception:
                # nichts spammen
                continue

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

        # Filter: alles vor heute ignorieren (wie abgesprochen)
        items: List[dict] = []
        for mid_str, data in searches.items():
            try:
                day_iso = data.get("day_date_iso")
                if not day_iso:
                    continue
                day_d = dt.date.fromisoformat(str(day_iso))
                if day_d < today:
                    continue
                data = dict(data)
                data["message_id"] = int(data.get("message_id") or int(mid_str))
                items.append(data)
            except Exception:
                continue

        # Sortierung: nach Tag, dann Start (optional), dann Kategorie
        def _sort_key(d: dict):
            day_iso = str(d.get("day_date_iso") or "")
            start = (d.get("start_text") or "").lower()
            cat = str(d.get("category") or "")
            return (day_iso, start, cat)

        items.sort(key=_sort_key)

        # Gruppen
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
                "Auto-Update läuft alle 15 Minuten (und nach Restarts/Cog-Reloads, sobald das Dashboard einmal gesetzt wurde)."
            ),
        )

        # Helfer für Zeile
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

            # Zusatz je Kategorie
            cat = str(d.get("category") or "")
            extra = ""
            if cat == "spots":
                spot = str(d.get("spot_key") or "")
                extra = f"{MIRUMOK_EMOJI if spot == 'mirumok' else (GYFIN_EMOJI if spot == 'gyfin' else CHEER_EMOJI)} {_spot_name(spot)}"
            elif cat == "pilafe":
                amount = d.get("scroll_amount") or "—"
                extra = f"{PILAFE_EMOJI} Menge: {amount}"
            else:
                diff = str(d.get("difficulty") or "normal")
                diff_label = "Schwer" if diff == "schwer" else "Normal"
                extra = f"{MUHKUH_EMOJI} {diff_label}"

            # WICHTIG: gewünschte/optionale Req soll mit rein (wie du meintest)
            return (
                f"• **{day_str}** | Start: **{start_text}** | Dauer: **{duration_text}**\n"
                f"  {extra} | Req: **{req}** | {status} | Frei: **{free}** | Warteschlange: **{len(waitlist)}**\n"
                f"  Suchender: {owner_txt} → {jump}"
            )

        def add_section(title: str, arr: List[dict]):
            if not arr:
                return
            lines = [fmt_line(x) for x in arr]
            # Discord field value max ~1024 chars – split falls nötig
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
            e.add_field(name="Keine Einträge", value="Aktuell gibt es **keine** Gruppensuchen ab heute.", inline=False)

        e.set_footer(text=f"Aktualisiert: {_now_local().strftime('%d.%m.%Y %H:%M')} Uhr")
        e.timestamp = discord.utils.utcnow()
        return e
