import discord
from discord import app_commands
from redbot.core import commands
from typing import Dict, Optional, List, Tuple, Set
import time

# === IDs / Konfiguration ===
TEST_CHANNEL_ID = 1199322485297000528  # Öffentlicher Test-Channel
TEST_ROLE_ID = 1445018518562017373     # Test-Rolle fürs "Neue Suche" Ping

ROLE_NORMAL_ID = 1424768638157852682   # Muhhelfer – Normal
ROLE_SCHWER_ID = 1424769286790054050   # Muhhelfer – Schwer

ADMIN_ROLE_ID: Optional[int] = 1198650646786736240     # Admin-Rolle
OFFIZIER_ROLE_ID: Optional[int] = 1198652039312453723  # Offizier-Rolle (gleich wie Admin)

PING_COOLDOWN_SECONDS = 600  # 10 Minuten Cooldown für Ersteller

MUHKUH_EMOJI = "<:muhkuh:1207038544510586890>"
PILAFE_EMOJI = "<:pilafe:1450051653297504368>"

GUILD_ID = 1198649628787212458         # Dein Server

# Empfohlene Mindestwerte
AKVK_NORMAL = "301/385"
AKVK_SCHWER = "330/401"

# Boss-Reihenfolge wie im Game (final)
BOSSES: List[Tuple[str, str]] = [
    ("jigwi", "Jigwi"),
    ("knabe_blau", "Knabe in Blau"),
    ("bulgasal", "Bulgasal"),
    ("uturi", "Uturi"),
    ("dunkler_bonghwang", "Dunkler Bonghwang"),
    ("entthronter_kronprinz", "Entthronter Kronprinz"),
    ("bihyung", "Bihyung"),
]


# === State-Objekte ===

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
        detail_lines: List[str],
        duration: Optional[str] = None,
        start_time: Optional[str] = None,
        note: Optional[str] = None,
        difficulty: Optional[str] = None,          # "Normal" / "Schwer"
        requirement_akvk: Optional[str] = None,    # Standard oder Override
        ping_role_id: Optional[int] = None,
        max_players: int = 5,
        doppel_runs: Optional[Set[str]] = None,    # boss_keys mit Doppel Run
    ) -> None:
        self.message_id = message_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.creator_id = creator_id
        self.category = category
        self.title = title
        self.subtitle = subtitle
        self.detail_lines = detail_lines
        self.duration = duration
        self.start_time = start_time
        self.note = note
        self.difficulty = difficulty
        self.requirement_akvk = requirement_akvk
        self.ping_role_id = ping_role_id
        self.max_players = max_players
        self.doppel_runs = doppel_runs or set()

        # Join-Reihenfolge: Liste statt Set
        self.participants_order: List[int] = []
        self.waitlist_order: List[int] = []

        # Cooldown timestamps (Creator)
        self.ping_role_last_ts: Optional[float] = None
        self.ping_waitlist_last_ts: Optional[float] = None


class MuhhWizardState:
    """Ephemeral Wizard state pro User."""
    def __init__(self) -> None:
        self.difficulty: Optional[str] = None  # "Normal" / "Schwer"
        self.max_players: int = 5              # 1–5
        self.selected_boss_keys: List[str] = []
        self.doppel_run_keys: Set[str] = set()
        self.custom_akvk: Optional[str] = None
        self.duration: Optional[str] = None
        self.start_time: Optional[str] = None
        self.note: Optional[str] = None


# === UI: Kategorieauswahl ===

class CategorySelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label="Muhhelfer (LoML Bosse)",
                value="muhhelfer",
                emoji=discord.PartialEmoji.from_str(MUHKUH_EMOJI),
                description="Gruppensuche für Muhhelfer / LoML Bosse",
            ),
            discord.SelectOption(
                label="Pila Fe Schriftrollen",
                value="pilafe",
                emoji=discord.PartialEmoji.from_str(PILAFE_EMOJI),
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
            custom_id="grpsearch_category_select",
            placeholder="Kategorie auswählen …",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: Optional[Gruppensuche] = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            return await interaction.response.send_message("Interner Fehler: Cog nicht gefunden.", ephemeral=True)

        value = self.values[0]
        if value == "muhhelfer":
            await cog.start_muhhelfer_wizard(interaction)
        elif value == "pilafe":
            await interaction.response.send_modal(PilaFeModal())
        elif value == "spot":
            await interaction.response.send_modal(SpotModal())
        else:
            await interaction.response.send_message("Unbekannte Kategorie.", ephemeral=True)


class CategorySelectView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=300)
        self.add_item(CategorySelect())


# === Muhhelfer Wizard Embeds / Views ===

def build_muhh_embed_step_diff() -> discord.Embed:
    return discord.Embed(
        title=f"{MUHKUH_EMOJI} Muhhelfer – Schwierigkeit",
        description=(
            "Wähle die **Schwierigkeit**.\n\n"
            f"**Normal** → Empfohlen mind. **AK/VK {AKVK_NORMAL}**\n"
            f"**Schwer** → Empfohlen mind. **AK/VK {AKVK_SCHWER}**"
        ),
        colour=discord.Colour.blurple(),
    )


def build_muhh_embed_step_size(state: MuhhWizardState) -> discord.Embed:
    req = AKVK_NORMAL if state.difficulty == "Normal" else AKVK_SCHWER
    return discord.Embed(
        title=f"{MUHKUH_EMOJI} Muhhelfer – Gruppengröße",
        description=(
            f"**Schwierigkeit:** {state.difficulty}\n"
            f"**Empfohlen mind. AK/VK:** {req}\n\n"
            "Wähle die **maximale Teilnehmerzahl**."
        ),
        colour=discord.Colour.blurple(),
    )


def build_muhh_embed_step_bosses(state: MuhhWizardState) -> discord.Embed:
    req = AKVK_NORMAL if state.difficulty == "Normal" else AKVK_SCHWER
    return discord.Embed(
        title=f"{MUHKUH_EMOJI} Muhhelfer – Bossauswahl",
        description=(
            f"**Schwierigkeit:** {state.difficulty}\n"
            f"**Empfohlen mind. AK/VK:** {req}\n"
            f"**Max. Teilnehmer:** {state.max_players}\n\n"
            "Wähle bis zu **5 Bosse**."
        ),
        colour=discord.Colour.blurple(),
    )


def build_muhh_embed_step_runs(state: MuhhWizardState) -> discord.Embed:
    req = AKVK_NORMAL if state.difficulty == "Normal" else AKVK_SCHWER

    boss_label_map = dict(BOSSES)
    boss_lines = []
    for k in state.selected_boss_keys:
        name = boss_label_map.get(k, k)
        if k in state.doppel_run_keys:
            boss_lines.append(f"• {name} **(Doppel Run)**")
        else:
            boss_lines.append(f"• {name}")

    boss_text = "\n".join(boss_lines) if boss_lines else "_Keine Bosse ausgewählt._"

    warning = ""
    if state.doppel_run_keys:
        warning = "\n\n⚠️ **2. Charakter erforderlich**"

    return discord.Embed(
        title=f"{MUHKUH_EMOJI} Muhhelfer – Doppel Run",
        description=(
            f"**Schwierigkeit:** {state.difficulty}\n"
            f"**Empfohlen mind. AK/VK:** {req}\n"
            f"**Max. Teilnehmer:** {state.max_players}\n\n"
            "**Ausgewählte Bosse:**\n"
            f"{boss_text}"
            f"{warning}\n\n"
            "Markiere Boss(e) als **Doppel Run** (Toggle), dann **Weiter**."
        ),
        colour=discord.Colour.blurple(),
    )


class MuhhDifficultyView(discord.ui.View):
    def __init__(self, cog: "Gruppensuche", user_id: int) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Normal", style=discord.ButtonStyle.primary)
    async def btn_normal(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.set_muhh_difficulty(interaction, self.user_id, "Normal")

    @discord.ui.button(label="Schwer", style=discord.ButtonStyle.danger)
    async def btn_schwer(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.set_muhh_difficulty(interaction, self.user_id, "Schwer")


class MuhhSizeSelect(discord.ui.Select):
    def __init__(self, user_id: int) -> None:
        # 1–5 (final)
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 6)]
        super().__init__(
            placeholder="Max. Teilnehmer auswählen …",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: Optional[Gruppensuche] = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            return await interaction.response.send_message("Interner Fehler: Cog nicht gefunden.", ephemeral=True)
        await cog.set_muhh_max_players(interaction, self.user_id, int(self.values[0]))


class MuhhSizeView(discord.ui.View):
    def __init__(self, cog: "Gruppensuche", user_id: int) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.add_item(MuhhSizeSelect(user_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Zurück", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.back_to_muhh_difficulty(interaction, self.user_id)


class MuhhBossSelect(discord.ui.Select):
    def __init__(self, user_id: int) -> None:
        options = [discord.SelectOption(label=label, value=key) for (key, label) in BOSSES]
        super().__init__(
            placeholder="Bosse auswählen (max. 5) …",
            min_values=1,
            max_values=5,
            options=options,
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: Optional[Gruppensuche] = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            return await interaction.response.send_message("Interner Fehler: Cog nicht gefunden.", ephemeral=True)
        await cog.set_muhh_bosses(interaction, self.user_id, list(self.values))


class MuhhBossView(discord.ui.View):
    def __init__(self, cog: "Gruppensuche", user_id: int) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.add_item(MuhhBossSelect(user_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Zurück", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.back_to_muhh_size(interaction, self.user_id)


class MuhhRunView(discord.ui.View):
    def __init__(self, cog: "Gruppensuche", user_id: int, boss_keys: List[str]) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id

        for k in boss_keys[:5]:
            label = dict(BOSSES).get(k, k)
            self.add_item(MuhhRunToggleButton(boss_key=k, label=label))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Zurück", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.back_to_muhh_bosses(interaction, self.user_id)

    @discord.ui.button(label="Weiter", style=discord.ButtonStyle.success, row=1)
    async def cont(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.open_muhh_details_modal(interaction, self.user_id)


class MuhhRunToggleButton(discord.ui.Button):
    def __init__(self, boss_key: str, label: str) -> None:
        super().__init__(
            label=f"Doppel Run: {label}",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        self.boss_key = boss_key

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: Optional[Gruppensuche] = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            return await interaction.response.send_message("Interner Fehler: Cog nicht gefunden.", ephemeral=True)
        await cog.toggle_muhh_doppel_run(interaction, interaction.user.id, self.boss_key)


# === Modals: PilaFe / Spot / Muhh Details ===

class PilaFeModal(discord.ui.Modal, title="Pila Fe Gruppensuche"):
    pilafe_amount = discord.ui.TextInput(
        label="Menge an Schriftrollen",
        placeholder="z. B. 1000",
        required=True,
        style=discord.TextStyle.short,
    )
    pilafe_duration_hours = discord.ui.TextInput(
        label="Geplante Dauer",
        placeholder="z. B. 30min, 2h, 90min",
        required=False,
        style=discord.TextStyle.short,
    )
    common_start_time = discord.ui.TextInput(
        label="Startzeit",
        placeholder="z. B. jetzt, 20:00 Uhr, später",
        required=False,
        style=discord.TextStyle.short,
    )
    common_note = discord.ui.TextInput(
        label="Optionale Notiz",
        placeholder="Gear, Anforderungen, Sonstiges …",
        required=False,
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        amount = str(self.pilafe_amount.value).strip()
        duration_raw = str(self.pilafe_duration_hours.value).strip()
        start_time_raw = str(self.common_start_time.value).strip()
        note_raw = str(self.common_note.value).strip()

        duration = duration_raw or None
        start_time = start_time_raw or None
        note = note_raw or None

        detail_lines = [f"Anzahl Rollen: **{amount}**"]

        cog: Optional[Gruppensuche] = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            return await interaction.response.send_message("Interner Fehler: Cog nicht gefunden.", ephemeral=True)

        await cog.create_public_group_message(
            interaction,
            category="pilafe",
            title=f"{PILAFE_EMOJI} Gruppensuche – Pila Fe Schriftrollen",
            subtitle="Pila Fe Schriftrollen",
            detail_lines=detail_lines,
            duration=duration,
            start_time=start_time,
            note=note,
            difficulty=None,
            requirement_akvk=None,
            ping_role_id=None,
            max_players=0,  # irrelevant
            doppel_runs=set(),
        )


class SpotModal(discord.ui.Modal, title="Gruppenspot-Suche"):
    spot_name = discord.ui.TextInput(
        label="Spot",
        placeholder="z. B. Orzekia, Dornenwald, …",
        required=True,
        style=discord.TextStyle.short,
    )
    spot_duration_hours = discord.ui.TextInput(
        label="Geplante Dauer",
        placeholder="z. B. 30min, 2h, 90min",
        required=False,
        style=discord.TextStyle.short,
    )
    common_start_time = discord.ui.TextInput(
        label="Startzeit",
        placeholder="z. B. jetzt, 20:00 Uhr, später",
        required=False,
        style=discord.TextStyle.short,
    )
    common_note = discord.ui.TextInput(
        label="Optionale Notiz",
        placeholder="Gear, Anforderungen, Sonstiges …",
        required=False,
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        spot_name = str(self.spot_name.value).strip()
        duration_raw = str(self.spot_duration_hours.value).strip()
        start_time_raw = str(self.common_start_time.value).strip()
        note_raw = str(self.common_note.value).strip()

        duration = duration_raw or None
        start_time = start_time_raw or None
        note = note_raw or None

        detail_lines = [f"Spot: **{spot_name}**"]

        cog: Optional[Gruppensuche] = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            return await interaction.response.send_message("Interner Fehler: Cog nicht gefunden.", ephemeral=True)

        await cog.create_public_group_message(
            interaction,
            category="spot",
            title="🗺️ Gruppensuche – Spot",
            subtitle="Gruppenspot",
            detail_lines=detail_lines,
            duration=duration,
            start_time=start_time,
            note=note,
            difficulty=None,
            requirement_akvk=None,
            ping_role_id=None,
            max_players=0,
            doppel_runs=set(),
        )


class MuhhDetailsModal(discord.ui.Modal, title="Muhhelfer – Details"):
    duration = discord.ui.TextInput(
        label="Geplante Dauer",
        placeholder="z. B. 30min, 2h, 90min",
        required=False,
        style=discord.TextStyle.short,
        custom_id="muhh_duration",
    )
    start_time = discord.ui.TextInput(
        label="Startzeit",
        placeholder="z. B. jetzt, 20:00 Uhr, später",
        required=False,
        style=discord.TextStyle.short,
        custom_id="muhh_start_time",
    )
    custom_akvk = discord.ui.TextInput(
        label="Gewünschte AK/VK (optional)",
        placeholder="z. B. 320/395",
        required=False,
        style=discord.TextStyle.short,
        custom_id="muhh_custom_akvk",
    )
    note = discord.ui.TextInput(
        label="Optionale Notiz",
        placeholder="Gear, Anforderungen, Sonstiges …",
        required=False,
        style=discord.TextStyle.paragraph,
        custom_id="muhh_note",
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cog: Optional[Gruppensuche] = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            return await interaction.response.send_message("Interner Fehler: Cog nicht gefunden.", ephemeral=True)
        await cog.finish_muhhelfer(interaction)


# === Haupt-Cog ===

class Gruppensuche(commands.Cog):
    """Gruppensuche: /gruppensuche Wizard + öffentliche Suche mit Teilnehmern/Warteschlange."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.group_searches: Dict[int, GroupSearchState] = {}
        self.muhh_wizard: Dict[int, MuhhWizardState] = {}

    async def cog_load(self) -> None:
        guild_obj = discord.Object(id=GUILD_ID)
        self.bot.tree.add_command(self.gruppensuche_command, guild=guild_obj)
        await self.bot.tree.sync(guild=guild_obj)

    async def cog_unload(self) -> None:
        guild_obj = discord.Object(id=GUILD_ID)
        self.bot.tree.remove_command(
            self.gruppensuche_command.name,
            type=self.gruppensuche_command.type,
            guild=guild_obj,
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="gruppensuche", description="Starte eine neue Gruppensuche mit Formular.")
    async def gruppensuche_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title=f"{MUHKUH_EMOJI} Gruppensuche erstellen",
            description=(
                "Wähle, wofür du eine Gruppe suchst.\n\n"
                "• **Muhhelfer (LoML Bosse)**\n"
                "• **Pila Fe Schriftrollen**\n"
                "• **Gruppenspots**\n\n"
                "Nach der Auswahl kannst du Details wie **Menge**, **Geplante Dauer** und **Startzeit** angeben."
            ),
            colour=discord.Colour.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=CategorySelectView(), ephemeral=True)

    # ===== Rechte / Helper =====

    def is_admin_or_offizier(self, member: discord.Member) -> bool:
        return any(
            (ADMIN_ROLE_ID is not None and r.id == ADMIN_ROLE_ID) or
            (OFFIZIER_ROLE_ID is not None and r.id == OFFIZIER_ROLE_ID)
            for r in member.roles
        )

    def is_admin_offizier_or_creator(self, member: discord.Member, creator_id: int) -> bool:
        return member.id == creator_id or self.is_admin_or_offizier(member) or member.guild_permissions.administrator

    def _remove_from_lists(self, uid: int, state: GroupSearchState) -> None:
        if uid in state.participants_order:
            state.participants_order = [x for x in state.participants_order if x != uid]
        if uid in state.waitlist_order:
            state.waitlist_order = [x for x in state.waitlist_order if x != uid]

    def _try_fill_from_waitlist(self, state: GroupSearchState) -> None:
        if state.max_players <= 0:
            return
        while len(state.participants_order) < state.max_players and state.waitlist_order:
            uid = state.waitlist_order.pop(0)
            if uid not in state.participants_order:
                state.participants_order.append(uid)

    # ===== Muhhelfer Wizard =====

    async def start_muhhelfer_wizard(self, interaction: discord.Interaction) -> None:
        user_id = interaction.user.id
        self.muhh_wizard[user_id] = MuhhWizardState()
        await interaction.response.edit_message(embed=build_muhh_embed_step_diff(), view=MuhhDifficultyView(self, user_id))

    async def set_muhh_difficulty(self, interaction: discord.Interaction, user_id: int, difficulty: str) -> None:
        st = self.muhh_wizard.get(user_id) or MuhhWizardState()
        self.muhh_wizard[user_id] = st
        st.difficulty = difficulty
        st.selected_boss_keys = []
        st.doppel_run_keys = set()
        st.max_players = 5
        await interaction.response.edit_message(embed=build_muhh_embed_step_size(st), view=MuhhSizeView(self, user_id))

    async def back_to_muhh_difficulty(self, interaction: discord.Interaction, user_id: int) -> None:
        await interaction.response.edit_message(embed=build_muhh_embed_step_diff(), view=MuhhDifficultyView(self, user_id))

    async def set_muhh_max_players(self, interaction: discord.Interaction, user_id: int, max_players: int) -> None:
        st = self.muhh_wizard.get(user_id)
        if st is None or st.difficulty is None:
            return await self.back_to_muhh_difficulty(interaction, user_id)
        st.max_players = max(1, min(5, int(max_players)))
        await interaction.response.edit_message(embed=build_muhh_embed_step_bosses(st), view=MuhhBossView(self, user_id))

    async def back_to_muhh_size(self, interaction: discord.Interaction, user_id: int) -> None:
        st = self.muhh_wizard.get(user_id)
        if st is None or st.difficulty is None:
            return await self.back_to_muhh_difficulty(interaction, user_id)
        await interaction.response.edit_message(embed=build_muhh_embed_step_size(st), view=MuhhSizeView(self, user_id))

    async def set_muhh_bosses(self, interaction: discord.Interaction, user_id: int, boss_keys: List[str]) -> None:
        st = self.muhh_wizard.get(user_id)
        if st is None or st.difficulty is None:
            return await self.back_to_muhh_difficulty(interaction, user_id)

        st.selected_boss_keys = boss_keys[:5]
        st.doppel_run_keys = {k for k in st.doppel_run_keys if k in st.selected_boss_keys}

        await interaction.response.edit_message(
            embed=build_muhh_embed_step_runs(st),
            view=MuhhRunView(self, user_id, st.selected_boss_keys),
        )

    async def back_to_muhh_bosses(self, interaction: discord.Interaction, user_id: int) -> None:
        st = self.muhh_wizard.get(user_id)
        if st is None or st.difficulty is None:
            return await self.back_to_muhh_difficulty(interaction, user_id)
        await interaction.response.edit_message(embed=build_muhh_embed_step_bosses(st), view=MuhhBossView(self, user_id))

    async def toggle_muhh_doppel_run(self, interaction: discord.Interaction, user_id: int, boss_key: str) -> None:
        st = self.muhh_wizard.get(user_id)
        if st is None:
            return await interaction.response.send_message("Wizard-Status verloren. Bitte /gruppensuche neu starten.", ephemeral=True)
        if boss_key not in st.selected_boss_keys:
            return await interaction.response.send_message("Boss ist nicht (mehr) ausgewählt.", ephemeral=True)

        if boss_key in st.doppel_run_keys:
            st.doppel_run_keys.remove(boss_key)
        else:
            st.doppel_run_keys.add(boss_key)

        await interaction.response.edit_message(
            embed=build_muhh_embed_step_runs(st),
            view=MuhhRunView(self, user_id, st.selected_boss_keys),
        )

    async def open_muhh_details_modal(self, interaction: discord.Interaction, user_id: int) -> None:
        st = self.muhh_wizard.get(user_id)
        if st is None or st.difficulty is None or not st.selected_boss_keys:
            return await interaction.response.send_message("Bitte erst Schwierigkeit + Bosse auswählen.", ephemeral=True)
        await interaction.response.send_modal(MuhhDetailsModal())

    async def finish_muhhelfer(self, interaction: discord.Interaction) -> None:
        user_id = interaction.user.id
        st = self.muhh_wizard.get(user_id)
        if st is None or st.difficulty is None or not st.selected_boss_keys:
            return await interaction.response.send_message("Wizard-Status verloren. Bitte /gruppensuche neu starten.", ephemeral=True)

        fields: Dict[str, str] = {}
        for row in interaction.data.get("components", []):  # type: ignore[union-attr]
            for comp in row.get("components", []):
                cid = comp.get("custom_id")
                val = comp.get("value", "")
                if cid:
                    fields[cid] = val

        duration_in = fields.get("muhh_duration", "").strip()
        start_in = fields.get("muhh_start_time", "").strip()
        custom_akvk_in = fields.get("muhh_custom_akvk", "").strip()
        note_in = fields.get("muhh_note", "").strip()

        st.duration = duration_in or None
        st.start_time = start_in or None
        st.note = note_in or None
        st.custom_akvk = custom_akvk_in or None

        requirement = st.custom_akvk if st.custom_akvk else (AKVK_NORMAL if st.difficulty == "Normal" else AKVK_SCHWER)
        ping_role_id = ROLE_NORMAL_ID if st.difficulty == "Normal" else ROLE_SCHWER_ID

        boss_label_map = dict(BOSSES)
        boss_lines = []
        for k in st.selected_boss_keys:
            name = boss_label_map.get(k, k)
            if k in st.doppel_run_keys:
                boss_lines.append(f"• {name} **(Doppel Run)**")
            else:
                boss_lines.append(f"• {name}")

        detail_lines = ["**Bosse:**", *boss_lines]
        if st.doppel_run_keys:
            detail_lines.append("")
            detail_lines.append("⚠️ **2. Charakter erforderlich**")

        # Schwierigkeit hervorheben + Titel
        diff_title = "Schwer" if st.difficulty == "Schwer" else "Normal"
        title = f"{MUHKUH_EMOJI} Gruppensuche – Muhhelfer ({diff_title})"

        await self.create_public_group_message(
            interaction,
            category="muhhelfer",
            title=title,
            subtitle="Muhhelfer (LoML Bosse)",
            detail_lines=detail_lines,
            duration=st.duration,
            start_time=st.start_time,
            note=st.note,
            difficulty=st.difficulty,
            requirement_akvk=requirement,
            ping_role_id=ping_role_id,
            max_players=st.max_players,
            doppel_runs=set(st.doppel_run_keys),
        )

        self.muhh_wizard.pop(user_id, None)

    # ===== Öffentliche Nachricht + Logik =====

    async def create_public_group_message(
        self,
        interaction: discord.Interaction,
        *,
        category: str,
        title: str,
        subtitle: str,
        detail_lines: List[str],
        duration: Optional[str],
        start_time: Optional[str],
        note: Optional[str],
        difficulty: Optional[str],
        requirement_akvk: Optional[str],
        ping_role_id: Optional[int],
        max_players: int,
        doppel_runs: Set[str],
    ) -> None:
        if interaction.guild is None:
            return await interaction.response.send_message("Dieser Befehl kann nur auf einem Server verwendet werden.", ephemeral=True)

        channel = interaction.guild.get_channel(TEST_CHANNEL_ID)
        if channel is None or not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("Test-Channel nicht gefunden.", ephemeral=True)

        creator_id = interaction.user.id

        state = GroupSearchState(
            message_id=0,
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            creator_id=creator_id,
            category=category,
            title=title,
            subtitle=subtitle,
            detail_lines=detail_lines,
            duration=duration,
            start_time=start_time,
            note=note,
            difficulty=difficulty,
            requirement_akvk=requirement_akvk,
            ping_role_id=ping_role_id,
            max_players=max_players,
            doppel_runs=doppel_runs,
        )

        # Ersteller immer als Teilnehmer
        state.participants_order.append(creator_id)

        embed = self.build_public_embed(state)
        sent = await channel.send(content=f"<@&{TEST_ROLE_ID}>", embed=embed, view=self.build_public_view(state))

        state.message_id = sent.id
        self.group_searches[sent.id] = state

        # keine zusätzliche ephemeral "erstellt" Nachricht (reduziert Noise)

    def build_public_view(self, state: GroupSearchState) -> discord.ui.View:
        view = discord.ui.View(timeout=None)

        # Row 0: Join/Leave
        btn_join = discord.ui.Button(label="Ich bin dabei", style=discord.ButtonStyle.success, row=0)
        btn_leave = discord.ui.Button(label="Abmelden", style=discord.ButtonStyle.secondary, row=0)

        async def join_cb(interaction: discord.Interaction):
            await self.handle_join(interaction, state.message_id)

        async def leave_cb(interaction: discord.Interaction):
            await self.handle_leave(interaction, state.message_id)

        btn_join.callback = join_cb  # type: ignore[assignment]
        btn_leave.callback = leave_cb  # type: ignore[assignment]

        view.add_item(btn_join)
        view.add_item(btn_leave)

        # Row 1: Ping Rolle + Ping Warteschlange (immer sichtbar)
        # Label nach Schwierigkeit
        if state.difficulty == "Schwer":
            ping_label = "🔔 Ping (Schwer)"
        elif state.difficulty == "Normal":
            ping_label = "🔔 Ping (Normal)"
        else:
            ping_label = "🔔 Ping"

        btn_ping_role = discord.ui.Button(
            label=ping_label,
            style=discord.ButtonStyle.primary,
            row=1,
        )

        async def ping_role_cb(interaction: discord.Interaction):
            await self.handle_ping_role(interaction, state.message_id)

        btn_ping_role.callback = ping_role_cb  # type: ignore[assignment]
        view.add_item(btn_ping_role)

        btn_ping_q = discord.ui.Button(
            label="🔔 Ping Warteschlange",
            style=discord.ButtonStyle.primary,
            row=1,
        )

        async def ping_q_cb(interaction: discord.Interaction):
            await self.handle_ping_waitlist(interaction, state.message_id)

        btn_ping_q.callback = ping_q_cb  # type: ignore[assignment]
        view.add_item(btn_ping_q)

        return view

    def build_public_embed(self, state: GroupSearchState) -> discord.Embed:
        creator_mention = f"<@{state.creator_id}>"
        desc_lines: List[str] = []
        desc_lines.append(f"**Suchender:** {creator_mention}")
        desc_lines.append(f"**Kategorie:** {state.subtitle}")

        # Schwierigkeit + Farbe
        colour = discord.Colour.blurple()
        if state.difficulty == "Schwer":
            desc_lines.append("**Schwierigkeit:** 🔴 **Schwer**")
            colour = discord.Colour.red()
        elif state.difficulty == "Normal":
            desc_lines.append("**Schwierigkeit:** 🔵 **Normal**")
            colour = discord.Colour.blurple()

        if state.requirement_akvk:
            desc_lines.append(f"**Anforderung AK/VK:** {state.requirement_akvk}")

        desc_lines.append(f"**Max. Teilnehmer:** {state.max_players}")

        desc_lines.append("")
        desc_lines.extend(state.detail_lines)

        if state.duration:
            desc_lines.append("")
            desc_lines.append(f"**Geplante Dauer:** {state.duration}")
        if state.start_time:
            desc_lines.append(f"**Start:** {state.start_time}")
        if state.note:
            desc_lines.append(f"**Hinweis:** {state.note}")

        participants = state.participants_order
        waitlist = state.waitlist_order

        p_text = "\n".join(f"• <@{uid}>" for uid in participants) if participants else "—"
        q_text = "\n".join(f"• <@{uid}>" for uid in waitlist) if waitlist else "—"

        embed = discord.Embed(
            title=state.title,
            description="\n".join(desc_lines),
            colour=colour,
        )

        embed.add_field(
            name=f"Teilnehmer ({len(participants)}/{state.max_players})",
            value=p_text,
            inline=False
        )
        embed.add_field(
            name=f"Warteschlange ({len(waitlist)})",
            value=q_text,
            inline=False
        )

        embed.set_footer(text='Klicke auf „Ich bin dabei“, um dich einzutragen.')
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def handle_join(self, interaction: discord.Interaction, message_id: int) -> None:
        state = self.group_searches.get(message_id)
        if state is None:
            return await interaction.response.send_message("Diese Gruppensuche ist nicht mehr aktiv.", ephemeral=True)

        uid = interaction.user.id

        if uid in state.participants_order or uid in state.waitlist_order:
            return await interaction.response.send_message("Du bist bereits eingetragen.", ephemeral=True)

        if len(state.participants_order) < state.max_players:
            state.participants_order.append(uid)
        else:
            state.waitlist_order.append(uid)

        embed = self.build_public_embed(state)
        view = self.build_public_view(state)
        await interaction.response.edit_message(embed=embed, view=view)

    async def handle_leave(self, interaction: discord.Interaction, message_id: int) -> None:
        state = self.group_searches.get(message_id)
        if state is None:
            return await interaction.response.send_message("Diese Gruppensuche ist nicht mehr aktiv.", ephemeral=True)

        uid = interaction.user.id
        was_participant = uid in state.participants_order
        self._remove_from_lists(uid, state)
        if was_participant:
            self._try_fill_from_waitlist(state)

        embed = self.build_public_embed(state)
        view = self.build_public_view(state)
        await interaction.response.edit_message(embed=embed, view=view)

    async def handle_ping_role(self, interaction: discord.Interaction, message_id: int) -> None:
        state = self.group_searches.get(message_id)
        if state is None:
            return await interaction.response.send_message("Diese Gruppensuche ist nicht mehr aktiv.", ephemeral=True)

        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Nicht erlaubt.", ephemeral=True)

        if not self.is_admin_offizier_or_creator(interaction.user, state.creator_id):
            return await interaction.response.send_message("Du darfst diesen Ping nicht auslösen.", ephemeral=True)

        if not state.ping_role_id:
            return await interaction.response.send_message("Für diese Suche ist kein Rollen-Ping konfiguriert.", ephemeral=True)

        channel = interaction.channel
        if channel is None or not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("Channel nicht gefunden.", ephemeral=True)

        now = time.time()
        is_admin = self.is_admin_or_offizier(interaction.user)
        is_creator = interaction.user.id == state.creator_id

        if is_creator and not is_admin:
            last = state.ping_role_last_ts
            if last is not None and (now - last) < PING_COOLDOWN_SECONDS:
                remaining = int(PING_COOLDOWN_SECONDS - (now - last))
                mins = max(1, (remaining + 59) // 60)
                return await interaction.response.send_message(
                    f"⏳ Ping noch nicht möglich. Bitte warte noch **{mins} Minute(n)**.",
                    ephemeral=True
                )

        await channel.send(f"<@&{state.ping_role_id}> – neue Suche von <@{state.creator_id}>")

        if is_creator and not is_admin:
            state.ping_role_last_ts = now

        return await interaction.response.send_message("🔔 Ping gesendet!", ephemeral=True)

    async def handle_ping_waitlist(self, interaction: discord.Interaction, message_id: int) -> None:
        state = self.group_searches.get(message_id)
        if state is None:
            return await interaction.response.send_message("Diese Gruppensuche ist nicht mehr aktiv.", ephemeral=True)

        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Nicht erlaubt.", ephemeral=True)

        if not self.is_admin_offizier_or_creator(interaction.user, state.creator_id):
            return await interaction.response.send_message("Du darfst diesen Ping nicht auslösen.", ephemeral=True)

        if not state.waitlist_order:
            return await interaction.response.send_message("Warteschlange ist leer.", ephemeral=True)

        channel = interaction.channel
        if channel is None or not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("Channel nicht gefunden.", ephemeral=True)

        now = time.time()
        is_admin = self.is_admin_or_offizier(interaction.user)
        is_creator = interaction.user.id == state.creator_id

        if is_creator and not is_admin:
            last = state.ping_waitlist_last_ts
            if last is not None and (now - last) < PING_COOLDOWN_SECONDS:
                remaining = int(PING_COOLDOWN_SECONDS - (now - last))
                mins = max(1, (remaining + 59) // 60)
                return await interaction.response.send_message(
                    f"⏳ Warteschlangen-Ping noch nicht möglich. Bitte warte noch **{mins} Minute(n)**.",
                    ephemeral=True
                )

        mentions = " ".join(f"<@{uid}>" for uid in state.waitlist_order)
        await channel.send(f"{mentions} – Hinweis: Bitte prüft die Gruppensuche, ggf. ist ein Platz frei geworden.")

        if is_creator and not is_admin:
            state.ping_waitlist_last_ts = now

        return await interaction.response.send_message("🔔 Warteschlange gepingt!", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gruppensuche(bot))
