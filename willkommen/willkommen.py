import asyncio
import random
import sys
import traceback
from collections import defaultdict
from datetime import datetime, timezone

import discord  # pyright: ignore[reportMissingImports]
from redbot.core import Config, commands  # pyright: ignore[reportMissingImports]
from redbot.core.bot import Red  # pyright: ignore[reportMissingImports]


GUILD_ID = 1198649628787212458
MEMBER_ROLE_ID = 1198654521354764449
ENTRY_ROLE_ID = 1199022986955603999
FRIEND_ROLE_ID = 1206903378014380063
WELCOME_CHANNEL_ID = 1199322485297000528
WELCOME_IMAGE_URL = (
    "https://cdn.discordapp.com/attachments/1404063753946796122/"
    "1424149435662733393/farm_resized_960x540.webp"
)

# Für die Testphase False; für den Produktivbetrieb auf True setzen.
WELCOME_ANTI_SPAM_ENABLED = False

WELCOME_LINES = (
    "Die Herde hat Zuwachs bekommen!",
    "Ein neues Kalb ist auf der Weide angekommen.",
    "Macht Platz auf der Weide - unsere Herde wächst!",
    "Muhment mal ... da ist ja jemand Neues!",
    "Frisches Muhen auf der Weide!",
    "Die KuHMuhs freuen sich über Verstärkung.",
    "Ein neues Paar Hufe betritt die Weide.",
    "Die Stallglocke läutet für dich!",
    "Neue Hufe, neue Geschichten.",
    "Die Weide bekommt Gesellschaft.",
    "Ein herzliches Muh aus der Herde!",
    "Die Milchbar ist offen und die Herde wächst.",
)

WELCOME_BACK_LINES = (
    "Da kennt jemand den Weg zur Weide noch!",
    "Eine bekannte Kuh ist wieder da.",
    "Die Herde bekommt ein bekanntes Gesicht zurück.",
    "Zurück auf der Weide!",
    "Die Stallglocke klingt vertraut.",
    "Die alte Weidespur hat dich zur Herde geführt.",
    "Bekannte Hufe auf der Weide.",
    "Die Herde freut sich über deine Rückkehr.",
)

DEFAULT_GUILD = {"welcome_users": {}}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_error(message: str):
    print(f"[willkommen] {message}", file=sys.stderr)


class Willkommen(commands.Cog):
    """Begrüßt Mitglieder beim erstmaligen Rollenbeitritt."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0x4B55484D554857, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)
        self._locks = defaultdict(asyncio.Lock)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.guild.id != GUILD_ID:
            return

        before_role_ids = {role.id for role in before.roles}
        after_role_ids = {role.id for role in after.roles}
        if MEMBER_ROLE_ID in before_role_ids or MEMBER_ROLE_ID not in after_role_ids:
            return

        async with self._locks[(after.guild.id, after.id)]:
            await self._handle_member_role_received(after, after_role_ids)

    async def _handle_member_role_received(self, member: discord.Member, role_ids: set[int]):
        guild_data = await self.config.guild(member.guild).all()
        users = guild_data.get("welcome_users", {})
        user_key = str(member.id)
        record = dict(users.get(user_key, {}))
        now = _timestamp()
        record["user_id"] = member.id
        record["last_member_role_received_at"] = now

        is_welcome_back = (
            FRIEND_ROLE_ID in role_ids
            or record.get("previous_status") in {"friend", "former_member"}
            or record.get("member_history", {}).get("was_former_member", False)
        )
        already_welcomed_back = record.get("last_welcome_type") == "welcome_back"
        if WELCOME_ANTI_SPAM_ENABLED and record.get("welcome_count", 0) > 0 and (
            not is_welcome_back or already_welcomed_back
        ):
            users[user_key] = record
            await self.config.guild(member.guild).welcome_users.set(users)
            return

        welcome_type = "welcome_back" if is_welcome_back else "welcome"
        title = (
            "<:muhkuh:1207038544510586890> Willkommen zurück!"
            if is_welcome_back
            else "<:muhkuh:1207038544510586890> Willkommen in der Herde!"
        )
        footer = "KuHMuh • Willkommen zurück" if is_welcome_back else "KuHMuh • Willkommen in der Herde"
        lines = WELCOME_BACK_LINES if is_welcome_back else WELCOME_LINES
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel is None or not hasattr(channel, "send"):
            _log_error(f"Welcome channel {WELCOME_CHANNEL_ID} not found in guild {member.guild.id}")
            return

        embed = discord.Embed(
            description=(
                f"# {title}\n\n"
                f"{random.choice(lines)}\n\n"
                f"Schön, dass du {'wieder ' if is_welcome_back else ''}da bist, {member.mention}!"
            ),
            color=discord.Color.gold(),
        )
        embed.set_image(url=WELCOME_IMAGE_URL)
        embed.set_footer(text=footer)
        try:
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=[member]),
            )
        except (discord.Forbidden, discord.HTTPException):
            _log_error(f"Could not send {welcome_type} message for user {member.id}")
            traceback.print_exc()
            return

        previous_status = self._previous_status(role_ids)
        record.setdefault("first_welcome_at", now)
        record["last_welcome_at"] = now
        record["welcome_count"] = int(record.get("welcome_count", 0)) + 1
        record["previous_status"] = previous_status
        record["last_welcome_type"] = welcome_type
        history = dict(record.get("member_history", {}))
        history["was_member"] = True
        history["was_former_member"] = previous_status in {"friend", "former_member"}
        record["member_history"] = history
        users[user_key] = record
        await self.config.guild(member.guild).welcome_users.set(users)

    @staticmethod
    def _previous_status(role_ids: set[int]) -> str:
        if FRIEND_ROLE_ID in role_ids:
            return "friend"
        if ENTRY_ROLE_ID in role_ids:
            return "entry"
        return "unknown"
