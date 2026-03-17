# kuhmuhupdate.py
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord import app_commands

from redbot.core import commands, Config
from redbot.core.bot import Red
from discord.ext.commands.view import StringView

log = logging.getLogger("red.kuhmuh.kuhmuhupdate")

# ============================
# FIXE SETTINGS (HART IM CODE)
# ============================
GUILD_ID = 1198649628787212458

# <- Setze hier eure Admin-Rolle fix ein:
ADMIN_ROLE_ID = 0  # z.B. 123456789012345678

# Optional: Log-Channel fix (0 = aus)
LOG_CHANNEL_ID = 1460298038269575282


# -----------------------------
# Helpers / Models
# -----------------------------
def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _normalize_key(name: str) -> str:
    return name.strip().casefold()


def _clamp_text(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _fmt_dt(ts: dt.datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC")


@dataclass
class StepResult:
    name: str
    status: str  # ✅ ⚠️ ❌ ⏭️
    summary: str
    details: str = ""


class _CapturedMessage:
    __slots__ = ("content", "embeds")

    def __init__(self, content: Optional[str] = None, embeds: Optional[List[discord.Embed]] = None):
        self.content = content
        self.embeds = embeds or []


class _CommandOutputCatcher:
    """Intercepts ctx.send output so commands don't spam channels."""

    def __init__(self) -> None:
        self.messages: List[_CapturedMessage] = []

    async def send(self, content: Optional[str] = None, **kwargs: Any) -> _CapturedMessage:
        embeds: List[discord.Embed] = []
        embed = kwargs.get("embed")
        if embed is not None:
            embeds.append(embed)
        embeds_arg = kwargs.get("embeds")
        if embeds_arg:
            embeds.extend(list(embeds_arg))

        msg = _CapturedMessage(content=content, embeds=embeds)
        self.messages.append(msg)
        return msg

    def render_text(self) -> str:
        parts: List[str] = []
        for m in self.messages:
            if m.content:
                parts.append(str(m.content))
            for e in m.embeds:
                title = e.title or ""
                desc = e.description or ""
                fields = "\n".join(f"{f.name}: {f.value}" for f in e.fields) if e.fields else ""
                chunk = "\n".join(x for x in [title, desc, fields] if x).strip()
                if chunk:
                    parts.append(chunk)
        return "\n".join(parts).strip()


# -----------------------------
# Cog
# -----------------------------
class KuhmuhUpdate(commands.Cog):
    """
    /update run    -> Update eines gespeicherten Cogs (public embed)
    /update manage -> add/remove/list
    """

    # /update
    update_group = app_commands.Group(
        name="kuhmuhupdate",
        description="Admin: Cogs updaten & verwalten.",
        guild_ids=[GUILD_ID],
    )

    manage_group = app_commands.Group(
        name="manage",
        description="Gespeicherte Cogs verwalten (add/remove/list).",
        parent=update_group,
    )


    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=946102221, force_registration=True)

        self.config.register_global(
            embed_detail_limit=400,
            stored_cogs={},  # dict: key -> {cog_name, repo_name}
        )

        self._update_lock = asyncio.Lock()
        self._startup_task: Optional[asyncio.Task] = self.bot.loop.create_task(self._startup_guild_sync())

    # -------------------------
    # App command registration
    # -------------------------
    async def cog_load(self) -> None:
        guild_obj = discord.Object(id=GUILD_ID)

        # alte Commands entfernen (update + kuhmuhupdate, global + guild)
        with contextlib.suppress(Exception):
            self.bot.tree.remove_command("update", guild=guild_obj)
        with contextlib.suppress(Exception):
            self.bot.tree.remove_command("update", guild=None)
        with contextlib.suppress(Exception):
            self.bot.tree.remove_command("kuhmuhupdate", guild=guild_obj)
        with contextlib.suppress(Exception):
            self.bot.tree.remove_command("kuhmuhupdate", guild=None)

        # Neu hinzufügen (guild-scoped)
        with contextlib.suppress(Exception):
            self.bot.tree.add_command(self.update_group, guild=guild_obj)


    async def cog_unload(self) -> None:
        guild_obj = discord.Object(id=GUILD_ID)

        with contextlib.suppress(Exception):
            self.bot.tree.remove_command("kuhmuhupdate", guild=guild_obj)

        with contextlib.suppress(Exception):
            await self.bot.tree.sync(guild=guild_obj)


    async def _startup_guild_sync(self) -> None:
        try:
            await self.bot.wait_until_red_ready()
            await self.bot.wait_until_ready()

            guild_obj = discord.Object(id=GUILD_ID)
            await self.bot.tree.sync(guild=guild_obj)
        except Exception:
            pass

    # -------------------------
    # Permissions
    # -------------------------
    async def _is_owner(self, user: discord.abc.User) -> bool:
        return await self.bot.is_owner(user)

    async def _require_admin(self, interaction: discord.Interaction) -> Tuple[bool, str]:
        # Hard guild-only
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False, "❌ Dieser Command ist nur innerhalb der Guild verfügbar."

        if interaction.guild.id != GUILD_ID:
            return False, "❌ Dieser Command ist nur in der Ziel-Guild verfügbar."

        if await self._is_owner(interaction.user):
            return True, ""

        if ADMIN_ROLE_ID == 0:
            return False, "❌ ADMIN_ROLE_ID ist im Code nicht gesetzt."

        role = interaction.guild.get_role(ADMIN_ROLE_ID)
        if role is None:
            return False, f"❌ ADMIN_ROLE_ID ({ADMIN_ROLE_ID}) existiert in dieser Guild nicht."

        if role not in interaction.user.roles:
            return False, "❌ Du hast keine Berechtigung (Admin-Rolle erforderlich)."

        return True, ""

    # -------------------------
    # Storage
    # -------------------------
    async def _get_stored_cogs(self) -> Dict[str, Dict[str, str]]:
        data = await self.config.stored_cogs()
        if not isinstance(data, dict):
            return {}
        out: Dict[str, Dict[str, str]] = {}
        for k, v in data.items():
            if not isinstance(k, str) or not isinstance(v, dict):
                continue
            cn = v.get("cog_name")
            rn = v.get("repo_name")
            if isinstance(cn, str) and isinstance(rn, str):
                out[k] = {"cog_name": cn, "repo_name": rn}
        return out

    async def _set_stored_cog(self, cog_name: str, repo_name: str) -> None:
        key = _normalize_key(cog_name)
        data = await self._get_stored_cogs()
        data[key] = {"cog_name": cog_name.strip(), "repo_name": repo_name.strip()}
        await self.config.stored_cogs.set(data)

    async def _remove_stored_cog(self, key: str) -> bool:
        data = await self._get_stored_cogs()
        if key in data:
            del data[key]
            await self.config.stored_cogs.set(data)
            return True
        return False

    # -------------------------
    # Logging helpers
    # -------------------------
    async def _maybe_log_full_output(self, interaction: discord.Interaction, title: str, text: str) -> None:
        if not text:
            return

        log.info("%s\n%s", title, text)

        if LOG_CHANNEL_ID == 0:
            return

        if not interaction.guild:
            return

        channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if channel is None or not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return

        safe = text
        if len(safe) > 1900:
            safe = safe[:1900] + "…"

        with contextlib.suppress(Exception):
            await channel.send(f"**{title}**\n```text\n{safe}\n```")

    def _extract_not_installed(self, text: str) -> bool:
        if not text:
            return False
        patterns = [
            r"\bnot installed\b",
            r"\bis not installed\b",
            r"\bnot\s+found\b",
            r"\bno such cog\b",
            r"\bcog.*not.*installed\b",
        ]
        low = text.casefold()
        return any(re.search(p, low) for p in patterns)

    async def _build_status_embed(
        self,
        cog_name: str,
        repo_name: str,
        started: dt.datetime,
        invoker: discord.abc.User,
        results: List[StepResult],
        duration_s: float,
    ) -> discord.Embed:
        e = discord.Embed(
            title=f"Update: {cog_name}",
            description=f"Repo: **{repo_name}**\nStart: `{_fmt_dt(started)}`",
        )

        for r in results:
            e.add_field(name=r.name, value=f"{r.status} {r.summary}", inline=False)

        e.set_footer(text=f"{invoker} • Dauer: {duration_s:.2f}s")
        return e

    # -------------------------
    # Core: invoke command capture
    # -------------------------
    async def _invoke_command_capture(
        self,
        interaction: discord.Interaction,
        qualified_command: str,
        arg_string: str = "",
    ) -> Tuple[bool, str]:
        """
        Führt einen Red-Textcommand aus (Converter/Parsing laufen), fängt Output ab.
        """
        cmd = self.bot.get_command(qualified_command)
        if cmd is None:
            return False, f"Command nicht gefunden: {qualified_command}"

        ctx = await commands.Context.from_interaction(interaction)
        ctx.prefix = "°"

        ctx.command = cmd
        ctx.view = StringView(arg_string or "")
        ctx.invoked_with = qualified_command.split(" ")[0]

        catcher = _CommandOutputCatcher()

        original_send = ctx.send
        ctx.send = catcher.send  # type: ignore

        original_reply = getattr(ctx, "reply", None)
        if original_reply is not None:
            ctx.reply = catcher.send  # type: ignore

        original_tick = getattr(ctx, "tick", None)
        if original_tick is not None:
            async def _tick(*_a: Any, **_k: Any) -> _CapturedMessage:
                return await catcher.send("✅")
            ctx.tick = _tick  # type: ignore

        try:
            await cmd.invoke(ctx)
            return True, catcher.render_text()
        except Exception as e:
            out = catcher.render_text()
            err = f"{type(e).__name__}: {e}".strip()
            return False, (out + "\n" + err).strip() if out else err
        finally:
            ctx.send = original_send  # type: ignore
            if original_reply is not None:
                ctx.reply = original_reply  # type: ignore
            if original_tick is not None:
                ctx.tick = original_tick  # type: ignore

    # -------------------------
    # Autocomplete
    # -------------------------
    async def _ac_stored_cogs(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        stored = await self._get_stored_cogs()
        cur = (current or "").casefold().strip()
        items: List[app_commands.Choice[str]] = []

        for key, v in stored.items():
            name = v.get("cog_name", "")
            repo = v.get("repo_name", "")
            if not name:
                continue
            if cur and cur not in name.casefold():
                continue
            items.append(app_commands.Choice(name=f"{name} ({repo})", value=key))

        items.sort(key=lambda c: c.name.casefold())
        return items[:25]

    # ==========================
    # /update run
    # ==========================
    @update_group.command(name="run", description="Gespeichertes Cog updaten (uninstall → repo update → install → load)")
    
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(cog="Cog auswählen (gespeichert)")
    @app_commands.autocomplete(cog=_ac_stored_cogs)
    async def update_run(self, interaction: discord.Interaction, cog: str) -> None:
        await interaction.response.send_message("✅ Update gestartet… Ergebnis wird im Channel gepostet.", ephemeral=True)

        ok, err = await self._require_admin(interaction)
        if not ok:
            await interaction.followup.send(err, ephemeral=True)
            return

        stored = await self._get_stored_cogs()
        sel = stored.get(cog)
        if not sel:
            await interaction.followup.send("⚠️ Auswahl nicht gefunden (Liste evtl. geändert).", ephemeral=True)
            return

        if self._update_lock.locked():
            await interaction.followup.send("⏭️ Ein Update läuft bereits. Bitte warten.", ephemeral=True)
            return

        if not interaction.channel:
            await interaction.followup.send("❌ Kein Channel-Kontext.", ephemeral=True)
            return

        cog_name_real = sel["cog_name"]
        repo_name_real = sel["repo_name"]

        started = _now_utc()
        t0 = dt.datetime.now(dt.timezone.utc)

        placeholder = discord.Embed(
            title=f"Update: {cog_name_real}",
            description=f"Repo: **{repo_name_real}**\nStart: `{_fmt_dt(started)}`\n\n⏳ Update läuft…",
        )

        try:
            public_msg = await interaction.channel.send(embed=placeholder)  # type: ignore
        except Exception:
            await interaction.followup.send("❌ Konnte keine öffentliche Nachricht posten (Rechte?).", ephemeral=True)
            return

        async with self._update_lock:
            results: List[StepResult] = []

            ok1, out1 = await self._invoke_command_capture(interaction, "cog uninstall", cog_name_real)
            await self._maybe_log_full_output(interaction, f"[KuhmuhUpdate] Uninstall {cog_name_real}", out1)

            if ok1:
                results.append(StepResult("Uninstall", "✅", "Deinstalliert.", out1))
            else:
                if self._extract_not_installed(out1):
                    results.append(StepResult("Uninstall", "⚠️", "Nicht installiert (weiter).", out1))
                else:
                    results.append(StepResult("Uninstall", "❌", "Fehler – Abbruch.", out1))
                    await self._finalize_public(public_msg, interaction, cog_name_real, repo_name_real, started, t0, results)
                    return

            ok2, out2 = await self._invoke_command_capture(interaction, "repo update", repo_name_real)
            await self._maybe_log_full_output(interaction, f"[KuhmuhUpdate] Repo Update {repo_name_real}", out2)

            if ok2:
                results.append(StepResult("Repo Update", "✅", "Aktualisiert.", out2))
            else:
                results.append(StepResult("Repo Update", "❌", "Fehler – Abbruch.", out2))
                await self._finalize_public(public_msg, interaction, cog_name_real, repo_name_real, started, t0, results)
                return

            ok3, out3 = await self._invoke_command_capture(interaction, "cog install", f"{repo_name_real} {cog_name_real}")
            await self._maybe_log_full_output(interaction, f"[KuhmuhUpdate] Install {repo_name_real}/{cog_name_real}", out3)

            if ok3:
                results.append(StepResult("Install", "✅", "Installiert.", out3))
            else:
                results.append(StepResult("Install", "❌", "Fehler – Abbruch.", out3))
                await self._finalize_public(public_msg, interaction, cog_name_real, repo_name_real, started, t0, results)
                return

            ok4, out4 = await self._invoke_command_capture(interaction, "load", cog_name_real)
            await self._maybe_log_full_output(interaction, f"[KuhmuhUpdate] Load {cog_name_real}", out4)

            if ok4:
                results.append(StepResult("Load", "✅", "Geladen.", out4))
            else:
                results.append(StepResult("Load", "❌", "Fehler – Prozess beendet.", out4))

            await self._finalize_public(public_msg, interaction, cog_name_real, repo_name_real, started, t0, results)

    async def _finalize_public(
        self,
        public_msg: discord.Message,
        interaction: discord.Interaction,
        cog_name: str,
        repo_name: str,
        started: dt.datetime,
        t0: dt.datetime,
        results: List[StepResult],
    ) -> None:
        duration = (dt.datetime.now(dt.timezone.utc) - t0).total_seconds()

        limit = int(await self.config.embed_detail_limit() or 400)
        for r in results:
            if r.details:
                snippet = _clamp_text(r.details.replace("```", "'''"), limit)
                if snippet:
                    r.summary = f"{r.summary}\n```text\n{snippet}\n```"

        embed_final = await self._build_status_embed(cog_name, repo_name, started, interaction.user, results, duration)

        with contextlib.suppress(Exception):
            await public_msg.edit(embed=embed_final)

        with contextlib.suppress(Exception):
            await interaction.followup.send("✅ Update abgeschlossen.", ephemeral=True)

    # ==========================
    # /update manage add
    # ==========================
    @manage_group.command(name="add", description="Cog + Repo speichern")
    
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(cog_name="z.B. gruppensuche_test", repo_name="z.B. kuhmuh")
    async def manage_add(self, interaction: discord.Interaction, cog_name: str, repo_name: str) -> None:
        await interaction.response.defer(ephemeral=True)

        ok, err = await self._require_admin(interaction)
        if not ok:
            await interaction.edit_original_response(content=err)
            return

        cn = (cog_name or "").strip()
        rn = (repo_name or "").strip()
        if not cn or not rn:
            await interaction.edit_original_response(content="❌ `cog_name` und `repo_name` dürfen nicht leer sein.")
            return

        await self._set_stored_cog(cn, rn)
        await interaction.edit_original_response(content=f"✅ Gespeichert: **{cn}** → Repo **{rn}**")

    # ==========================
    # /update manage remove
    # ==========================
    @manage_group.command(name="remove", description="Gespeichertes Cog entfernen")
    
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(cog="Gespeichertes Cog")
    @app_commands.autocomplete(cog=_ac_stored_cogs)
    async def manage_remove(self, interaction: discord.Interaction, cog: str) -> None:
        await interaction.response.defer(ephemeral=True)

        ok, err = await self._require_admin(interaction)
        if not ok:
            await interaction.edit_original_response(content=err)
            return

        removed = await self._remove_stored_cog(cog)
        if removed:
            await interaction.edit_original_response(content="✅ Eintrag entfernt.")
        else:
            await interaction.edit_original_response(content="⚠️ Eintrag nicht gefunden.")

    # ==========================
    # /update manage list
    # ==========================
    @manage_group.command(name="list", description="Alle gespeicherten Cogs anzeigen")
    
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def manage_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        ok, err = await self._require_admin(interaction)
        if not ok:
            await interaction.edit_original_response(content=err)
            return

        stored = await self._get_stored_cogs()
        if not stored:
            await interaction.edit_original_response(content="⚠️ Keine gespeicherten Cogs vorhanden.")
            return

        lines = []
        for _, v in sorted(stored.items(), key=lambda x: x[1]["cog_name"].casefold()):
            lines.append(f"• **{v['cog_name']}** → `{v['repo_name']}`")

        embed = discord.Embed(title="Update: Stored Cogs", description="\n".join(lines))
        await interaction.edit_original_response(content=None, embed=embed)
