# gruppensuche.py
import discord
from discord import app_commands
from redbot.core import commands
from typing import Dict, Set

TEST_CHANNEL_ID = 1199322485297000528
TEST_ROLE_ID = 1445018518562017373
MUHKUH_EMOJI = "<:muhkuh:1207038544510586890>"
GUILD_ID = 1198649628787212458


CUSTOM_ID_CATEGORY_SELECT = "grpsearch_category_select"

CUSTOM_ID_MODAL_PILAFE = "grpsearch_pilafe_modal"
CUSTOM_ID_MODAL_SPOT = "grpsearch_spot_modal"
CUSTOM_ID_MODAL_MUHH = "grpsearch_muhhelfer_modal"

CUSTOM_ID_BUTTON_JOIN = "grpsearch_join"
CUSTOM_ID_BUTTON_LEAVE = "grpsearch_leave"


class GroupSearchState:
    def __init__(
        self,
        message_id: int,
        guild_id: int,
        channel_id: int,
        creator_id: int,
        category: str,
        title: str,
        subtitle: str,
        detail_line: str,
        duration: str | None = None,
        start_time: str | None = None,
        note: str | None = None,
    ) -> None:
        self.message_id: int = message_id
        self.guild_id: int = guild_id
        self.channel_id: int = channel_id
        self.creator_id: int = creator_id
        self.category: str = category    @app_commands.command(
        self.title: str = title
        self.subtitle: str = subtitle
        self.detail_line: str = detail_line
        self.duration: str | None = duration
        self.start_time: str | None = start_time
        self.note: str | None = note
        self.participants: Set[int] = set()


class CategorySelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label="Muhhelfer (LoML Bosse)",
                value="muhhelfer",
                emoji="🐄",
                description="Gruppensuche für Muhhelfer / LoML Bosse",
            ),
            discord.SelectOption(
                label="Pila Fe Schriftrollen",
                value="pilafe",
                emoji="📜",
                description="Gruppensuche für Pila Fe Schriftrollen",
            ),
            discord.SelectOption(
                label="Gruppenspots",
                value="spot",
                emoji="🗺️",
                description="Gruppenspots (z. B. Orzekia, Dornenwald, …)",
            ),
        ]
        super().__init__(
            custom_id=CUSTOM_ID_CATEGORY_SELECT,
            placeholder="Kategorie auswählen …",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        value = self.values[0]

        if value == "pilafe":
            await interaction.response.send_modal(PilaFeModal())
        elif value == "spot":
            await interaction.response.send_modal(SpotModal())
        elif value == "muhhelfer":
            await interaction.response.send_modal(MuhhelferModal())
        else:
            await interaction.response.send_message(
                "Unbekannte Kategorie.", ephemeral=True
            )


class CategorySelectView(discord.ui.View):
    def __init__(self, timeout: float | None = 300) -> None:
        super().__init__(timeout=timeout)
        self.add_item(CategorySelect())


class PilaFeModal(discord.ui.Modal, title="Pila Fe Gruppensuche"):
    pilafe_amount = discord.ui.TextInput(
        label="Menge an Schriftrollen",
        placeholder="z. B. 1000",
        required=True,
        style=discord.TextStyle.short,
        custom_id="pilafe_amount",
    )
    pilafe_duration_hours = discord.ui.TextInput(
        label="Dauer (in Stunden)",
        placeholder="z. B. 3",
        required=False,
        style=discord.TextStyle.short,
        custom_id="pilafe_duration_hours",
    )
    common_start_time = discord.ui.TextInput(
        label="Startzeit",
        placeholder="z. B. jetzt, 20:00 Uhr, später",
        required=False,
        style=discord.TextStyle.short,
        custom_id="common_start_time",
    )
    common_note = discord.ui.TextInput(
        label="Optionale Notiz",
        placeholder="Gear, Anforderungen, Sonstiges …",
        required=False,
        style=discord.TextStyle.paragraph,
        custom_id="common_note",
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        amount = str(self.pilafe_amount.value).strip()
        duration_raw = str(self.pilafe_duration_hours.value).strip()
        start_time_raw = str(self.common_start_time.value).strip()
        note_raw = str(self.common_note.value).strip()

        duration = f"{duration_raw} Stunden" if duration_raw else None
        start_time = start_time_raw or None
        note = note_raw or None

        detail_line = f"Anzahl Rollen: **{amount}**"

        cog: Gruppensuche | None = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            await interaction.response.send_message(
                "Interner Fehler: Cog nicht gefunden.", ephemeral=True
            )
            return

        await cog.create_public_group_message(
            interaction,
            category="pilafe",
            title="📜 Gruppensuche – Pila Fe Schriftrollen",
            subtitle="Pila Fe Schriftrollen",
            detail_line=detail_line,
            duration=duration,
            start_time=start_time,
            note=note,
        )


class SpotModal(discord.ui.Modal, title="Gruppenspot-Suche"):
    spot_name = discord.ui.TextInput(
        label="Spot",
        placeholder="z. B. Orzekia, Dornenwald, …",
        required=True,
        style=discord.TextStyle.short,
        custom_id="spot_name",
    )
    spot_duration_hours = discord.ui.TextInput(
        label="Dauer (in Stunden)",
        placeholder="z. B. 3",
        required=False,
        style=discord.TextStyle.short,
        custom_id="spot_duration_hours",
    )
    common_start_time = discord.ui.TextInput(
        label="Startzeit",
        placeholder="z. B. jetzt, 20:00 Uhr, später",
        required=False,
        style=discord.TextStyle.short,
        custom_id="common_start_time",
    )
    common_note = discord.ui.TextInput(
        label="Optionale Notiz",
        placeholder="Gear, Anforderungen, Sonstiges …",
        required=False,
        style=discord.TextStyle.paragraph,
        custom_id="common_note",
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        spot_name = str(self.spot_name.value).strip()
        duration_raw = str(self.spot_duration_hours.value).strip()
        start_time_raw = str(self.common_start_time.value).strip()
        note_raw = str(self.common_note.value).strip()

        duration = f"{duration_raw} Stunden" if duration_raw else None
        start_time = start_time_raw or None
        note = note_raw or None

        detail_line = f"Spot: **{spot_name}**"

        cog: Gruppensuche | None = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            await interaction.response.send_message(
                "Interner Fehler: Cog nicht gefunden.", ephemeral=True
            )
            return

        await cog.create_public_group_message(
            interaction,
            category="spot",
            title="🗺️ Gruppensuche – Spot",
            subtitle="Gruppenspot",
            detail_line=detail_line,
            duration=duration,
            start_time=start_time,
            note=note,
        )


class MuhhelferModal(discord.ui.Modal, title="Muhhelfer-Gruppensuche"):
    muhhelfer_target = discord.ui.TextInput(
        label="Boss / Inhalt",
        placeholder="z. B. LoML-Bosse, bestimmter Boss …",
        required=True,
        style=discord.TextStyle.short,
        custom_id="muhhelfer_target",
    )
    muhhelfer_duration_hours = discord.ui.TextInput(
        label="Dauer (in Stunden)",
        placeholder="z. B. 2",
        required=False,
        style=discord.TextStyle.short,
        custom_id="muhhelfer_duration_hours",
    )
    common_start_time = discord.ui.TextInput(
        label="Startzeit",
        placeholder="z. B. jetzt, 20:00 Uhr, später",
        required=False,
        style=discord.TextStyle.short,
        custom_id="common_start_time",
    )
    common_note = discord.ui.TextInput(
        label="Optionale Notiz",
        placeholder="Gear, Anforderungen, Sonstiges …",
        required=False,
        style=discord.TextStyle.paragraph,
        custom_id="common_note",
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        target = str(self.muhhelfer_target.value).strip()
        duration_raw = str(self.muhhelfer_duration_hours.value).strip()
        start_time_raw = str(self.common_start_time.value).strip()
        note_raw = str(self.common_note.value).strip()

        duration = f"{duration_raw} Stunden" if duration_raw else None
        start_time = start_time_raw or None
        note = note_raw or None

        detail_line = f"Ziel: **{target}**"

        cog: Gruppensuche | None = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            await interaction.response.send_message(
                "Interner Fehler: Cog nicht gefunden.", ephemeral=True
            )
            return

        await cog.create_public_group_message(
            interaction,
            category="muhhelfer",
            title="🐄 Gruppensuche – Muhhelfer",
            subtitle="Muhhelfer (LoML Bosse)",
            detail_line=detail_line,
            duration=duration,
            start_time=start_time,
            note=note,
        )


class GroupSearchView(discord.ui.View):
    def __init__(self, cog: "Gruppensuche", message_id: int) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.message_id = message_id

    @discord.ui.button(
        label="Ich bin dabei",
        style=discord.ButtonStyle.success,
        custom_id=CUSTOM_ID_BUTTON_JOIN,
    )
    async def join_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.handle_join_leave(interaction, self.message_id, join=True)

    @discord.ui.button(
        label="Abmelden",
        style=discord.ButtonStyle.secondary,
        custom_id=CUSTOM_ID_BUTTON_LEAVE,
    )
    async def leave_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog.handle_join_leave(interaction, self.message_id, join=False)


class Gruppensuche(commands.Cog):
    """Cog für /gruppensuche mit ephemerem Formular und öffentlicher Gruppensuche."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.group_searches: Dict[int, GroupSearchState] = {}

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="gruppensuche",
        description="Starte eine neue Gruppensuche mit Formular.",
    )
    async def gruppensuche_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title=f"{MUHKUH_EMOJI} Gruppensuche erstellen",
            description=(
                "Wähle, wofür du eine Gruppe suchst.\n\n"
                "• **Muhhelfer (LoML Bosse)**\n"
                "• **Pila Fe Schriftrollen**\n"
                "• **Gruppenspots**\n\n"
                "Nach der Auswahl kannst du Details wie **Menge**, "
                "**Dauer** und **Startzeit** angeben."
            ),
            colour=discord.Colour.blurple(),
        )

        view = CategorySelectView()
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )

    async def create_public_group_message(
        self,
        interaction: discord.Interaction,
        *,
        category: str,
        title: str,
        subtitle: str,
        detail_line: str,
        duration: str | None,
        start_time: str | None,
        note: str | None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Dieser Befehl kann nur auf einem Server verwendet werden.",
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(TEST_CHANNEL_ID)
        if channel is None or not isinstance(
            channel, (discord.TextChannel, discord.Thread)
        ):
            await interaction.response.send_message(
                "Der konfigurierte Channel für Gruppensuchen wurde nicht gefunden.",
                ephemeral=True,
            )
            return

        creator_id = interaction.user.id

        dummy_state = GroupSearchState(
            message_id=0,
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            creator_id=creator_id,
            category=category,
            title=title,
            subtitle=subtitle,
            detail_line=detail_line,
            duration=duration,
            start_time=start_time,
            note=note,
        )

        embed = self.build_group_embed(dummy_state, initial=True)
        view_placeholder = GroupSearchView(self, message_id=0)  # id wird gleich gesetzt

        sent = await channel.send(
            content=f"<@&{TEST_ROLE_ID}>",
            embed=embed,
            view=view_placeholder,
        )

        state = GroupSearchState(
            message_id=sent.id,
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            creator_id=creator_id,
            category=category,
            title=title,
            subtitle=subtitle,
            detail_line=detail_line,
            duration=duration,
            start_time=start_time,
            note=note,
        )
        self.group_searches[sent.id] = state

        view = GroupSearchView(self, message_id=sent.id)
        await sent.edit(view=view)

        await interaction.response.send_message(
            f"Deine Gruppensuche wurde in <#{TEST_CHANNEL_ID}> erstellt.",
            ephemeral=True,
        )

    def build_group_embed(
        self, state: GroupSearchState, initial: bool = False
    ) -> discord.Embed:
        creator_mention = f"<@{state.creator_id}>"
        lines: list[str] = []

        lines.append(f"**Suchender:** {creator_mention}")
        lines.append(f"**Kategorie:** {state.subtitle}")
        lines.append(state.detail_line)

        if state.duration:
            lines.append(f"**Dauer:** {state.duration}")
        if state.start_time:
            lines.append(f"**Start:** {state.start_time}")
        if state.note:
            lines.append(f"**Hinweis:** {state.note}")

        participants_list = list(state.participants)
        if participants_list:
            participants_text = "\n".join(f"• <@{uid}>" for uid in participants_list)
        else:
            participants_text = (
                "Noch keine Teilnehmer."
                if initial
                else "Keine Teilnehmer mehr eingetragen."
            )

        embed = discord.Embed(
            title=state.title,
            description="\n".join(lines),
            colour=discord.Colour.blurple(),
        )
        embed.add_field(
            name=f"Teilnehmer ({len(participants_list)})",
            value=participants_text,
            inline=False,
        )
        embed.set_footer(text='Klicke auf „Ich bin dabei“, um dich einzutragen.')
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def handle_join_leave(
        self,
        interaction: discord.Interaction,
        message_id: int,
        *,
        join: bool,
    ) -> None:
        state = self.group_searches.get(message_id)
        if state is None:
            await interaction.response.send_message(
                "Diese Gruppensuche ist nicht mehr aktiv oder konnte nicht gefunden werden.",
                ephemeral=True,
            )
            return

        user_id = interaction.user.id

        if join:
            state.participants.add(user_id)
        else:
            state.participants.discard(user_id)

        embed = self.build_group_embed(state)
        view = GroupSearchView(self, message_id=message_id)

        await interaction.response.edit_message(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gruppensuche(bot))



