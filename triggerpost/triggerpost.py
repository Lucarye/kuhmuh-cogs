# triggerpost/triggerpost.py
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

DEFAULT_GUILD = {
    "triggers": ["hilfe"],
    "target_channel_id": None,
    "message_id": None,
    "cooldown_seconds": 30,
    "intro_text": "Oh, es scheint du brauchst einen Muhhelfer bei deinen Bossen? :muhkuh:",
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
    async def _build_embed(self, guild: discord.Guild, author: discord.Member) -> discord.Embed:
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
        embed = discord.Embed(
            title=f"{EMOJI_TITLE} Muhhelfer – Übersicht",
            description=desc,
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Angefragt von: {author.display_name}")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def _post_or_edit(self, channel, embed, msg_id):
        view = self._PingView(self)
        data = await self.config.guild(channel.guild).all()
        intro = f"{data.get('intro_text')}\n\n🔔 Muhhelfer – Übersicht:" if data.get("intro_text") else "🔔 Muhhelfer – Übersicht:"
        try:
            if msg_id:
                msg = await channel.fetch_message(int(msg_id))
                await msg.edit(content=intro, embed=embed, view=view)
            else:
                await channel.send(content=intro, embed=embed, view=view)
        except (discord.NotFound, discord.Forbidden):
            await channel.send(content=intro, embed=embed, view=view)

    # ========= Commands =========
    @commands.guild_only()
    @commands.group(name="muhhelfer", aliases=["triggerpost"])
    async def muhhelfer(self, ctx):
        """Muhhelfer-Tools und Konfiguration."""
        pass

    # --- Admin/Offizier ---
    @muhhelfer.command(name="addtrigger")
    async def add_trigger(self, ctx, *, phrase: str):
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
    async def list_triggers(self, ctx):
        """Zeigt aktuelle Trigger, Channel, Cooldown und Introtext."""
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
            f"**Bypass-Rolle:** <@&{ROLE_OFFIZIERE_BYPASS}>\n"
            f"**Intro:** {data['intro_text'] or '— kein Text —'}"
        )

    @muhhelfer.command(name="refresh")
    async def refresh_list(self, ctx):
        """Baut das Muhhelfer-Embed neu und aktualisiert die gespeicherte Nachricht."""
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
        await self._post_or_edit(channel, embed, data["message_id"])
        await ctx.send("✅ Muhhelfer-Liste aktualisiert.", delete_after=5)

    # --- Admin-only ---
    @muhhelfer.command(name="setchannel")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_channel(self, ctx, channel: discord.TextChannel = None):
        if not channel:
            return await ctx.send("⚠️ Bitte gib einen Channel an.")
        await self.config.guild(ctx.guild).target_channel_id.set(channel.id)
        await ctx.send(f"📍 Ziel-Channel gesetzt: {channel.mention}")

    @muhhelfer.command(name="intro")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_intro(self, ctx, *, text: str = None):
        if not text:
            intro = await self.config.guild(ctx.guild).intro_text()
            return await ctx.send(f"📜 Aktuell: {intro or '— kein Text —'}")
        if text.lower() in ("clear", "none", "off"):
            await self.config.guild(ctx.guild).intro_text.set(None)
            return await ctx.send("🧹 Intro gelöscht.")
        await self.config.guild(ctx.guild).intro_text.set(text)
        await ctx.send(f"✅ Intro gesetzt auf:\n> {text}")

    @muhhelfer.command(name="cooldown")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_cooldown(self, ctx, seconds: int):
        if seconds < 0 or seconds > 3600:
            return await ctx.send("⚠️ Bitte 0–3600 Sekunden.")
        await self.config.guild(ctx.guild).cooldown_seconds.set(seconds)
        await ctx.send(f"⏱️ Cooldown gesetzt: {seconds}s")

    # --- Öffentlicher Post ---
    @muhhelfer.command(name="post")
    async def manual_post(self, ctx):
        """Postet die Muhhelfer-Nachricht (für alle, im Ziel-Channel, mit Cooldown)."""
        guild = ctx.guild
        data = await self.config.guild(guild).all()
        target_id = data["target_channel_id"]
        if not target_id:
            return await ctx.send("⚠️ Kein Ziel-Channel gesetzt.")
        if ctx.channel.id != target_id:
            target = guild.get_channel(target_id)
            return await ctx.send(f"⚠️ Bitte nutze den Befehl im {target.mention}.", delete_after=5)

        now = time.time()
        until = self._cooldown_until.get(ctx.channel.id, 0)
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        has_bypass = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
        if not (is_admin or has_bypass):
            cd = (await self.config.guild(guild).cooldown_seconds())
            if now < until:
                return
            self._cooldown_until[ctx.channel.id] = now + cd

        embed = await self._build_embed(guild, author)
        await self._post_or_edit(ctx.channel, embed, data["message_id"])
        await ctx.send("✅ Muhhelfer-Nachricht gepostet.", delete_after=5)

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
        await self._post_or_edit(message.channel, embed, data["message_id"])
