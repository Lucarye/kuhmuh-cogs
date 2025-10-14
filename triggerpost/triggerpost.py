from __future__ import annotations

import time
from typing import Optional, List, Tuple

import discord
from discord import ui, AllowedMentions
from redbot.core import commands, Config
from redbot.core.bot import Red


# ====== Server-spezifische IDs ======
ROLE_NORMAL = 1424768638157852682            # Muhhelfer – Normal
ROLE_SCHWER = 1424769286790054050            # Muhhelfer – Schwer
ROLE_OFFIZIERE_BYPASS = 1198652039312453723  # Offiziere: Bypass + erweiterte Rechte

# ====== Emojis / Visuals ======
EMOJI_TITLE = "<:muhkuh:1207038544510586890>"  # Titel-Emoji (mit ID)
EMOJI_NORMAL = discord.PartialEmoji(name="muh_normal", id=1424467460228124803)
EMOJI_SCHWER = discord.PartialEmoji(name="muh_schwer", id=1424467458118647849)

# Muhkuh-Bild (Thumbnail oben rechts)
MUHKU_THUMBNAIL = "https://cdn.discordapp.com/attachments/1404063753946796122/1404063845491671160/muhku.png?ex=68e8451b&is=68e6f39b&hm=92c4de08b4562cdb9779ffaf1177dfa141515658028cd9335a29f2670618c9c0&"

# ====== Default-Config ======
DEFAULT_GUILD = {
    "triggers": ["hilfe"],
    "target_channel_id": None,
    "message_id": None,
    "cooldown_seconds": 30,
    "intro_text": f"Oh, es scheint du brauchst einen Muhhelfer bei deinen Bossen? {EMOJI_TITLE}:",
    "autodelete_minutes": 10,   # Posts außerhalb des Zielchannels werden nach X Minuten gelöscht (0 = aus)
    "layout_mode": 1            # 1=Standard, 2=Kompakt, 3=Event, 4=Admin/Debug
}

PING_COOLDOWN_SECONDS = 60  # Button-Ping-Cooldown pro Channel (nicht für Offiziere/Admins)


class TriggerPost(commands.Cog):
    """Muhhelfer-System mit Triggern, Embed, Buttons und Pings (nur Präfix-Befehle, keine DMs/Threads)."""

    _ping_cd_until: dict[int, float] = {}

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=81521025, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)
        self._cooldown_until: dict[int, float] = {}

    # ---------------- Lifecycle: Views sicher registrieren ----------------
    async def cog_load(self) -> None:
        try:
            self.bot.add_view(self._PingView(self))
        except Exception:
            # Wenn Red gerade keine Views akzeptiert (z. B. beim Reload), stillschweigend ignorieren.
            pass

    # ---------------- Persistente Buttons ----------------
    class _PingView(ui.View):
        def __init__(self, parent: "TriggerPost"):
            super().__init__(timeout=None)
            self.parent = parent

        @ui.button(
            label="Muhhelfer – normal ping",
            style=discord.ButtonStyle.primary,
            emoji=EMOJI_NORMAL,
            custom_id="muh_ping_normal",
        )
        async def ping_normal(self, interaction: discord.Interaction, button: ui.Button):
            await self.parent._handle_ping(interaction, ROLE_NORMAL, "Muhhelfer – normal")

        @ui.button(
            label="Muhhelfer – schwer ping",
            style=discord.ButtonStyle.danger,
            emoji=EMOJI_SCHWER,
            custom_id="muh_ping_schwer",
        )
        async def ping_schwer(self, interaction: discord.Interaction, button: ui.Button):
            await self.parent._handle_ping(interaction, ROLE_SCHWER, "Muhhelfer – schwer")

    async def _handle_ping(self, interaction: discord.Interaction, role_id: int, label: str):
        # Keine DMs/Threads unterstützen – nur Guild TextChannels
        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user
        if not isinstance(channel, discord.TextChannel) or not guild:
            try:
                await interaction.response.send_message("⚠️ Nur in Server-Textkanälen nutzbar.", ephemeral=True)
            except discord.HTTPException:
                await interaction.followup.send("⚠️ Nur in Server-Textkanälen nutzbar.", ephemeral=True)
            return

        is_admin = user.guild_permissions.administrator or user.guild_permissions.manage_guild
        has_bypass = any(r.id == ROLE_OFFIZIERE_BYPASS for r in getattr(user, "roles", []))

        now = time.time()
        until = self._ping_cd_until.get(channel.id, 0)
        if not (is_admin or has_bypass):
            if now < until:
                remaining = int(until - now)
                try:
                    await interaction.response.send_message(
                        f"⏱️ Bitte warte **{remaining}s**, bevor erneut gepingt wird.",
                        ephemeral=True,
                    )
                except discord.HTTPException:
                    await interaction.followup.send(
                        f"⏱️ Bitte warte **{remaining}s**, bevor erneut gepingt wird.",
                        ephemeral=True,
                    )
                return
            self._ping_cd_until[channel.id] = now + PING_COOLDOWN_SECONDS

        role_mention = f"<@&{role_id}>"
        content = f"🔔 {role_mention} – angefragt von {user.mention}"
        try:
            await interaction.response.send_message(
                content, allowed_mentions=AllowedMentions(roles=True, users=True, everyone=False)
            )
        except discord.HTTPException:
            await interaction.followup.send(
                content, allowed_mentions=AllowedMentions(roles=True, users=True, everyone=False)
            )

    # ---------------- Helpers: Daten & Layout ----------------
    async def _fetch_members_by_role(self, guild: discord.Guild, role_id: int) -> List[discord.Member]:
        role = guild.get_role(role_id)
        if not role:
            return []
        # Optional: Presence/Member-Intents nötig für Status; wir filtern auf sichtbar aktiv
        members = [
            m for m in role.members
            if getattr(m, "status", discord.Status.offline) in (
                discord.Status.online, discord.Status.idle, discord.Status.dnd
            )
        ]
        members.sort(key=lambda x: x.display_name.lower())
        return members

    def _fmt_section(self, title: str, members: List[discord.Member], show_count: bool = True) -> Tuple[str, str]:
        count = len(members)
        head = f"**{title} ({count})**" if show_count else f"**{title}**"
        if count == 0:
            body = "– aktuell niemand –"
        else:
            body = "\n".join(m.mention for m in members)
        return head, body

    async def _build_embed(
        self,
        guild: discord.Guild,
        author: discord.Member,
        *,
        manual_info: Optional[str] = None,
        footer_note: Optional[str] = None,
        mode: int = 1,
        intro_text: Optional[str] = None
    ) -> discord.Embed:

        try:
            await guild.chunk()
        except Exception:
            pass

        normal = await self._fetch_members_by_role(guild, ROLE_NORMAL)
        schwer = await self._fetch_members_by_role(guild, ROLE_SCHWER)

        # Shared header
        base_title = f"{EMOJI_TITLE} Muhhelfer – Übersicht"
        title = base_title
        if manual_info:
            # Kursive Zusatzzeile unter dem Titel: wird später als erste Zeile in description eingefügt
            pass

        # ---------------- Layout switch ----------------
        if mode == 1:
            # Standard
            embed = discord.Embed(color=discord.Color.blue())
            embed.title = title

            desc_parts = []
            if intro_text:
                desc_parts.append(intro_text)

            if manual_info:
                desc_parts.append(f"*({manual_info})*")

            head1, body1 = self._fmt_section("Muhhelfer – normal", normal, True)
            head2, body2 = self._fmt_section("Muhhelfer – schwer", schwer, True)
            desc_parts.append(f"{head1}\n{body1}")
            desc_parts.append(f"{head2}\n{body2}")

            embed.description = "\n\n".join(desc_parts)
            embed.set_thumbnail(url=MUHKU_THUMBNAIL)

        elif mode == 2:
            # Kompakt
            embed = discord.Embed(color=discord.Color.light_grey())
            embed.title = title

            lines = []
            if manual_info:
                lines.append(f"*({manual_info})*")

            n_count = len(normal)
            s_count = len(schwer)
            n_text = "– aktuell niemand –" if n_count == 0 else ", ".join(m.mention for m in normal)
            s_text = "– aktuell niemand –" if s_count == 0 else ", ".join(m.mention for m in schwer)
            lines.append(f"• **Normal ({n_count})**: {n_text}")
            lines.append(f"• **Schwer ({s_count})**: {s_text}")

            embed.description = "\n".join(lines)

        elif mode == 3:
            # Event
            embed = discord.Embed(color=discord.Color.orange())
            embed.title = f"🎉 {title}"

            desc_parts = []
            if intro_text:
                desc_parts.append(f"**Event-Ping!**\n{intro_text}")
            else:
                desc_parts.append("**Event-Ping!**")

            if manual_info:
                desc_parts.append(f"*({manual_info})*")

            head1, body1 = self._fmt_section("Muhhelfer – NORMAL", normal, True)
            head2, body2 = self._fmt_section("Muhhelfer – SCHWER", schwer, True)
            desc_parts.append(f"{head1}\n{body1}")
            desc_parts.append(f"{head2}\n{body2}")
            embed.description = "\n\n".join(desc_parts)
            embed.set_thumbnail(url=MUHKU_THUMBNAIL)

        else:
            # Admin/Debug (4)
            embed = discord.Embed(color=discord.Color.dark_grey())
            embed.title = f"{title} • Admin/Debug"

            # Namen statt Mentions
            n_names = [m.display_name for m in normal]
            s_names = [m.display_name for m in schwer]
            n_count = len(n_names)
            s_count = len(s_names)
            n_text = "– aktuell niemand –" if n_count == 0 else ", ".join(n_names)
            s_text = "– aktuell niemand –" if s_count == 0 else ", ".join(s_names)

            desc_parts = []
            if manual_info:
                desc_parts.append(f"*({manual_info})*")
            desc_parts.append(f"**Normal ({n_count})**: {n_text}")
            desc_parts.append(f"**Schwer ({s_count})**: {s_text}")
            # weitere technische Infos werden in list/preview separat gezeigt; hier bleibt es knapp
            embed.description = "\n".join(desc_parts)

        footer = f"Angefragt von: {author.display_name}"
        if footer_note:
            footer += f" • {footer_note}"
        embed.set_footer(text=footer)
        embed.timestamp = discord.utils.utcnow()

        return embed

    async def _post_or_edit(
        self,
        channel: discord.TextChannel,
        embed: discord.Embed,
        msg_id: Optional[int],
        *,
        target_id: Optional[int],
        autodelete_after_min: Optional[int] = None,
        intro_text: Optional[str] = None
    ) -> discord.Message:

        view = self._PingView(self)
        is_target = (target_id is not None) and (channel.id == target_id)

        # Nur im Zielchannel aufräumen (alte Bot-Posts mit Überschrift)
        if is_target:
            async for m in channel.history(limit=300):
                try:
                    if m.author == self.bot.user and isinstance(m.content, str) and "Muhhelfer – Übersicht" in m.content:
                        await m.delete()
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # Intro über dem Embed als Content:
        intro = None
        if intro_text:
            intro = f"{intro_text}\n\n{EMOJI_TITLE} Muhhelfer – Übersicht:"
        else:
            intro = f"{EMOJI_TITLE} Muhhelfer – Übersicht:"

        sent_message: Optional[discord.Message] = None
        try:
            if msg_id and is_target:
                old = await channel.fetch_message(int(msg_id))
                await old.edit(content=intro, embed=embed, view=view)
                sent_message = old
            else:
                sent_message = await channel.send(content=intro, embed=embed, view=view)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            sent_message = await channel.send(content=intro, embed=embed, view=view)

        # In Nicht-Zielchannels: optional Auto-Delete
        if not is_target:
            minutes = int(autodelete_after_min or 0)
            if minutes > 0 and sent_message:
                try:
                    await sent_message.delete(delay=minutes * 60)
                except Exception:
                    pass

        return sent_message

    # ---------------- Commands (nur Präfix) ----------------
    @commands.guild_only()
    @commands.group(name="muhhelfer", aliases=["triggerpost"], invoke_without_command=True)
    async def muhhelfer(self, ctx: commands.Context):
        prefix = (await self.bot.get_valid_prefixes(ctx.guild))[0]
        await ctx.send(
            "**📜 Commands:**\n"
            f"• `{prefix}muhhelfer post [min]` – Übersicht posten (Auto-Delete optional)\n"
            f"• `{prefix}muhhelfer addtrigger <text>` / `removetrigger <text>`\n"
            f"• `{prefix}muhhelfer list` – Einstellungen anzeigen\n"
            f"• `{prefix}muhhelfer refresh` – Übersicht im Zielchannel aktualisieren\n"
            f"• `{prefix}muhhelfer layout` / `layout <1-4>` / `layout preview <1-4>`\n"
            f"• `{prefix}muhhelfer setchannel #chan` · `setmessage <id>` · `cooldown <sek>` · `intro <text|clear>` · `autodelete <min>`\n"
        )

    @muhhelfer.command(name="post")
    async def manual_post(self, ctx: commands.Context, minutes: Optional[int] = None):
        guild = ctx.guild
        author = ctx.author
        data = await self.config.guild(guild).all()

        target_id = data.get("target_channel_id")
        if not target_id:
            return await ctx.send("⚠️ Kein Ziel-Channel gesetzt.")

        # Nur Server-Textkanäle
        if not isinstance(ctx.channel, discord.TextChannel):
            return await ctx.send("⚠️ Nur in Server-Textkanälen nutzbar.", delete_after=5)

        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offizier = any(r.id == ROLE_OFFIZIERE_BYPASS for r in getattr(author, "roles", []))

        # Normale User: nur im Zielchannel erlaubt
        if not (is_admin or is_offizier) and ctx.channel.id != target_id:
            target = guild.get_channel(target_id)
            return await ctx.send(f"⚠️ Bitte nutze den Befehl im {target.mention}.", delete_after=5)

        # Cooldown für Nicht-Bypass
        now = time.time()
        until = self._cooldown_until.get(ctx.channel.id, 0)
        if not (is_admin or is_offizier):
            cd = int(data.get("cooldown_seconds") or 30)
            if now < until:
                return
            self._cooldown_until[ctx.channel.id] = now + cd

        # Minuten-Override prüfen
        minutes_override = None
        if minutes is not None:
            if minutes < 0 or minutes > 1440:
                return await ctx.send("⚠️ Bitte Minuten zwischen 0 und 1440 angeben.")
            minutes_override = minutes

        # Auto-Delete (nur für Nicht-Zielchannel relevant)
        is_target = ctx.channel.id == target_id
        autodelete_conf = int(data.get("autodelete_minutes") or 0)
        autodelete_used = None if is_target else (minutes_override if minutes_override is not None else autodelete_conf)

        # Footer-Hinweis (nur außerhalb Zielchannel, wenn aktiv)
        footer_note = None
        if not is_target and autodelete_used and autodelete_used > 0:
            footer_note = f"Auto-Delete in {autodelete_used} Min"

        manual_info = None
        if (is_admin or is_offizier) and not is_target:
            manual_info = f"manuell ausgelöst von {author.display_name}"

        mode = int(data.get("layout_mode") or 1)
        embed = await self._build_embed(
            guild,
            author,
            manual_info=manual_info,
            footer_note=footer_note,
            mode=mode,
            intro_text=data.get("intro_text")
        )
        await self._post_or_edit(
            ctx.channel,
            embed,
            data.get("message_id"),
            target_id=target_id,
            autodelete_after_min=autodelete_used,
            intro_text=data.get("intro_text")
        )
        await ctx.send("✅ Muhhelfer-Nachricht gepostet.", delete_after=5)

    # --- Trigger-Verwaltung ---
    @muhhelfer.command(name="addtrigger")
    async def add_trigger(self, ctx: commands.Context, *, phrase: str):
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offizier = any(r.id == ROLE_OFFIZIERE_BYPASS for r in getattr(author, "roles", []))
        if not (is_admin or is_offizier):
            return await ctx.send("🚫 Du darfst diesen Befehl nicht verwenden.")

        phrase = (phrase or "").strip().casefold()
        if not phrase:
            return await ctx.send("⚠️ Leerer Trigger ist nicht erlaubt.")
        async with self.config.guild(ctx.guild).triggers() as t:
            if phrase in t:
                return await ctx.send("⚠️ Dieser Trigger existiert bereits.")
            t.append(phrase)
        await ctx.send(f"✅ Trigger hinzugefügt: `{phrase}`")

    @muhhelfer.command(name="removetrigger")
    async def remove_trigger(self, ctx: commands.Context, *, phrase: str):
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offizier = any(r.id == ROLE_OFFIZIERE_BYPASS for r in getattr(author, "roles", []))
        if not (is_admin or is_offizier):
            return await ctx.send("🚫 Du darfst diesen Befehl nicht verwenden.")

        phrase = (phrase or "").strip().casefold()
        async with self.config.guild(ctx.guild).triggers() as t:
            if phrase not in t:
                return await ctx.send("⚠️ Trigger nicht gefunden.")
            t.remove(phrase)
        await ctx.send(f"🗑️ Trigger entfernt: `{phrase}`")

    @muhhelfer.command(name="list")
    async def list_triggers(self, ctx: commands.Context):
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offizier = any(r.id == ROLE_OFFIZIERE_BYPASS for r in getattr(author, "roles", []))
        if not (is_admin or is_offizier):
            return await ctx.send("🚫 Du darfst diesen Befehl nicht verwenden.")

        data = await self.config.guild(ctx.guild).all()
        triggers = ", ".join(f"`{x}`" for x in data.get("triggers", [])) or "—"
        ch = ctx.guild.get_channel(data.get("target_channel_id")) if data.get("target_channel_id") else None
        layout_mode = int(data.get("layout_mode") or 1)
        layout_name = {1: "Standard", 2: "Kompakt", 3: "Event", 4: "Admin/Debug"}.get(layout_mode, "Standard")

        commands_block = (
            "**📜 Commands (Präfix):**\n"
            "• `muhhelfer post [min]` – Embed posten (Offis/Admins überall; User nur im Zielchannel). Optional Auto-Delete-Minuten.\n"
            "• `muhhelfer addtrigger <text>` – Trigger hinzufügen (mit `+` für UND).\n"
            "• `muhhelfer removetrigger <text>` – Trigger entfernen.\n"
            "• `muhhelfer list` – Diese Übersicht.\n"
            "• `muhhelfer refresh` – Embed im Zielchannel neu aufbauen.\n"
            "• `muhhelfer layout` · `layout <1-4>` · `layout preview <1-4>`\n"
            "• `muhhelfer setchannel #channel` · `setmessage <id>` · `cooldown <sek>` · `intro <text|clear>` · `autodelete <min>`\n"
        )

        await ctx.send(
            f"**Trigger:** {triggers}\n"
            f"**Ziel-Channel:** {ch.mention if ch else '— nicht gesetzt —'}\n"
            f"**Message-ID:** `{data.get('message_id')}`\n"
            f"**Cooldown:** {data.get('cooldown_seconds')}s\n"
            f"**Auto-Delete (andere Channels):** {data.get('autodelete_minutes', 0)} min\n"
            f"**Layout:** {layout_name} ({layout_mode})\n"
            f"**Bypass-Rolle:** <@&{ROLE_OFFIZIERE_BYPASS}>\n"
            f"**Intro:** {data.get('intro_text') or '— kein Text —'}\n\n"
            f"{commands_block}"
        )

    @muhhelfer.command(name="refresh")
    async def refresh_list(self, ctx: commands.Context):
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offizier = any(r.id == ROLE_OFFIZIERE_BYPASS for r in getattr(author, "roles", []))
        if not (is_admin or is_offizier):
            return await ctx.send("🚫 Du darfst diesen Befehl nicht verwenden.")

        data = await self.config.guild(ctx.guild).all()
        target_id = data.get("target_channel_id")
        if not target_id:
            return await ctx.send("⚠️ Kein Ziel-Channel gesetzt.")
        channel = ctx.guild.get_channel(target_id)
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("⚠️ Ziel-Channel ist kein Textkanal.", delete_after=5)

        mode = int(data.get("layout_mode") or 1)
        embed = await self._build_embed(ctx.guild, ctx.author, mode=mode, intro_text=data.get("intro_text"))
        await self._post_or_edit(channel, embed, data.get("message_id"), target_id=target_id, intro_text=data.get("intro_text"))
        await ctx.send("✅ Muhhelfer-Liste aktualisiert.", delete_after=5)

    # --- Layout-Management ---
    @muhhelfer.command(name="layout")
    async def layout_cmd(self, ctx: commands.Context, action: Optional[str] = None, arg: Optional[str] = None):
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offizier = any(r.id == ROLE_OFFIZIERE_BYPASS for r in getattr(author, "roles", []))
        if not (is_admin or is_offizier):
            return await ctx.send("🚫 Du darfst diesen Befehl nicht verwenden.")

        data = await self.config.guild(ctx.guild).all()

        # No args -> show help/current
        if action is None:
            mode = int(data.get("layout_mode") or 1)
            name = {1: "Standard", 2: "Kompakt", 3: "Event", 4: "Admin/Debug"}.get(mode, "Standard")
            return await ctx.send(
                f"Aktuelles Layout: **{name} ({mode})**\n"
                f"Verfügbare Layouts: `1` – Standard · `2` – Kompakt · `3` – Event · `4` – Admin/Debug\n"
                f"• `muhhelfer layout <1-4>` – Layout wechseln\n"
                f"• `muhhelfer layout preview <1-4>` – Vorschau anzeigen"
            )

        if action.lower() == "preview":
            if not arg or not arg.isdigit():
                return await ctx.send("⚠️ Bitte `muhhelfer layout preview <1-4>` verwenden.")
            mode = max(1, min(4, int(arg)))
            embed = await self._build_embed(
                ctx.guild, ctx.author, mode=mode, intro_text=(await self.config.guild(ctx.guild).intro_text())
            )
            await ctx.send(embed=embed, delete_after=25)
            return

        # Otherwise treat as mode switch
        if action.isdigit():
            mode = max(1, min(4, int(action)))
            await self.config.guild(ctx.guild).layout_mode.set(mode)
            name = {1: "Standard", 2: "Kompakt", 3: "Event", 4: "Admin/Debug"}.get(mode, "Standard")
            return await ctx.send(f"✅ Layout geändert auf **{name} ({mode})**")
        else:
            return await ctx.send("⚠️ Unbekannter Parameter. Nutze `muhhelfer layout`, `muhhelfer layout <1-4>` oder `muhhelfer layout preview <1-4>`.")

    # --- Admin-only: Setup ---
    @muhhelfer.command(name="setchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        if not channel or not isinstance(channel, discord.TextChannel):
            return await ctx.send("⚠️ Bitte gib einen **Text**-Channel an.")
        await self.config.guild(ctx.guild).target_channel_id.set(channel.id)
        await ctx.send(f"📍 Ziel-Channel gesetzt: {channel.mention}")

    @muhhelfer.command(name="setmessage")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_message(self, ctx: commands.Context, message_id: Optional[int] = None):
        await self.config.guild(ctx.guild).message_id.set(message_id)
        await ctx.send(f"🧷 Message-ID gesetzt: `{message_id}`")

    @muhhelfer.command(name="cooldown")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_cooldown(self, ctx: commands.Context, seconds: int):
        if seconds < 0 or seconds > 3600:
            return await ctx.send("⚠️ Bitte 0–3600 Sekunden.")
        await self.config.guild(ctx.guild).cooldown_seconds.set(seconds)
        await ctx.send(f"⏱️ Cooldown gesetzt: {seconds}s")

    @muhhelfer.command(name="intro")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_intro(self, ctx: commands.Context, *, text: Optional[str] = None):
        if text is None:
            intro = await self.config.guild(ctx.guild).intro_text()
            return await ctx.send(f"📜 Aktuell: {intro or '— kein Text —'}")
        if text.lower() in ("clear", "none", "off"):
            await self.config.guild(ctx.guild).intro_text.set(None)
            return await ctx.send("🧹 Intro gelöscht.")
        await self.config.guild(ctx.guild).intro_text.set(text)
        await ctx.send(f"✅ Intro gesetzt auf:\n> {text}")

    @muhhelfer.command(name="autodelete")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_autodelete(self, ctx: commands.Context, minutes: int):
        if minutes < 0 or minutes > 1440:
            return await ctx.send("⚠️ Bitte 0–1440 Minuten.")
        await self.config.guild(ctx.guild).autodelete_minutes.set(minutes)
        await ctx.send(f"🗑️ Auto-Delete (außerhalb Zielchannel): **{minutes} min**")

    # --- Listener für Trigger ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        # Nur Server-Textkanäle unterstützen
        if not isinstance(message.channel, discord.TextChannel):
            return

        guild = message.guild
        data = await self.config.guild(guild).all()
        target_id = data.get("target_channel_id")
        if not target_id or message.channel.id != target_id:
            return

        content = (message.content or "").casefold()
        matched = False
        for trigger in data.get("triggers", []):
            if "+" in trigger:
                parts = [p.strip() for p in trigger.split("+") if p.strip()]
                if parts and all(p in content for p in parts):
                    matched = True
                    break
            elif trigger in content:
                matched = True
                break
        if not matched:
            return

        now = time.time()
        until = self._cooldown_until.get(message.channel.id, 0)
        author = message.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        has_bypass = any(r.id == ROLE_OFFIZIERE_BYPASS for r in getattr(author, "roles", []))
        if not (is_admin or has_bypass):
            cd = int(data.get("cooldown_seconds") or 30)
            if now < until:
                return
            self._cooldown_until[message.channel.id] = now + cd

        mode = int(data.get("layout_mode") or 1)
        embed = await self._build_embed(guild, author, mode=mode, intro_text=data.get("intro_text"))
        await self._post_or_edit(message.channel, embed, data.get("message_id"), target_id=target_id, intro_text=data.get("intro_text"))
