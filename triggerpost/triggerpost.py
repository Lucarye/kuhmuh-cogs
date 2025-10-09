import time
import discord
from discord import ui, AllowedMentions
from redbot.core import commands, Config
from redbot.core.bot import Red

# ====== Server-spezifische IDs ======
ROLE_NORMAL = 1424768638157852682            # Muhhelfer – Normal
ROLE_SCHWER = 1424769286790054050            # Muhhelfer – Schwer
ROLE_OFFIZIERE_BYPASS = 1198652039312453723  # Offiziere: Bypass + erweiterte Rechte

# Custom Emojis
EMOJI_TITLE = "<:muhkuh:1207038544510586890>"
EMOJI_NORMAL = discord.PartialEmoji(name="muh_normal", id=1424467460228124803)
EMOJI_SCHWER = discord.PartialEmoji(name="muh_schwer", id=1424467458118647849)

# Muhkuh-Bild (Thumbnail oben rechts)
MUHKU_THUMBNAIL = "https://cdn.discordapp.com/attachments/1404063753946796122/1404063845491671160/muhku.png?ex=68e8451b&is=68e6f39b&hm=92c4de08b4562cdb9779ffaf1177dfa141515658028cd9335a29f2670618c9c0&"

DEFAULT_GUILD = {
    "triggers": ["hilfe"],
    "target_channel_id": None,
    "message_id": None,
    "cooldown_seconds": 30,
    "intro_text": "Oh, es scheint du brauchst einen Muhhelfer bei deinen Bossen? <:muhkuh:1207038544510586890>:",
    "autodelete_minutes": 10,  # Posts außerhalb des Zielchannels werden nach X Minuten gelöscht (0 = aus)
}


class TriggerPost(commands.Cog):
    """Muhhelfer-System mit Triggern, Embed, Buttons und Pings."""

    _ping_cd_until: dict[int, float] = {}

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=81521025, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)
        self._cooldown_until = {}

    # ========= Buttons =========
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
        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user
        if not channel or not guild:
            return await interaction.response.send_message("⚠️ Nur in Server-Channels nutzbar.", ephemeral=True)

        is_admin = user.guild_permissions.administrator or user.guild_permissions.manage_guild
        has_bypass = any(r.id == ROLE_OFFIZIERE_BYPASS for r in getattr(user, "roles", []))

        now = time.time()
        until = self._ping_cd_until.get(channel.id, 0)
        PING_CD = 60
        if not (is_admin or has_bypass):
            if now < until:
                remaining = int(until - now)
                return await interaction.response.send_message(
                    f"⏱️ Bitte warte **{remaining}s**, bevor erneut gepingt wird.",
                    ephemeral=True,
                )
            self._ping_cd_until[channel.id] = now + PING_CD

        role_mention = f"<@&{role_id}>"
        content = f"🔔 {role_mention} – angefragt von {user.mention}"
        await interaction.response.send_message(
            content, allowed_mentions=AllowedMentions(roles=True, users=True, everyone=False)
        )

    # ========= Embed Builder =========
    async def _build_embed(self, guild: discord.Guild, author: discord.Member, manual_info: str | None = None) -> discord.Embed:
        try:
            await guild.chunk()
        except Exception:
            pass

        def online_members(role_id: int):
            role = guild.get_role(role_id)
            if not role:
                return []
            members = [
                m for m in role.members
                if getattr(m, "status", discord.Status.offline) in (
                    discord.Status.online, discord.Status.idle, discord.Status.dnd
                )
            ]
            members.sort(key=lambda x: x.display_name.lower())
            return members

        normal = online_members(ROLE_NORMAL)
        schwer = online_members(ROLE_SCHWER)

        def section(name, members):
            if not members:
                return f"{name}:\n– aktuell niemand –"
            return f"{name}:\n" + "\n".join(m.mention for m in members)

        desc = f"{section('Muhhelfer – normal', normal)}\n\n{section('Muhhelfer – schwer', schwer)}"

        title_text = f"{EMOJI_TITLE} Muhhelfer – Übersicht"
        if manual_info:
            title_text += f"\n*({manual_info})*"

        embed = discord.Embed(
            title=title_text,
            description=desc,
            color=discord.Color.blue(),
        )

        # 🖼️ Muhkuh als Thumbnail oben rechts
        embed.set_thumbnail(url=MUHKU_THUMBNAIL)

        embed.set_footer(text=f"Angefragt von: {author.display_name}")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def _post_or_edit(self, channel: discord.TextChannel, embed: discord.Embed, msg_id: int | None, *, target_id: int | None) -> discord.Message:
        """Postet/editiert die Nachricht.
        - Im Zielchannel: alte Muhhelfer-Posts des Bots automatisch löschen
        - In anderen Channels: nichts löschen; ggf. Auto-Delete nach X Minuten
        """
        view = self._PingView(self)
        data = await self.config.guild(channel.guild).all()
        intro = (
            f"{data.get('intro_text')}\n\n{EMOJI_TITLE} Muhhelfer – Übersicht:"
            if data.get("intro_text")
            else f"{EMOJI_TITLE} Muhhelfer – Übersicht:"
        )

        is_target = (target_id is not None) and (channel.id == target_id)

        # Nur im Zielchannel aufräumen
        if is_target:
            # Alte Muhhelfer-Posts (vom Bot) im Zielchannel löschen – bis zu 500 Nachrichten
            async for m in channel.history(limit=500):
                if m.author == self.bot.user and "Muhhelfer – Übersicht" in (m.content or ""):
                    try:
                        await m.delete()
                    except discord.Forbidden:
                        pass

        # Posten / Editieren
        sent_message: discord.Message | None = None
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
            minutes = int(data.get("autodelete_minutes") or 0)
            if minutes > 0 and sent_message:
                try:
                    await sent_message.delete(delay=minutes * 60)
                except Exception:
                    pass

        return sent_message

    # ========= Commands =========
    @commands.guild_only()
    @commands.group(name="muhhelfer", aliases=["triggerpost"])
    async def muhhelfer(self, ctx: commands.Context):
        """Muhhelfer-Tools und Konfiguration."""
        pass

    # --- Öffentlicher Post (überall für Offis/Admins) ---
    @muhhelfer.command(name="post")
    async def manual_post(self, ctx: commands.Context):
        """Postet die Muhhelfer-Nachricht.
        - Admins/Offiziere dürfen überall posten
        - Normale Mitglieder nur im Zielchannel (mit Cooldown)
        """
        guild = ctx.guild
        author = ctx.author
        data = await self.config.guild(guild).all()
        target_id = data["target_channel_id"]
        if not target_id:
            return await ctx.send("⚠️ Kein Ziel-Channel gesetzt.")

        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offizier = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)

        # Normale User: nur im Zielchannel erlaubt
        if not (is_admin or is_offizier):
            if ctx.channel.id != target_id:
                target = guild.get_channel(target_id)
                return await ctx.send(f"⚠️ Bitte nutze den Befehl im {target.mention}.", delete_after=5)

        # Cooldown für Nicht-Bypass (wie beim Trigger)
        now = time.time()
        until = self._cooldown_until.get(ctx.channel.id, 0)
        if not (is_admin or is_offizier):
            cd = (await self.config.guild(guild).cooldown_seconds())
            if now < until:
                return
            self._cooldown_until[ctx.channel.id] = now + cd

        # Embed bauen & posten
        manual_info = None
        if (is_admin or is_offizier) and ctx.channel.id != target_id:
            manual_info = f"manuell ausgelöst von {author.display_name}"

        embed = await self._build_embed(guild, author, manual_info)
        await self._post_or_edit(ctx.channel, embed, data["message_id"], target_id=target_id)
        await ctx.send("✅ Muhhelfer-Nachricht gepostet.", delete_after=5)

    # --- Admin/Offizier: Trigger & Übersicht ---
    @muhhelfer.command(name="addtrigger")
    async def add_trigger(self, ctx: commands.Context, *, phrase: str):
        """Fügt einen Trigger hinzu. '+' verbindet Wörter (z. B. 'loml+hard')."""
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offizier = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
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

    @muhhelfer.command(name="list")
    async def list_triggers(self, ctx: commands.Context):
        """Zeigt aktuelle Trigger, Channel, Cooldown, Introtext und Auto-Delete-Minuten."""
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offizier = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
        if not (is_admin or is_offizier):
            return await ctx.send("🚫 Du darfst diesen Befehl nicht verwenden.")

        data = await self.config.guild(ctx.guild).all()
        triggers = ", ".join(f"`{x}`" for x in data["triggers"]) or "—"
        ch = ctx.guild.get_channel(data["target_channel_id"]) if data["target_channel_id"] else None
        await ctx.send(
            f"**Trigger:** {triggers}\n"
            f"**Ziel-Channel:** {ch.mention if ch else '— nicht gesetzt —'}\n"
            f"**Message-ID:** `{data['message_id']}`\n"
            f"**Cooldown:** {data['cooldown_seconds']}s\n"
            f"**Auto-Delete (andere Channels):** {data.get('autodelete_minutes', 0)} min\n"
            f"**Bypass-Rolle:** <@&{ROLE_OFFIZIERE_BYPASS}>\n"
            f"**Intro:** {data['intro_text'] or '— kein Text —'}"
        )

    @muhhelfer.command(name="refresh")
    async def refresh_list(self, ctx: commands.Context):
        """Baut das Muhhelfer-Embed neu und aktualisiert die gespeicherte Nachricht (Admins/Offiziere)."""
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offizier = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
        if not (is_admin or is_offizier):
            return await ctx.send("🚫 Du darfst diesen Befehl nicht verwenden.")

        data = await self.config.guild(ctx.guild).all()
        target_id = data["target_channel_id"]
        if not target_id:
            return await ctx.send("⚠️ Kein Ziel-Channel gesetzt.")
        channel = ctx.guild.get_channel(target_id)
        embed = await self._build_embed(ctx.guild, ctx.author)
        await self._post_or_edit(channel, embed, data["message_id"], target_id=target_id)
        await ctx.send("✅ Muhhelfer-Liste aktualisiert.", delete_after=5)

    # --- Admin-only: Setup ---
    @muhhelfer.command(name="setchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        if not channel:
            return await ctx.send("⚠️ Bitte gib einen Channel an.")
        await self.config.guild(ctx.guild).target_channel_id.set(channel.id)
        await ctx.send(f"📍 Ziel-Channel gesetzt: {channel.mention}")

    @muhhelfer.command(name="setmessage")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_message(self, ctx: commands.Context, message_id: int = None):
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
    async def set_intro(self, ctx: commands.Context, *, text: str = None):
        if not text:
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
        """Setzt Auto-Delete für Posts außerhalb des Zielchannels (0 = aus)."""
        if minutes < 0 or minutes > 1440:
            return await ctx.send("⚠️ Bitte 0–1440 Minuten.")
        await self.config.guild(ctx.guild).autodelete_minutes.set(minutes)
        await ctx.send(f"🗑️ Auto-Delete (außerhalb Zielchannel): **{minutes} min**")

    # --- Listener für Trigger ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        guild = message.guild
        data = await self.config.guild(guild).all()
        target_id = data["target_channel_id"]
        if not target_id or message.channel.id != target_id:
            return

        content = message.content.casefold()
        matched = False
        for trigger in data["triggers"]:
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
        has_bypass = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
        if not (is_admin or has_bypass):
            cd = data.get("cooldown_seconds", 30)
            if now < until:
                return
            self._cooldown_until[message.channel.id] = now + cd

        embed = await self._build_embed(guild, author)
        await self._post_or_edit(message.channel, embed, data["message_id"], target_id=target_id)
