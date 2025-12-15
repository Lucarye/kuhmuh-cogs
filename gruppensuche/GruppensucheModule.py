import discord
from discord import app_commands
from redbot.core import commands
from typing import Dict, Set, Optional, List, Tuple

# === IDs / Konfiguration ===
TEST_CHANNEL_ID = 1199322485297000528  # Öffentlicher Test-Channel
TEST_ROLE_ID = 1445018518562017373     # Test-Rolle fürs "Neue Suche" Ping

ROLE_NORMAL_ID = 1424768638157852682   # Muhhelfer – Normal
ROLE_SCHWER_ID = 1424769286790054050   # Muhhelfer – Schwer

# OPTIONAL: Wenn du eine feste Admin-Rolle hast, trage hier die ID ein.
# Dann dürfen nur Ersteller + Mitglieder mit dieser Rolle pingen.
# Wenn None: Ersteller + Administrator-Permission dürfen pingen.
ADMIN_ROLE_ID: Optional[int] = 1198650646786736240

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

# --- Custom IDs ---
CID_CATEGORY_SELECT = "grpsearch_category_select"

CID_BTN_JOIN = "grpsearch_join"
CID_BTN_LEAVE = "grpsearch_leave"
CID_BTN_PING = "grpsearch_ping"

CID_MUHH_DIFFICULTY_NORMAL = "muhh_diff_normal"
CID_MUHH_DIFFICULTY_SCHWER = "muhh_diff_schwer"
CID_MUHH_GO_BOSSES = "muhh_go_bosses"
CID_MUHH_BACK_DIFF = "muhh_back_diff"
CID_MUHH_BACK_BOSSES = "muhh_back_bosses"
CID_MUHH_TO_MODAL = "muhh_to_modal"

CID_MUHH_BOSS_SELECT = "muhh_boss_select"
CID_MUHH_TAG_PREFIX = "muhh_tag_"  # + boss_key

CID_MODAL_PILAFE = "grpsearch_pilafe_modal"
CID_MODAL_SPOT = "grpsearch_spot_modal"
CID_MODAL_MUHH_DETAILS = "grpsearch_muhhelfer_details_modal"


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
        requirement_akvk: Optional[str] = None,    # "301/385" etc. oder Override
        ping_role_id: Optional[int] = None,
        ping_used: bool = False,
        tag_runs: Optional[Set[str]] = None,       # boss_keys mit TAG Run
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
        self.ping_used = ping_used
        self.tag_runs = tag_runs or set()
        self.participants: Set[int] = set()


class MuhhWizardState:
    """Ephemeral Wizard state pro User."""
    def __init__(self) -> None:
        self.difficulty: Optional[str] = None  # "Normal" / "Schwer"
        self.selected_boss_keys: List[str] = []
        self.tag_run_keys: Set[str] = set()


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
            custom_id=CID_CATEGORY_SELECT,
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


# === Muhhelfer Wizard Views ===

def build_muhh_embed_step_diff() -> discord.Embed:
    embed = discord.Embed(
        title=f"{MUHKUH_EMOJI} Muhhelfer – Schwierigkeit",
        description=(
            "Wähle die **Schwierigkeit**.\n\n"
            f"**Normal** → Empfohlen mind. **AK/VK {AKVK_NORMAL}**\n"
            f"**Schwer** → Empfohlen mind. **AK/VK {AKVK_SCHWER}**\n\n"
            "Danach wählst du bis zu **5 Bosse** (wie im Game)."
        ),
        colour=discord.Colour.blurple(),
    )
    return embed


def build_muhh_embed_step_bosses(state: MuhhWizardState) -> discord.Embed:
    diff = state.difficulty or "—"
    req = AKVK_NORMAL if diff == "Normal" else (AKVK_SCHWER if diff == "Schwer" else "—")
    embed = discord.Embed(
        title=f"{MUHKUH_EMOJI} Muhhelfer – Bossauswahl",
        description=(
            f"**Schwierigkeit:** {diff}\n"
            f"**Empfohlen mind. AK/VK:** {req}\n\n"
            "Wähle bis zu **5 Bosse**."
        ),
        colour=discord.Colour.blurple(),
    )
    return embed


def build_muhh_embed_step_tags(state: MuhhWizardState) -> discord.Embed:
    diff = state.difficulty or "—"
    req = AKVK_NORMAL if diff == "Normal" else (AKVK_SCHWER if diff == "Schwer" else "—")

    chosen = state.selected_boss_keys
    boss_lines = []
    for k in chosen:
        name = dict(BOSSES).get(k, k)
        if k in state.tag_run_keys:
            boss_lines.append(f"• {name} **(TAG Run)**")
        else:
            boss_lines.append(f"• {name}")

    if not boss_lines:
        boss_text = "_Keine Bosse ausgewählt._"
    else:
        boss_text = "\n".join(boss_lines)

    warning = ""
    if state.tag_run_keys:
        warning = "\n\n⚠️ **TAG-Char / 2. Charakter erforderlich**"

    embed = discord.Embed(
        title=f"{MUHKUH_EMOJI} Muhhelfer – TAG Run",
        description=(
            f"**Schwierigkeit:** {diff}\n"
            f"**Empfohlen mind. AK/VK:** {req}\n\n"
            "**Ausgewählte Bosse:**\n"
            f"{boss_text}"
            f"{warning}\n\n"
            "Markiere Boss(e) als **TAG Run** (Toggle), dann **Weiter**."
        ),
        colour=discord.Colour.blurple(),
    )
    return embed


class MuhhDifficultyView(discord.ui.View):
    def __init__(self, cog: "Gruppensuche", user_id: int) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Normal", style=discord.ButtonStyle.primary, custom_id=CID_MUHH_DIFFICULTY_NORMAL)
    async def btn_normal(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.set_muhh_difficulty(interaction, self.user_id, "Normal")

    @discord.ui.button(label="Schwer", style=discord.ButtonStyle.danger, custom_id=CID_MUHH_DIFFICULTY_SCHWER)
    async def btn_schwer(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.set_muhh_difficulty(interaction, self.user_id, "Schwer")


class MuhhBossSelect(discord.ui.Select):
    def __init__(self, user_id: int) -> None:
        options = [discord.SelectOption(label=label, value=key) for (key, label) in BOSSES]
        super().__init__(
            custom_id=CID_MUHH_BOSS_SELECT,
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

    @discord.ui.button(label="Zurück", style=discord.ButtonStyle.secondary, custom_id=CID_MUHH_BACK_DIFF)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.back_to_muhh_difficulty(interaction, self.user_id)


class MuhhTagView(discord.ui.View):
    def __init__(self, cog: "Gruppensuche", user_id: int, boss_keys: List[str]) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id

        # Toggle Buttons (max 5) – pro ausgewähltem Boss
        for k in boss_keys[:5]:
            label = dict(BOSSES).get(k, k)
            self.add_item(MuhhTagToggleButton(boss_key=k, label=label))

        # Control Row
        self.add_item(MuhhBackBossesButton())
        self.add_item(MuhhContinueButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id


class MuhhTagToggleButton(discord.ui.Button):
    def __init__(self, boss_key: str, label: str) -> None:
        super().__init__(
            label=f"TAG Run: {label}",
            style=discord.ButtonStyle.secondary,
            custom_id=f"{CID_MUHH_TAG_PREFIX}{boss_key}",
            row=0
        )
        self.boss_key = boss_key

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: Optional[Gruppensuche] = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            return await interaction.response.send_message("Interner Fehler: Cog nicht gefunden.", ephemeral=True)
        await cog.toggle_muhh_tag(interaction, interaction.user.id, self.boss_key)


class MuhhBackBossesButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Zurück", style=discord.ButtonStyle.secondary, custom_id=CID_MUHH_BACK_BOSSES, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: Optional[Gruppensuche] = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            return await interaction.response.send_message("Interner Fehler: Cog nicht gefunden.", ephemeral=True)
        await cog.back_to_muhh_bosses(interaction, interaction.user.id)


class MuhhContinueButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Weiter", style=discord.ButtonStyle.success, custom_id=CID_MUHH_TO_MODAL, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        cog: Optional[Gruppensuche] = interaction.client.get_cog("Gruppensuche")  # type: ignore[attr-defined]
        if cog is None:
            return await interaction.response.send_message("Interner Fehler: Cog nicht gefunden.", ephemeral=True)
        await cog.open_muhh_details_modal(interaction, interaction.user.id)


# === Modals: PilaFe / Spot / Muhh Details ===

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
            tag_runs=set(),
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
            tag_runs=set(),
        )


class MuhhDetailsModal(discord.ui.Modal, title="Muhhelfer – Details"):
    duration_hours = discord.ui.TextInput(
        label="Dauer (in Stunden)",
        placeholder="z. B. 2",
        required=False,
        style=discord.TextStyle.short,
        custom_id="muhh_duration_hours",
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
        placeholder="z. B. 320/395 (überschreibt Standard)",
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


# === Öffentliche View (Join/Leave + Ping) ===

class GroupSearchJoinLeaveView(discord.ui.View):
    def __init__(self, cog: "Gruppensuche", message_id: int) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.message_id = message_id

    @discord.ui.button(label="Ich bin dabei", style=discord.ButtonStyle.success, custom_id=CID_BTN_JOIN)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.handle_join_leave(interaction, self.message_id, join=True)

    @discord.ui.button(label="Abmelden", style=discord.ButtonStyle.secondary, custom_id=CID_BTN_LEAVE)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.handle_join_leave(interaction, self.message_id, join=False)


class GroupSearchPingView(discord.ui.View):
    def __init__(self, cog: "Gruppensuche", message_id: int) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.message_id = message_id

    @discord.ui.button(label="🔔 Ping", style=discord.ButtonStyle.primary, custom_id=CID_BTN_PING)
    async def ping_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.cog.handle_ping(interaction, self.message_id)


# === Haupt-Cog ===

class Gruppensuche(commands.Cog):
    """Gruppensuche: /gruppensuche Wizard + öffentliche Suche mit Join/Ping."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.group_searches: Dict[int, GroupSearchState] = {}
        self.muhh_wizard: Dict[int, MuhhWizardState] = {}

    async def cog_load(self) -> None:
        guild_obj = discord.Object(id=GUILD_ID)
        self.bot.tree.add_command(self.gruppensuche_command, guild=guild_obj)
        print("Gruppensuche: Slash-Command registriert, sync ...")
        await self.bot.tree.sync(guild=guild_obj)
        print("Gruppensuche: Slash-Commands gesynct.")

    async def cog_unload(self) -> None:
        guild_obj = discord.Object(id=GUILD_ID)
        self.bot.tree.remove_command(
            self.gruppensuche_command.name,
            type=self.gruppensuche_command.type,
            guild=guild_obj,
        )

    # === Slash Command Einstieg ===
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="gruppensuche", description="Starte eine neue Gruppensuche mit Formular.")
    async def gruppensuche_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title=f"{MUHKUH_EMOJI} gruppensuche erstellen",
            description=(
                "Wähle, wofür du eine Gruppe suchst.\n\n"
                f"• **Muhhelfer (LoML Bosse)**\n"
                f"• **Pila Fe Schriftrollen**\n"
                f"• **Gruppenspots**\n\n"
                "Nach der Auswahl kannst du Details wie **Menge**, **Dauer** und **Startzeit** angeben."
            ),
            colour=discord.Colour.blurple(),
        )

        view = CategorySelectView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # === Muhhelfer Wizard: Schritt 1 (Schwierigkeit) ===
    async def start_muhhelfer_wizard(self, interaction: discord.Interaction) -> None:
        user_id = interaction.user.id
        self.muhh_wizard[user_id] = MuhhWizardState()

        embed = build_muhh_embed_step_diff()
        view = MuhhDifficultyView(self, user_id)
        await interaction.response.edit_message(embed=embed, view=view)

    async def set_muhh_difficulty(self, interaction: discord.Interaction, user_id: int, difficulty: str) -> None:
        state = self.muhh_wizard.get(user_id)
        if state is None:
            self.muhh_wizard[user_id] = MuhhWizardState()
            state = self.muhh_wizard[user_id]

        state.difficulty = difficulty
        state.selected_boss_keys = []
        state.tag_run_keys = set()

        embed = build_muhh_embed_step_bosses(state)
        view = MuhhBossView(self, user_id)
        await interaction.response.edit_message(embed=embed, view=view)

    async def back_to_muhh_difficulty(self, interaction: discord.Interaction, user_id: int) -> None:
        state = self.muhh_wizard.get(user_id)
        if state is None:
            self.muhh_wizard[user_id] = MuhhWizardState()
        embed = build_muhh_embed_step_diff()
        view = MuhhDifficultyView(self, user_id)
        await interaction.response.edit_message(embed=embed, view=view)

    # === Muhhelfer Wizard: Schritt 2 (Bosse) ===
    async def set_muhh_bosses(self, interaction: discord.Interaction, user_id: int, boss_keys: List[str]) -> None:
        state = self.muhh_wizard.get(user_id)
        if state is None or not state.difficulty:
            # Falls jemand "komisch" klickt, zurück auf Schwierigkeit
            return await self.back_to_muhh_difficulty(interaction, user_id)

        state.selected_boss_keys = boss_keys[:5]
        # TagRuns bereinigen, falls Boss abgewählt
        state.tag_run_keys = {k for k in state.tag_run_keys if k in state.selected_boss_keys}

        embed = build_muhh_embed_step_tags(state)
        view = MuhhTagView(self, user_id, state.selected_boss_keys)
        await interaction.response.edit_message(embed=embed, view=view)

    async def back_to_muhh_bosses(self, interaction: discord.Interaction, user_id: int) -> None:
        state = self.muhh_wizard.get(user_id)
        if state is None or not state.difficulty:
            return await self.back_to_muhh_difficulty(interaction, user_id)

        embed = build_muhh_embed_step_bosses(state)
        view = MuhhBossView(self, user_id)
        await interaction.response.edit_message(embed=embed, view=view)

    # === Muhhelfer Wizard: Schritt 3 (TAG Toggle) ===
    async def toggle_muhh_tag(self, interaction: discord.Interaction, user_id: int, boss_key: str) -> None:
        state = self.muhh_wizard.get(user_id)
        if state is None:
            return await interaction.response.send_message("Wizard-Status verloren. Bitte /gruppensuche neu starten.", ephemeral=True)
        if boss_key not in state.selected_boss_keys:
            return await interaction.response.send_message("Boss ist nicht (mehr) ausgewählt.", ephemeral=True)

        if boss_key in state.tag_run_keys:
            state.tag_run_keys.remove(boss_key)
        else:
            state.tag_run_keys.add(boss_key)

        embed = build_muhh_embed_step_tags(state)
        view = MuhhTagView(self, user_id, state.selected_boss_keys)
        await interaction.response.edit_message(embed=embed, view=view)

    async def open_muhh_details_modal(self, interaction: discord.Interaction, user_id: int) -> None:
        state = self.muhh_wizard.get(user_id)
        if state is None or not state.difficulty or not state.selected_boss_keys:
            return await interaction.response.send_message("Bitte erst Schwierigkeit + Bosse auswählen.", ephemeral=True)

        await interaction.response.send_modal(MuhhDetailsModal(custom_id=CID_MODAL_MUHH_DETAILS))

    # === Muhhelfer Wizard: Finish (Modal Submit) ===
    async def finish_muhhelfer(self, interaction: discord.Interaction) -> None:
        user_id = interaction.user.id
        state = self.muhh_wizard.get(user_id)
        if state is None or not state.difficulty or not state.selected_boss_keys:
            return await interaction.response.send_message("Wizard-Status verloren. Bitte /gruppensuche neu starten.", ephemeral=True)

        # Modal Inputs
        duration_raw = interaction.data.get("components", [])
        # discord.py liefert Modal-Felder in interaction.data; einfacher: direkt über response fields gibt’s hier nicht.
        # Daher lesen wir über interaction.data (ModalSubmitInteraction-like).
        # Wir extrahieren die custom_ids:
        fields: Dict[str, str] = {}
        for row in interaction.data.get("components", []):  # type: ignore[union-attr]
            for comp in row.get("components", []):
                cid = comp.get("custom_id")
                val = comp.get("value", "")
                if cid:
                    fields[cid] = val

        duration_in = fields.get("muhh_duration_hours", "").strip()
        start_in = fields.get("muhh_start_time", "").strip()
        custom_akvk_in = fields.get("muhh_custom_akvk", "").strip()
        note_in = fields.get("muhh_note", "").strip()

        duration = f"{duration_in} Stunden" if duration_in else None
        start_time = start_in or None
        note = note_in or None

        # Requirement (Standard oder Override)
        if custom_akvk_in:
            requirement = custom_akvk_in
        else:
            requirement = AKVK_NORMAL if state.difficulty == "Normal" else AKVK_SCHWER

        ping_role_id = ROLE_NORMAL_ID if state.difficulty == "Normal" else ROLE_SCHWER_ID

        # Detail Lines (Bosse + TAG Run)
        boss_label_map = dict(BOSSES)
        boss_lines = []
        for k in state.selected_boss_keys:
            name = boss_label_map.get(k, k)
            if k in state.tag_run_keys:
                boss_lines.append(f"• {name} **(TAG Run)**")
            else:
                boss_lines.append(f"• {name}")

        detail_lines = [
            "**Bosse:**",
            *boss_lines
        ]
        if state.tag_run_keys:
            detail_lines.append("")
            detail_lines.append("⚠️ **TAG-Char / 2. Charakter erforderlich**")

        await self.create_public_group_message(
            interaction,
            category="muhhelfer",
            title=f"{MUHKUH_EMOJI} gruppensuche – Muhhelfer",
            subtitle="Muhhelfer (LoML Bosse)",
            detail_lines=detail_lines,
            duration=duration,
            start_time=start_time,
            note=note,
            difficulty=state.difficulty,
            requirement_akvk=requirement,
            ping_role_id=ping_role_id,
            tag_runs=set(state.tag_run_keys),
        )

        # Wizard-Status löschen
        self.muhh_wizard.pop(user_id, None)

    # === Öffentliche Nachricht erstellen ===
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
        tag_runs: Set[str],
    ) -> None:
        if interaction.guild is None:
            return await interaction.response.send_message("Dieser Befehl kann nur auf einem Server verwendet werden.", ephemeral=True)

        channel = interaction.guild.get_channel(TEST_CHANNEL_ID)
        if channel is None or not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("Test-Channel nicht gefunden.", ephemeral=True)

        creator_id = interaction.user.id

        # State vorbereiten
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
            ping_used=False,
            tag_runs=tag_runs,
        )

        # Ersteller automatisch als Teilnehmer
        state.participants.add(creator_id)

        embed = self.build_public_embed(state)

        # Zwei Reihen: Join/Leave oben, Ping unten
        join_view = GroupSearchJoinLeaveView(self, message_id=0)
        ping_view = GroupSearchPingView(self, message_id=0)

        # Senden
        sent = await channel.send(
            content=f"<@&{TEST_ROLE_ID}>",
            embed=embed,
            view=join_view
        )

        # Ping-Buttons als zweite Nachricht? -> du wolltest "unten drunter" als zweite Reihe.
        # Discord Views können mehrere Reihen in einer View – wir nutzen daher eine kombinierte View:
        combined_view = self.build_combined_public_view(sent.id, ping_enabled=True, ping_used=False)

        # State finalisieren
        state.message_id = sent.id
        self.group_searches[sent.id] = state

        await sent.edit(view=combined_view)

        await interaction.response.send_message(f"Deine Gruppensuche wurde in <#{TEST_CHANNEL_ID}> erstellt.", ephemeral=True)

    def build_combined_public_view(self, message_id: int, ping_enabled: bool, ping_used: bool) -> discord.ui.View:
        view = discord.ui.View(timeout=None)

        # Row 0: Join/Leave
        btn_join = discord.ui.Button(label="Ich bin dabei", style=discord.ButtonStyle.success, custom_id=CID_BTN_JOIN, row=0)
        btn_leave = discord.ui.Button(label="Abmelden", style=discord.ButtonStyle.secondary, custom_id=CID_BTN_LEAVE, row=0)

        async def join_cb(interaction: discord.Interaction):
            await self.handle_join_leave(interaction, message_id, join=True)
        async def leave_cb(interaction: discord.Interaction):
            await self.handle_join_leave(interaction, message_id, join=False)

        btn_join.callback = join_cb  # type: ignore[assignment]
        btn_leave.callback = leave_cb  # type: ignore[assignment]

        view.add_item(btn_join)
        view.add_item(btn_leave)

        # Row 1: Ping
        if ping_enabled:
            label = "🔔 Ping"
            style = discord.ButtonStyle.primary
            disabled = ping_used

            if ping_used:
                label = "🔔 Ping gesendet"
                style = discord.ButtonStyle.secondary

            btn_ping = discord.ui.Button(label=label, style=style, custom_id=CID_BTN_PING, row=1, disabled=disabled)

            async def ping_cb(interaction: discord.Interaction):
                await self.handle_ping(interaction, message_id)

            btn_ping.callback = ping_cb  # type: ignore[assignment]
            view.add_item(btn_ping)

        return view

    def build_public_embed(self, state: GroupSearchState) -> discord.Embed:
        creator_mention = f"<@{state.creator_id}>"
        desc_lines: List[str] = []
        desc_lines.append(f"**Suchender:** {creator_mention}")
        desc_lines.append(f"**Kategorie:** {state.subtitle}")

        if state.difficulty:
            desc_lines.append(f"**Schwierigkeit:** {state.difficulty}")
        if state.requirement_akvk:
            desc_lines.append(f"**Anforderung AK/VK:** {state.requirement_akvk}")

        desc_lines.append("")  # spacing

        desc_lines.extend(state.detail_lines)

        if state.duration:
            desc_lines.append("")
            desc_lines.append(f"**Dauer:** {state.duration}")
        if state.start_time:
            desc_lines.append(f"**Start:** {state.start_time}")
        if state.note:
            desc_lines.append(f"**Hinweis:** {state.note}")

        participants_list = list(state.participants)
        participants_text = "\n".join(f"• <@{uid}>" for uid in participants_list) if participants_list else "Noch keine Teilnehmer."

        embed = discord.Embed(
            title=state.title,
            description="\n".join(desc_lines),
            colour=discord.Colour.blurple(),
        )
        embed.add_field(name=f"Teilnehmer ({len(participants_list)})", value=participants_text, inline=False)
        embed.set_footer(text='Klicke auf „Ich bin dabei“, um dich einzutragen.')
        embed.timestamp = discord.utils.utcnow()
        return embed

    # === Buttons: Join/Leave ===
    async def handle_join_leave(self, interaction: discord.Interaction, message_id: int, *, join: bool) -> None:
        state = self.group_searches.get(message_id)
        if state is None:
            return await interaction.response.send_message("Diese Gruppensuche ist nicht mehr aktiv.", ephemeral=True)

        user_id = interaction.user.id
        if join:
            state.participants.add(user_id)
        else:
            # Ersteller darf sich abmelden – wenn du das NICHT willst, sag Bescheid.
            state.participants.discard(user_id)

        embed = self.build_public_embed(state)
        view = self.build_combined_public_view(message_id, ping_enabled=bool(state.ping_role_id), ping_used=state.ping_used)

        await interaction.response.edit_message(embed=embed, view=view)

    # === Button: Ping (einmalig, Ersteller + Admin) ===
    async def handle_ping(self, interaction: discord.Interaction, message_id: int) -> None:
        state = self.group_searches.get(message_id)
        if state is None:
            return await interaction.response.send_message("Diese Gruppensuche ist nicht mehr aktiv.", ephemeral=True)

        if state.ping_used:
            return await interaction.response.send_message("Ping wurde bereits gesendet.", ephemeral=True)

        # Berechtigungscheck: Ersteller oder Admin
        if not self.is_ping_allowed(interaction, state.creator_id):
            return await interaction.response.send_message("Du darfst diesen Ping nicht auslösen.", ephemeral=True)

        if not state.ping_role_id:
            return await interaction.response.send_message("Für diese Suche ist kein Ping konfiguriert.", ephemeral=True)

        # Ping senden (als neue Nachricht im Channel)
        channel = interaction.channel
        if channel is None or not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("Channel nicht gefunden.", ephemeral=True)

        await channel.send(f"<@&{state.ping_role_id}> – neue Suche: <@{state.creator_id}>")

        state.ping_used = True

        embed = self.build_public_embed(state)
        view = self.build_combined_public_view(message_id, ping_enabled=True, ping_used=True)

        # Button deaktivieren + Interaction Message aktualisieren
        await interaction.response.edit_message(embed=embed, view=view)

    def is_ping_allowed(self, interaction: discord.Interaction, creator_id: int) -> bool:
        if interaction.user.id == creator_id:
            return True

        # Admin-Rolle bevorzugt, wenn gesetzt
        if ADMIN_ROLE_ID is not None:
            if isinstance(interaction.user, discord.Member):
                return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)
            return False

        # Fallback: Discord Admin Permission
        if isinstance(interaction.user, discord.Member):
            return interaction.user.guild_permissions.administrator

        return False


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gruppensuche(bot))
