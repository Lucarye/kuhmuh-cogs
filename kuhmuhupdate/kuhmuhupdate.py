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

log = logging.getLogger("red.kuhmuh.kuhmuhupdate")

GUILD_ID = 1198649628787212458


# -----------------------------
# Helpers / Models
# -----------------------------

def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _normalize_key(name: str) -> str:
    # Case-insensitive, stable keys
    return name.strip().casefold()


def _clamp_text(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _fmt_dt(ts: dt.datetime) -> str:
    # short timestamp
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
    """
    Intercepts ctx.send / ctx.reply-like output so Downloader/commands don't spam channels.
    """

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
                # best-effort embed text extraction
                title = e.title or ""
                desc = e.description or ""
                fields = "\n".join(
                    f"{f.name}: {f.value}" for f in e.fields) if e.fields else ""
                chunk = "\n".join(
                    x for x in [title, desc, fields] if x).strip()
                if chunk:
                    parts.append(chunk)
        return "\n".join(parts).strip()


# -----------------------------
# UI Views (Dropdowns)
# -----------------------------

class CogSelectView(discord.ui.View):
    def __init__(self, *, options: List[discord.SelectOption], placeholder: str, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.selected_key: Optional[str] = None

        self.select = discord.ui.Select(
            placeholder=placeholder,
            options=options[:25],  # discord limit
            min_values=1,
            max_values=1,
        )
        self.select.callback = self._on_select  # type: ignore
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        self.selected_key = str(self.select.values[0])
        for item in self.children:
            item.disabled = True  # lock UI after choice
        await interaction.response.edit_message(view=self)
        self.stop()


# -----------------------------
# Cog
# -----------------------------

class KuhmuhUpdate(commands.Cog):
    """
    Admin-Tool: einzelne Cogs updaten (uninstall → repo update → install → load)
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=946102221, force_registration=True)

        self.config.register_global(
            admin_role_id=0,            # int, Pflicht (0 = nicht gesetzt)
            log_channel_id=0,           # optional
            embed_detail_limit=400,     # int
            repo_update_required=True,  # bool (v1 fix true)
            stored_cogs={},             # dict: key -> {cog_name, repo_name}
        )

        self._update_lock = asyncio.Lock()

        # ✅ Startup: guild-scope tree sync (wie in euren anderen Cogs)
        self._startup_task: Optional[asyncio.Task] = self.bot.loop.create_task(
            self._startup_guild_sync()
        )

    # -------------------------
    # Permission helpers
    # -------------------------

    async def _startup_guild_sync(self) -> None:
        try:
            await self.bot.wait_until_red_ready()
            await self.bot.wait_until_ready()

            guild_obj = discord.Object(id=GUILD_ID)

            # ✅ robust: ensures app commands are present in the guild scope
            self.bot.tree.copy_global_to(guild=guild_obj)
            await self.bot.tree.sync(guild=guild_obj)
        except Exception:
            # keine harte Fehlerbehandlung: Sync darf das Cog nicht blockieren
            pass

    async def _admin_role_id(self) -> int:
        rid = await self.config.admin_role_id()
        return int(rid or 0)

    async def _is_owner(self, user: discord.abc.User) -> bool:
        return await self.bot.is_owner(user)

    async def _require_admin(self, interaction: discord.Interaction) -> Tuple[bool, Optional[str]]:
        """
        Returns (ok, error_message). Enforces:
        - admin_role_id must be set (non-zero)
        - user must have that role
        """
        rid = await self._admin_role_id()
        if rid == 0:
            return False, "❌ ADMIN_ROLE ist nicht gesetzt. Nutze `/update manage setadminrole` (Owner-only initial)."

        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False, "❌ Dieser Command ist nur innerhalb einer Guild verfügbar."

        role = interaction.guild.get_role(rid)
        if role is None:
            return False, f"❌ ADMIN_ROLE (ID {rid}) existiert in dieser Guild nicht (mehr)."

        if role not in interaction.user.roles:
            return False, "❌ Du hast keine Berechtigung (ADMIN_ROLE erforderlich)."

        return True, None

    # -------------------------
    # Data helpers
    # -------------------------

    async def _get_stored_cogs(self) -> Dict[str, Dict[str, str]]:
        data = await self.config.stored_cogs()
        if not isinstance(data, dict):
            return {}
        # defensive: ensure structure
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
        data[key] = {"cog_name": cog_name.strip(
        ), "repo_name": repo_name.strip()}
        await self.config.stored_cogs.set(data)

    async def _remove_stored_cog(self, key: str) -> bool:
        data = await self._get_stored_cogs()
        if key in data:
            del data[key]
            await self.config.stored_cogs.set(data)
            return True
        return False

    # -------------------------
    # Command invocation helpers
    # -------------------------
    
    def _downloader(self) -> Optional[commands.Cog]:
        # Downloader cog name in Red is usually "Downloader"
        return self.bot.get_cog("Downloader")  # type: ignore

    async def _make_ctx(self, interaction: discord.Interaction) -> commands.Context:
        ctx = await commands.Context.from_interaction(interaction)
        ctx.prefix = "°"
        return ctx

    async def _dl_repo_update(self, interaction: discord.Interaction, repo: str) -> Tuple[bool, str]:
        dl = self._downloader()
        if dl is None:
            return False, "Downloader-Cog nicht geladen."

        ctx = await self._make_ctx(interaction)

        # Best-effort across versions: manche Methoden wollen (ctx, repo), manche nur (ctx)
        for meth in ("repo_update", "_repo_update", "update_repo"):
            fn = getattr(dl, meth, None)
            if fn:
                try:
                    # zuerst (ctx, repo) probieren
                    try:
                        res = await fn(ctx, repo)  # type: ignore
                    except TypeError:
                        # fallback: (ctx)
                        res = await fn(ctx)  # type: ignore
                    return True, str(res) if res is not None else ""
                except Exception as e:
                    return False, f"{type(e).__name__}: {e}"

        return False, "Keine passende Repo-Update Methode im Downloader gefunden."

    async def _dl_cog_install(self, interaction: discord.Interaction, repo: str, cog: str) -> Tuple[bool, str]:
        dl = self._downloader()
        if dl is None:
            return False, "Downloader-Cog nicht geladen."

        ctx = await self._make_ctx(interaction)

        for meth in ("cog_install", "_cog_install", "install_cog"):
            fn = getattr(dl, meth, None)
            if fn:
                try:
                    # meist (ctx, repo, cog) – optional noch extras in manchen Versionen
                    res = await fn(ctx, repo, cog)  # type: ignore
                    return True, str(res) if res is not None else ""
                except TypeError:
                    # fallback: (ctx, cog) – falls repo intern ermittelt wird
                    try:
                        res = await fn(ctx, cog)  # type: ignore
                        return True, str(res) if res is not None else ""
                    except Exception as e:
                        return False, f"{type(e).__name__}: {e}"
                except Exception as e:
                    return False, f"{type(e).__name__}: {e}"

        return False, "Keine passende Install-Methode im Downloader gefunden."

    async def _dl_cog_uninstall(self, interaction: discord.Interaction, cog: str) -> Tuple[bool, str]:
        dl = self._downloader()
        if dl is None:
            return False, "Downloader-Cog nicht geladen."

        ctx = await self._make_ctx(interaction)

        for meth in ("cog_uninstall", "_cog_uninstall", "uninstall_cog"):
            fn = getattr(dl, meth, None)
            if fn:
                try:
                    # meist (ctx, cog)
                    res = await fn(ctx, cog)  # type: ignore
                    return True, str(res) if res is not None else ""
                except TypeError:
                    # fallback: (ctx) – selten, aber defensiv
                    try:
                        res = await fn(ctx)  # type: ignore
                        return True, str(res) if res is not None else ""
                    except Exception as e:
                        return False, f"{type(e).__name__}: {e}"
                except Exception as e:
                    return False, f"{type(e).__name__}: {e}"

        return False, "Keine passende Uninstall-Methode im Downloader gefunden."


    def _get_subcommand(self, group_name: str, sub_name: str) -> Optional[commands.Command]:
        group = self.bot.get_command(group_name)
        if group is None:
            return None
        # group can be Command or Group
        if hasattr(group, "get_command"):
            return group.get_command(sub_name)  # type: ignore
        return None

    async def _invoke_command_capture(
        self,
        interaction: discord.Interaction,
        command_line: str,
    ) -> Tuple[bool, str]:
        """
        Führt einen Red-Command über echten Text aus (inkl. Converter/Parsing),
        fängt aber ctx.send-Ausgaben ab.
        Beispiel command_line: "°cog uninstall mein_cog"
        Returns (success, rendered_output_text)
        """

        class _FakeMessage:
            __slots__ = ("content", "author", "channel", "guild", "id")

            def __init__(self) -> None:
                self.content = command_line
                self.author = interaction.user
                self.channel = interaction.channel
                self.guild = interaction.guild
                self.id = 0

        catcher = _CommandOutputCatcher()

        try:
            msg = _FakeMessage()
            ctx = await self.bot.get_context(msg)  # type: ignore
            ctx.prefix = "°"

            # Patch ctx.send to capture
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
                await self.bot.invoke(ctx)
                output = catcher.render_text()
                # Wenn command nicht gefunden wurde, ctx.command ist None
                if ctx.command is None:
                    return False, (output + "\nCommandNotFound").strip() if output else "CommandNotFound"
                return True, output
            except Exception as e:
                output = catcher.render_text()
                err = f"{type(e).__name__}: {e}".strip()
                combined = (output + "\n" + err).strip() if output else err
                return False, combined
            finally:
                ctx.send = original_send  # type: ignore
                if original_reply is not None:
                    ctx.reply = original_reply  # type: ignore
                if original_tick is not None:
                    ctx.tick = original_tick  # type: ignore

        except Exception as e:
            # Falls get_context/invoke selbst hart scheitert
            err = f"{type(e).__name__}: {e}".strip()
            return False, err


    def _extract_not_installed(self, text: str) -> bool:
        """
        Best-effort detection for 'not installed' cases to mark as ⚠️ and continue.
        Keeps it loose to avoid locale/output changes.
        """
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

    # -------------------------
    # Embeds / Logging
    # -------------------------

    async def _maybe_log_full_output(self, interaction: discord.Interaction, title: str, text: str) -> None:
        if not text:
            return

        # Always log to python logger
        log.info("%s\n%s", title, text)

        # Optional: log channel
        ch_id = int(await self.config.log_channel_id() or 0)
        if ch_id == 0:
            return

        if not interaction.guild:
            return

        channel = interaction.guild.get_channel(ch_id)
        if channel is None or not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return

        # Avoid massive dumps; Discord hard limit per message
        safe = text
        if len(safe) > 1900:
            safe = safe[:1900] + "…"

        with contextlib.suppress(Exception):
            await channel.send(f"**{title}**\n```text\n{safe}\n```")

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
            e.add_field(
                name=r.name,
                value=f"{r.status} {r.summary}",
                inline=False,
            )

        e.set_footer(text=f"{invoker} • Dauer: {duration_s:.2f}s")
        return e

    # -------------------------
    # /update (single command UX)
    # -------------------------

    async def _autocomplete_stored_cogs(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        stored = await self._get_stored_cogs()
        cur = (current or "").casefold().strip()

        items = []
        for key, v in stored.items():
            name = v.get("cog_name", "")
            repo = v.get("repo_name", "")
            if not name:
                continue
            if cur and cur not in name.casefold():
                continue
            # value = key (normalized) -> wir lösen später wieder auf
            items.append(app_commands.Choice(name=f"{name}", value=key))

        # Discord Limit: max 25 choices
        items.sort(key=lambda c: c.name.casefold())
        return items[:25]

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="update",
        description="Admin: Cog updaten/verwalten (Dropdown via action).",
    )
    @app_commands.describe(
        action="Aktion auswählen",
        cog="Gespeichertes Cog (für run/remove)",
        cog_name="Cog-Name (für add)",
        repo_name="Repository-Name (für add)",
        role="ADMIN_ROLE setzen (für setadminrole)",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(
                name="Run (uninstall → repo update → install → load)", value="run"),
            app_commands.Choice(
                name="Manage: Add (Cog + Repo speichern)", value="add"),
            app_commands.Choice(
                name="Manage: Remove (gespeichertes Cog löschen)", value="remove"),
            app_commands.Choice(
                name="Manage: List (alle gespeicherten Cogs)", value="list"),
            app_commands.Choice(
                name="Manage: SetAdminRole (ADMIN_ROLE setzen)", value="setadminrole"),
        ]
    )
    @app_commands.autocomplete(cog=_autocomplete_stored_cogs)
    async def update_cmd(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        cog: Optional[str] = None,
        cog_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        role: Optional[discord.Role] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=False)

        act = (action.value or "").strip()

        # ---------- setadminrole (Owner-only initial; otherwise ADMIN_ROLE required) ----------
        if act == "setadminrole":
            if role is None:
                await interaction.edit_original_response(content="❌ Für `setadminrole` musst du `role` angeben.")
                return

            current = await self._admin_role_id()

            if current == 0:
                if not await self._is_owner(interaction.user):
                    await interaction.edit_original_response(
                        content="❌ ADMIN_ROLE ist noch nicht gesetzt. Initial darf nur der Bot-Owner `setadminrole` ausführen."
                    )
                    return
            else:
                ok, err = await self._require_admin(interaction)
                if not ok:
                    await interaction.edit_original_response(content=err)
                    return

            await self.config.admin_role_id.set(int(role.id))
            await interaction.edit_original_response(content=f"✅ ADMIN_ROLE gesetzt auf: {role.mention} (`{role.id}`)")
            return

        # Ab hier: ADMIN_ROLE strikt erforderlich
        ok, err = await self._require_admin(interaction)
        if not ok:
            await interaction.edit_original_response(content=err)
            return

        # ---------- list ----------
        if act == "list":
            stored = await self._get_stored_cogs()
            if not stored:
                await interaction.edit_original_response(content="⚠️ Keine gespeicherten Cogs vorhanden.")
                return

            lines = []
            for _, v in sorted(stored.items(), key=lambda x: x[1]["cog_name"].casefold()):
                lines.append(f"• **{v['cog_name']}** → `{v['repo_name']}`")

            embed = discord.Embed(
                title="Update: Stored Cogs", description="\n".join(lines))
            await interaction.edit_original_response(embed=embed, content=None, view=None)
            return

        # ---------- add ----------
        if act == "add":
            cn = (cog_name or "").strip()
            rn = (repo_name or "").strip()

            if not cn or not rn:
                await interaction.edit_original_response(
                    content="❌ Für `add` musst du `cog_name` und `repo_name` angeben."
                )
                return

            await self._set_stored_cog(cn, rn)
            await interaction.edit_original_response(content=f"✅ Gespeichert: **{cn}** → Repo **{rn}**")
            return

        # ---------- remove ----------
        if act == "remove":
            if not cog:
                await interaction.edit_original_response(content="❌ Für `remove` musst du `cog` auswählen.")
                return

            removed = await self._remove_stored_cog(cog)
            if removed:
                await interaction.edit_original_response(content="✅ Eintrag entfernt.")
            else:
                await interaction.edit_original_response(content="⚠️ Eintrag nicht gefunden.")
            return

        # ---------- run ----------
        if act == "run":
            if not cog:
                await interaction.edit_original_response(content="❌ Für `run` musst du `cog` auswählen.")
                return

            stored = await self._get_stored_cogs()
            selection = stored.get(cog)
            if not selection:
                await interaction.edit_original_response(content="⚠️ Auswahl nicht gefunden (Liste evtl. geändert).")
                return

            cog_name_real = selection["cog_name"]
            repo_name_real = selection["repo_name"]

            # Lock to prevent parallel updates
            if self._update_lock.locked():
                await interaction.edit_original_response(
                    content="⏭️ Ein Update läuft bereits. Bitte warte, bis es abgeschlossen ist.",
                    embed=None,
                    view=None,
                )
                return

            started = _now_utc()
            t0 = dt.datetime.now(dt.timezone.utc)

            async with self._update_lock:
                results: List[StepResult] = []

                # Step 1: Uninstall
                ok1, out1 = await self._dl_cog_uninstall(interaction, cog_name_real)
                await self._maybe_log_full_output(interaction, f"[KuhmuhUpdate] Uninstall {cog_name_real}", out1)

                if ok1:
                    results.append(StepResult(
                        name="Uninstall", status="✅", summary="Deinstalliert.", details=out1))
                else:
                    if self._extract_not_installed(out1):
                        results.append(StepResult(
                            name="Uninstall", status="⚠️", summary="Nicht installiert (weiter).", details=out1))
                    else:
                        results.append(StepResult(
                            name="Uninstall", status="❌", summary="Fehler – Abbruch.", details=out1))
                        duration = (dt.datetime.now(
                            dt.timezone.utc) - t0).total_seconds()
                        embed_final = await self._build_status_embed(
                            cog_name=cog_name_real,
                            repo_name=repo_name_real,
                            started=started,
                            invoker=interaction.user,
                            results=results,
                            duration_s=duration,
                        )
                        await interaction.edit_original_response(embed=embed_final, content=None, view=None)
                        return

                # Step 2: Repo Update
                ok2, out2 = await self._dl_repo_update(interaction, repo_name_real)
                await self._maybe_log_full_output(interaction, f"[KuhmuhUpdate] Repo Update {repo_name_real}", out2)

                if ok2:
                    results.append(StepResult(
                        name="Repo Update", status="✅", summary="Aktualisiert.", details=out2))
                else:
                    results.append(StepResult(
                        name="Repo Update", status="❌", summary="Fehler – Abbruch.", details=out2))
                    duration = (dt.datetime.now(
                        dt.timezone.utc) - t0).total_seconds()
                    embed_final = await self._build_status_embed(
                        cog_name=cog_name_real,
                        repo_name=repo_name_real,
                        started=started,
                        invoker=interaction.user,
                        results=results,
                        duration_s=duration,
                    )
                    await interaction.edit_original_response(embed=embed_final, content=None, view=None)
                    return

                # Step 3: Install
                ok3, out3 = await self._dl_cog_install(interaction, repo_name_real, cog_name_real)
                await self._maybe_log_full_output(interaction, f"[KuhmuhUpdate] Install {repo_name_real}/{cog_name_real}", out3)

                if ok3:
                    results.append(StepResult(
                        name="Install", status="✅", summary="Installiert.", details=out3))
                else:
                    results.append(StepResult(
                        name="Install", status="❌", summary="Fehler – Abbruch.", details=out3))
                    duration = (dt.datetime.now(
                        dt.timezone.utc) - t0).total_seconds()
                    embed_final = await self._build_status_embed(
                        cog_name=cog_name_real,
                        repo_name=repo_name_real,
                        started=started,
                        invoker=interaction.user,
                        results=results,
                        duration_s=duration,
                    )
                    await interaction.edit_original_response(embed=embed_final, content=None, view=None)
                    return

                # Step 4: Load (über echten ctx)
                ctx_load = await commands.Context.from_interaction(interaction)
                ctx_load.prefix = "°"

                catcher = _CommandOutputCatcher()
                original_send = ctx_load.send
                ctx_load.send = catcher.send  # type: ignore

                try:
                    load_cmd = self.bot.get_command("load")
                    if load_cmd is None:
                        ok4, out4 = False, "Load-Command nicht gefunden."
                    else:
                        await ctx_load.invoke(load_cmd, cog_name_real)
                        ok4, out4 = True, catcher.render_text()
                except Exception as e:
                    out4 = catcher.render_text()
                    err = f"{type(e).__name__}: {e}".strip()
                    ok4 = False
                    out4 = (out4 + "\n" + err).strip() if out4 else err
                finally:
                    ctx_load.send = original_send  # type: ignore

                await self._maybe_log_full_output(interaction, f"[KuhmuhUpdate] Load {cog_name_real}", out4)

                if ok4:
                    results.append(StepResult(
                        name="Load", status="✅", summary="Geladen.", details=out4))
                else:
                    results.append(StepResult(
                        name="Load", status="❌", summary="Fehler – Prozess beendet.", details=out4))

                duration = (dt.datetime.now(
                    dt.timezone.utc) - t0).total_seconds()

                limit = int(await self.config.embed_detail_limit() or 400)
                for r in results:
                    if r.details:
                        snippet = _clamp_text(
                            r.details.replace("```", "'''"), limit)
                        if snippet:
                            r.summary = f"{r.summary}\n```text\n{snippet}\n```"

                embed_final = await self._build_status_embed(
                    cog_name=cog_name_real,
                    repo_name=repo_name_real,
                    started=started,
                    invoker=interaction.user,
                    results=results,
                    duration_s=duration,
                )
                await interaction.edit_original_response(embed=embed_final, content=None, view=None)
            return

        await interaction.edit_original_response(content="❌ Unbekannte Aktion.")

    # -------------------------
    # App command registration
    # -------------------------

    async def cog_load(self) -> None:
        # App Commands werden von Red/discord.py automatisch beim Cog-Inject registriert.
        # Keine manuelle Registrierung, sonst: CommandAlreadyRegistered.
        return

    async def cog_unload(self) -> None:
        # Best-effort Cleanup ist hier nicht nötig und kann bei Reloads zu Edge-Cases führen.
        return
