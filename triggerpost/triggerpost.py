# triggerpost/triggerpost.py
import time
import discord
from discord import ui, AllowedMentions
from redbot.core import commands, Config
from redbot.core.bot import Red

# ====== Server-spezifische IDs (gemerkt) ======
ROLE_NORMAL = 1424768638157852682            # Muhhelfer – Normal
ROLE_SCHWER = 1424769286790054050            # Muhhelfer – Schwer
ROLE_OFFIZIERE_BYPASS = 1198652039312453723  # Offiziere: Cooldown-Bypass

# Custom Emojis (nur dein :muhkuh:)
EMOJI_TITLE = "<:muhkuh:1207038544510586890>"
EMOJI_NORMAL = discord.PartialEmoji(name="muh_normal", id=1424467460228124803)
EMOJI_SCHWER = discord.PartialEmoji(name="muh_schwer", id=1424467458118647849)

DEFAULT_GUILD = {
    "triggers": ["hilfe"],                  # weitere Trigger per Command hinzufügen (+ für UND)
    "target_channel_id": None,              # MUSS gesetzt werden
    "message_id": None,                     # optional: bestehende Nachricht zum Editieren
    "cooldown_seconds": 30,                 # Text-Trigger-Cooldown
    "intro_text": "Oh, es scheint du brauchst einen Muhhelfer bei deinen Bossen? :muhkuh:",
}

class TriggerPost(commands.Cog):
    """Muhhelfer-Übersicht bei Triggern (nur online Mitglieder) + Ping-Buttons & Intro."""

    _ping_cd_until: dict[int, float] = {}

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=81521025, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)
        self._cooldown_until = {}  # channel_id -> timestamp

    # ========= Buttons / View =========
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
        """Pingt eine Rolle mit Cooldown & Bypass."""
        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user

        if not channel or not guild:
            return await interaction.response.send_message("⚠️ Nur in Server-Channels nutzbar.", ephemeral=True)

        # Bypass prüfen
        is_admin = user.guild_permissions.administrator or user.guild_permissions.manage_guild
        has_bypass_role = any(r.id == ROLE_OFFIZIERE_BYPASS for r in getattr(user, "roles", []))

        # Cooldown (pro Channel) – nur für Nicht-Bypass
        now = time.time()
        until = self._ping_cd_until.get(channel.id, 0)
        PING_CD = 60
        if not (is_admin or has_bypass_role):
            if now < until:
                remaining = int(until - now)
                try:
                    return await interaction.response.send_message(
                        f"⏱️ Bitte warte **{remaining}s**, bevor erneut gepingt wird.",
                        ephemeral=True,
                    )
                except Exception:
                    return
            self._ping_cd_until[channel.id] = now + PING_CD

        # Ping senden
        role_mention = f"<@&{role_id}>"
        content = f"🔔 {role_mention} – angefragt von {user.mention}"
        try:
            await interaction.response.send_message(
                content,
                allowed_mentions=AllowedMentions(roles=True, users=True, everyone=False),
            )
        except discord.InteractionResponded:
            await channel.send(
                content,
                allowed_mentions=AllowedMentions(roles=True, users=True, everyone=False),
            )

    # ========= Helpers =========
    async def _build_embed(self, guild: discord.Guild, author: discord.Member) -> discord.Embed:
        """Baut das Embed (nur online/idle/dnd) und formatiert die Abschnitte."""
        # Presence/Member-Intents im Dev-Portal aktivieren!
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

        normal_list = online_members(ROLE_NORMAL)
        schwer_list = online_members(ROLE_SCHWER)

        def section(name_lower: str, members):
            if not members:
                return f"{name_lower}:\n– aktuell niemand –"
            lines = "\n".join(m.mention for m in members)
            return f"{name_lower}:\n{lines}"

        desc = (
            f"{section('Muhhelfer – normal', normal_list)}\n\n"
            f"{section('Muhhelfer – schwer', schwer_list)}"
        )

        embed = discord.Embed(
            title=f"{EMOJI_TITLE} Muhhelfer – Übersicht",
            description=desc,
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Angefragt von: {author.display_name}")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def _post_or_edit(self, channel: discord.TextChannel, embed: discord.Embed, msg_id: int | None):
        """Postet ein neues Embed oder editiert eine bestehende Nachricht-ID – mit Buttons und optionalem Intro-Text."""
        view = self._PingView(self)
        data = await self.config.guild(channel.guild).all()
        intro_text = data.get("intro_text") or ""
        if intro_text:
            intro = f"{intro_text}\n\n🔔 Muhhelfer – Übersicht:"
        else:
            intro = "🔔 Muhhelfer – Übersicht:"

        try:
            if msg_id:
                old = await channel.fetch_message(int(msg_id))
                await old.edit(content=intro, embed=embed, view=view)
            else:
                await channel.send(content=intro, embed=embed, view=view)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            await channel.send(content=intro, embed=embed, view=view)

    # ========= Commands (Gruppe jetzt 'muhhelfer') =========
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.group(name="muhhelfer", aliases=["triggerpost"])
    async def muhhelfer(self, ctx: commands.Context):
        """Konfiguration & Tools für den Muhhelfer-Post."""
        pass

    @muhhelfer.command(name="addtrigger")
    async def add_trigger(self, ctx: commands.Context, *, phrase: str):
        """Fügt einen Trigger hinzu. '+' verbindet UND-Kombinationen (z. B. 'loml+hard')."""
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
        phrase = (phrase or "").strip().casefold()
        async with self.config.guild(ctx.guild).triggers() as t:
            if phrase not in t:
                return await ctx.send("⚠️ Trigger nicht gefunden.")
            t.remove(phrase)
        await ctx.send(f"🗑️ Trigger entfernt: `{phrase}`")

    @muhhelfer.command(name="list")
    async def list_triggers(self, ctx: commands.Context):
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

    @muhhelfer.command(name="setchannel")
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        if channel is None:
            return await ctx.send("⚠️ Bitte gib einen Channel an, z. B. `°muhhelfer setchannel #bot-test`.")
        await self.config.guild(ctx.guild).target_channel_id.set(channel.id)
        await ctx.send(f"📍 Ziel-Channel gesetzt: {channel.mention}")

    @muhhelfer.command(name="setmessage")
    async def set_message(self, ctx: commands.Context, message_id: int = None):
        await self.config.guild(ctx.guild).message_id.set(message_id)
        await ctx.send(f"🧷 Message-ID gesetzt: `{message_id}`")

    @muhhelfer.command(name="cooldown")
    async def set_cooldown(self, ctx: commands.Context, seconds: int):
        if seconds < 0 or seconds > 3600:
            return await ctx.send("⚠️ Bitte 0–3600 Sekunden.")
        await self.config.guild(ctx.guild).cooldown_seconds.set(seconds)
        await ctx.send(f"⏱️ Cooldown gesetzt: **{seconds}s**")

    @muhhelfer.command(name="intro")
    async def set_intro(self, ctx: commands.Context, *, text: str = None):
        """Setzt oder löscht den Intro-Text (vor dem Embed)."""
        if not text:
            data = await self.config.guild(ctx.guild).intro_text()
            if not data:
                return await ctx.send("ℹ️ Kein Intro-Text gesetzt.")
            return await ctx.send(f"📜 Aktueller Intro-Text:\n> {data}")

        if text.lower() in ("clear", "none", "off"):
            await self.config.guild(ctx.guild).intro_text.set(None)
            return await ctx.send("🧹 Intro-Text gelöscht.")

        await self.config.guild(ctx.guild).intro_text.set(text)
        await ctx.send(f"✅ Intro-Text gesetzt auf:\n> {text}")

    @muhhelfer.command(name="refresh")
    async def refresh_list(self, ctx: commands.Context):
        """Baut Embed neu und editiert die gespeicherte Nachricht (falls gesetzt)."""
        author: discord.Member = ctx.author
        guild: discord.Guild = ctx.guild

        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        has_bypass_role = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
        if not (is_admin or has_bypass_role):
            return await ctx.send("🚫 Du darfst diesen Befehl nicht ausführen.", delete_after=5)

        data = await self.config.guild(guild).all()
        target_id = data["target_channel_id"]
        if not target_id:
            return await ctx.send("⚠️ Kein Ziel-Channel gesetzt. `°muhhelfer setchannel #bot-test`")
        channel = guild.get_channel(target_id)
        if not channel:
            return await ctx.send("⚠️ Ziel-Channel nicht gefunden oder keine Rechte.")

        embed = await self._build_embed(guild, author)
        await self._post_or_edit(channel, embed, data["message_id"])
        await ctx.send("✅ Muhhelfer-Liste aktualisiert.", delete_after=5)

    @muhhelfer.command(name="buttons")
    async def post_buttons(self, ctx: commands.Context):
        """Postet nur die Ping-Buttons im Ziel-Channel."""
        data = await self.config.guild(ctx.guild).all()
        target_id = data["target_channel_id"]
        if not target_id:
            return await ctx.send("⚠️ Kein Ziel-Channel gesetzt. `°muhhelfer setchannel #bot-test`")
        channel = ctx.guild.get_channel(target_id) or ctx.channel
        await channel.send("🔘 **Muhhelfer-Buttons:**", view=self._PingView(self))
        await ctx.send("✅ Buttons gepostet.", delete_after=5)

    @muhhelfer.command(name="post")
    async def manual_post(self, ctx: commands.Context):
        """Postet die Muhhelfer-Nachricht sofort im Ziel-Channel (Intro + Embed + Buttons)."""
        data = await self.config.guild(ctx.guild).all()
        target_id = data["target_channel_id"]
        if not target_id:
            return await ctx.send("⚠️ Kein Ziel-Channel gesetzt. `°muhhelfer setchannel #bot-test`")
        channel = ctx.guild.get_channel(target_id)
        if not channel:
            return await ctx.send("⚠️ Ziel-Channel nicht gefunden oder keine Rechte.")
        embed = await self._build_embed(ctx.guild, ctx.author)
        await self._post_or_edit(channel, embed, data["message_id"])
        await ctx.send(f"✅ Muhhelfer-Nachricht im {channel.mention} gepostet.", delete_after=5)

    # ========= Listener =========
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Bots/DMs ignorieren
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        data = await self.config.guild(guild).all()

        # Nur im gesetzten Channel reagieren
        target_id = data["target_channel_id"]
        if not target_id or message.channel.id != target_id:
            return

        # Trigger prüfen – unterstützt UND-Kombinationen via "+"
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

        # Cooldown (still); Admin/Manage_Guild/Offiziere bypass
        now = time.time()
        until = self._cooldown_until.get(message.channel.id, 0)
        is_admin = (
            message.author.guild_permissions.administrator
            or message.author.guild_permissions.manage_guild
        )
        has_bypass_role = any(r.id == ROLE_OFFIZIERE_BYPASS for r in message.author.roles)
        if not (is_admin or has_bypass_role):
            cd = data.get("cooldown_seconds", 30)
            if now < until:
                return  # still: keine Nachricht
            self._cooldown_until[message.channel.id] = now + cd

        # Embed bauen & posten/aktualisieren (mit Buttons)
        embed = await self._build_embed(guild, message.author)
        await self._post_or_edit(message.channel, embed, data["message_id"])
