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

# Fuer die Testphase False; fuer den Produktivbetrieb auf True setzen.
WELCOME_ANTI_SPAM_ENABLED = False

WELCOME_MESSAGES = (
    "Die Herde hat Zuwachs bekommen! Willkommen bei den KuHMuhs, {member} - schoen, dass du bei uns bist.",
    "Ein neues Kalb ist auf der Weide angekommen. Herzlich willkommen bei den KuHMuhs, {member}!",
    "Macht Platz auf der Weide - unsere Herde waechst! Willkommen bei den KuHMuhs, {member}.",
    "Muhment mal ... da ist ja jemand Neues! Herzlich willkommen in der Herde, {member}.",
    "Die Weide wird voller: Willkommen in der KuHMuh-Herde, {member}!",
    "Frisches Muhen auf der Weide! Schoen, dass du da bist, {member}.",
    "Die Herde macht ein herzliches Muh fuer dich. Willkommen bei den KuHMuhs, {member}!",
    "Unsere Weide hat ein neues Gesicht bekommen. Willkommen, {member}!",
    "Vorhang auf fuer ein neues Herdenmitglied: Willkommen bei den KuHMuhs, {member}.",
    "Die Stallglocke laeutet fuer dich! Herzlich willkommen, {member}.",
    "Ein neues Paar Hufe betritt die Weide. Willkommen in der Herde, {member}!",
    "Die KuHMuhs freuen sich ueber Verstaerkung. Willkommen, {member}!",
    "Die Herde waechst um ein muh-tiges Mitglied: Willkommen, {member}!",
    "Schnapp dir einen Platz auf der Weide - willkommen bei den KuHMuhs, {member}.",
    "Ein herzliches Muh und willkommen in unserer Herde, {member}!",
    "Die Weide ist bereit fuer dich. Schoen, dass du zu den KuHMuhs kommst, {member}!",
    "Unsere Herde hat dich schon erwartet. Willkommen, {member}!",
    "Neue Hufe, neue Geschichten: Herzlich willkommen bei den KuHMuhs, {member}!",
    "Die Milchbar ist offen und die Herde komplettiert sich. Willkommen, {member}!",
    "Muh an, Herdenmitglied! Willkommen bei den KuHMuhs, {member}.",
    "Die Weide bekommt Gesellschaft. Herzlich willkommen, {member}!",
    "Ein neues Kalb ist da - die Herde sagt willkommen, {member}!",
    "Gemeinsam grasen macht mehr Spass. Willkommen in der Herde, {member}!",
    "Die KuHMuh-Herde begruesst dich mit einem frohen Muh, {member}!",
)

WELCOME_BACK_MESSAGES = (
    "Da kennt jemand den Weg zur Weide noch! Willkommen zurueck bei den KuHMuhs, {member}.",
    "Eine bekannte Kuh ist wieder da - willkommen zurueck in der Herde, {member}!",
    "Die Herde bekommt ein bekanntes Gesicht zurueck. Schoen, dass du wieder da bist, {member}.",
    "Zurueck auf der Weide! Willkommen zurueck bei den KuHMuhs, {member}.",
    "Die Stallglocke klingt vertraut: Willkommen zurueck, {member}!",
    "Die alte Weidespur hat dich zur Herde gefuehrt. Willkommen zurueck, {member}!",
    "Bekannte Hufe auf der Weide - schoen, dich wiederzusehen, {member}.",
    "Die Herde freut sich ueber deine Rueckkehr. Willkommen zurueck, {member}!",
)

DEFAULT_GUILD = {"welcome_users": {}}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_error(message: str):
    print(f"[willkommen] {message}", file=sys.stderr)


class Willkommen(commands.Cog):
    """Begruesst Mitglieder beim erstmaligen Rollenbeitritt."""

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
        messages = WELCOME_BACK_MESSAGES if is_welcome_back else WELCOME_MESSAGES
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel is None or not hasattr(channel, "send"):
            _log_error(f"Welcome channel {WELCOME_CHANNEL_ID} not found in guild {member.guild.id}")
            return

        embed = discord.Embed(
            description=random.choice(messages).format(member=member.mention),
            color=discord.Color.gold(),
        )
        embed.set_image(url=WELCOME_IMAGE_URL)
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
