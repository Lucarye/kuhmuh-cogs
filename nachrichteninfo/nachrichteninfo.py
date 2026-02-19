import re
import io
import json
from typing import Any, Dict, List, Optional

import discord
from redbot.core import commands

MSG_RE = re.compile(r"channels/(\d+)/(\d+)")


def _discord_ts(dt: Optional[discord.utils.utcnow().__class__]) -> str:
    """Formats a datetime as Discord timestamp, if possible."""
    if not dt:
        return ""
    try:
        unix = int(dt.timestamp())
        return f"<t:{unix}:F> (unix={unix})"
    except Exception:
        return ""


def _iso(dt) -> str:
    if not dt:
        return ""
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def _fmt_embed_info(e: discord.Embed) -> str:
    parts = []
    if e.title:
        parts.append(f"Titel: {e.title}")
    if e.description:
        parts.append(f"Beschreibung: {e.description}")
    if e.url:
        parts.append(f"URL: {e.url}")
    if e.color:
        parts.append(f"Farbe: #{e.color.value:06X}")
    if e.author and (e.author.name or e.author.url):
        parts.append(
            f"Author: {(e.author.name or '').strip()} {f'({e.author.url})' if e.author.url else ''}".strip()
        )
    if e.footer and (e.footer.text or e.footer.icon_url):
        parts.append(f"Footer: {e.footer.text or ''}")

    if e.thumbnail and e.thumbnail.url:
        parts.append(f"Thumbnail: {e.thumbnail.url}")
    if e.image and e.image.url:
        parts.append(f"Image: {e.image.url}")

    if e.fields:
        parts.append(f"Felder: {len(e.fields)}")
        for i, f in enumerate(e.fields, start=1):
            parts.append(f"  [{i}] {f.name} | inline={f.inline} | Wert: {f.value or ''}")
    return "\n".join(parts) if parts else "(kein Embed-Inhalt)"


def _fmt_components(components) -> str:
    lines = []
    for row_i, row in enumerate(components or [], start=1):
        comps = getattr(row, "children", getattr(row, "components", []))
        for comp in comps:
            if isinstance(comp, discord.Button):
                emoji = ""
                if comp.emoji:
                    emoji = comp.emoji.name or str(getattr(comp.emoji, "id", "")) or str(comp.emoji)
                lines.append(
                    f"Reihe {row_i} | Label: '{comp.label}' | Emoji: '{emoji}' | "
                    f"Style: {comp.style} | Custom-ID: '{comp.custom_id}' | URL: '{comp.url}'"
                )
            else:
                # Falls später SelectMenus o.ä. dazukommen, wenigstens sichtbar machen
                t = type(comp).__name__
                lines.append(f"Reihe {row_i} | Komponente: {t}")
    return "\n".join(lines) if lines else "(keine Buttons/Komponenten)"


def _split_text_safely(text: str, limit: int) -> List[str]:
    """
    Splittet Text in Teile <= limit Zeichen, bevorzugt an Zeilenumbrüchen.
    Falls eine einzelne Zeile länger als limit ist, wird sie hart gesplittet.
    """
    if not text:
        return [""]

    chunks: List[str] = []
    buf: List[str] = []
    buf_len = 0

    lines = text.split("\n")
    for line in lines:
        add_len = len(line) + (1 if buf else 0)

        if len(line) > limit:
            if buf:
                chunks.append("\n".join(buf))
                buf = []
                buf_len = 0

            start = 0
            while start < len(line):
                chunks.append(line[start : start + limit])
                start += limit
            continue

        if buf_len + add_len <= limit:
            if buf:
                buf.append(line)
                buf_len += add_len
            else:
                buf.append(line)
                buf_len = len(line)
        else:
            chunks.append("\n".join(buf))
            buf = [line]
            buf_len = len(line)

    if buf:
        chunks.append("\n".join(buf))

    return chunks


def _extract_flags(raw: str) -> (str, Dict[str, bool]):
    """
    Simple flag parsing for prefix-only usage.
    Recognizes: --json
    Returns (clean_input, flags)
    """
    flags = {"json": False}
    parts = raw.split()
    kept = []
    for p in parts:
        if p.lower() == "--json":
            flags["json"] = True
        else:
            kept.append(p)
    return " ".join(kept).strip(), flags


def _embed_to_dict(e: discord.Embed) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "title": e.title,
        "description": e.description,
        "url": e.url,
        "color": (e.color.value if e.color else None),
        "timestamp": _iso(e.timestamp) if getattr(e, "timestamp", None) else None,
        "author": None,
        "footer": None,
        "thumbnail": None,
        "image": None,
        "fields": [],
    }

    if e.author and (e.author.name or e.author.url or e.author.icon_url):
        d["author"] = {
            "name": e.author.name,
            "url": e.author.url,
            "icon_url": str(e.author.icon_url) if e.author.icon_url else None,
        }

    if e.footer and (e.footer.text or e.footer.icon_url):
        d["footer"] = {
            "text": e.footer.text,
            "icon_url": str(e.footer.icon_url) if e.footer.icon_url else None,
        }

    if e.thumbnail and e.thumbnail.url:
        d["thumbnail"] = {"url": e.thumbnail.url}
    if e.image and e.image.url:
        d["image"] = {"url": e.image.url}

    if e.fields:
        for f in e.fields:
            d["fields"].append(
                {"name": f.name, "value": f.value, "inline": bool(f.inline)}
            )

    return d


def _components_to_dict(components) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row_i, row in enumerate(components or [], start=1):
        comps = getattr(row, "children", getattr(row, "components", []))
        row_entry = {"row": row_i, "components": []}
        for comp in comps:
            if isinstance(comp, discord.Button):
                emoji = None
                if comp.emoji:
                    emoji = {
                        "name": getattr(comp.emoji, "name", None) or str(comp.emoji),
                        "id": getattr(comp.emoji, "id", None),
                    }
                row_entry["components"].append(
                    {
                        "type": "button",
                        "label": comp.label,
                        "style": int(comp.style) if comp.style is not None else None,
                        "custom_id": comp.custom_id,
                        "url": comp.url,
                        "disabled": bool(comp.disabled),
                        "emoji": emoji,
                    }
                )
            else:
                row_entry["components"].append({"type": type(comp).__name__})
        rows.append(row_entry)
    return rows


class NachrichtenInfo(commands.Cog):
    """Zeigt Buttons (custom_id) und Embed-Infos einer Nachricht an. Optional: JSON-Export."""

    def __init__(self, bot):
        self.bot = bot

    @commands.is_owner()
    @commands.command(name="nachrichteninfo")
    async def nachrichteninfo_prefix(self, ctx: commands.Context, *, nachricht: str):
        """
        Owner: Nachricht analysieren (Nachrichtenlink ODER 'channel_id message_id').
        Flags:
          --json   -> JSON-Export als Datei anhängen
        """
        clean, flags = _extract_flags(nachricht)
        await self._run(ctx, clean, do_json=flags["json"])

    async def _run(self, ctx: commands.Context, nachricht: str, do_json: bool):
        ch_id = msg_id = None
        m = MSG_RE.search(nachricht)
        if m:
            ch_id, msg_id = int(m.group(1)), int(m.group(2))
        else:
            parts = nachricht.strip().split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                ch_id, msg_id = int(parts[0]), int(parts[1])

        if not ch_id or not msg_id:
            return await ctx.send("❌ Bitte gültigen **Nachrichtenlink** oder `channel_id message_id` angeben.")

        try:
            channel = await self.bot.fetch_channel(ch_id)
            message = await channel.fetch_message(msg_id)
        except Exception as e:
            return await ctx.send(f"⚠️ Nachricht konnte nicht geladen werden:\n`{e}`")

        # ---- Meta ----
        guild = getattr(channel, "guild", None)
        guild_line = f"{guild.name} ({guild.id})" if guild else "(unbekannt)"
        channel_name = getattr(channel, "name", None) or "(kein Name)"

        created_iso = _iso(message.created_at)
        created_ts = _discord_ts(message.created_at)

        edited_line = ""
        if message.edited_at:
            edited_iso = _iso(message.edited_at)
            edited_ts = _discord_ts(message.edited_at)
            edited_line = f"Edited: {edited_iso} | {edited_ts}"
        else:
            edited_line = "Edited: (nicht bearbeitet / keine Info)"

        meta_lines = [
            "=== Meta ===",
            f"Guild: {guild_line}",
            f"Channel: {channel_name} ({message.channel.id})",
            f"Message ID: {message.id}",
            f"Jump URL: {message.jump_url}",
            f"Created: {created_iso} | {created_ts}",
            edited_line,
            "Hinweis: Discord liefert keine vollständige Edit-Historie (nur edited_at, wenn vorhanden).",
            "",
        ]

        # ---- Components & Embeds (Text) ----
        comp_txt = _fmt_components(message.components)

        emb_txts = []
        for idx, emb in enumerate(message.embeds, start=1):
            emb_txts.append(f"[Embed {idx}]\n{_fmt_embed_info(emb)}")
        embeds_block = "\n\n".join(emb_txts) if emb_txts else "(kein Embed vorhanden)"

        out = []
        out.extend(meta_lines)
        out.append("=== Komponenten ===")
        out.append(comp_txt)
        out.append("\n=== Embed-Infos ===")
        out.append(embeds_block)

        text = "\n".join(out)

        # ---- Split output into multiple messages (chat) ----
        base_limit = 1800  # safe for codeblock + header
        chunks = _split_text_safely(text, base_limit)
        total = len(chunks)

        for i, chunk in enumerate(chunks, start=1):
            header = f"[Nachrichteninfo – Teil {i}/{total}]"
            payload = f"```\n{header}\n{chunk}\n```"
            await ctx.send(payload)

        # ---- JSON export as file ----
        if do_json:
            export: Dict[str, Any] = {
                "meta": {
                    "guild_id": guild.id if guild else None,
                    "guild_name": guild.name if guild else None,
                    "channel_id": message.channel.id,
                    "channel_name": channel_name,
                    "message_id": message.id,
                    "jump_url": message.jump_url,
                    "created_at": created_iso,
                    "edited_at": _iso(message.edited_at) if message.edited_at else None,
                    "author_id": message.author.id if message.author else None,
                    "author_name": str(message.author) if message.author else None,
                },
                "components": _components_to_dict(message.components),
                "embeds": [_embed_to_dict(e) for e in message.embeds],
            }

            data = json.dumps(export, ensure_ascii=False, indent=2).encode("utf-8")
            fp = io.BytesIO(data)
            filename = f"nachrichteninfo_{message.id}.json"
            file = discord.File(fp=fp, filename=filename)

            await ctx.send(f"📎 JSON-Export: `{filename}`", file=file)


async def setup(bot):
    await bot.add_cog(NachrichtenInfo(bot))
