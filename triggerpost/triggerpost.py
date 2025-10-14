# triggerpost.py
import re
import time
from datetime import datetime
from typing import Optional

import discord
from discord import ui, AllowedMentions
from discord.ext import tasks
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
    "autodelete_minutes": 10,             # Posts außerhalb Zielchannel werden nach X Minuten gelöscht (0 = aus)
    "force_role_ping": True,              # Rolle kurzzeitig erwähnbar machen, wenn nötig (erfordert Manage Roles)
    "auto_refresh_seconds": 0,            # 0 = aus
    "rolesource_url": None,               # Optional: Link zu Rollen-Nachricht ODER Channel-URL/Mention
}

# ====== Status & Sortierung ======
def _status_icon(member: discord.Member) -> str:
    st = getattr(member, "status", discord.Status.offline)
    if st is discord.Status.online:
        base = "🟢"
    elif st is discord.Status.idle:
        base = "🟠"
    elif st is discord.Status.dnd:
        base = "🔴"
    else:
        base = "⚫"
    in_voice = bool(getattr(member, "voice", None))
    return ("🎙️" if in_voice else "") + base

def _sort_key(member: discord.Member):
    in_voice = bool(getattr(member, "voice", None))
    st = getattr(member, "status", discord.Status.offline)
    voice_rank = 0 if in_voice else 1
    if st is discord.Status.online:
        st_rank = 0
    elif st is discord.Status.idle:
        st_rank = 1
    elif st is discord.Status.dnd:
        st_rank = 2
    else:
        st_rank = 3
    return (voice_rank, st_rank, member.display_name.lower())


class TriggerPost(commands.Cog):
    """Muhhelfer-System: Trigger, Main-Embed, Test-Layouts, Buttons, Auto-Refresh, Role-Source-Link."""

    _ping_cd_until: dict[int, float] = {}

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=81521025, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)
        self._cooldown_until = {}
        self._last_signature: dict[int, str] = {}   # guild_id -> letzte Embed-Signatur
        self._last_refresh_ts: dict[int, float] = {}  # guild_id -> letzter Auto-Refresh-Check
        # Persistente Views registrieren
        try:
            self.bot.add_view(self.PingView(self))
            self.bot.add_view(self.ColumnsView(self))
            self.bot.add_view(self.DashboardView(self))
            self.bot.add_view(self.CommandsView(self))
        except Exception:
            pass
        self._auto_refresher.start()

    def cog_unload(self):
        try:
            self._auto_refresher.cancel()
        except Exception:
            pass

    # ====== Utility ======
    @staticmethod
    def _now_str() -> str:
        return datetime.now().strftime("%d.%m.%Y, %H:%M")

    def _signature_for_guild(self, guild: discord.Guild) -> str:
        def sig_for_role(role_id: int):
            role = guild.get_role(role_id)
            if not role:
                return ""
            mems = [
                m for m in role.members
                if getattr(m, "status", discord.Status.offline) in (
                    discord.Status.online, discord.Status.idle, discord.Status.dnd
                )
            ]
            mems.sort(key=_sort_key)
            ids = [m.id for m in mems]
            return ",".join(map(str, ids))
        return f"N:{sig_for_role(ROLE_NORMAL)}|S:{sig_for_role(ROLE_SCHWER)}"

    async def _force_role_mention_once(
        self,
        *,
        guild: discord.Guild,
        channel: discord.abc.MessageableChannel,
        role: discord.Role,
        content: str,
    ):
        """Erzwingt Pings, wenn nötig (Rolle kurz mentionable setzen)."""
        me: discord.Member = guild.me  # type: ignore
        perms = channel.permissions_for(me)
        if perms.mention_everyone or role.mentionable:
            return await channel.send(
                content,
                allowed_mentions=AllowedMentions(roles=True, users=True, everyone=False),
            )
        can_manage = perms.manage_roles and (role.position < (me.top_role.position if me.top_role else 0))
        if not can_manage:
            return await channel.send(
                content,
                allowed_mentions=AllowedMentions(roles=True, users=True, everyone=False),
            )
        try:
            await role.edit(mentionable=True, reason="Force role ping (temporary)")
            msg = await channel.send(
                content,
                allowed_mentions=AllowedMentions(roles=True, users=True, everyone=False),
            )
        finally:
            try:
                await role.edit(mentionable=False, reason="Force role ping (revert)")
            except Exception:
                pass
        return msg

    async def _handle_ping_button(self, interaction: discord.Interaction, role_id: int):
        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user
        if not channel or not guild:
            return await interaction.response.send_message("⚠️ Nur in Server-Channels nutzbar.", ephemeral=True)

        is_admin = user.guild_permissions.administrator or user.guild_permissions.manage_guild
        has_bypass = any(r.id == ROLE_OFFIZIERE_BYPASS for r in getattr(user, "roles", []))

        # einfacher Kanal-Cooldown für Pings
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

        role = guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message("⚠️ Rolle nicht gefunden.", ephemeral=True)

        content = f"🔔 {role.mention} – angefragt von {user.mention}"
        await interaction.response.defer(ephemeral=False, thinking=False)
        force_on = await self.config.guild(guild).force_role_ping()
        if force_on:
            await self._force_role_mention_once(guild=guild, channel=channel, role=role, content=content)
        else:
            await channel.send(
                content,
                allowed_mentions=AllowedMentions(roles=True, users=True, everyone=False),
            )

    # ====== Member-Listen ======
    @staticmethod
    def _online_members(guild: discord.Guild, role_id: int):
        role = guild.get_role(role_id)
        if not role:
            return []
        members = [
            m for m in role.members
            if getattr(m, "status", discord.Status.offline) in (
                discord.Status.online, discord.Status.idle, discord.Status.dnd
            )
        ]
        members.sort(key=_sort_key)
        return members

    # ====== EMBEDS ======
    async def _embed_main(self, guild: discord.Guild, author: discord.Member, *, manual_info: Optional[str] = None, footer_note: Optional[str] = None):
        """Mainlayout: Vollansicht mit Status-Icons."""
        normal = self._online_members(guild, ROLE_NORMAL)
        schwer = self._online_members(guild, ROLE_SCHWER)

        def render(name, members):
            if not members:
                return f"{name}:\n– aktuell niemand –"
            return f"{name}:\n" + "\n".join(f"{_status_icon(m)} {m.mention}" for m in members)

        desc = f"{render('Muhhelfer – normal', normal)}\n\n{render('Muhhelfer – schwer', schwer)}"
        title_text = f"{EMOJI_TITLE} Muhhelfer – Übersicht"
        if manual_info:
            title_text += f"\n*({manual_info})*"

        e = discord.Embed(title=title_text, description=desc, color=discord.Color.blue())
        e.set_thumbnail(url=MUHKU_THUMBNAIL)
        foot = f"Angefragt von: {author.display_name} • Letzte Aktualisierung: {self._now_str()}"
        if footer_note:
            foot += f" • {footer_note}"
        e.set_footer(text=foot)
        e.timestamp = discord.utils.utcnow()
        return e

    async def _embed_columns(self, guild: discord.Guild, author: discord.Member):
        """Layout 1: Spaltenansicht (Normal/Schwer in je einem Field)."""
        normal = self._online_members(guild, ROLE_NORMAL)
        schwer = self._online_members(guild, ROLE_SCHWER)

        def block(members):
            if not members:
                return "– aktuell niemand –"
            return "\n".join(f"{_status_icon(m)} {m.mention}" for m in members)

        title = f"{EMOJI_TITLE} Muhhelfer – Spaltenansicht"
        e = discord.Embed(title=title, color=discord.Color.blue())
        e.description = f"**Normal:** {len(normal)} • **Schwer:** {len(schwer)}"
        e.set_thumbnail(url=MUHKU_THUMBNAIL)
        e.add_field(name="Muhhelfer – normal", value=block(normal), inline=True)
        e.add_field(name="Muhhelfer – schwer", value=block(schwer), inline=True)
        e.set_footer(text=f"Letzte Aktualisierung: {self._now_str()}")
        e.timestamp = discord.utils.utcnow()
        return e

    async def _embed_dashboard(self, guild: discord.Guild, tab: str):
        """Layout 2/3: Dashboard mit Tabs (Übersicht | Normal | Schwer)."""
        normal = self._online_members(guild, ROLE_NORMAL)
        schwer = self._online_members(guild, ROLE_SCHWER)
        in_voice_n = sum(1 for m in normal if getattr(m, "voice", None))
        in_voice_s = sum(1 for m in schwer if getattr(m, "voice", None))

        title = f"{EMOJI_TITLE} Muhhelfer – Dashboard"
        head = f"📊 **Normal:** {len(normal)} online • **Schwer:** {len(schwer)} online • 🎙️ Voice: N {in_voice_n} | S {in_voice_s}"
        e = discord.Embed(title=title, description=head, color=discord.Color.blue())
        e.set_thumbnail(url=MUHKU_THUMBNAIL)

        if tab == "overview":
            # nur Kopf
            pass
        elif tab == "normal":
            if normal:
                e.add_field(
                    name="Muhhelfer – normal",
                    value="\n".join(f"{_status_icon(m)} {m.mention}" for m in normal),
                    inline=False,
                )
            else:
                e.add_field(name="Muhhelfer – normal", value="– aktuell niemand –", inline=False)
        elif tab == "schwer":
            if schwer:
                e.add_field(
                    name="Muhhelfer – schwer",
                    value="\n".join(f"{_status_icon(m)} {m.mention}" for m in schwer),
                    inline=False,
                )
            else:
                e.add_field(name="Muhhelfer – schwer", value="– aktuell niemand –", inline=False)

        e.set_footer(text=f"Letzte Aktualisierung: {self._now_str()}")
        e.timestamp = discord.utils.utcnow()
        return e

    async def _embed_commands(self, show_admin: bool):
        """Layout 4: Befehlsübersicht (Embed)."""
        e = discord.Embed(
            title=f"{EMOJI_TITLE} Muhhelfer – Befehlsübersicht",
            description="Tippe auf **Admin anzeigen**, um zusätzliche Befehle einzublenden.",
            color=discord.Color.blue(),
        )
        e.set_thumbnail(url=MUHKU_THUMBNAIL)

        # Member
        e.add_field(name="Member", value="```\n°muhhelfer post [min]\n```", inline=False)

        # Offizier/Admin
        e.add_field(
            name="Offizier / Admin",
            value="```\n°muhhelfer addtrigger <text>\n°muhhelfer removetrigger <text>\n°muhhelfer list\n°muhhelfer refresh\n```",
            inline=False,
        )

        # Admin (toggle)
        if show_admin:
            e.add_field(
                name="Admin",
                value=(
                    "```\n"
                    "°muhhelfer setchannel #channel\n"
                    "°muhhelfer setmessage <id>\n"
                    "°muhhelfer cooldown <sek>\n"
                    "°muhhelfer intro <text|clear>\n"
                    "°muhhelfer autodelete <min>\n"
                    "°muhhelfer forceping on|off\n"
                    "°muhhelfer autorefresh <sek|off>\n"
                    "```"
                ),
                inline=False,
            )

        e.set_footer(text=f"Letzte Aktualisierung: {self._now_str()}")
        e.timestamp = discord.utils.utcnow()
        return e

    # ====== Post/Edit Helper ======
    async def _post_or_edit(
        self,
        channel: discord.TextChannel,
        embed: discord.Embed,
        msg_id: Optional[int],
        *,
        target_id: Optional[int],
        autodelete_after_min: Optional[int] = None,
        view: Optional[ui.View] = None,
        intro_text: Optional[str] = None,
        cleanup_in_target: bool = True,
        identifier_for_cleanup: Optional[str] = None,
    ) -> discord.Message:
        """Postet/editiert Content. Im Zielchannel räumen wir optional alte Posts des Bots auf (identifier match im content)."""
        content = intro_text or ""
        is_target = (target_id is not None) and (channel.id == target_id)

        # Zielchannel: alte identische Posts löschen (sauber halten)
        if is_target and cleanup_in_target and identifier_for_cleanup:
            async for m in channel.history(limit=500):
                if m.author == self.bot.user and identifier_for_cleanup in (m.content or ""):
                    try:
                        await m.delete()
                    except discord.Forbidden:
                        pass

        sent: Optional[discord.Message] = None
        try:
            if msg_id and is_target and view is not None:
                old = await channel.fetch_message(int(msg_id))
                await old.edit(content=content, embed=embed, view=view)
                sent = old
            else:
                sent = await channel.send(content=content, embed=embed, view=view)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            sent = await channel.send(content=content, embed=embed, view=view)

        # Auto-Delete (nur außerhalb Zielchannel)
        if not is_target and autodelete_after_min and autodelete_after_min > 0 and sent:
            try:
                await sent.delete(delay=autodelete_after_min * 60)
            except Exception:
                pass

        return sent

    # ====== VIEWS ======
    class PingView(ui.View):
        """Buttons: Normal/Schwer ping. Wird im Main & Columns genutzt."""
        def __init__(self, parent: "TriggerPost"):
            super().__init__(timeout=None)
            self.parent = parent

        @ui.button(label="Muhhelfer – normal ping", style=discord.ButtonStyle.primary, emoji=EMOJI_NORMAL, custom_id="muh_ping_normal")
        async def ping_normal(self, interaction: discord.Interaction, _button: ui.Button):
            await self.parent._handle_ping_button(interaction, ROLE_NORMAL)

        @ui.button(label="Muhhelfer – schwer ping", style=discord.ButtonStyle.danger, emoji=EMOJI_SCHWER, custom_id="muh_ping_schwer")
        async def ping_schwer(self, interaction: discord.Interaction, _button: ui.Button):
            await self.parent._handle_ping_button(interaction, ROLE_SCHWER)

        @ui.button(label="Aktualisieren", style=discord.ButtonStyle.secondary, custom_id="muh_refresh_simple")
        async def refresh_simple(self, interaction: discord.Interaction, _button: ui.Button):
            guild = interaction.guild
            if not guild:
                return await interaction.response.send_message("⚠️ Nur im Server.", ephemeral=True)
            embed = await self.parent._embed_columns(guild, interaction.user) if "Spaltenansicht" in (interaction.message.embeds[0].title if interaction.message.embeds else "") else await self.parent._embed_main(guild, interaction.user)
            await interaction.response.edit_message(embed=embed, view=self)

    class ColumnsView(PingView):
        """Für Layout1 identisch zu PingView (Ping + Refresh)."""
        pass

    class DashboardView(ui.View):
        """Layout 2/3: Tabs + kontextsensitive Ping-Buttons + optional Rollenbutton."""
        def __init__(self, parent: "TriggerPost", *, with_role_button: bool = False):
            super().__init__(timeout=None)
            self.parent = parent
            self.with_role_button = with_role_button
            # Standard-Tab = Übersicht
            self.current_tab = "overview"

        # Tabs
        @ui.button(label="Übersicht", style=discord.ButtonStyle.secondary, custom_id="muh_tab_overview")
        async def tab_overview(self, interaction: discord.Interaction, _button: ui.Button):
            await self._switch_tab(interaction, "overview")

        @ui.button(label="Normal", style=discord.ButtonStyle.primary, emoji=EMOJI_NORMAL, custom_id="muh_tab_normal")
        async def tab_normal(self, interaction: discord.Interaction, _button: ui.Button):
            await self._switch_tab(interaction, "normal")

        @ui.button(label="Schwer", style=discord.ButtonStyle.danger, emoji=EMOJI_SCHWER, custom_id="muh_tab_schwer")
        async def tab_schwer(self, interaction: discord.Interaction, _button: ui.Button):
            await self._switch_tab(interaction, "schwer")

        async def _switch_tab(self, interaction: discord.Interaction, tab: str):
            guild = interaction.guild
            if not guild:
                return await interaction.response.send_message("⚠️ Nur im Server.", ephemeral=True)
            self.current_tab = tab
            embed = await self.parent._embed_dashboard(guild, tab)
            await interaction.response.edit_message(embed=embed, view=self)

        # Kontextsensitive Ping-Buttons
        @ui.button(label="Normal pingen", style=discord.ButtonStyle.primary, emoji=EMOJI_NORMAL, custom_id="muh_dash_ping_normal")
        async def dash_ping_normal(self, interaction: discord.Interaction, _button: ui.Button):
            if self.current_tab != "normal":
                return await interaction.response.send_message("ℹ️ Öffne zuerst den **Normal**-Tab.", ephemeral=True)
            await self.parent._handle_ping_button(interaction, ROLE_NORMAL)

        @ui.button(label="Schwer pingen", style=discord.ButtonStyle.danger, emoji=EMOJI_SCHWER, custom_id="muh_dash_ping_schwer")
        async def dash_ping_schwer(self, interaction: discord.Interaction, _button: ui.Button):
            if self.current_tab != "schwer":
                return await interaction.response.send_message("ℹ️ Öffne zuerst den **Schwer**-Tab.", ephemeral=True)
            await self.parent._handle_ping_button(interaction, ROLE_SCHWER)

        @ui.button(label="Aktualisieren", style=discord.ButtonStyle.secondary, custom_id="muh_dash_refresh")
        async def dash_refresh(self, interaction: discord.Interaction, _button: ui.Button):
            guild = interaction.guild
            if not guild:
                return await interaction.response.send_message("⚠️ Nur im Server.", ephemeral=True)
            embed = await self.parent._embed_dashboard(guild, self.current_tab)
            await interaction.response.edit_message(embed=embed, view=self)

        # Optionaler Rollenbutton (nur Layout 3)
        @ui.button(label="Rolle holen", style=discord.ButtonStyle.success, custom_id="muh_dash_rolebtn")
        async def role_button(self, interaction: discord.Interaction, _button: ui.Button):
            if not self.with_role_button:
                return await interaction.response.send_message("ℹ️ Kein Rollen-Link hinterlegt.", ephemeral=True)
            data = await self.parent.config.guild(interaction.guild).all()
            link = data.get("rolesource_url")
            if not link:
                return await interaction.response.send_message("ℹ️ Kein Rollen-Link hinterlegt.", ephemeral=True)
            await interaction.response.send_message(f"🔗 Rollen holen: {link}", ephemeral=True)

        async def on_timeout(self):
            # persistente Views: nichts
            pass

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            # Button „Rolle holen“ nur anzeigen, wenn with_role_button und rolesource vorhanden
            for child in self.children:
                if isinstance(child, ui.Button) and child.custom_id == "muh_dash_rolebtn":
                    child.disabled = not self.with_role_button
            return True

    class CommandsView(ui.View):
        """Layout 4: Befehlsübersicht – Admin toggeln, ‚Alle Befehle (kopieren)‘ ephemer senden."""
        def __init__(self, parent: "TriggerPost", show_admin: bool = False):
            super().__init__(timeout=None)
            self.parent = parent
            self.show_admin = show_admin

        @ui.button(label="Admin anzeigen/ausblenden", style=discord.ButtonStyle.secondary, custom_id="muh_cmd_toggle_admin")
        async def toggle_admin(self, interaction: discord.Interaction, _button: ui.Button):
            embed = await self.parent._embed_commands(not self.show_admin)
            self.show_admin = not self.show_admin
            await interaction.response.edit_message(embed=embed, view=self)

        @ui.button(label="Alle Befehle (kopieren)", style=discord.ButtonStyle.primary, custom_id="muh_cmd_copy_all")
        async def copy_all(self, interaction: discord.Interaction, _button: ui.Button):
            txt = (
                "**Member**\n"
                "```\n°muhhelfer post [min]\n```\n"
                "**Offizier / Admin**\n"
                "```\n°muhhelfer addtrigger <text>\n°muhhelfer removetrigger <text>\n°muhhelfer list\n°muhhelfer refresh\n```\n"
                "**Admin**\n"
                "```\n°muhhelfer setchannel #channel\n°muhhelfer setmessage <id>\n°muhhelfer cooldown <sek>\n°muhhelfer intro <text|clear>\n°muhhelfer autodelete <min>\n°muhhelfer forceping on|off\n°muhhelfer autorefresh <sek|off>\n```"
            )
            await interaction.response.send_message(txt, ephemeral=True)

    # ====== COMMANDS: Main & Setup ======
    @commands.guild_only()
    @commands.group(name="muhhelfer", aliases=["triggerpost"])
    async def muhhelfer(self, ctx: commands.Context):
        """Muhhelfer-Tools und Konfiguration."""
        pass

    @muhhelfer.command(name="post")
    async def manual_post(self, ctx: commands.Context, minutes: Optional[int] = None):
        """Mainlayout posten (Member im Zielchannel, Offiziere/Admins überall)."""
        guild = ctx.guild
        author = ctx.author
        data = await self.config.guild(guild).all()
        target_id = data["target_channel_id"]
        if not target_id:
            return await ctx.send("⚠️ Kein Ziel-Channel gesetzt.")

        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offi = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
        if not (is_admin or is_offi) and ctx.channel.id != target_id:
            target = guild.get_channel(target_id)
            return await ctx.send(f"⚠️ Bitte nutze den Befehl im {target.mention}.", delete_after=5)

        now = time.time()
        until = self._cooldown_until.get(ctx.channel.id, 0)
        if not (is_admin or is_offi):
            cd = (await self.config.guild(guild).cooldown_seconds())
            if now < until:
                return
            self._cooldown_until[ctx.channel.id] = now + cd

        # Auto-Delete nur außerhalb Zielchannel
        is_target = ctx.channel.id == target_id
        autodelete_conf = int(data.get("autodelete_minutes") or 0)
        minutes_override = None
        if minutes is not None:
            if minutes < 0 or minutes > 1440:
                return await ctx.send("⚠️ Bitte Minuten zwischen 0 und 1440 angeben.")
            minutes_override = minutes
        autodel = None if is_target else (minutes_override if minutes_override is not None else autodelete_conf)

        footer_note = None
        if not is_target and autodel and autodel > 0:
            footer_note = f"Auto-Delete in {autodel} Min"
        manual_info = None
        if (is_admin or is_offi) and not is_target:
            manual_info = f"manuell ausgelöst von {author.display_name}"

        embed = await self._embed_main(guild, author, manual_info=manual_info, footer_note=footer_note)
        intro = (f"{data.get('intro_text')}\n\n{EMOJI_TITLE} Muhhelfer – Übersicht:" if data.get("intro_text")
                 else f"{EMOJI_TITLE} Muhhelfer – Übersicht:")
        view = self.PingView(self)
        await self._post_or_edit(
            ctx.channel,
            embed,
            data["message_id"],
            target_id=target_id,
            autodelete_after_min=autodel,
            view=view,
            intro_text=intro,
            identifier_for_cleanup="Muhhelfer – Übersicht",
        )
        await ctx.send("✅ Muhhelfer-Nachricht gepostet.", delete_after=5)

    # Trigger-Verwaltung
    @muhhelfer.command(name="addtrigger")
    async def add_trigger(self, ctx: commands.Context, *, phrase: str):
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offi = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
        if not (is_admin or is_offi):
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
        is_offi = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
        if not (is_admin or is_offi):
            return await ctx.send("🚫 Du darfst diesen Befehl nicht verwenden.")
        phrase = (phrase or "").strip().casefold()
        async with self.config.guild(ctx.guild).triggers() as t:
            if phrase not in t:
                return await ctx.send("⚠️ Trigger nicht gefunden.")
            t.remove(phrase)
        await ctx.send(f"🗑️ Trigger entfernt: `{phrase}`")

    @muhhelfer.command(name="list")
    async def list_triggers(self, ctx: commands.Context):
        """Zeigt (neu) das Befehls-Embed (Layout 4) statt Textwand."""
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offi = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
        if not (is_admin or is_offi):
            # Member sehen nur Member/Offi-Teil (ohne Admin)
            e = await self._embed_commands(False)
            return await ctx.send(embed=e, view=self.CommandsView(self, show_admin=False))
        e = await self._embed_commands(False)
        await ctx.send(embed=e, view=self.CommandsView(self, show_admin=False))

    @muhhelfer.command(name="refresh")
    async def refresh_list(self, ctx: commands.Context):
        author = ctx.author
        is_admin = author.guild_permissions.administrator or author.guild_permissions.manage_guild
        is_offi = any(r.id == ROLE_OFFIZIERE_BYPASS for r in author.roles)
        if not (is_admin or is_offi):
            return await ctx.send("🚫 Du darfst diesen Befehl nicht verwenden.")
        data = await self.config.guild(ctx.guild).all()
        target_id = data["target_channel_id"]
        if not target_id:
            return await ctx.send("⚠️ Kein Ziel-Channel gesetzt.")
        channel = ctx.guild.get_channel(target_id)
        embed = await self._embed_main(ctx.guild, ctx.author)
        view = self.PingView(self)
        await self._post_or_edit(channel, embed, data["message_id"], target_id=target_id, view=view, intro_text=f"{EMOJI_TITLE} Muhhelfer – Übersicht:", identifier_for_cleanup="Muhhelfer – Übersicht")
        await ctx.send("✅ Muhhelfer-Liste aktualisiert.", delete_after=5)

    # Admin/Setup
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
        if minutes < 0 or minutes > 1440:
            return await ctx.send("⚠️ Bitte 0–1440 Minuten.")
        await self.config.guild(ctx.guild).autodelete_minutes.set(minutes)
        await ctx.send(f"🗑️ Auto-Delete (außerhalb Zielchannel): **{minutes} min**")

    @muhhelfer.command(name="forceping")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_forceping(self, ctx: commands.Context, state: str):
        state_l = (state or "").strip().lower()
        if state_l not in {"on", "off"}:
            return await ctx.send("⚠️ Nutzung: `°muhhelfer forceping on` oder `off`")
        await self.config.guild(ctx.guild).force_role_ping.set(state_l == "on")
        await ctx.send(f"🔧 force_role_ping: **{state_l}**")

    @muhhelfer.command(name="autorefresh")
    @commands.admin_or_permissions(manage_guild=True)
    async def set_autorefresh(self, ctx: commands.Context, seconds: str):
        s = (seconds or "").strip().lower()
        if s in {"off", "0"}:
            await self.config.guild(ctx.guild).auto_refresh_seconds.set(0)
            return await ctx.send("🛑 Auto-Refresh: **aus**")
        try:
            val = int(s)
        except ValueError:
            return await ctx.send("⚠️ Zahl in Sekunden oder `off` angeben.")
        if val < 60 or val > 3600:
            return await ctx.send("⚠️ Bitte zwischen **60** und **3600** Sekunden wählen.")
        await self.config.guild(ctx.guild).auto_refresh_seconds.set(val)
        await ctx.send(f"🔁 Auto-Refresh: **alle {val}s** (nur Zielchannel, nur bei Änderungen).")

    # ====== Role-Source (für Layout 3) ======
    @muhhelfer.group(name="rolesource")
    @commands.admin_or_permissions(manage_guild=True)
    async def rolesource(self, ctx: commands.Context):
        """Rollen-Quelle für ‚Rolle holen‘-Button setzen/anzeigen/löschen."""
        pass

    @rolesource.command(name="set")
    async def rolesource_set(self, ctx: commands.Context, *, link_or_mention: str):
        """Akzeptiert Nachrichtenlink ODER Channel-Link/Mention."""
        link_or_mention = link_or_mention.strip()
        # einfache Validierung: URL oder <#id>
        chan_match = re.match(r"<#(\d+)>", link_or_mention)
        url_match = re.match(r"https?://", link_or_mention)
        if not (chan_match or url_match):
            return await ctx.send("⚠️ Bitte eine Nachrichten-URL oder Channel-Mention/Link angeben.")
        await self.config.guild(ctx.guild).rolesource_url.set(link_or_mention)
        await ctx.send(f"✅ Rollen-Quelle gesetzt: {link_or_mention}")

    @rolesource.command(name="show")
    async def rolesource_show(self, ctx: commands.Context):
        link = await self.config.guild(ctx.guild).rolesource_url()
        await ctx.send(f"🔗 Rollen-Quelle: {link or '— nicht gesetzt —'}")

    @rolesource.command(name="clear")
    async def rolesource_clear(self, ctx: commands.Context):
        await self.config.guild(ctx.guild).rolesource_url.set(None)
        await ctx.send("🧹 Rollen-Quelle gelöscht.")

    # ====== TEST-LAYOUTS ======
    @muhhelfer.group(name="test")
    async def test_layouts(self, ctx: commands.Context):
        """Test-Layouts posten (beeinflusst Main nicht)."""
        pass

    @test_layouts.command(name="layout1")
    async def test_layout1(self, ctx: commands.Context, minutes: Optional[int] = None):
        """Layout 1 – Spaltenansicht."""
        embed = await self._embed_columns(ctx.guild, ctx.author)
        view = self.ColumnsView(self)
        await self._post_or_edit(
            ctx.channel, embed, None, target_id=None, autodelete_after_min=minutes, view=view,
            intro_text=f"{EMOJI_TITLE} Muhhelfer – Spaltenansicht:",
            cleanup_in_target=False
        )

    @test_layouts.command(name="layout2")
    async def test_layout2(self, ctx: commands.Context, minutes: Optional[int] = None):
        """Layout 2 – Dashboard (ohne Rollenbutton)."""
        embed = await self._embed_dashboard(ctx.guild, "overview")
        view = self.DashboardView(self, with_role_button=False)
        await self._post_or_edit(
            ctx.channel, embed, None, target_id=None, autodelete_after_min=minutes, view=view,
            intro_text=f"{EMOJI_TITLE} Muhhelfer – Dashboard:",
            cleanup_in_target=False
        )

    @test_layouts.command(name="layout3")
    async def test_layout3(self, ctx: commands.Context, minutes: Optional[int] = None):
        """Layout 3 – Dashboard + Rollenbutton (nutzt gespeicherte rolesource)."""
        data = await self.config.guild(ctx.guild).all()
        has_link = bool(data.get("rolesource_url"))
        embed = await self._embed_dashboard(ctx.guild, "overview")
        view = self.DashboardView(self, with_role_button=has_link)
        await self._post_or_edit(
            ctx.channel, embed, None, target_id=None, autodelete_after_min=minutes, view=view,
            intro_text=f"{EMOJI_TITLE} Muhhelfer – Dashboard:",
            cleanup_in_target=False
        )

    @test_layouts.command(name="layout4")
    async def test_layout4(self, ctx: commands.Context, minutes: Optional[int] = None):
        """Layout 4 – Befehlsübersicht (Embed mit Buttons)."""
        embed = await self._embed_commands(show_admin=False)
        view = self.CommandsView(self, show_admin=False)
        await self._post_or_edit(
            ctx.channel, embed, None, target_id=None, autodelete_after_min=minutes, view=view,
            intro_text=f"{EMOJI_TITLE} Muhhelfer – Befehlsübersicht:",
            cleanup_in_target=False
        )

    # Alle Layouts auf einmal posten (1..n)
    @muhhelfer.group(name="layouts")
    async def layouts(self, ctx: commands.Context):
        """Layout-Funktionen (Liste, alle posten)."""
        pass

    @layouts.command(name="postall")
    async def layouts_postall(self, ctx: commands.Context, minutes: Optional[int] = None):
        await self.test_layout1.callback(self, ctx, minutes)  # type: ignore
        await self.test_layout2.callback(self, ctx, minutes)  # type: ignore
        await self.test_layout3.callback(self, ctx, minutes)  # type: ignore
        await self.test_layout4.callback(self, ctx, minutes)  # type: ignore

    @muhhelfer.command(name="layout")
    async def layout_single(self, ctx: commands.Context, sub: str = None):
        """Alias: °muhhelfer layout list"""
        if (sub or "").lower() == "list":
            await self.layout_list(ctx)
        else:
            await ctx.send("ℹ️ Nutzung: `°muhhelfer layout list`")

    async def layout_list(self, ctx: commands.Context):
        txt = (
            "**Verfügbare Layouts:**\n"
            "• **Layout 1 – Spaltenansicht** (Normal/Schwer in Spalten, beide Ping-Buttons)\n"
            "• **Layout 2 – Dashboard** (Übersicht + Tabs; Ping nur im aktiven Tab)\n"
            "• **Layout 3 – Dashboard + Rollenbutton** (wie 2, plus ‚Rolle holen‘ bei hinterlegter Quelle)\n"
            "• **Layout 4 – Befehlsübersicht** (Embed mit Admin-Toggle & Kopier-Button)\n"
            "\n"
            "Posten: `°muhhelfer test layout1|layout2|layout3|layout4 [min]`\n"
            "Alle: `°muhhelfer layouts postall [min]`\n"
        )
        await ctx.send(txt)

    # ====== Listener: Trigger im Zielchannel ======
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

        embed = await self._embed_main(guild, author)
        intro = (f"{data.get('intro_text')}\n\n{EMOJI_TITLE} Muhhelfer – Übersicht:" if data.get("intro_text")
                 else f"{EMOJI_TITLE} Muhhelfer – Übersicht:")
        view = self.PingView(self)
        await self._post_or_edit(message.channel, embed, data["message_id"], target_id=target_id, view=view, intro_text=intro, identifier_for_cleanup="Muhhelfer – Übersicht")

    # ====== Auto-Refresh ======
    @tasks.loop(seconds=30)  # per-Guild Intervallsteuerung
    async def _auto_refresher(self):
        now = time.time()
        for guild in self.bot.guilds:
            try:
                data = await self.config.guild(guild).all()
                interval = int(data.get("auto_refresh_seconds") or 0)
                target_id = data.get("target_channel_id")
                if not interval or not target_id:
                    continue

                last_ts = self._last_refresh_ts.get(guild.id, 0.0)
                if (now - last_ts) < interval:
                    continue
                self._last_refresh_ts[guild.id] = now

                channel = guild.get_channel(target_id)
                if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.ForumChannel, discord.VoiceChannel)):
                    continue

                sig = self._signature_for_guild(guild)
                if self._last_signature.get(guild.id) == sig:
                    continue

                author = guild.me  # Footer
                embed = await self._embed_main(guild, author)  # type: ignore
                view = self.PingView(self)
                await self._post_or_edit(channel, embed, data["message_id"], target_id=target_id, view=view, intro_text=f"{EMOJI_TITLE} Muhhelfer – Übersicht:", identifier_for_cleanup="Muhhelfer – Übersicht")
                self._last_signature[guild.id] = sig
            except Exception:
                continue

    @_auto_refresher.before_loop
    async def _before_refresher(self):
        await self.bot.wait_until_ready()
