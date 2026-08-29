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
WELCOME_MEDIA_THREAD_ID = 1543373634427559946
WELCOME_IMAGE_URL = "https://cdn.discordapp.com/attachments/1543373634427559946/1543376216004886618/mxks5HTw3tqI3zGJ8a.gif?ex=6a94a49c&is=6a93531c&hm=e3c990b9709476995101370728d22ce6bcc8a75e0cbeabd8871dd311cc1d1555&"
WELCOME_HOLY_COW_IMAGE_URL = WELCOME_IMAGE_URL
WELCOME_HOLY_COW_CHANCE = 1

# Für die Testphase False; für den Produktivbetrieb auf True setzen.
WELCOME_ANTI_SPAM_ENABLED = False

WELCOME_LINES = (
    "Die Herde hat Zuwachs bekommen!",
    "Ein neues Kalb ist auf der Weide angekommen.",
    "Macht Platz auf der Weide - unsere Herde wächst!",
    "Muhment mal ... da ist ja jemand Neues!",
    "Frisches Muhen auf der Weide!",
    "Die KuhMuhs freuen sich über Verstärkung.",
    "Ein neues Paar Hufe betritt die Weide.",
    "Die Stallglocke läutet für dich!",
    "Neue Hufe, neue Geschichten.",
    "Die Weide bekommt Gesellschaft.",
    "Ein herzliches Muh aus der Herde!",
    "Die Milchbar ist offen und die Herde wächst weiter.",
    "Die Herde rückt ein Stück zusammen - du bist jetzt dabei!",
    "Die KuhMuhs begrüßen ein neues Gesicht!",
    "Heute gibt es ein besonders fröhliches Muh für dich.",
    "Die Herde hat Verstärkung auf vier Hufen bekommen.",
    "Ein neuer Tag, ein neues Herdenmitglied.",
    "Die Weide wird bunter - herzlich willkommen!",
    "Die Herde zählt jetzt ein Mitglied mehr.",
    "Das nächste Abenteuer auf der Weide kann beginnen.",
    "Die KuhMuh-Gemeinschaft freut sich auf dich.",
    "Ein frischer Wind weht durch den Stall.",
    "Willkommen an dem Ort, an dem jedes Muh dazugehört.",
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
    "Die Weide fühlt sich gleich wieder vertraut an.",
    "Ein bekanntes Muh schallt über die Weide.",
    "Die Herde macht dir wieder Platz.",
    "Schön, dass du den Weg zurück gefunden hast.",
    "Die KuhMuhs erkennen dich sofort wieder.",
    "Dein Platz in der Herde ist noch frei.",
    "Die Weide begrüßt ein vertrautes Gesicht.",
    "Zurück bei den KuhMuhs - das passt doch wie Huf auf Weide.",
    "Die Herde ist wieder ein Stück vollständiger.",
    "Ein vertrautes Mitglied kehrt auf die Weide zurück.",
    "Die Stallglocke läutet zur Wiedersehens-Muh!",
    "Schön, dass du wieder Teil unserer Herde bist.",
)

WELCOME_TITLES = (
    "<:muhKuh:1207038544510586890> Willkommen in der Herde!",
    "<:muhKuh:1207038544510586890> Ein herzliches Muh!",
    "<:muhKuh:1207038544510586890> Schön, dass du da bist!",
    "<:muhKuh:1207038544510586890> Die Herde begrüßt dich!",
    "<:muhKuh:1207038544510586890> Willkommen auf der Weide!",
    "<:muhKuh:1207038544510586890> Neues Mitglied in der Herde!",
)

WELCOME_BACK_TITLES = (
    "<:muhKuh:1207038544510586890> Willkommen zurück!",
    "<:muhKuh:1207038544510586890> Schön, dich wiederzusehen!",
    "<:muhKuh:1207038544510586890> Die Herde hat dich vermisst!",
    "<:muhKuh:1207038544510586890> Zurück auf der Weide!",
    "<:muhKuh:1207038544510586890> Ein vertrautes Muh kehrt zurück!",
    "<:muhKuh:1207038544510586890> Wieder da bei den KuhMuhs!",
)

HOLY_COW_TITLES = (
    "✨ HOLY COW! ✨",
    "✨ Die Legendenglocke der Weide erklingt ✨",
    "✨ Die Mythen sind wahr: Die Holy Cow ist da ✨",
    "✨ Ein uraltes Muh durch die Nacht ✨",
    "✨ Die Weide hält den Atem an ✨",
)

HOLY_COW_LINES = (
    "<:muhKuh:1207038544510586890> Ein legendäres Muh durchzieht die Weide.",
    "<:muhKuh:1207038544510586890> Die Weide glüht, als die Mythen wahr werden.",
    "<:muhKuh:1207038544510586890> Der Stall ist still, denn die Holy Cow ist erschienen.",
    "<:muhKuh:1207038544510586890> Ein uraltes Muh erinnert die Herde an alte Zeiten.",
    "<:muhKuh:1207038544510586890> Die Nacht auf der Weide wird von einer Legende beherrscht.",
)

HOLY_COW_CLOSERS = (
    "**Die Herde hält den Atem an.**",
    "**Die Legende der Weide ist wahr geworden.**",
    "**Der Stall flüstert noch immer von der Holy Cow.**",
    "**Die Mythen sind wieder lebendig.**",
    "**Die Weide lauscht noch immer auf das seltene Muh.**",
)

DEFAULT_GUILD = {
    "welcome_users": {},
    "last_welcome_media_url": None,
    "last_welcome_text": None,
    "last_welcome_title": None,
}


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

    @staticmethod
    def _pick_unique_value(options: tuple[str, ...], previous: str | None) -> str:
        candidates = [option for option in options if option != previous] if previous else list(options)
        if not candidates:
            candidates = list(options)
        return random.choice(candidates)

    async def _pick_random_media(self, guild: discord.Guild, previous_url: str | None) -> str:
        media_urls: list[str] = []

        if WELCOME_MEDIA_THREAD_ID:
            try:
                thread = guild.get_thread(WELCOME_MEDIA_THREAD_ID)
                if thread is None:
                    thread = await guild.fetch_channel(WELCOME_MEDIA_THREAD_ID)
                if isinstance(thread, discord.Thread):
                    async for message in thread.history(limit=200, oldest_first=False):
                        for attachment in message.attachments:
                            if attachment.url:
                                media_urls.append(attachment.url)
                        for embed in message.embeds:
                            if embed.thumbnail and embed.thumbnail.url:
                                media_urls.append(embed.thumbnail.url)
                            if embed.image and embed.image.url:
                                media_urls.append(embed.image.url)
            except (discord.Forbidden, discord.HTTPException, AttributeError, TypeError):
                media_urls = []

        if not media_urls:
            media_urls = [WELCOME_HOLY_COW_IMAGE_URL, WELCOME_IMAGE_URL]

        if WELCOME_HOLY_COW_IMAGE_URL and random.random() < WELCOME_HOLY_COW_CHANCE:
            if WELCOME_HOLY_COW_IMAGE_URL != previous_url:
                return WELCOME_HOLY_COW_IMAGE_URL

        for _ in range(25):
            candidate = random.choice(media_urls)
            if candidate != previous_url:
                return candidate

        return media_urls[0]

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.guild.id != GUILD_ID:
            return

        before_role_ids = {role.id for role in before.roles}
        after_role_ids = {role.id for role in after.roles}
        member_role_added = MEMBER_ROLE_ID not in before_role_ids and MEMBER_ROLE_ID in after_role_ids
        friend_role_added = FRIEND_ROLE_ID not in before_role_ids and FRIEND_ROLE_ID in after_role_ids
        if not member_role_added and not friend_role_added:
            return

        async with self._locks[(after.guild.id, after.id)]:
            if friend_role_added:
                await self._handle_friend_role_received(after)
            if member_role_added:
                await self._handle_member_role_received(after, after_role_ids)

    async def _handle_friend_role_received(self, member: discord.Member):
        guild_data = await self.config.guild(member.guild).all()
        users = guild_data.get("welcome_users", {})
        user_key = str(member.id)
        record = dict(users.get(user_key, {}))
        history = dict(record.get("member_history", {}))
        history["friend_status_count"] = int(history.get("friend_status_count", 0)) + 1
        history["was_former_member"] = True
        record["user_id"] = member.id
        record["previous_status"] = "friend"
        record["member_history"] = history
        users[user_key] = record
        await self.config.guild(member.guild).welcome_users.set(users)

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
            or record.get("member_history", {}).get("friend_status_count", 0) > 0
        )
        friend_status_count = record.get("member_history", {}).get("friend_status_count", 0)
        already_welcomed_back = (
            record.get("last_welcome_type") == "welcome_back"
            and record.get("member_history", {}).get("last_welcomed_friend_count") == friend_status_count
        )
        if WELCOME_ANTI_SPAM_ENABLED and record.get("welcome_count", 0) > 0 and (
            not is_welcome_back or already_welcomed_back
        ):
            users[user_key] = record
            await self.config.guild(member.guild).welcome_users.set(users)
            return

        welcome_type = "welcome_back" if is_welcome_back else "welcome"
        titles = WELCOME_BACK_TITLES if is_welcome_back else WELCOME_TITLES
        lines = WELCOME_BACK_LINES if is_welcome_back else WELCOME_LINES

        guild_settings = await self.config.guild(member.guild).all()
        last_title = guild_settings.get("last_welcome_title")
        last_text = guild_settings.get("last_welcome_text")
        last_media_url = guild_settings.get("last_welcome_media_url")

        media_url = await self._pick_random_media(member.guild, last_media_url)
        is_holy_cow = media_url == WELCOME_HOLY_COW_IMAGE_URL

        if is_holy_cow:
            title = self._pick_unique_value(HOLY_COW_TITLES, last_title)
            text = self._pick_unique_value(HOLY_COW_LINES, last_text)
            closer = self._pick_unique_value(HOLY_COW_CLOSERS, last_text)
            footer = "✨ KuHMuh • Die Holy Cow ist erschienen ✨"
            embed_color = discord.Color.gold()
            description = (
                f"## {title}\n\n"
                f"**{text}**\n\n"
                f"{closer}"
            )
        else:
            title = self._pick_unique_value(titles, last_title)
            text = self._pick_unique_value(lines, last_text)
            footer = "KuhMuh • Eine Kuh macht Muh, viele Kühe machen Muuuuuhhh!"
            embed_color = discord.Color.green()
            description = (
                f"# {title}\n\n"
                f"{text}\n\n"
                f"Schön, dass du {'wieder ' if is_welcome_back else ''}da bist, {member.mention}!"
            )

        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel is None or not hasattr(channel, "send"):
            _log_error(f"Welcome channel {WELCOME_CHANNEL_ID} not found in guild {member.guild.id}")
            return

        embed = discord.Embed(
            description=description,
            color=embed_color,
        )
        embed.set_image(url=media_url)
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
        if welcome_type == "welcome_back":
            history["last_welcomed_friend_count"] = friend_status_count
        record["member_history"] = history
        users[user_key] = record
        await self.config.guild(member.guild).welcome_users.set(users)
        await self.config.guild(member.guild).last_welcome_media_url.set(media_url)
        await self.config.guild(member.guild).last_welcome_text.set(text)
        await self.config.guild(member.guild).last_welcome_title.set(title)

    @staticmethod
    def _previous_status(role_ids: set[int]) -> str:
        if FRIEND_ROLE_ID in role_ids:
            return "friend"
        if ENTRY_ROLE_ID in role_ids:
            return "entry"
        return "unknown"
