import re
import discord
from redbot.core import commands

MSG_RE = re.compile(r"channels/(\d+)/(\d+)")

def _fmt_embed_info(e: discord.Embed) -> str:
    parts = []
    if e.title:
        parts.append(f"Titel: {e.title}")
    if e.description:
        parts.append(f"Beschreibung: {e.description[:300]}{'…' if len(e.description) > 300 else ''}")
    if e.color:
        parts.append(f"Farbe: #{e.color.value:06X}")
    if e.author and (e.author.name or e.author.url):
        parts.append(f"Author: {e.author.name or ''} {f'({e.author.url})' if e.author.url else ''}".strip())
    if e.footer and (e.footer.text or e.footer.icon_url):
        parts.append(f"Footer: {e.footer.text or ''}")
    if e.fields:
        parts.append(f"Felder: {len(e.fields)}")
        for i, f in enumerate(e.fields, start=1):
            parts.append(f"  [{i}] {f.name} | inline={f.inline} | Wert: {(f.value or '')[:120]}{'…' if f.value and len(f.value)>120 else ''}")
    return "\n".join(parts) if parts else "(kein Embed-Inhalt)"

def _fmt_components(components) -> str:
    lines = []
    for row_i, row in enumerate(components or [], start=1):
        comps = getattr(row, "children", getattr(row, "components", []))
        for comp in comps:
            if isinstance(comp, discord.Button):
                emoji = ""
                if comp.emoji:
                    emoji = comp.emoji.name or str(comp.emoji.id)
                lines.append(
                    f"Reihe {row_i} | Label: '{comp.label}' | Emoji: '{emoji}' | Style: {comp.style} | Custom-ID: '{comp.custom_id}' | URL: '{comp.url}'"
                )
    return "\n".join(lines) if lines else "(keine Buttons/Komponenten)"

class NachrichtenInfo(commands.Cog):
    """Zeigt Buttons (custom_id) und Embed-Infos einer Nachricht an."""

    def __init__(self, bot):
        self.bot = bot

    @commands.is_owner()
    @commands.command(name="nachrichteninfo")
    async def nachrichteninfo_prefix(self, ctx: commands.Context, *, nachricht: str):
        """Owner: Nachricht analysieren (Nachrichtenlink ODER 'channel_id message_id')."""
        await self._run(ctx, nachricht, ephemeral=False)

    @commands.is_owner()
    @commands.hybrid_command(name="nachrichteninfoh", with_app_command=True, description="Analysiert eine Nachricht (Buttons & Embed-Infos).")
    async def nachrichteninfo_hybrid(self, ctx: commands.Context, *, nachricht: str):
        await ctx.defer(ephemeral=True)
        await self._run(ctx, nachricht, ephemeral=True)

    async def _run(self, ctx: commands.Context, nachricht: str, ephemeral: bool):
        ch_id = msg_id = None
        m = MSG_RE.search(nachricht)
        if m:
            ch_id, msg_id = int(m.group(1)), int(m.group(2))
        else:
            parts = nachricht.strip().split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                ch_id, msg_id = int(parts[0]), int(parts[1])

        if not ch_id or not msg_id:
            return await self._send(ctx, "❌ Bitte gültigen **Nachrichtenlink** oder `channel_id message_id` angeben.", ephemeral)

        try:
            channel = await self.bot.fetch_channel(ch_id)
            message = await channel.fetch_message(msg_id)
        except Exception as e:
            return await self._send(ctx, f"⚠️ Nachricht konnte nicht geladen werden:\n`{e}`", ephemeral)

        comp_txt = _fmt_components(message.components)
        emb_txts = []
        for idx, emb in enumerate(message.embeds, start=1):
            emb_txts.append(f"[Embed {idx}]\n{_fmt_embed_info(emb)}")
        embeds_block = "\n\n".join(emb_txts) if emb_txts else "(kein Embed vorhanden)"

        out = []
        out.append("=== Komponenten ===")
        out.append(comp_txt)
        out.append("\n=== Embed-Infos ===")
        out.append(embeds_block)
        text = "\n".join(out)
        if len(text) > 1900:
            text = text[:1900] + "\n… (gekürzt)"

        await self._send(ctx, f"```\n{text}\n```", ephemeral)

    async def _send(self, ctx: commands.Context, content: str, ephemeral: bool):
        try:
            if hasattr(ctx, "interaction") and ctx.interaction is not None:
                return await ctx.interaction.followup.send(content, ephemeral=ephemeral)
        except Exception:
            pass
        await ctx.send(content)

async def setup(bot):
    await bot.add_cog(NachrichtenInfo(bot))
