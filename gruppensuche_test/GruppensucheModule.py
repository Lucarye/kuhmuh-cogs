from __future__ import annotations
from discord import app_commands

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import discord
from redbot.core import commands, Config


# =========================
# IDs / Konfiguration
# =========================

TEST_CHANNEL_ID = 1199322485297000528
TEST_ROLE_ID = 1445018518562017373

ROLE_NORMAL_ID = 1424768638157852682
ROLE_SCHWER_ID = 1424769286790054050

ROLE_MIRUMOK_ID = 1459832247405248707
ROLE_GYFIN_ID = 1459832490603708590

ROLE_PILAFE_ID = 1458832343149318269
ROLE_ALTAR_ID = 1459833455369130140

ADMIN_ROLE_ID: Optional[int] = 1198650646786736240
OFFIZIER_ROLE_ID: Optional[int] = 1198652039312453723

PING_COOLDOWN_SECONDS = 600

MUHKUH_EMOJI = "<:muhkuh:1207038544510586890>"
PILAFE_EMOJI = "<:pilafe:1450051653297504368>"
MIRUMOK_EMOJI = "<:Mirumok:1461101498954940428>"
GYFIN_EMOJI = "<:Gyfin:1461102103266066502>"
CHEER_EMOJI = "<:blackspiritcheer:1199730129476268183>"

GUILD_ID = 1198649628787212458

AKVK_NORMAL = "301/385"
AKVK_SCHWER = "330/401"

BOSSES: List[Tuple[str, str]] = [
    ("bulgasal", "Bulgasal"),
    ("jigwi", "Jigwi"),
    ("uturi", "Uturi"),
    ("dunkler_bonghwang", "Dunkler Bonghwang"),
    ("bihyung", "Bihyung"),
    ("entthronter_kronprinz", "Entthronter Kronprinz"),
    ("knabe_blau", "Knabe in Blau"),
]

SPOTS: List[Tuple[str, str]] = [
    ("mirumok", "Mirumok"),
    ("gyfin", "Gyfin"),
]

SPOT_REQ: Dict[str, str] = {
    "mirumok": "350+ AP / 427+ VK",
    "gyfin": "370+ AP / 440+ VK",
}

SPOT_TOTAL_AP: Dict[str, str] = {
    "mirumok": "Total AP 1565 - 1595",
    "gyfin": "Total AP 1650 - 1680",
}

SPOT_PING_ROLE: Dict[str, int] = {
    "mirumok": ROLE_MIRUMOK_ID,
    "gyfin": ROLE_GYFIN_ID,
}


# =========================
# Helpers
# =========================

WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _now_local() -> dt.datetime:
    return dt.datetime.now()


def _format_day(d: dt.date) -> str:
    wd = WEEKDAYS_DE[d.weekday()]
    return f"{wd}, {d.day:02d}.{d.month:02d}."


def _safe_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except Exception:
        return None


def _parse_date_input(text: str) -> Optional[dt.date]:
    t = (text or "").strip()
    if not t:
        return None

    parts = t.replace("/", ".").split(".")
    if len(parts) in (2, 3):
        day = _safe_int(parts[0])
        month = _safe_int(parts[1])
        year = None
        if len(parts) == 3:
            year = _safe_int(parts[2])
        if day is None or month is None:
            return None
        if year is None:
            year = _now_local().year
        try:
            return dt.date(year, month, day)
        except Exception:
            return None

    if "-" in t:
        ymd = t.split("-")
        if len(ymd) == 3:
            year = _safe_int(ymd[0])
            month = _safe_int(ymd[1])
            day = _safe_int(ymd[2])
            if year is None or month is None or day is None:
                return None
            try:
                return dt.date(year, month, day)
            except Exception:
                return None

    return None


def _has_mod_rights(member: discord.Member) -> bool:
    role_ids = {r.id for r in member.roles}
    if ADMIN_ROLE_ID and ADMIN_ROLE_ID in role_ids:
        return True
    if OFFIZIER_ROLE_ID and OFFIZIER_ROLE_ID in role_ids:
        return True
    return False


def _boss_name(key: str) -> str:
    for k, name in BOSSES:
        if k == key:
            return name
    return key


def _spot_name(key: str) -> str:
    for k, name in SPOTS:
        if k == key:
            return name
    return key


def _sum_runs(boss_runs: Dict[str, int]) -> int:
    return sum(int(v) for v in boss_runs.values())


def _allowed_party_range(category: str) -> Tuple[int, int]:
    if category == "spots":
        return (2, 3)
    if category == "muhhelfer":
        return (2, 5)
    if category == "pilafe":
        return (2, 5)
    return (2, 5)


def _default_req_for(data: dict) -> str:
    cat = data.get("category")
    if cat == "muhhelfer":
        diff = data.get("difficulty", "normal")
        return AKVK_SCHWER if diff == "schwer" else AKVK_NORMAL
    if cat == "spots":
        spot = data.get("spot_key", "")
        return SPOT_REQ.get(spot, "")
    return ""


# =========================
# Session
# =========================

@dataclass
class WizardSession:
    user_id: int
    guild_id: int
    mode: str = "create"  # "create" | "edit"
    edit_message_id: Optional[int] = None
    wizard_interaction: Optional[discord.Interaction] = None
    
    category: Optional[str] = None  # "muhhelfer" | "spots" | "pilafe"
    day_date_iso: Optional[str] = None

    difficulty: Optional[str] = None  # muhhelfer: "normal"|"schwer"
    boss_runs: Dict[str, int] = field(default_factory=dict)

    spot_key: Optional[str] = None  # spots: "mirumok"|"gyfin"

    max_players: Optional[int] = None

    scroll_amount: Optional[str] = None  # pilafe required on create
    duration_text: Optional[str] = None
    start_text: Optional[str] = None
    req_text: Optional[str] = None
    notes: Optional[str] = None
    own_ap: Optional[str] = None



# =========================
# Modals
# =========================

class CustomDateModal(discord.ui.Modal):
    def __init__(self, title: str, on_done):
        super().__init__(title=title)
        self.on_done = on_done

        self.date_input = discord.ui.TextInput(
            label="Datum",
            placeholder="z.B. 15.01.2026 oder 15.01. oder 2026-01-15",
            required=True,
            max_length=20,
        )
        self.add_item(self.date_input)

    async def on_submit(self, interaction: discord.Interaction):
        d = _parse_date_input(str(self.date_input.value))
        if d is None:
            await interaction.response.send_message("Ungültiges Datum. Bitte versuche es erneut.", ephemeral=True)
            return

        today = _now_local().date()
        if d < today:
            await interaction.response.send_message("Das Datum darf nicht in der Vergangenheit liegen.", ephemeral=True)
            return

        await self.on_done(interaction, d)


class DetailsModal(discord.ui.Modal):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession, defaults: Optional[dict] = None):
        super().__init__(title="Details zur Gruppensuche")
        self.cog = cog
        self.session = session
        self.defaults = defaults or {}
        current_own_ap = self.defaults.get("own_ap") or ""
        self.own_ap = discord.ui.TextInput(
            label="Deine AP (Pflicht)",
            placeholder="z.B. 305",
            required=True if session.mode == "create" else False,
            max_length=10,
            default=str(current_own_ap) if current_own_ap else None,
        )
        self.add_item(self.own_ap)


        is_pilafe = session.category == "pilafe"

        current_amount = self.defaults.get("scroll_amount") if is_pilafe else ""
        current_duration = self.defaults.get("duration_text") or ""
        current_start = self.defaults.get("start_text") or ""
        current_req = self.defaults.get("req_text") or self.defaults.get("req_default") or ""
        current_notes = self.defaults.get("notes") or ""
        


        self.scroll_amount = discord.ui.TextInput(
            label="Menge an Schriftrollen (nur Pila Fe)",
            placeholder="z.B. 1000",
            required=is_pilafe and session.mode == "create",
            max_length=30,
            default=str(current_amount) if current_amount else None,
        )
        self.duration_text = discord.ui.TextInput(
            label="Geplante Dauer",
            placeholder="z.B. 30min, 90min, 2h",
            required=False,
            max_length=60,
            default=str(current_duration) if current_duration else None,
        )
        self.start_text = discord.ui.TextInput(
            label="Startzeit",
            placeholder="z.B. jetzt, 20Uhr, später",
            required=False,
            max_length=60,
            default=str(current_start) if current_start else None,
        )
        self.req_text = discord.ui.TextInput(
            label="Gewünschte AK/VK (optional)",
            placeholder=f"Empfohlen: {current_req}" if current_req else "z.B. 370+ AP / 440+ VK",
            required=False,
            max_length=60,
            default=None,   # wichtig!
        )
        self.notes = discord.ui.TextInput(
            label="Optionale Notizen",
            placeholder="Gear, Anforderungen, Sonstiges",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=400,
            default=str(current_notes) if current_notes else None,
        )

        if is_pilafe:
            self.add_item(self.scroll_amount)
        self.add_item(self.duration_text)
        self.add_item(self.start_text)
        self.add_item(self.req_text)
        self.add_item(self.notes)

    async def on_submit(self, interaction: discord.Interaction):
        # Modal immer zuerst sauber beantworten -> Modal schließt zuverlässig
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        own_ap_val = str(self.own_ap.value).strip() if hasattr(self, "own_ap") else ""
        if self.session.mode == "create":
            if not own_ap_val:
                await interaction.followup.send("AP ist Pflicht.", ephemeral=True)
                return
            self.session.own_ap = own_ap_val
        else:
            # im Edit-Mode optional übernehmen, wenn gesetzt
            if own_ap_val:
                self.session.own_ap = own_ap_val


        # Session-Felder setzen
        if self.session.category == "pilafe" and self.session.mode == "create":
            if not str(self.scroll_amount.value).strip():
                await interaction.followup.send("Bei Pila Fe ist die Menge Pflicht.", ephemeral=True)
                return
            self.session.scroll_amount = str(self.scroll_amount.value).strip()
        elif self.session.category == "pilafe":
            val = str(self.scroll_amount.value).strip()
            self.session.scroll_amount = val if val else (self.defaults.get("scroll_amount") or None)

        self.session.duration_text = str(self.duration_text.value).strip() or None
        self.session.start_text = str(self.start_text.value).strip() or None
        self.session.req_text = str(self.req_text.value).strip() or None
        self.session.notes = str(self.notes.value).strip() or None

        # Ab hier NICHT die Modal-Interaction verwenden,
        # sondern die Interaction, die das Wizard-Ephemeral besitzt.
        base_interaction = self.session.wizard_interaction or interaction

        if self.session.mode == "create":
            await self.cog._create_public_post_from_session(base_interaction, self.session)
            return

        await self.cog._apply_edit_details(base_interaction, self.session)

class JoinApModal(discord.ui.Modal):
    def __init__(self, on_done):
        super().__init__(title="AP bei Anmeldung")
        self.on_done = on_done

        self.ap = discord.ui.TextInput(
            label="Deine AP (Pflicht)",
            placeholder="z.B. 305",
            required=True,
            max_length=10,
        )
        self.add_item(self.ap)

    async def on_submit(self, interaction: discord.Interaction):
        val = str(self.ap.value).strip()
        if not val:
            await interaction.response.send_message("AP ist Pflicht.", ephemeral=True)
            return
        await self.on_done(interaction, val)



# =========================
# Base View
# =========================

class WizardBaseView(discord.ui.View):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession, timeout_seconds: int = 90):
        super().__init__(timeout=timeout_seconds)
        self.cog = cog
        self.session = session

    async def on_timeout(self):
        self.cog._expire_session(self.session.user_id)


# =========================
# Create Wizard Views
# =========================

class StartSelect(discord.ui.Select):
    def __init__(self, host_view: "StartView"):
        options = [
            discord.SelectOption(label="Muhhelfer (LoML Bosse)", value="muhhelfer", emoji=MUHKUH_EMOJI),
            discord.SelectOption(label="Gruppenspots", value="spots", emoji=CHEER_EMOJI),
            discord.SelectOption(label="Pila Fe Schriftrollen", value="pilafe", emoji=PILAFE_EMOJI),
        ]
        super().__init__(placeholder="Wähle eine Kategorie...", min_values=1, max_values=1, options=options)
        self.host_view = host_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.host_view.session.user_id:
            await interaction.response.send_message("Das kannst nur du bedienen.", ephemeral=True)
            return

        self.host_view.session.category = self.values[0]
        await self.host_view.cog._send_category_specific(interaction, self.host_view.session)



class StartView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(cog, session)
        self.add_item(StartSelect(self))

    def embed(self) -> discord.Embed:
        return discord.Embed(
            title=f"{MUHKUH_EMOJI} Gruppensuche erstellen",
            description=(
                "Wähle, wofür du eine Gruppe suchst.\n\n"
                "• Muhhelfer (LoML Bosse)\n"
                "• Gruppenspots\n"
                "• Pila Fe Schriftrollen\n\n"
                "Nach der Auswahl kannst du Details wie Menge, Geplante Dauer und Startzeit angeben."
            ),
        )


class DaySelectView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession, back_to: str):
        super().__init__(cog, session)
        self.back_to = back_to

        self._add_day_buttons()

        custom_btn = discord.ui.Button(label="Anderen Tag wählen", style=discord.ButtonStyle.secondary, row=2)
        custom_btn.callback = self._custom_day
        self.add_item(custom_btn)

        back_btn = discord.ui.Button(label="Zurück", style=discord.ButtonStyle.secondary, row=3)
        back_btn.callback = self._back
        self.add_item(back_btn)

    def _add_day_buttons(self):
        today = _now_local().date()
        for i in range(5):
            d = today + dt.timedelta(days=i)
            label = "Heute" if i == 0 else _format_day(d)
            if i == 0:
                label = f"Heute ({_format_day(d)})"
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.primary, row=0 if i < 3 else 1)
            btn.callback = self._make_day_cb(d)
            self.add_item(btn)

    def _make_day_cb(self, d: dt.date):
        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.session.user_id:
                await interaction.response.defer()
                return
            self.session.day_date_iso = d.isoformat()

            if self.session.mode == "create":
                # Nach Datum geht es jetzt weiter zu PartySize (für Muhhelfer/Spots)
                # bzw. für PilaFe bleibt es auch PartySize (passt)
                await self.cog._send_party_size(interaction, self.session)
                return
            
            await self.cog._apply_edit_day(interaction, self.session)

        return _cb

    async def _custom_day(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        async def _done(i: discord.Interaction, d: dt.date):
            self.session.day_date_iso = d.isoformat()

            if self.session.mode == "create":
                await self.cog._send_party_size(i, self.session)
                return

            # EDIT: Tag speichern + zurück ins Edit-Menü
            await self.cog._apply_edit_day(i, self.session)

        await interaction.response.send_modal(CustomDateModal("Anderen Tag wählen", _done))


    async def _back(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        if self.session.mode == "edit":
            await self.cog._send_edit_menu(interaction, self.session)
            return

        if self.back_to == "bosses":
            if self.session.category == "muhhelfer":
                await self.cog._send_boss_select(interaction, self.session)
                return

        if self.back_to == "spot":
            if self.session.category == "spots":
                await self.cog._send_spot_select(interaction, self.session)
                return

        # default
        await self.cog._send_start(interaction, self.session)



    def embed(self) -> discord.Embed:
        return discord.Embed(
            title=f"{MUHKUH_EMOJI} Tag",
            description="Wähle den Tag, für den die Suche gedacht ist.\nDas erscheint später im öffentlichen Beitrag.",
        )


class DifficultyView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(cog, session)

        normal_btn = discord.ui.Button(label="Normal", style=discord.ButtonStyle.primary, row=0)
        schwer_btn = discord.ui.Button(label="Schwer", style=discord.ButtonStyle.danger, row=0)
        normal_btn.callback = self._pick_normal
        schwer_btn.callback = self._pick_schwer
        self.add_item(normal_btn)
        self.add_item(schwer_btn)

        back_btn = discord.ui.Button(label="Zurück", style=discord.ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def _pick_normal(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        self.session.difficulty = "normal"
        await self.cog._send_boss_select(interaction, self.session)

    async def _pick_schwer(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        self.session.difficulty = "schwer"
        await self.cog._send_boss_select(interaction, self.session)

    async def _back(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        await self.cog._send_day_selection(interaction, self.session, back_to="start")

    def embed(self) -> discord.Embed:
        return discord.Embed(
            title=f"{MUHKUH_EMOJI} Muhhelfer – Schwierigkeit",
            description=(
                "Wähle die Schwierigkeit.\n\n"
                f"Normal → Empfohlen mind. AK/VK {AKVK_NORMAL}\n"
                f"Schwer → Empfohlen mind. AK/VK {AKVK_SCHWER}"
            ),
        )


class BossSelectView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(cog, session)

        self._boss_buttons: Dict[str, discord.ui.Button] = {}

        for idx, (key, name) in enumerate(BOSSES):
            row = 0 if idx < 5 else 1
            btn = discord.ui.Button(label=name, style=discord.ButtonStyle.secondary, row=row)
            btn.callback = self._make_toggle_boss(key)
            self._boss_buttons[key] = btn
            self.add_item(btn)

        back_btn = discord.ui.Button(label="Zurück", style=discord.ButtonStyle.secondary, row=2)
        next_btn = discord.ui.Button(label="Weiter", style=discord.ButtonStyle.success, row=2)
        back_btn.callback = self._back
        next_btn.callback = self._next
        self.add_item(back_btn)
        self.add_item(next_btn)

        self._refresh_styles()

    def _refresh_styles(self):
        for key, btn in self._boss_buttons.items():
            if key in self.session.boss_runs:
                btn.style = discord.ButtonStyle.success
            else:
                btn.style = discord.ButtonStyle.secondary

    def _runs_info(self) -> str:
        total = _sum_runs(self.session.boss_runs)
        free = max(0, 5 - total)
        return f"Runs: {total}/5 (frei: {free})"

    def _make_toggle_boss(self, key: str):
        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.session.user_id:
                await interaction.response.defer()
                return

            if key in self.session.boss_runs:
                del self.session.boss_runs[key]
            else:
                if _sum_runs(self.session.boss_runs) >= 5:
                    await interaction.response.send_message("Maximal 5 Runs insgesamt möglich.", ephemeral=True)
                    return
                self.session.boss_runs[key] = 1

            self._refresh_styles()
            await interaction.response.edit_message(embed=self.embed(), view=self)

        return _cb

    async def _back(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        if self.session.mode == "edit":
            await self.cog._send_edit_menu(interaction, self.session)
            return

        await self.cog._send_difficulty(interaction, self.session)

    async def _next(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        if not self.session.boss_runs:
            await interaction.response.send_message("Bitte wähle mindestens 1 Boss.", ephemeral=True)
            return

        total = _sum_runs(self.session.boss_runs)
        has_double = any(int(v) >= 2 for v in self.session.boss_runs.values())

        # EDIT-MODE:
        # Wenn bereits Doppelruns existieren, muss der User IMMER die Doppelrun-Ansicht sehen,
        # damit er sie ggf. wieder abwählen kann - auch bei 5/5.
        if self.session.mode == "edit":
            if has_double:
                await self.cog._send_double_run(interaction, self.session)
                return

            # keine Doppelruns gesetzt:
            # wenn voll, können wir direkt speichern
            if total >= 5:
                await self.cog._apply_edit_bosses(interaction, self.session)
                return

            # sonst optional Doppelruns anbieten
            await self.cog._send_double_run(interaction, self.session)
            return

        # CREATE-MODE (wie gehabt)
        if total >= 5:
            await self.cog._send_day_selection(interaction, self.session, back_to="bosses")
            return

        await self.cog._send_double_run(interaction, self.session)



    def embed(self) -> discord.Embed:
        diff = "Schwer" if self.session.difficulty == "schwer" else "Normal"
        req = AKVK_SCHWER if self.session.difficulty == "schwer" else AKVK_NORMAL
        return discord.Embed(
            title=f"{MUHKUH_EMOJI} Muhhelfer – Bossauswahl",
            description=(
                f"Schwierigkeit: {diff}\n"
                f"Empfohlen mind. AK/VK: {req}\n\n"
                "Wähle bis zu 5 Runs.\n"
                "Wenn noch Runs frei sind, kannst du danach optional Doppelruns markieren.\n"
                "Doppelrun = Boss wird 2x gelaufen (⚠️ 2. Charakter erforderlich).\n\n"
                f"{self._runs_info()}"
            ),
        )


class DoubleRunView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(cog, session)

        self._dr_buttons: Dict[str, discord.ui.Button] = {}

        selected = list(session.boss_runs.keys())
        order = [k for k, _ in BOSSES]
        selected.sort(key=lambda k: order.index(k) if k in order else 999)

        for idx, key in enumerate(selected):
            name = _boss_name(key)
            btn = discord.ui.Button(
                label=f"Doppel Run: {name}",
                style=discord.ButtonStyle.secondary,
                row=0 if idx < 5 else 1,
            )
            btn.callback = self._make_toggle_double(key)
            self._dr_buttons[key] = btn
            self.add_item(btn)

        back_btn = discord.ui.Button(label="Zurück", style=discord.ButtonStyle.secondary, row=2)
        next_label = "Speichern" if session.mode == "edit" else "Weiter"
        next_btn = discord.ui.Button(label=next_label, style=discord.ButtonStyle.success, row=2)
        back_btn.callback = self._back
        next_btn.callback = self._next
        self.add_item(back_btn)
        self.add_item(next_btn)

        self._refresh_styles()

    def _free_runs(self) -> int:
        return max(0, 5 - _sum_runs(self.session.boss_runs))

    def _refresh_styles(self):
        for key, btn in self._dr_buttons.items():
            if int(self.session.boss_runs.get(key, 1)) >= 2:
                btn.style = discord.ButtonStyle.success
            else:
                btn.style = discord.ButtonStyle.secondary

    def _make_toggle_double(self, key: str):
        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.session.user_id:
                await interaction.response.defer()
                return

            current = int(self.session.boss_runs.get(key, 1))
            if current >= 2:
                self.session.boss_runs[key] = 1
            else:
                if self._free_runs() <= 0:
                    await interaction.response.send_message("Keine freien Runs mehr. Maximal 5 Runs insgesamt.", ephemeral=True)
                    return
                self.session.boss_runs[key] = 2

            self._refresh_styles()
            await interaction.response.edit_message(embed=self.embed(), view=self)

        return _cb

    async def _back(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        await self.cog._send_boss_select(interaction, self.session)

    async def _next(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        if self.session.mode == "edit":
            await self.cog._apply_edit_bosses(interaction, self.session)
            return

        await self.cog._send_day_selection(interaction, self.session, back_to="bosses")


    def embed(self) -> discord.Embed:
        diff = "Schwer" if self.session.difficulty == "schwer" else "Normal"
        req = AKVK_SCHWER if self.session.difficulty == "schwer" else AKVK_NORMAL

        lines = []
        has_double = False
        for key, runs in self.session.boss_runs.items():
            name = _boss_name(key)
            if int(runs) >= 2:
                has_double = True
                lines.append(f"• {name} (Doppel Run)")
            else:
                lines.append(f"• {name}")

        chosen_text = "\n".join(lines) if lines else "—"
        extra = "\n\n⚠️ 2. Charakter erforderlich." if has_double else ""

        return discord.Embed(
            title=f"{MUHKUH_EMOJI} Muhhelfer – Doppel Run",
            description=(
                f"Schwierigkeit: {diff}\n"
                f"Empfohlen mind. AK/VK: {req}\n\n"
                "Ausgewählte Bosse:\n"
                f"{chosen_text}\n\n"
                "Markiere Boss(e) als Doppel Run (Toggle)."
                f"{extra}\n\n"
                f"Runs: {_sum_runs(self.session.boss_runs)}/5 (frei: {self._free_runs()})"
            ),
        )


class SpotSelectView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(cog, session)

        miru_btn = discord.ui.Button(label="Mirumok", style=discord.ButtonStyle.primary, row=0)
        gyfin_btn = discord.ui.Button(label="Gyfin", style=discord.ButtonStyle.primary, row=0)
        miru_btn.callback = self._pick_miru
        gyfin_btn.callback = self._pick_gyfin
        self.add_item(miru_btn)
        self.add_item(gyfin_btn)

        back_btn = discord.ui.Button(label="Zurück", style=discord.ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def _pick_miru(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        self.session.spot_key = "mirumok"
        await self.cog._send_day_selection(interaction, self.session, back_to="spot")


    async def _pick_gyfin(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        self.session.spot_key = "gyfin"
        await self.cog._send_day_selection(interaction, self.session, back_to="spot")


    async def _back(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        await self.cog._send_day_selection(interaction, self.session, back_to="start")

    def embed(self) -> discord.Embed:
        return discord.Embed(
            title=f"{CHEER_EMOJI} Gruppensuche – Mirumok / Gyfin",
            description=(
                "Wähle den Spot, für den du eine Gruppe suchst.\n\n"
                f"Mirumok\n• Empfohlen mind. {SPOT_REQ['mirumok']}\n• {SPOT_TOTAL_AP['mirumok']}\n\n"
                f"Gyfin\n• Empfohlen mind. {SPOT_REQ['gyfin']}\n• {SPOT_TOTAL_AP['gyfin']}"
            ),
        )


class PartySizeSelect(discord.ui.Select):
    def __init__(self, host_view: "PartySizeView", min_n: int, max_n: int, current: Optional[int] = None):
        options = []
        for n in range(min_n, max_n + 1):
            opt = discord.SelectOption(label=str(n), value=str(n), default=(current == n))
            options.append(opt)

        super().__init__(
            placeholder="Wähle die maximale Teilnehmerzahl...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.host_view = host_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.host_view.session.user_id:
            await interaction.response.send_message("Das kannst nur du bedienen.", ephemeral=True)
            return

        self.host_view.session.max_players = int(self.values[0])

        if self.host_view.session.mode == "create":
            await self.host_view.cog._send_final_form(interaction, self.host_view.session)
            return

        await self.host_view.cog._apply_edit_max_players(interaction, self.host_view.session)


class PartySizeView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession, current: Optional[int] = None):
        super().__init__(cog, session)

        mn, mx = _allowed_party_range(session.category or "")
        self.add_item(PartySizeSelect(self, mn, mx, current=current))

        back_btn = discord.ui.Button(label="Zurück", style=discord.ButtonStyle.secondary, row=1)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def _back(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        if self.session.mode == "edit":
            await self.cog._send_edit_menu(interaction, self.session)
            return

        if self.session.category == "spots":
            await self.cog._send_spot_select(interaction, self.session)
            return

        if self.session.category == "muhhelfer":
            if _sum_runs(self.session.boss_runs) >= 5:
                await self.cog._send_boss_select(interaction, self.session)
                return
            await self.cog._send_double_run(interaction, self.session)
            return

        await self.cog._send_day_selection(interaction, self.session, back_to="start")

    def embed(self) -> discord.Embed:
        if self.session.category == "muhhelfer":
            diff = "Schwer" if self.session.difficulty == "schwer" else "Normal"
            req = AKVK_SCHWER if self.session.difficulty == "schwer" else AKVK_NORMAL
            return discord.Embed(
                title=f"{MUHKUH_EMOJI} Muhhelfer – Gruppengröße",
                description=(
                    f"Schwierigkeit: {diff}\n"
                    f"Empfohlen mind. AK/VK: {req}\n\n"
                    "Wähle die maximale Teilnehmerzahl 2-5"
                ),
            )

        if self.session.category == "spots" and self.session.spot_key:
            spot = self.session.spot_key
            emoji = MIRUMOK_EMOJI if spot == "mirumok" else GYFIN_EMOJI
            return discord.Embed(
                title=f"{emoji} {_spot_name(spot)} - Gruppengröße",
                description=(
                    f"• Empfohlen mind. {SPOT_REQ.get(spot, '')}\n"
                    f"• {SPOT_TOTAL_AP.get(spot, '')}\n\n"
                    "Wähle die maximale Teilnehmerzahl."
                ),
            )

        if self.session.category == "pilafe":
            return discord.Embed(
                title="👥 Pila Fe - Gruppengröße",
                description="Wähle die maximale Teilnehmerzahl.",
            )

        return discord.Embed(title="Gruppengröße", description="Wähle die maximale Teilnehmerzahl.")


# =========================
# Edit Menu (ephemeral)
# =========================

class EditMenuView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession, post_data: dict):
        super().__init__(cog, session)
        self.post_data = post_data

        tag_btn = discord.ui.Button(label="Tag ändern", style=discord.ButtonStyle.secondary, row=0)
        size_btn = discord.ui.Button(label="Max. Teilnehmer ändern", style=discord.ButtonStyle.secondary, row=0)
        details_btn = discord.ui.Button(label="Zeiten & Notiz bearbeiten", style=discord.ButtonStyle.secondary, row=1)

        tag_btn.callback = self._tag
        size_btn.callback = self._size
        details_btn.callback = self._details

        self.add_item(tag_btn)
        self.add_item(size_btn)
        self.add_item(details_btn)

        if post_data.get("category") == "muhhelfer":
            bosses_btn = discord.ui.Button(label="Bosse & Doppelrun bearbeiten", style=discord.ButtonStyle.secondary, row=1)
            bosses_btn.callback = self._bosses
            self.add_item(bosses_btn)

        back_btn = discord.ui.Button(label="Zurück", style=discord.ButtonStyle.secondary, row=2)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def _tag(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        await self.cog._send_day_selection(interaction, self.session, back_to="edit_menu")

    async def _size(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        current = int(self.post_data.get("max_players", 2))
        view = PartySizeView(self.cog, self.session, current=current)
        await self.cog._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _details(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        defaults = dict(self.post_data)
        defaults["req_default"] = _default_req_for(self.post_data)

        try:
            await interaction.response.send_modal(DetailsModal(self.cog, self.session, defaults=defaults))
        except discord.InteractionResponded:
            await interaction.followup.send_modal(DetailsModal(self.cog, self.session, defaults=defaults))

    async def _bosses(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        await self.cog._send_boss_select(interaction, self.session)

    async def _back(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Bearbeitung beendet.", embed=None, view=None)

    def embed(self) -> discord.Embed:
        return discord.Embed(
            title="✏️ Suche bearbeiten",
            description=(
                "Du kannst nur bestehende Werte anpassen.\n"
                "Kategorie/Spot können nicht gewechselt werden.\n"
                "Wenn du etwas anderes suchst, starte bitte eine neue Gruppensuche."
            ),
        )


# =========================
# Persistent Public Views
# =========================

class ConfirmView(discord.ui.View):
    def __init__(self, cog: "GruppensucheTest", message_id: int, action: str, user_id: int):
        super().__init__(timeout=30)
        self.cog = cog
        self.message_id = message_id
        self.action = action  # "close" | "delete"
        self.user_id = user_id

        if action == "close":
            self.text = (
                "Möchtest du diese Suche wirklich schließen?\n"
                "Danach sind keine Anmeldungen/Pings mehr möglich (du kannst sie später wieder öffnen)."
            )
            confirm_label = "🔒 Ja, schließen"
        else:
            self.text = (
                "Möchtest du diese Suche wirklich endgültig löschen?\n"
                "⚠️ Dieser Vorgang kann nicht rückgängig gemacht werden."
            )
            confirm_label = "🗑 Ja, endgültig löschen"

        confirm_btn = discord.ui.Button(label=confirm_label, style=discord.ButtonStyle.danger)
        cancel_btn = discord.ui.Button(label="❌ Abbrechen", style=discord.ButtonStyle.secondary)

        confirm_btn.callback = self._confirm
        cancel_btn.callback = self._cancel

        self.add_item(confirm_btn)
        self.add_item(cancel_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Das kannst nur du bedienen.", ephemeral=True)
            return False
        return True

    async def _cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Abgebrochen.", view=None)

    async def _confirm(self, interaction: discord.Interaction):
        if self.action == "delete":
            await self.cog._delete_search(interaction, self.message_id)
            await interaction.response.edit_message(content="Suche wurde gelöscht.", view=None)
            return

        await self.cog._close_search(interaction, self.message_id)
        await interaction.response.edit_message(content="Suche wurde geschlossen.", view=None)

    

class PublicPostView(discord.ui.View):
    def __init__(self, cog: "GruppensucheTest", message_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.message_id = message_id

        join_btn = discord.ui.Button(
            label="Ich bin dabei",
            emoji="✅",
            style=discord.ButtonStyle.success,
            row=0,
            custom_id=f"gst:join:{message_id}",
        )

        leave_btn = discord.ui.Button(
            label="Abmelden",
            emoji="⛔",
            style=discord.ButtonStyle.danger,
            row=0,
            custom_id=f"gst:leave:{message_id}",
        )
        ping_part_btn = discord.ui.Button(
            label="Ping Teilnehmer",
            emoji="📣",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id=f"gst:pingparts:{message_id}",
        )
        ping_part_btn.callback = self._on_ping_participants
        self.add_item(ping_part_btn)

        ping_type_btn = discord.ui.Button(
            label="Ping",
            emoji="🔔",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id=f"gst:pingtype:{message_id}",
        )

        ping_wait_btn = discord.ui.Button(
            label="Ping Warteschlange",
            emoji="🔔",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id=f"gst:pingwait:{message_id}",
        )

        edit_btn = discord.ui.Button(
            label="Bearbeiten",
            emoji="✏️",
            style=discord.ButtonStyle.secondary,
            row=2,
            custom_id=f"gst:edit:{message_id}",
        )

        close_btn = discord.ui.Button(
            label="Schließen",
            emoji="🔒",
            style=discord.ButtonStyle.secondary,
            row=2,
            custom_id=f"gst:close:{message_id}",
        )

        delete_btn = discord.ui.Button(
            label="Löschen",
            emoji="🗑️",
            style=discord.ButtonStyle.secondary,
            row=2,
            custom_id=f"gst:delete:{message_id}",
        )


        join_btn.callback = self._on_join
        leave_btn.callback = self._on_leave
        ping_type_btn.callback = self._on_ping_type
        ping_wait_btn.callback = self._on_ping_wait
        edit_btn.callback = self._on_edit
        close_btn.callback = self._on_close
        delete_btn.callback = self._on_delete

        self.add_item(join_btn)
        self.add_item(leave_btn)
        self.add_item(ping_type_btn)
        self.add_item(ping_wait_btn)
        self.add_item(edit_btn)
        self.add_item(close_btn)
        self.add_item(delete_btn)

    async def _ensure_owner_or_mod(self, interaction: discord.Interaction) -> Optional[dict]:
        data = await self.cog._get_search(self.message_id)
        if data is None:
            await interaction.response.send_message("Diese Suche existiert nicht mehr.", ephemeral=True)
            return None

        owner_id = int(data.get("owner_id", 0))
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if interaction.user.id != owner_id and not (member and _has_mod_rights(member)):
            await interaction.response.send_message("Das darf nur der Ersteller (oder Admin/Offizier).", ephemeral=True)
            return None

        return data

    async def _on_join(self, interaction: discord.Interaction):
        async def _done(i: discord.Interaction, ap_val: str):
            await self.cog._join(i, self.message_id, ap_val)

        await interaction.response.send_modal(JoinApModal(_done))


    async def _on_leave(self, interaction: discord.Interaction):
        await self.cog._leave(interaction, self.message_id)  

    async def _on_ping_participants(self, interaction: discord.Interaction):
        data = await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        await self.cog._ping_participants(interaction, self.message_id, data)
      

    async def _on_ping_type(self, interaction: discord.Interaction):
        data = await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        await self.cog._ping_type(interaction, self.message_id, data)

    async def _on_ping_wait(self, interaction: discord.Interaction):
        data = await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        await self.cog._ping_wait(interaction, self.message_id, data)

    async def _on_edit(self, interaction: discord.Interaction):
        data = await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        await self.cog._start_edit_flow(interaction, self.message_id, data)

    async def _on_close(self, interaction: discord.Interaction):
        data = await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        v = ConfirmView(self.cog, self.message_id, "close", interaction.user.id)
        await interaction.response.send_message(v.text, ephemeral=True, view=v)

    async def _on_delete(self, interaction: discord.Interaction):
        data = await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        v = ConfirmView(self.cog, self.message_id, "delete", interaction.user.id)
        await interaction.response.send_message(v.text, ephemeral=True, view=v)


class ClosedPostView(discord.ui.View):
    def __init__(self, cog: "GruppensucheTest", message_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.message_id = message_id

        open_btn = discord.ui.Button(
            label="Öffnen",
            style=discord.ButtonStyle.success,
            row=0,
            custom_id=f"gst:open:{message_id}",
        )
        open_btn.callback = self._on_open
        self.add_item(open_btn)

    async def _on_open(self, interaction: discord.Interaction):
        data = await self.cog._get_search(self.message_id)
        if data is None:
            await interaction.response.send_message("Diese Suche existiert nicht mehr.", ephemeral=True)
            return

        owner_id = int(data.get("owner_id", 0))
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if interaction.user.id != owner_id and not (member and _has_mod_rights(member)):
            await interaction.response.send_message("Das darf nur der Ersteller (oder Admin/Offizier).", ephemeral=True)
            return

        await self.cog._open_search(interaction, self.message_id)


# =========================
# Cog
# =========================

class GruppensucheTest(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=935771234123, force_registration=True)
        self.config.register_guild(searches={})

        self._sessions: Dict[int, WizardSession] = {}
        self._startup_task: Optional[asyncio.Task] = self.bot.loop.create_task(self._startup_register_views())

    def cog_unload(self):
        if self._startup_task and not self._startup_task.done():
            self._startup_task.cancel()

    async def _startup_register_views(self):
        await self.bot.wait_until_red_ready()
        await self.bot.wait_until_ready()

        await self._register_all_persistent_views()

        try:
            guild_obj = discord.Object(id=GUILD_ID)
            await self.bot.tree.sync(guild=guild_obj)
        except Exception:
            pass


    async def _register_all_persistent_views(self):
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        data = await self.config.guild(guild).searches()
        if not data:
            return

        for mid_str, post in data.items():
            mid = int(mid_str)
            if bool(post.get("is_closed", False)):
                self.bot.add_view(ClosedPostView(self, mid))
            else:
                self.bot.add_view(PublicPostView(self, mid))

    def _expire_session(self, user_id: int):
        if user_id in self._sessions:
            del self._sessions[user_id]

    # =========================
    # Command (Test)
    # =========================

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="gs_test", description="TEST: Starte eine neue Gruppensuche (Wizard).")
    async def gs_test_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        session = WizardSession(
            user_id=interaction.user.id,
            guild_id=interaction.guild_id or 0,
            mode="create",
        )
        session.wizard_interaction = interaction
        self._sessions[interaction.user.id] = session

        # nach defer musst du über followup oder edit_original_response arbeiten:
        view = StartView(self, session)
        await interaction.edit_original_response(embed=view.embed(), view=view)



    # =========================
    # Wizard Senders
    # =========================

    async def _send_start(self, interaction: discord.Interaction, session: WizardSession):
        view = StartView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_day_selection(self, interaction: discord.Interaction, session: WizardSession, back_to: str):
        view = DaySelectView(self, session, back_to=back_to)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_category_specific(self, interaction: discord.Interaction, session: WizardSession):
        if session.category == "muhhelfer":
            await self._send_difficulty(interaction, session)
            return
        if session.category == "spots":
            await self._send_spot_select(interaction, session)
            return
        if session.category == "pilafe":
            await self._send_party_size(interaction, session)
            return
        await interaction.response.edit_message(
            content="Ungültige Auswahl. Bitte neu starten.",
            embed=None,
            view=None,
        )

    async def _send_difficulty(self, interaction: discord.Interaction, session: WizardSession):
        view = DifficultyView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_boss_select(self, interaction: discord.Interaction, session: WizardSession):
        view = BossSelectView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_double_run(self, interaction: discord.Interaction, session: WizardSession):
        """
        Doppelrun-Ansicht anzeigen.
        WICHTIG:
        - Im EDIT-Mode muss die Ansicht auch bei 5/5 erreichbar sein,
          damit man Doppelruns wieder abwählen kann.
        - Im CREATE-Mode nur anzeigen, wenn noch Runs frei sind (<5), sonst weiter.
        """
        total = _sum_runs(session.boss_runs)

        # EDIT: IMMER Doppelrun-View anzeigen (auch bei 5/5),
        # weil man Doppelruns ggf. entfernen will.
        if session.mode == "edit":
            view = DoubleRunView(self, session)
            await self._edit_or_send_ephemeral(interaction, view.embed(), view)
            return

        # CREATE: wenn voll, weiter zum nächsten Step
        if total >= 5:
            await self._send_party_size(interaction, session)
            return

        view = DoubleRunView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)


    async def _send_spot_select(self, interaction: discord.Interaction, session: WizardSession):
        view = SpotSelectView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_party_size(self, interaction: discord.Interaction, session: WizardSession):
        view = PartySizeView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_final_form(self, interaction: discord.Interaction, session: WizardSession):
        defaults = {
            "req_default": _default_req_for(
                {
                    "category": session.category,
                    "difficulty": session.difficulty,
                    "spot_key": session.spot_key,
                }
            )
        }
        try:
            await interaction.response.send_modal(DetailsModal(self, session, defaults=defaults))
        except discord.InteractionResponded:
            await interaction.followup.send_modal(DetailsModal(self, session, defaults=defaults))

    async def _edit_or_send_ephemeral(
        self,
        interaction: discord.Interaction,
        embed: discord.Embed,
        view: discord.ui.View,
    ):
        try:
            # 1) Wenn wir schon geantwortet haben (z.B. Modal submit), können wir nicht mehr response.send/edit nutzen.
            if interaction.response.is_done():
                # Modal-Submit hat oft kein "original response" zum Editieren -> fallback auf followup ephemeral
                try:
                    await interaction.edit_original_response(embed=embed, view=view)
                except Exception:
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                return

            # 2) Wenn es eine Message gibt (typisch bei Button/Select auf einer Ephemeral-Message)
            if interaction.message is not None:
                await interaction.response.edit_message(embed=embed, view=view)
                return

            # 3) Erstes Slash-Command: neue Ephemeral senden
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

        except Exception:
            try:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception:
                return

            
    async def _send_ephemeral_new(self, interaction: discord.Interaction, embed: discord.Embed, view: discord.ui.View):
        """Sendet IMMER eine neue ephemeral Nachricht (niemals edit_message auf einem öffentlichen Post)."""
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception:
            pass
    async def _ping_participants(self, interaction: discord.Interaction, message_id: int, data: dict):
        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass

        if bool(data.get("is_closed", False)):
            return

        guild = interaction.guild
        if guild is None:
            return
        channel = guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            return

        participants = list(data.get("participants") or [])
        if not participants:
            return

        mentions = " ".join(f"<@{uid}>" for uid in participants)
        jump = f"https://discord.com/channels/{guild.id}/{channel.id}/{message_id}"

        day_iso = data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_d = dt.date.fromisoformat(day_iso)
            day_str = _format_day(day_d)
        except Exception:
            day_str = str(day_iso)

        start_text = data.get("start_text") or "—"

        await channel.send(
            f"{mentions}\n📣 Teilnehmer-Ping | Start: {start_text} | {day_str}\n{jump}",
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )

    # =========================
    # Storage
    # =========================

    async def _get_search(self, message_id: int) -> Optional[dict]:
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return None
        searches = await self.config.guild(guild).searches()
        return (searches or {}).get(str(message_id))

    async def _set_search(self, message_id: int, data: dict):
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        async with self.config.guild(guild).searches() as searches:
            searches[str(message_id)] = data

    async def _del_search(self, message_id: int):
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        async with self.config.guild(guild).searches() as searches:
            if str(message_id) in searches:
                del searches[str(message_id)]

    # =========================
    # Public Post Build/Refresh
    # =========================

    async def _build_public_embed(self, guild: discord.Guild, data: dict) -> discord.Embed:
        cat = str(data.get("category", ""))
        owner_id = int(data.get("owner_id", 0))
        owner = guild.get_member(owner_id)

        times_block = (
            f"**Geplante Dauer:** {duration_text}\n"
                    f"**Start:** {start_text}\n\n"
        )


        day_iso = data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_d = dt.date.fromisoformat(day_iso)
            day_str = _format_day(day_d)
        except Exception:
            day_str = str(day_iso)

        max_players = int(data.get("max_players", 2))
        participants: List[int] = list(data.get("participants") or [])
        waitlist: List[int] = list(data.get("waitlist") or [])

        is_closed = bool(data.get("is_closed", False))
        is_full = len(participants) >= max_players

        if is_closed:
            status_line = "🔴 Geschlossen"
        else:
            status_line = "🔴 Voll" if is_full else "🟢 Offen"

        duration_text = data.get("duration_text") or "—"
        start_text = data.get("start_text") or "—"
        notes = data.get("notes") or "—"

        req_text = data.get("req_text") or ""

        # Titel
        if cat == "muhhelfer":
            diff = str(data.get("difficulty", "normal"))
            diff_label = "Schwer" if diff == "schwer" else "Normal"
            title = f"{MUHKUH_EMOJI} Gruppensuche – Muhhelfer ({diff_label})"
        elif cat == "spots":
            spot = str(data.get("spot_key", ""))
            emoji = MIRUMOK_EMOJI if spot == "mirumok" else GYFIN_EMOJI
            title = f"{emoji} Gruppensuche – {_spot_name(spot)}"
        else:
            title = f"{PILAFE_EMOJI} Gruppensuche – Pila Fe"

        e = discord.Embed(title=title)

        # Kopfblock (wie rechts)
        owner_txt = owner.mention if owner else f"<@{owner_id}>"
        owner_ap = data.get("owner_ap")
        owner_display = owner_txt if not owner_ap else f"{owner_txt} ({owner_ap} AP)"


        if cat == "muhhelfer":
            diff = str(data.get("difficulty", "normal"))
            diff_label = "Schwer" if diff == "schwer" else "Normal"
            diff_icon = "🔴" if diff == "schwer" else "🟢"
            req_default = AKVK_SCHWER if diff == "schwer" else AKVK_NORMAL
            req = req_text or req_default

            header = (
                f"**Suchender:** {owner_display}\n"
                f"**Kategorie:** Muhhelfer (LoML Bosse)\n"
                f"**Tag:** {day_str}\n"
                f"**Schwierigkeit:** {diff_icon} {diff_label}\n"
                f"**Anforderung AK/VK:** {req}\n"
                f"**Max. Teilnehmer:** {max_players}\n\n"
            )


            boss_runs = data.get("boss_runs") or {}
            boss_lines = []
            has_double = False
            for key, runs in boss_runs.items():
                name = _boss_name(str(key))
                if int(runs) >= 2:
                    has_double = True
                    boss_lines.append(f"• {name} **(Doppel Run)**")
                else:
                    boss_lines.append(f"• {name}")

            bosses_block = "**Bosse:**\n" + ("\n".join(boss_lines) if boss_lines else "—") + "\n\n"
            if has_double:
                bosses_block += "⚠️ **2. Charakter erforderlich**\n\n"

        
            status_block = f"**Status**\n{status_line}\n\n"

            part_lines = []
            for uid in participants:
                m = guild.get_member(int(uid))
                ap_map = data.get("participant_ap") or {}

                mention = (m.mention if m else f"<@{uid}>")
                ap = ap_map.get(str(uid))
                part_lines.append(f"{mention} ({ap} AP)" if ap else mention)

            participants_block = (
                f"**Teilnehmer ({len(participants)}/{max_players})**\n"
                + ("\n".join([f"• {x}" for x in part_lines]) if part_lines else "—")
                + "\n\n"
            )

            wait_lines = []
            wl_map = data.get("waitlist_ap") or {}
            for uid in waitlist:
                m = guild.get_member(int(uid))
                mention = (m.mention if m else f"<@{uid}>")
                ap = wl_map.get(str(uid))
                wait_lines.append(f"{mention} ({ap} AP)" if ap else mention)

            wait_block = (
                f"**Warteschlange ({len(waitlist)})**\n"
                + ("\n".join([f"• {x}" for x in wait_lines]) if wait_lines else "—")
            )

            e.description = header + bosses_block + times_block + status_block + participants_block + wait_block

        elif cat == "spots":
            spot = str(data.get("spot_key", ""))
            req_default = SPOT_REQ.get(spot, "")
            req = req_text or req_default

            header = (
                f"**Suchender:** {owner_display}\n"
                f"**Kategorie:** Gruppenspots\n"
                f"**Tag:** {day_str}\n"
                f"**Anforderung AK/VK:** {req if req else '—'}\n"
                f"**Max. Teilnehmer:** {max_players}\n\n"
            )


            spot_block = ""
            total_ap = SPOT_TOTAL_AP.get(spot, "")
            if total_ap:
                spot_block += f"**Spot:** {_spot_name(spot)}\n{total_ap}\n\n"
            else:
                spot_block += f"**Spot:** {_spot_name(spot)}\n\n"


            status_block = f"**Status**\n{status_line}\n\n"

            part_lines = []
            for uid in participants:
                m = guild.get_member(int(uid))
                ap_map = data.get("participant_ap") or {}

                mention = (m.mention if m else f"<@{uid}>")
                ap = ap_map.get(str(uid))
                part_lines.append(f"{mention} ({ap} AP)" if ap else mention)
            participants_block = (
                f"**Teilnehmer ({len(participants)}/{max_players})**\n"
                + ("\n".join([f"• {x}" for x in part_lines]) if part_lines else "—")
                + "\n\n"
            )

            wait_lines = []
            wl_map = data.get("waitlist_ap") or {}
            for uid in waitlist:
                m = guild.get_member(int(uid))
                mention = (m.mention if m else f"<@{uid}>")
                ap = wl_map.get(str(uid))
                wait_lines.append(f"{mention} ({ap} AP)" if ap else mention)
            wait_block = (
                f"**Warteschlange ({len(waitlist)})**\n"
                + ("\n".join([f"• {x}" for x in wait_lines]) if wait_lines else "—")
            )

            e.description = header + spot_block + times_block + status_block + participants_block + wait_block

        else:
            amount = data.get("scroll_amount") or "—"
            header = (
                f"**Suchender:** {owner_display}\n"
                f"**Kategorie:** Pila Fe Schriftrollen\n"
                f"**Menge:** {amount}\n"
                f"**Max. Teilnehmer:** {max_players}\n\n"
            )

            status_block = f"**Status**\n{status_line}\n\n"

            part_lines = []
            for uid in participants:
                m = guild.get_member(int(uid))
                ap_map = data.get("participant_ap") or {}

                mention = (m.mention if m else f"<@{uid}>")
                ap = ap_map.get(str(uid))
                part_lines.append(f"{mention} ({ap} AP)" if ap else mention)
            participants_block = (
                f"**Teilnehmer ({len(participants)}/{max_players})**\n"
                + ("\n".join([f"• {x}" for x in part_lines]) if part_lines else "—")
                + "\n\n"
            )

            wait_lines = []
            wl_map = data.get("waitlist_ap") or {}
            for uid in waitlist:
                m = guild.get_member(int(uid))
                mention = (m.mention if m else f"<@{uid}>")
                ap = wl_map.get(str(uid))
                wait_lines.append(f"{mention} ({ap} AP)" if ap else mention)
            wait_block = (
                f"**Warteschlange ({len(waitlist)})**\n"
                + ("\n".join([f"• {x}" for x in wait_lines]) if wait_lines else "—")
            )

            e.description = header + times_block + status_block + participants_block + wait_block

        e.set_footer(text="Klicke auf „Ich bin dabei“, um dich einzutragen.")
        e.timestamp = discord.utils.utcnow()
        return e

    async def _refresh_public_message(self, data: dict):
        guild = self.bot.get_guild(int(data.get("guild_id", 0)))
        if guild is None:
            return
        channel = guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            return

        mid = int(data.get("message_id", 0))
        if mid == 0:
            return

        try:
            msg = await channel.fetch_message(mid)
        except Exception:
            return

        embed = await self._build_public_embed(guild, data)

        if bool(data.get("is_closed", False)):
            view = ClosedPostView(self, mid)
            self.bot.add_view(view)
            await msg.edit(embed=embed, view=view)
            return

        view = PublicPostView(self, mid)
        self.bot.add_view(view)
        await self._apply_dynamic_button_labels(view, data)
        await msg.edit(embed=embed, view=view)


    async def _apply_dynamic_button_labels(self, view: discord.ui.View, data: dict):
        label = "🔔 Rollen-Ping"
        cat = str(data.get("category", ""))

        if cat == "muhhelfer":
            diff = str(data.get("difficulty", "normal"))
            label = f"🔔 Rollen-Ping ({'Schwer' if diff == 'schwer' else 'Normal'})"
        elif cat == "spots":
            spot = str(data.get("spot_key", ""))
            label = f"🔔 Rollen-Ping ({_spot_name(spot)})" if spot else "🔔 Rollen-Ping (Spot)"
        elif cat == "pilafe":
            label = "🔔 Rollen-Ping (Pila Fe)"

        for item in view.children:
            if isinstance(item, discord.ui.Button) and str(item.custom_id or "").startswith("gst:pingtype:"):
                item.label = label
                break


    # =========================
    # Create Public Post
    # =========================

    async def _create_public_post_from_session(self, interaction: discord.Interaction, session: WizardSession):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
            return

        channel = guild.get_channel(TEST_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Zielchannel nicht gefunden.", ephemeral=True)
            return

        day_iso = session.day_date_iso or _now_local().date().isoformat()
        max_players = int(session.max_players or 2)
        owner_id = interaction.user.id

        if session.category == "muhhelfer":
            ping_role_id = ROLE_SCHWER_ID if session.difficulty == "schwer" else ROLE_NORMAL_ID
        elif session.category == "spots":
            ping_role_id = SPOT_PING_ROLE.get(session.spot_key or "", TEST_ROLE_ID)
        else:
            ping_role_id = ROLE_PILAFE_ID

        data = {
            "guild_id": guild.id,
            "channel_id": channel.id,
            "message_id": 0,
            "owner_id": owner_id,
            "category": session.category,
            "day_date_iso": day_iso,
            "max_players": max_players,
            "participants": [owner_id],
            "waitlist": [],
            "is_closed": False,
            "ping_role_id": int(ping_role_id),
            "created_at": int(_now_local().timestamp()),
            "updated_at": int(_now_local().timestamp()),
            "ping_cd": {},
            "duration_text": session.duration_text,
            "start_text": session.start_text,
            "req_text": session.req_text,
            "notes": session.notes,
            "owner_ap": session.own_ap,
            "participant_ap": {str(owner_id): session.own_ap or ""},
            "waitlist_ap": {},
        }

        if session.category == "muhhelfer":
            data["difficulty"] = session.difficulty or "normal"
            data["boss_runs"] = dict(session.boss_runs)
        if session.category == "spots":
            data["spot_key"] = session.spot_key
        if session.category == "pilafe":
            data["scroll_amount"] = session.scroll_amount

        embed = await self._build_public_embed(guild, data)

        content = f"<@&{ping_role_id}>"
        allowed = discord.AllowedMentions(roles=True, users=False, everyone=False)

        msg = await channel.send(content=content, embed=embed, allowed_mentions=allowed)
        data["message_id"] = msg.id

        view = PublicPostView(self, msg.id)
        await msg.edit(view=view)
        self.bot.add_view(view)

        async with self.config.guild(guild).searches() as searches:
            searches[str(msg.id)] = data

        self._expire_session(session.user_id)

        # Wizard-Ephemeral sauber "abschließen" (immer über wizard_interaction)
        try:
            if session.wizard_interaction:
                await session.wizard_interaction.edit_original_response(
                    content="✅ Gruppensuche erstellt.",
                    embed=None,
                    view=None,
                )
        except Exception:
            pass



    # =========================
    # Public Actions
    # =========================

    async def _join(self, interaction: discord.Interaction, message_id: int, ap_val: str):

        data = await self._get_search(message_id)
        if data is None:
            await interaction.response.send_message("Diese Suche existiert nicht mehr.", ephemeral=True)
            return
        if bool(data.get("is_closed", False)):
            await interaction.response.send_message("Diese Suche ist geschlossen.", ephemeral=True)
            return

        uid = interaction.user.id
        participants: List[int] = list(data.get("participants") or [])
        waitlist: List[int] = list(data.get("waitlist") or [])
        max_players = int(data.get("max_players", 2))

        if uid in participants:
            await interaction.response.send_message("Du bist bereits Teilnehmer.", ephemeral=True)
            return
        if uid in waitlist:
            await interaction.response.send_message("Du bist bereits in der Warteschlange.", ephemeral=True)
            return

        if len(participants) < max_players:
            participants.append(uid)
            data["participants"] = participants
            data["updated_at"] = int(_now_local().timestamp())
            ap_map = data.get("participant_ap") or {}
            ap_map[str(uid)] = ap_val
            data["participant_ap"] = ap_map
            await self._set_search(message_id, data)
            await self._refresh_public_message(data)
            await interaction.response.send_message("✅ Du bist jetzt Teilnehmer.", ephemeral=True)
            return

        waitlist.append(uid)
        data["waitlist"] = waitlist
        data["updated_at"] = int(_now_local().timestamp())
        wl_map = data.get("waitlist_ap") or {}
        wl_map[str(uid)] = ap_val
        data["waitlist_ap"] = wl_map
        await self._set_search(message_id, data)
        await self._refresh_public_message(data)
        await interaction.response.send_message("ℹ️ Gruppe ist voll. Du bist in der Warteschlange.", ephemeral=True)

    async def _leave(self, interaction: discord.Interaction, message_id: int):
        data = await self._get_search(message_id)
        if data is None:
            await interaction.response.send_message("Diese Suche existiert nicht mehr.", ephemeral=True)
            return

        uid = interaction.user.id
        participants: List[int] = list(data.get("participants") or [])
        waitlist: List[int] = list(data.get("waitlist") or [])
        max_players = int(data.get("max_players", 2))

        was_participant = uid in participants
        was_wait = uid in waitlist

        if not was_participant and not was_wait:
            await interaction.response.send_message("Du bist nicht eingetragen.", ephemeral=True)
            return

        if was_participant:
            participants.remove(uid)
        if was_wait:
            waitlist.remove(uid)

        # AP Maps aufräumen
        ap_map = data.get("participant_ap") or {}
        wl_map = data.get("waitlist_ap") or {}

        if was_participant:
            ap_map.pop(str(uid), None)
        if was_wait:
            wl_map.pop(str(uid), None)

        data["participant_ap"] = ap_map
        data["waitlist_ap"] = wl_map
    

        promoted_id: Optional[int] = None
        if was_participant and len(participants) < max_players and waitlist:
            promoted_id = int(waitlist.pop(0))
            participants.append(promoted_id)
            wl_map = data.get("waitlist_ap") or {}
            ap_map = data.get("participant_ap") or {}

            promoted_ap = wl_map.pop(str(promoted_id), None)
            if promoted_ap:
                ap_map[str(promoted_id)] = promoted_ap

            data["waitlist_ap"] = wl_map
            data["participant_ap"] = ap_map


        data["participants"] = participants
        data["waitlist"] = waitlist
        data["updated_at"] = int(_now_local().timestamp())
        await self._set_search(message_id, data)
        await self._refresh_public_message(data)

        await interaction.response.send_message("✅ Du wurdest abgemeldet.", ephemeral=True)

        if promoted_id:
            await self._notify_promotion(data, promoted_id)

    async def _notify_promotion(self, data: dict, promoted_id: int):
        guild = self.bot.get_guild(int(data.get("guild_id", 0)))
        if guild is None:
            return
        channel = guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            return

        owner_id = int(data.get("owner_id", 0))
        mid = int(data.get("message_id", 0))
        jump = f"https://discord.com/channels/{guild.id}/{channel.id}/{mid}"

        day_iso = data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_d = dt.date.fromisoformat(day_iso)
            day_str = _format_day(day_d)
        except Exception:
            day_str = str(day_iso)

        start_text = data.get("start_text") or "—"

        owner_member = guild.get_member(owner_id)
        promoted_member = guild.get_member(promoted_id)

        owner_dm_ok = False
        promoted_dm_ok = False

        if owner_member:
            try:
                await owner_member.send(
                    f"🔔 **Warteschlange aufgerückt**\n"
                    f"In deiner Suche ({day_str} / {start_text}) ist "
                    f"{promoted_member.mention if promoted_member else f'<@{promoted_id}>'} nachgerückt.\n"
                    f"Link: {jump}"
                )
                owner_dm_ok = True
            except Exception:
                owner_dm_ok = False

        if promoted_member:
            try:
                await promoted_member.send(
                    f"❗ **Ein Teilnehmer hat abgesagt.**\n"
                    f"Du bist bei der Suche nachgerückt und jetzt **Teilnehmer**.\n\n"
                    f"⏰ Start: {day_str} / {start_text}\n"
                    f"Link: {jump}"
                )
                promoted_dm_ok = True
            except Exception:
                promoted_dm_ok = False

        if owner_dm_ok and promoted_dm_ok:
            return

        try:
            await channel.send(
                content=f"{promoted_member.mention if promoted_member else f'<@{promoted_id}>'} ist nachgerückt! "
                        f"({day_str} / {start_text})\n{jump}",
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
        except Exception:
            return

    async def _ping_type(self, interaction: discord.Interaction, message_id: int, data: dict):
        if bool(data.get("is_closed", False)):
            await interaction.response.send_message("Diese Suche ist geschlossen.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass

        cd = data.get("ping_cd") or {}
        now_ts = int(_now_local().timestamp())
        last = int(cd.get("type", 0))
        if now_ts - last < PING_COOLDOWN_SECONDS:
            await interaction.followup.send("Ping-Cooldown aktiv.", ephemeral=True)
            return


        cd["type"] = now_ts
        data["ping_cd"] = cd
        data["updated_at"] = now_ts
        await self._set_search(message_id, data)

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Nur auf Servern nutzbar.", ephemeral=True)
            return

        channel = guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Channel nicht gefunden.", ephemeral=True)
            return

        ping_role_id = int(data.get("ping_role_id", TEST_ROLE_ID))
        max_players = int(data.get("max_players", 2))
        participants = list(data.get("participants") or [])
        free = max(0, max_players - len(participants))

        day_iso = data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_d = dt.date.fromisoformat(day_iso)
            day_str = _format_day(day_d)
        except Exception:
            day_str = str(day_iso)

        start_text = data.get("start_text") or "—"
        jump = f"https://discord.com/channels/{guild.id}/{channel.id}/{message_id}"

        txt = f"<@&{ping_role_id}> | {day_str} | Start: {start_text} | Frei: {free}\n{jump}"
        await channel.send(txt, allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False))

    async def _ping_wait(self, interaction: discord.Interaction, message_id: int, data: dict):
        if bool(data.get("is_closed", False)):
            await interaction.response.send_message("Diese Suche ist geschlossen.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
        except discord.InteractionResponded:
            pass

        cd = data.get("ping_cd") or {}
        now_ts = int(_now_local().timestamp())
        last = int(cd.get("wait", 0))
        if now_ts - last < PING_COOLDOWN_SECONDS:
            await interaction.followup.send("Ping-Cooldown aktiv.", ephemeral=True)
            return


        cd["wait"] = now_ts
        data["ping_cd"] = cd
        data["updated_at"] = now_ts
        await self._set_search(message_id, data)

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Nur auf Servern nutzbar.", ephemeral=True)
            return

        channel = guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Channel nicht gefunden.", ephemeral=True)
            return

        day_iso = data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_d = dt.date.fromisoformat(day_iso)
            day_str = _format_day(day_d)
        except Exception:
            day_str = str(day_iso)

        start_text = data.get("start_text") or "—"
        jump = f"https://discord.com/channels/{guild.id}/{channel.id}/{message_id}"

        txt = f"🔔 Ping Warteschlange | {day_str} | Start: {start_text}\n{jump}"
        await channel.send(txt, allowed_mentions=discord.AllowedMentions.none())

    async def _close_search(self, interaction: discord.Interaction, message_id: int):
        data = await self._get_search(message_id)
        if data is None:
            return
        data["is_closed"] = True
        data["updated_at"] = int(_now_local().timestamp())
        await self._set_search(message_id, data)
        await self._refresh_public_message(data)

    async def _open_search(self, interaction: discord.Interaction, message_id: int):
        data = await self._get_search(message_id)
        if data is None:
            await interaction.response.send_message("Diese Suche existiert nicht mehr.", ephemeral=True)
            return
        data["is_closed"] = False
        data["updated_at"] = int(_now_local().timestamp())
        await self._set_search(message_id, data)
        await self._refresh_public_message(data)
        await interaction.response.send_message("✅ Suche wieder geöffnet.", ephemeral=True)

    async def _delete_search(self, interaction: discord.Interaction, message_id: int):
        data = await self._get_search(message_id)
        if data is None:
            return

        guild = interaction.guild
        if guild is None:
            await self._del_search(message_id)
            return

        channel = guild.get_channel(int(data.get("channel_id", 0)))
        if isinstance(channel, discord.TextChannel):
            try:
                msg = await channel.fetch_message(int(data.get("message_id", 0)))
                await msg.delete()
            except Exception:
                pass

        await self._del_search(message_id)

    # =========================
    # Edit Flow
    # =========================

    async def _start_edit_flow(self, interaction: discord.Interaction, message_id: int, data: dict):
        session = WizardSession(
            user_id=interaction.user.id,
            guild_id=interaction.guild_id or 0,
            mode="edit",
            edit_message_id=message_id,
            category=str(data.get("category")),
            day_date_iso=str(data.get("day_date_iso")),
            difficulty=str(data.get("difficulty")) if data.get("category") == "muhhelfer" else None,
            boss_runs=dict(data.get("boss_runs") or {}),
            spot_key=str(data.get("spot_key")) if data.get("category") == "spots" else None,
            max_players=int(data.get("max_players", 2)),
            scroll_amount=str(data.get("scroll_amount")) if data.get("category") == "pilafe" else None,
            duration_text=data.get("duration_text"),
            start_text=data.get("start_text"),
            req_text=data.get("req_text"),
            notes=data.get("notes"),
        )
        session.wizard_interaction = interaction
        self._sessions[interaction.user.id] = session

        # WICHTIG: Edit-Menü darf niemals den öffentlichen Post überschreiben.
        view = EditMenuView(self, session, data)
        await self._send_ephemeral_new(interaction, view.embed(), view)


    async def _send_edit_menu(self, interaction: discord.Interaction, session: WizardSession):
        if not session.edit_message_id:
            await interaction.response.edit_message(
                content="Edit-Session ungültig.",
                embed=None,
                view=None,
            )
            return

        data = await self._get_search(session.edit_message_id)
        if data is None:
            await interaction.response.send_message("Diese Suche existiert nicht mehr.", ephemeral=True)
            return

        view = EditMenuView(self, session, data)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _apply_edit_day(self, interaction: discord.Interaction, session: WizardSession):
        if not session.edit_message_id:
            return
        data = await self._get_search(session.edit_message_id)
        if data is None:
            await interaction.response.send_message("Diese Suche existiert nicht mehr.", ephemeral=True)
            return

        data["day_date_iso"] = session.day_date_iso
        data["updated_at"] = int(_now_local().timestamp())
        await self._set_search(session.edit_message_id, data)
        await self._refresh_public_message(data)

        await self._send_edit_menu(interaction, session)

    async def _apply_edit_max_players(self, interaction: discord.Interaction, session: WizardSession):
        if not session.edit_message_id:
            return
        data = await self._get_search(session.edit_message_id)
        if data is None:
            await interaction.response.send_message("Diese Suche existiert nicht mehr.", ephemeral=True)
            return

        new_max = int(session.max_players or int(data.get("max_players", 2)))
        mn, mx = _allowed_party_range(str(data.get("category", "")))
        if new_max < mn or new_max > mx:
            await interaction.response.send_message("Ungültige Teilnehmerzahl.", ephemeral=True)
            return

        data["max_players"] = new_max

        participants = list(data.get("participants") or [])
        waitlist = list(data.get("waitlist") or [])

        ap_map = data.get("participant_ap") or {}
        wl_map = data.get("waitlist_ap") or {}

        while len(participants) < new_max and waitlist:
            pid = int(waitlist.pop(0))
            participants.append(pid)

            promoted_ap = wl_map.pop(str(pid), None)
            if promoted_ap:
                ap_map[str(pid)] = promoted_ap

        data["participant_ap"] = ap_map
        data["waitlist_ap"] = wl_map


        data["participants"] = participants
        data["waitlist"] = waitlist
        data["updated_at"] = int(_now_local().timestamp())
        await self._set_search(session.edit_message_id, data)
        await self._refresh_public_message(data)

        await self._send_edit_menu(interaction, session)

    async def _apply_edit_details(self, interaction: discord.Interaction, session: WizardSession):
        if not session.edit_message_id:
            return
        data = await self._get_search(session.edit_message_id)
        if data is None:
            await interaction.response.send_message("Diese Suche existiert nicht mehr.", ephemeral=True)
            return

        if data.get("category") == "pilafe":
            if session.scroll_amount is not None:
                data["scroll_amount"] = session.scroll_amount

        data["duration_text"] = session.duration_text
        data["start_text"] = session.start_text
        data["req_text"] = session.req_text
        data["notes"] = session.notes
        data["updated_at"] = int(_now_local().timestamp())

        await self._set_search(session.edit_message_id, data)
        await self._refresh_public_message(data)

        await self._send_edit_menu(interaction, session)

    async def _apply_edit_bosses(self, interaction: discord.Interaction, session: WizardSession):
        if not session.edit_message_id:
            return
        data = await self._get_search(session.edit_message_id)
        if data is None:
            await interaction.response.send_message("Diese Suche existiert nicht mehr.", ephemeral=True)
            return

        if data.get("category") != "muhhelfer":
            await interaction.response.send_message("Bossbearbeitung ist nur für Muhhelfer.", ephemeral=True)
            return

        if not session.boss_runs:
            await interaction.response.send_message("Bitte mindestens 1 Boss auswählen.", ephemeral=True)
            return

        data["boss_runs"] = dict(session.boss_runs)
        data["updated_at"] = int(_now_local().timestamp())
        await self._set_search(session.edit_message_id, data)
        await self._refresh_public_message(data)

        await self._send_edit_menu(interaction, session)
