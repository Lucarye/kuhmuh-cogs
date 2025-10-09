# triggerpost/triggerpost.py
import time
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red

# ====== Server-spezifische IDs ======
ROLE_NORMAL = 1424769286790054050            # Muhhelfer – Normal
ROLE_SCHWER = 1424768638157852682            # Muhhelfer – Schwer
ROLE_OFFIZIERE_BYPASS = 1198652039312453723  # Offiziere: Cooldown-Bypass

DEFAULT_GUILD = {
    "triggers": ["hilfe"],       # weitere Trigger per Command hinzufügen
    "target_channel_id": None,   # MUSS gesetzt werden (Channel, in dem getriggert wird)
    "message_id": None,          # optional: bestehende Nachricht zum Editieren
    "cooldown_seconds": 30,      # Standard-Cooldown
}

class TriggerPost(commands.Cog):
    """Postet/aktualisiert eine Muhhelfer-Übersicht bei Triggerwörtern (nur online Mitglieder)."""

    def __init__(self, bot: Red):
        self.bot = bot
        # Achtung: identifier muss eine gültige Ganzzahl/Hex sein.
        self.config = Config.get_conf(self, identifier=81521025, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)
        self._cooldown_until = {}  # channel_id -> timestamp

    # ========= Helpers =========
    async def _build_embed(self, guild: discord.Guild, author: discord.Member) -> discord.Embed:
        """Baut das Embed (nur online/idle/dnd) und formatiert die Abschnitte."""
        # Präsenzdaten sicherstellen (Presence/Member-Intents im Dev-Portal aktivieren!)
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
            title="🐮 Muhhelfer – Übersicht",
            description=desc,
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Angefragt von: {author.display_name}")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def _post_or_edit(self, channel: discord.TextChannel, embed: discord.Embed, msg_id: int | None):
        """Postet ein neues Embed oder editiert eine bestehende Nachricht-ID."""
        try:
            if msg_id:
                old = await channel.fetch_message(int(msg_id))
                await old.edit(content="🔔 Muhhelfer – Übersicht (aktualisiert):", embed=embed)
            else:
                await channel.send(content="🔔 Muhhelfer – Übersicht:", embed=embed)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            await channel.send(content="🔔 Muhhelfer – Übersicht:", embed=embed)

    # ========= Commands =========
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.group(name="triggerpost")
    async def triggerpost(self, ctx: commands.Context):
        """Konfiguration & Tools für den Trigger-Post."""
        pass

    @triggerpost.command(name="addtrigger")
    async def add_trigger(self, ctx: commands.Context, *, phrase: str):
        phrase = phrase.strip().casefold()
        async with self.config.guild(ctx.guild).triggers() as t:
            if phrase in t:
                return await ctx.send("⚠️ Dieser Trigger existiert bereits.")
            t.append(phrase)
        await ctx.send(f"✅ Trigger hinzugefügt: `{phrase}`")

    @triggerpost.command(name="removetrigger")
    async def remove_trigger(self, ctx: commands.Context, *, phrase: str):
        phrase = phrase.strip().casefold()
        async with self.config.guild(ctx.guild).triggers() as t:
            if phrase not in t:
                return await ctx.send("⚠️ Trigger nicht gefunden.")
            t.remove(phrase)
        await ctx.send(f"🗑️ Trigger entfernt: `{phrase}`")

    @triggerpost.command(name="list")
    async def list_triggers(self, ctx: commands.Context):
        data = await self.config.guild(ctx.guild).all()
        triggers = ", ".join(f"`{x}`" for x in data["triggers"]) or "—"
        ch = ctx.guild.get_channel(data["target_channel_id"]) if data["target_channel_id"] else None
        await ctx.send(
            f"**Trigger:** {triggers}\n"
            f"**Ziel-Channel:** {ch.mention if ch else '— nicht gesetzt —'}\n"
            f"**Message-ID:** `{data['message_id']}`\n"
            f"**Cooldown:** {data['cooldown_seconds']}s\n"
            f"**Bypass-Rolle:** <@&{ROLE_OFFIZIERE_BYPASS}>"
        )

    @triggerpost.command(name="setchannel")
    async def set_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Setzt den Ziel-Channel (nur dort triggert der Bot)."""
        if channel is None:
            return await ctx.send("⚠️ Bitte gib einen Channel an, z. B. `°triggerpost setchannel #bot-test`.")
        await self.config.guild(ctx.guild).target_channel_id.set(channel.id)
        await ctx.send(f"📍 Ziel-Channel gesetzt: {channel.mention}")

    @triggerpost.command(name="setmessage")
    async def set_message(self, ctx: commands.Context, message_id: int = None):
        """Optional: bestehende Nachricht-ID, die künftig editiert wird (0/leer = deaktivieren)."""
        await self.config.guild(ctx.guild).message_id.set(message_id)
        await ctx.send(f"🧷 Message-ID gesetzt: `{message_id}`")

    @triggerpost.command(name="cooldown")
    async def set_cooldown(self, ctx: commands.Context, seconds: int):
        """Cooldown (Sekunden) für Nicht-Bypass. Empfohlen: 30."""
        if seconds < 0 or seconds > 3600:
            return await ctx.send("⚠️ Bitte 0–3600 Sekunden.")
        await self.config.guild(ctx.guild).cooldown_seconds.set(seconds)
        await ctx.send(f"⏱️ Cooldown gesetzt: **{seconds}s**")

    @triggerpost.command(name="refresh")
    async def refresh_list(self, ctx: commands.Context):
        """Manuell aktualisieren: Muhhelfer-Übersicht im Ziel-Channel."""
        author: discord.Member = ctx.author
        guild: discord.Guild = ctx.guild

        # Bypass-Berechtigung
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        has_bypass_role = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
        if not (is_admin or has_bypass_role):
            return await ctx.send("🚫 Du darfst diesen Befehl nicht ausführen.", delete_after=5)

        data = await self.config.guild(guild).all()
        target_id = data["target_channel_id"]
        if not target_id:
            return await ctx.send("⚠️ Kein Ziel-Channel gesetzt. `°triggerpost setchannel #bot-test`")
        channel = guild.get_channel(target_id)
        if not channel:
            return await ctx.send("⚠️ Ziel-Channel nicht gefunden oder keine Rechte.")

        embed = await self._build_embed(guild, author)
        await self._post_or_edit(channel, embed, data["message_id"])
        await ctx.send("✅ Muhhelfer-Liste aktualisiert.", delete_after=5)

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

        # Trigger prüfen (substring, case-insensitive)
        content = message.content.casefold()
        if not any(t in content for t in data["triggers"]):
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

        # Embed bauen & posten/aktualisieren
        embed = await self._build_embed(guild, message.author)
        await self._post_or_edit(message.channel, embed, data["message_id"])
