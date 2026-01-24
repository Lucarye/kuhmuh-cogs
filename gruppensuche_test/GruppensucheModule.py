from __future__ import annotations
import re
from typing import Callable, Union, Any
from zoneinfo import ZoneInfo
from discord import app_commands # pyright: ignore[reportMissingImports]

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from discord import PartialEmoji # pyright: ignore[reportMissingImports]

import discord # pyright: ignore[reportMissingImports]
from redbot.core import commands, Config # pyright: ignore[reportMissingImports]


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
ROLE_ATORAXXION_ID = 1463872163516911808

ADMIN_ROLE_ID: Optional[int] = 1452050940952838214
OFFIZIER_ROLE_ID: Optional[int] = 1198652039312453723

PING_COOLDOWN_SECONDS = 600
PARTICIPANT_PING_COOLDOWN_SECONDS = 60
WIZARD_TIMEOUT_SECONDS = 300  # 5 Minuten (oder 600 = 10 Minuten)


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
# Feature Flags
# =========================
FEATURE_SPOTS_GYFIN = True          # (falls du mal einzelne Spots togglen willst)
FEATURE_SPOTS_MIRUMOK = True

FEATURE_ALTAR = False              # <- vorbereitet, aber nicht im Menü
FEATURE_ATORAXXION = False         # <- vorbereitet, aber nicht im Menü

FEATURE_POST_IN_CURRENT_CHANNEL = True  # statt TEST_CHANNEL_ID


# =========================
# Wizard UI Schema (global)
# =========================


def _muh_title(session: "WizardSession") -> str:
    diff_label = "Schwer" if session.difficulty == "schwer" else "Normal"
    return f"{MUHKUH_EMOJI} Gruppensuche – Muhhelfer ({diff_label})"


def _spots_title(session: "WizardSession") -> str:
    spot = session.spot_key or ""
    emoji = MIRUMOK_EMOJI if spot == "mirumok" else GYFIN_EMOJI
    return f"{emoji} Gruppensuche – {_spot_name(spot) if spot else 'Gruppenspots'}"


def _pilafe_title(session: "WizardSession") -> str:
    return f"{PILAFE_EMOJI} Gruppensuche – Pila Fe"


WIZARD_UI = {
    "muhhelfer": {
        "party_min": 2,
        "party_max": 5,
        "party_text": "Wähle die maximale Teilnehmerzahl **2–5**.",
        "title_fn": _muh_title,
    },
    "spots": {
        "party_min": 2,
        "party_max": 3,
        "party_text": "Wähle die maximale Teilnehmerzahl **2–3**.",
        "title_fn": _spots_title,
    },
    "pilafe": {
        "party_min": 2,
        "party_max": 5,
        "party_text": "Wähle die maximale Teilnehmerzahl **2–5**.",
        "title_fn": _pilafe_title,
    },
}


def _ui_for(category: str) -> dict:
    return WIZARD_UI.get(category or "", {
        "party_min": 2,
        "party_max": 5,
        "party_text": "Wähle die maximale Teilnehmerzahl.",
        "title_fn": lambda s: "Gruppensuche",
    })


# =========================
# Helpers
# =========================

WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _format_remaining(seconds: int) -> str:
    seconds = int(seconds)

    if seconds <= 0:
        seconds = abs(seconds)
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, sec = divmod(rem, 60)
        if days > 0:
            return f"vor {days} Tagen"
        if hours > 0:
            return f"vor {hours}h {minutes:02d}m"
        if minutes > 0:
            return f"vor {minutes}m {sec:02d}s"
        return f"vor {sec}s"

    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, sec = divmod(rem, 60)
    if days > 0:
        return f"in {days} Tagen"
    if hours > 0:
        return f"in {hours}h {minutes:02d}m"
    if minutes > 0:
        return f"in {minutes}m {sec:02d}s"
    return f"in {sec}s"


def _party_size_help_text(min_n: int, max_n: int) -> str:
    return (
        f"Wähle die maximale Teilnehmerzahl **{min_n}–{max_n}** (inkl. dir).\n"
        f"Beispiel: **{max_n}** = du + **{max_n - 1}** weitere."
    )


class BackTarget:
    START = "start"          # Kategorieauswahl
    DIFFICULTY = "difficulty"
    SPOT = "spot"
    BOSSES = "bosses"
    DOUBLE = "double"
    DAY = "day"
    EDIT_MENU = "edit_menu"

class Step:
    START = "start"
    DIFFICULTY = "difficulty"
    BOSSES = "bosses"
    DOUBLE = "double"
    SPOT = "spot"
    DAY = "day"
    PARTY = "party"
    DETAILS = "details"
    EDIT_MENU = "edit_menu"


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


BERLIN = ZoneInfo("Europe/Berlin")


def _now_local() -> dt.datetime:
    return dt.datetime.now(BERLIN)


BackSpec = Union[
    str,                                  # z.B. BackTarget.START
    # z.B. (BackTarget.DAY, {"back_target": BackTarget.SPOT})
    tuple[str, dict],
    # dynamisch je nach Session
    Callable[["WizardSession"], Union[str, tuple[str, dict]]],
]


def build_back_button(
    label: str,
    target: BackSpec,
    view: "WizardBaseView",
    *,
    row: int = 2,
) -> discord.ui.Button:
    btn = discord.ui.Button(
        label=f"Zurück ({label})",
        style=discord.ButtonStyle.secondary,
        row=row,
    )

    async def _cb(interaction: discord.Interaction):
        if interaction.user.id != view.session.user_id:
            await interaction.response.defer()
            return

        # --- target auflösen (statisch / tuple / callable) ---
        spec: Any = target(view.session) if callable(target) else target

        if isinstance(spec, tuple):
            resolved_target, kwargs = spec
            kwargs = dict(kwargs or {})
        else:
            resolved_target, kwargs = spec, {}

        # --- Edit-Mode: Back IMMER ins Edit-Menü (keine Mischlogik mehr) ---
        if view.session.mode == "edit":
            resolved_target = BackTarget.EDIT_MENU
            kwargs = {}

        await view.cog._go_back(interaction, view.session, resolved_target, **kwargs)

    btn.callback = _cb
    return btn


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


_TIME_RE = re.compile(
    r"(?P<h>\d{1,2})(?:[:\.,](?P<m>\d{2}))?\s*(?:uhr)?", re.IGNORECASE)


def _parse_time_token(token: str) -> Optional[tuple[int, int]]:
    token = (token or "").strip().lower()
    m = _TIME_RE.search(token)
    if not m:
        return None
    h = int(m.group("h"))
    mi = int(m.group("m") or 0)
    if h == 24 and mi == 0:
        # 24:00 -> wir geben (0,0) zurück, aber markieren es später als "next day end"
        return (24, 0)
    if h < 0 or h > 23 or mi < 0 or mi > 59:
        return None
    return (h, mi)


def _extract_start_time_from_start_text(start_text: str) -> Optional[tuple[int, int]]:
    t = (start_text or "").strip().lower()
    if not t:
        return None

    # Schnellfilter: "jetzt" etc.
    if any(x in t for x in ["jetzt", "sofort"]):
        now = _now_local()
        return (now.hour, now.minute)

    # Fenster: zwischen X und Y / X-Y
    if "zwischen" in t and "und" in t:
        parts = t.replace("zwischen", "").split("und")
        if len(parts) >= 2:
            p1 = _parse_time_token(parts[0])
            return p1

    if "-" in t:
        left = t.split("-", 1)[0]
        p1 = _parse_time_token(left)
        return p1

    # Fixzeit
    return _parse_time_token(t)


def _build_start_dt_if_possible(data: dict) -> Optional[dt.datetime]:
    day_iso = str(data.get("day_date_iso") or "").strip()
    if not day_iso:
        return None
    try:
        day_d = dt.date.fromisoformat(day_iso)
    except Exception:
        return None

    start_text = str(data.get("start_text") or "")
    hm = _extract_start_time_from_start_text(start_text)
    if not hm:
        return None

    h, m = hm

    # ✅ gleiche Zeitzone wie _now_local()
    tz = BERLIN

    # 24:00 → nächster Tag 00:00 (lokale Zeit)
    if h == 24 and m == 0:
        return dt.datetime.combine(
            day_d + dt.timedelta(days=1),
            dt.time(0, 0),
            tzinfo=tz,
        )

    return dt.datetime.combine(
        day_d,
        dt.time(h, m),
        tzinfo=tz,
    )


def _has_mod_rights(member: discord.Member) -> bool:
    role_ids = {r.id for r in member.roles}
    if ADMIN_ROLE_ID and ADMIN_ROLE_ID in role_ids:
        return True
    if OFFIZIER_ROLE_ID and OFFIZIER_ROLE_ID in role_ids:
        return True
    return False


def _is_admin_only(member: discord.Member) -> bool:
    # NUR Admin-Rolle
    if not ADMIN_ROLE_ID:
        return False
    return ADMIN_ROLE_ID in {r.id for r in member.roles}


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
    ui = _ui_for(category)
    return (int(ui["party_min"]), int(ui["party_max"]))


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

        current_amount = self.defaults.get(
            "scroll_amount") if is_pilafe else ""
        current_duration = self.defaults.get("duration_text") or ""
        current_start = self.defaults.get("start_text") or ""
        current_req = self.defaults.get(
            "req_text") or self.defaults.get("req_default") or ""
        current_notes = self.defaults.get("notes") or ""

        self.scroll_amount = discord.ui.TextInput(
            label="Menge an Schriftrollen",
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
            # PilaFe: Modal max 5 Felder -> req_text NICHT anzeigen
            self.add_item(self.scroll_amount)
            self.add_item(self.duration_text)
            self.add_item(self.start_text)
            self.add_item(self.notes)
        else:
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

        own_ap_val = str(self.own_ap.value).strip(
        ) if hasattr(self, "own_ap") else ""
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
            self.session.scroll_amount = val if val else (
                self.defaults.get("scroll_amount") or None)

        self.session.duration_text = str(
            self.duration_text.value).strip() or None
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
    def __init__(self, cog: "GruppensucheTest", session: WizardSession, timeout_seconds: int = WIZARD_TIMEOUT_SECONDS):
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
            discord.SelectOption(
                label="Muhhelfer (LoML Bosse)",
                value="muhhelfer",
                emoji=MUHKUH_EMOJI,
            ),
            discord.SelectOption(
                label="Gruppenspots (Mirumok / Gyfin)",
                value="spots",
                emoji=CHEER_EMOJI,
            ),
            discord.SelectOption(
                label="Pila Fe Schriftrollen",
                value="pilafe",
                emoji=PILAFE_EMOJI,
            ),
        ]

        if FEATURE_ALTAR:
            options.append(discord.SelectOption(
                label="Altar des Blutes (Tower Defense)",
                value="altar",
                emoji="🩸",
            ))

        if FEATURE_ATORAXXION:
            options.append(discord.SelectOption(
                label="Atoraxxion (Dungeon)",
                value="atoraxxion",
                emoji="🏛️",
            ))

        super().__init__(
            placeholder="Wähle eine Kategorie...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.host_view = host_view

    async def callback(self, interaction: discord.Interaction):
        # nur der Ersteller darf bedienen
        if interaction.user.id != self.host_view.session.user_id:
            await interaction.response.send_message("Das kannst nur du bedienen.", ephemeral=True)
            return

        picked = str(self.values[0])
        self.host_view.session.category = picked

        # optional: Felder resetten, wenn Kategorie gewechselt wird
        self.host_view.session.difficulty = None
        self.host_view.session.boss_runs = {}
        self.host_view.session.spot_key = None
        self.host_view.session.scroll_amount = None
        self.host_view.session.day_date_iso = None
        self.host_view.session.max_players = None

        # und weiter im Flow (zentraler Router)
        await self.host_view.cog._goto_next(interaction, self.host_view.session, Step.START)



class StartView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(cog, session)
        self.add_item(StartSelect(self))

    def embed(self) -> discord.Embed:
        return discord.Embed(
            title=f"{MUHKUH_EMOJI} Gruppensuche erstellen",
            description=(
                "Wähle, wofür du eine Gruppe suchst.\n\n"
                "• **Muhhelfer** (LoML Bosse)\n"
                "• **Gruppenspots** (Mirumok / Gyfin)\n"
                "• **Pila Fe** Schriftrollen\n"
                + ("• **Altar des Blutes**\n" if FEATURE_ALTAR else "")
                + ("• **Atoraxxion**\n" if FEATURE_ATORAXXION else "")
                + "\nNach der Auswahl kannst du Details wie **Menge**, **Geplante Dauer** und **Startzeit** angeben."
            ),
        )


class DaySelectView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(cog, session)

        # ✅ BackTarget wird IMMER zentral berechnet
        self.back_target = cog._resolve_back_target_for_day(session)

        self._add_day_buttons()

        label_map = {
            BackTarget.START: "Kategorie",
            BackTarget.DIFFICULTY: "Schwierigkeit",
            BackTarget.BOSSES: "Bosse",
            BackTarget.SPOT: "Spot",
            BackTarget.DOUBLE: "Doppelrun",
            BackTarget.EDIT_MENU: "Bearbeiten",
        }
        back_label = label_map.get(self.back_target, "Zurück")
        self.add_item(build_back_button(back_label, self.back_target, self))


    def embed(self) -> discord.Embed:
        return discord.Embed(
            title=f"{MUHKUH_EMOJI} Tag",
            description=(
                "Wähle den Tag, für den die Suche gedacht ist.\n"
                "Du kannst bis zu **7 Tage im Voraus** planen."
            ),
        )

    def _add_day_buttons(self):
        self._day_buttons: Dict[str, discord.ui.Button] = {}

        today = _now_local().date()

        # ✅ Heute vorauswählen (falls noch nichts gesetzt)
        if not self.session.day_date_iso:
            self.session.day_date_iso = today.isoformat()

        days = [today + dt.timedelta(days=i) for i in range(7)]

        for idx, day in enumerate(days):
            iso = day.isoformat()

            # Label: Heute ist länger
            if idx == 0:
                label = f"Heute ({day.day:02d}.{day.month:02d}.)"
            else:
                label = _format_day(day)

            # Layout:
            # Row 0: Heute + 2 weitere = 3 Buttons
            # Row 1: Rest = 4 Buttons
            row = 0 if idx <= 2 else 1

            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.primary,  # 👈 standard: blau
                row=row,
            )

            async def _cb(interaction: discord.Interaction, iso_val=iso):
                if interaction.user.id != self.session.user_id:
                    await interaction.response.defer()
                    return

                # Auswahl setzen + Styles updaten
                self.session.day_date_iso = iso_val
                self._refresh_day_styles()

                if self.session.mode == "edit":
                    # optional: sofort visuell updaten
                    await interaction.response.edit_message(embed=self.embed(), view=self)
                    await self.cog._apply_edit_day(interaction, self.session)
                    return

                # create-mode: sofort visuell updaten, dann weiter
                await interaction.response.edit_message(embed=self.embed(), view=self)
                await self.cog._goto_next(interaction, self.session, Step.DAY)


            btn.callback = _cb
            self._day_buttons[iso] = btn
            self.add_item(btn)

        # initial styles setzen (Heute = grün, Rest = blau)
        self._refresh_day_styles()

    def _refresh_day_styles(self):
        selected = str(self.session.day_date_iso or "")
        for iso, btn in self._day_buttons.items():
            # ✅ ausgewählter Tag grün, sonst blau
            btn.style = discord.ButtonStyle.success if iso == selected else discord.ButtonStyle.primary


class DifficultyView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(cog, session)

        normal_btn = discord.ui.Button(
            label="Normal", style=discord.ButtonStyle.primary, row=0)
        schwer_btn = discord.ui.Button(
            label="Schwer", style=discord.ButtonStyle.danger, row=0)
        normal_btn.callback = self._pick_normal
        schwer_btn.callback = self._pick_schwer
        self.add_item(normal_btn)
        self.add_item(schwer_btn)

        self.add_item(build_back_button(
            "Kategorie", BackTarget.START, self, row=1))

    async def _pick_normal(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        self.session.difficulty = "normal"
        await self.cog._goto_next(interaction, self.session, Step.DIFFICULTY)

    async def _pick_schwer(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        self.session.difficulty = "schwer"
        await self.cog._goto_next(interaction, self.session, Step.DIFFICULTY)

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
            btn = discord.ui.Button(
                label=name, style=discord.ButtonStyle.secondary, row=row)
            btn.callback = self._make_toggle_boss(key)
            self._boss_buttons[key] = btn
            self.add_item(btn)

        self.add_item(build_back_button("Schwierigkeit", BackTarget.DIFFICULTY, self, row=2))

        next_btn = discord.ui.Button(
            label="Weiter", style=discord.ButtonStyle.success, row=2)
        next_btn.callback = self._next
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
        # - Wenn Doppelruns existieren: IMMER DOUBLE anzeigen (zum Abwählen)
        # - Wenn 5/5 und keine Doppelruns: direkt speichern
        # - Sonst: DOUBLE anzeigen
        if self.session.mode == "edit":
            if has_double:
                await self.cog._send_double_run(interaction, self.session)
                return

            if total >= 5:
                await self.cog._apply_edit_bosses(interaction, self.session)
                return

            await self.cog._send_double_run(interaction, self.session)
            return

        # ✅ CREATE-MODE: ab hier nur noch Router
        await self.cog._goto_next(interaction, self.session, Step.BOSSES)


    def embed(self) -> discord.Embed:
        diff = "Schwer" if self.session.difficulty == "schwer" else "Normal"
        req = AKVK_SCHWER if self.session.difficulty == "schwer" else AKVK_NORMAL
        return discord.Embed(
            title=f"{MUHKUH_EMOJI} Muhhelfer – Bossauswahl",
            description=(
                f"**Schwierigkeit:** {diff}\n"
                f"**Empfohlen mind. AK/VK:** {req}\n\n"
                "Wähle bis zu **5 Runs**.\n"
                "Optional: **Doppel-Runs** können im nächsten Schritt markiert werden.\n"
                "Beispiel: **3 Runs** auswählen, davon **2** im nächsten Schritt als Doppelrun markieren.\n"
                "Doppelrun = Boss wird **2×** gelaufen (⚠️ **2. Charakter erforderlich**).\n\n"
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

        self.add_item(build_back_button("Bosse", BackTarget.BOSSES, self, row=2))

        next_label = "Speichern" if session.mode == "edit" else "Weiter"
        next_btn = discord.ui.Button(label=next_label, style=discord.ButtonStyle.success, row=2)
        next_btn.callback = self._next
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
                    await interaction.response.send_message(
                        "Keine freien Runs mehr. Maximal 5 Runs insgesamt.",
                        ephemeral=True,
                    )
                    return
                self.session.boss_runs[key] = 2

            self._refresh_styles()
            await interaction.response.edit_message(embed=self.embed(), view=self)

        return _cb

    async def _next(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        # Edit bleibt eine Aktion (speichern)
        if self.session.mode == "edit":
            await self.cog._apply_edit_bosses(interaction, self.session)
            return

        # ✅ Create: zentraler Flow
        await self.cog._goto_next(interaction, self.session, Step.DOUBLE)


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

        miru_btn = discord.ui.Button(
            label="Mirumok", style=discord.ButtonStyle.primary, row=0)
        gyfin_btn = discord.ui.Button(
            label="Gyfin", style=discord.ButtonStyle.primary, row=0)
        miru_btn.callback = self._pick_miru
        gyfin_btn.callback = self._pick_gyfin
        self.add_item(miru_btn)
        self.add_item(gyfin_btn)

        self.add_item(build_back_button(
            "Kategorie", BackTarget.START, self, row=1))

    async def _pick_miru(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        self.session.spot_key = "mirumok"
        await self.cog._goto_next(interaction, self.session, Step.SPOT)

    async def _pick_gyfin(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        self.session.spot_key = "gyfin"
        await self.cog._goto_next(interaction, self.session, Step.SPOT)

    def embed(self) -> discord.Embed:
        return discord.Embed(
            title=f"{CHEER_EMOJI} Gruppensuche – Mirumok / Gyfin",
            description=(
                "Wähle den Spot, für den du eine Gruppe suchst.\n\n"
                f"**Mirumok**\n• Empfohlen mind. {SPOT_REQ['mirumok']}\n• {SPOT_TOTAL_AP['mirumok']}\n\n"
                f"**Gyfin**\n• Empfohlen mind. {SPOT_REQ['gyfin']}\n• {SPOT_TOTAL_AP['gyfin']}"
            ),
        )



class PartySizeSelect(discord.ui.Select):
    def __init__(self, host_view: "PartySizeView", min_n: int, max_n: int, current: Optional[int] = None):
        options = []
        for n in range(min_n, max_n + 1):
            opt = discord.SelectOption(
                label=str(n), value=str(n), default=(current == n))
            options.append(opt)

        super().__init__(
            placeholder="Wähle die maximale Teilnehmerzahl (inkl. dir)...",
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

        # ✅ Create: Flow zentral über Router
        if self.host_view.session.mode == "create":
            await self.host_view.cog._goto_next(interaction, self.host_view.session, Step.PARTY)
            return

        # Edit: bleibt speichern
        await self.host_view.cog._apply_edit_max_players(interaction, self.host_view.session)

class PartySizeView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession, current: Optional[int] = None):
        super().__init__(cog, session)

        mn, mx = _allowed_party_range(session.category or "")
        self.add_item(PartySizeSelect(self, mn, mx, current=current))

        # Zurück-Ziel hängt an der Kategorie / dem Flow
        self.add_item(build_back_button("Tag", BackTarget.DAY, self, row=1))



    def embed(self) -> discord.Embed:
        mn, mx = _allowed_party_range(self.session.category or "")

        if self.session.category == "muhhelfer":
            diff = "Schwer" if self.session.difficulty == "schwer" else "Normal"
            req = AKVK_SCHWER if self.session.difficulty == "schwer" else AKVK_NORMAL
            return discord.Embed(
                title=f"{MUHKUH_EMOJI} Muhhelfer – Gruppengröße",
                description=(
                    f"Schwierigkeit: {diff}\n"
                    f"Empfohlen mind. AK/VK: {req}\n\n"
                    f"{_party_size_help_text(mn, mx)}"
                ),
            )

        if self.session.category == "spots" and self.session.spot_key:
            spot = self.session.spot_key
            emoji = MIRUMOK_EMOJI if spot == "mirumok" else GYFIN_EMOJI
            return discord.Embed(
                title=f"{emoji} {_spot_name(spot)} – Gruppengröße",
                description=(
                    f"• Empfohlen mind. {SPOT_REQ.get(spot, '')}\n"
                    f"• {SPOT_TOTAL_AP.get(spot, '')}\n\n"
                    f"{_party_size_help_text(mn, mx)}"
                ),
            )

        if self.session.category == "pilafe":
            return discord.Embed(
                title=f"{PILAFE_EMOJI} Gruppensuche – Pila Fe",
                description=_party_size_help_text(mn, mx),
            )

        return discord.Embed(title="Gruppengröße", description=_party_size_help_text(mn, mx))

# =========================
# Edit Menu (ephemeral)
# =========================


class EditMenuView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession, post_data: dict):
        super().__init__(cog, session)
        self.post_data = post_data

        tag_btn = discord.ui.Button(
            label="Tag ändern", style=discord.ButtonStyle.secondary, row=0)
        size_btn = discord.ui.Button(
            label="Max. Teilnehmer ändern", style=discord.ButtonStyle.secondary, row=0)
        details_btn = discord.ui.Button(
            label="Zeiten & Notiz bearbeiten", style=discord.ButtonStyle.secondary, row=1)

        tag_btn.callback = self._tag
        size_btn.callback = self._size
        details_btn.callback = self._details

        self.add_item(tag_btn)
        self.add_item(size_btn)
        self.add_item(details_btn)

        if post_data.get("category") == "muhhelfer":
            bosses_btn = discord.ui.Button(
                label="Bosse & Doppelrun bearbeiten", style=discord.ButtonStyle.secondary, row=1)
            bosses_btn.callback = self._bosses
            self.add_item(bosses_btn)

        back_btn = discord.ui.Button(
            label="Bearbeitung beenden", style=discord.ButtonStyle.secondary, row=2)
        back_btn.callback = self._back
        self.add_item(back_btn)

    async def _tag(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        await self.cog._send_day_selection(interaction, self.session)

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

        confirm_btn = discord.ui.Button(
            label=confirm_label, style=discord.ButtonStyle.danger)
        cancel_btn = discord.ui.Button(
            label="❌ Abbrechen", style=discord.ButtonStyle.secondary)

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
        member = interaction.user if isinstance(
            interaction.user, discord.Member) else None
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
        v = ConfirmView(self.cog, self.message_id,
                        "close", interaction.user.id)
        await interaction.response.send_message(v.text, ephemeral=True, view=v)

    async def _on_delete(self, interaction: discord.Interaction):
        data = await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        v = ConfirmView(self.cog, self.message_id,
                        "delete", interaction.user.id)
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
        member = interaction.user if isinstance(
            interaction.user, discord.Member) else None
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

        self.config = Config.get_conf(
            self, identifier=935771234123, force_registration=True)
        self.config.register_guild(searches={})

        self._sessions: Dict[int, WizardSession] = {}
        self._startup_task: Optional[asyncio.Task] = self.bot.loop.create_task(
            self._startup_register_views())
        self._reminder_task: Optional[asyncio.Task] = self.bot.loop.create_task(
            self._reminder_loop())

    def cog_unload(self):
        if self._startup_task and not self._startup_task.done():
            self._startup_task.cancel()
        if self._reminder_task and not self._reminder_task.done():
            self._reminder_task.cancel()

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

    async def _go_back(self, interaction: discord.Interaction, session: WizardSession, target: str, **kwargs):
        # Edit-Mode Back bleibt wie bei euch über build_back_button geregelt.
        if target == BackTarget.START:
            await self._send_step(interaction, session, Step.START)
            return
        if target == BackTarget.DIFFICULTY:
            await self._send_step(interaction, session, Step.DIFFICULTY)
            return
        if target == BackTarget.SPOT:
            await self._send_step(interaction, session, Step.SPOT)
            return
        if target == BackTarget.BOSSES:
            await self._send_step(interaction, session, Step.BOSSES)
            return
        if target == BackTarget.DOUBLE:
            await self._send_step(interaction, session, Step.DOUBLE)
            return
        if target == BackTarget.DAY:
            await self._send_step(interaction, session, Step.DAY)
            return
        if target == BackTarget.EDIT_MENU:
            await self._send_step(interaction, session, Step.EDIT_MENU)
            return


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

    async def _send_step(self, interaction: discord.Interaction, session: WizardSession, step: str, **kwargs):
        """
        Zentrale Render-Funktion für Wizard-Steps.
        kwargs sind nur für spezielle Steps (z.B. back_target bei DAY).
        """
        if step == Step.START:
            await self._send_start(interaction, session)
            return

        if step == Step.DIFFICULTY:
            await self._send_difficulty(interaction, session)
            return

        if step == Step.BOSSES:
            await self._send_boss_select(interaction, session)
            return

        if step == Step.DOUBLE:
            await self._send_double_run(interaction, session)
            return

        if step == Step.SPOT:
            await self._send_spot_select(interaction, session)
            return

        if step == Step.DAY:
            await self._send_day_selection(interaction, session)
            return

        if step == Step.PARTY:
            await self._send_party_size(interaction, session)
            return

        if step == Step.DETAILS:
            await self._send_final_form(interaction, session)
            return

        if step == Step.EDIT_MENU:
            await self._send_edit_menu(interaction, session)
            return

        # Fallback
        await interaction.followup.send("Unbekannter Step.", ephemeral=True)

    def _resolve_back_target_for_day(self, session: WizardSession) -> str:
        """
        Wenn wir DAY anzeigen: Wohin zeigt der Zurück-Button?
        Das hängt von Kategorie / Flow ab.
        """
        if session.mode == "edit":
            return BackTarget.EDIT_MENU

        if session.category == "spots":
            return BackTarget.SPOT

        if session.category == "pilafe":
            return BackTarget.START

        # muhhelfer:
        total = _sum_runs(session.boss_runs)
        prev = BackTarget.BOSSES if total >= 5 else BackTarget.DOUBLE
        return prev

    def _resolve_next_step(self, session: WizardSession, current_step: str) -> str:
        """
        Zentrale Next-Entscheidung.
        Gibt den nächsten Step zurück.
        """
        # Edit-Mode: “Back-Regel” bleibt separat (über build_back_button). Next-Flow bleibt hier zentral steuerbar.
        cat = session.category or ""

        # -------- START --------
        if current_step == Step.START:
            if cat == "muhhelfer":
                return Step.DIFFICULTY
            if cat == "spots":
                return Step.SPOT
            if cat == "pilafe":
                return Step.DAY
            return Step.START

        # -------- MUHHELFER --------
        if cat == "muhhelfer":
            if current_step == Step.DIFFICULTY:
                return Step.BOSSES

            if current_step == Step.BOSSES:
                total = _sum_runs(session.boss_runs)
                return Step.DAY if total >= 5 else Step.DOUBLE


            if current_step == Step.DOUBLE:
                # Create: danach DAY; Edit: danach speichern (macht _apply_edit_bosses im View)
                return Step.DAY if session.mode == "create" else Step.EDIT_MENU

            if current_step == Step.DAY:
                return Step.PARTY

            if current_step == Step.PARTY:
                return Step.DETAILS if session.mode == "create" else Step.EDIT_MENU

        # -------- SPOTS --------
        if cat == "spots":
            if current_step == Step.SPOT:
                return Step.DAY
            if current_step == Step.DAY:
                return Step.PARTY
            if current_step == Step.PARTY:
                return Step.DETAILS if session.mode == "create" else Step.EDIT_MENU

        # -------- PILAFE --------
        if cat == "pilafe":
            if current_step == Step.DAY:
                return Step.PARTY
            if current_step == Step.PARTY:
                return Step.DETAILS if session.mode == "create" else Step.EDIT_MENU

        # Fallback
        return Step.START

    async def _goto_next(self, interaction: discord.Interaction, session: WizardSession, current_step: str):
        next_step = self._resolve_next_step(session, current_step)
        await self._send_step(interaction, session, next_step)


    async def _send_start(self, interaction: discord.Interaction, session: WizardSession):
        view = StartView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_day_selection(self, interaction: discord.Interaction, session: WizardSession):
        view = DaySelectView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)


    async def _send_category_specific(self, interaction: discord.Interaction, session: WizardSession):
        if session.category == "muhhelfer":
            await self._send_difficulty(interaction, session)
            return
        if session.category == "spots":
            await self._send_spot_select(interaction, session)
            return
        if session.category == "pilafe":
            await self._send_day_selection(interaction, session)
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
        # ✅ Nur rendern. Flow-Entscheidung macht der Router.
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

    async def _ephemeral_notice(self, interaction: discord.Interaction, text: str):
        try:
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)
        except Exception:
            pass
    

    async def _send_ephemeral_new(self, interaction: discord.Interaction, embed: discord.Embed, view: discord.ui.View):
        # Sendet IMMER eine neue ephemeral Nachricht (niemals edit_message auf einem öffentlichen Post).
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

        # ========= Cooldown (pro Post) =========
        cd = data.get("ping_cd") or {}
        now_ts = int(_now_local().timestamp())
        last = int(cd.get("participants", 0))

        remaining = PARTICIPANT_PING_COOLDOWN_SECONDS - (now_ts - last)
        if remaining > 0:
            await interaction.followup.send(
                f"📣 Teilnehmer-Ping ist noch im Cooldown. Bitte warte **{remaining}s**.",
                ephemeral=True,
            )
            return

        cd["participants"] = now_ts
        data["ping_cd"] = cd
        data["updated_at"] = now_ts

        try:
            await self._set_search(message_id, data)
        except Exception:
            pass

        # =======================================

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
            allowed_mentions=discord.AllowedMentions(
                users=True, roles=False, everyone=False),
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

    def _dispatch_dashboard_update(self, guild_id: int):
        # Trigger für Gruppenübersicht Cog (sofortiges Refresh).
        try:
            self.bot.dispatch("gruppensuche_updated", int(guild_id))
        except Exception:
            pass

    async def _save_refresh_dispatch(self, data: dict, *, refresh_public: bool = True):

        # Zentraler Helper:
        # - updated_at setzen
        # - in Config speichern
        # - public message refreshen (optional)
        # - Dashboard-Refresh dispatchen

        try:
            now_ts = int(_now_local().timestamp())
            data["updated_at"] = now_ts

            mid = int(data.get("message_id", 0))
            if mid:
                await self._set_search(mid, data)

            if refresh_public and mid:
                await self._refresh_public_message(data)

            gid = int(data.get("guild_id", 0))
            if gid:
                self._dispatch_dashboard_update(gid)
        except Exception:
            pass

    # =========================
    # Public Post Build/Refresh
    # =========================

    async def _build_public_embed(self, guild: discord.Guild, data: dict) -> discord.Embed:
        cat = str(data.get("category", ""))
        owner_id = int(data.get("owner_id", 0))
        owner = guild.get_member(owner_id)

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

        # ✅ Einmal zentral setzen
        duration_text = data.get("duration_text") or "—"
        start_text = data.get("start_text") or "—"
        notes = data.get("notes") or "—"

        # ✅ Times-Block erst jetzt bauen
        # ✅ Times-Block
        times_block = (
            f"**Tag:** {day_str}\n"
            f"**Start:** {start_text}\n"
            f"**Geplante Dauer:** {duration_text}\n\n"
        )

        # ✅ Notes-Block (NEU)
        notes_block = f"**Notiz:** {notes}\n\n"

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

            bosses_block = "**Bosse:**\n" + \
                ("\n".join(boss_lines) if boss_lines else "—") + "\n\n"
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
                + ("\n".join([f"• {x}" for x in part_lines])
                   if part_lines else "—")
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
                + ("\n".join([f"• {x}" for x in wait_lines])
                   if wait_lines else "—")
            )

            e.description = header + bosses_block + times_block + \
                notes_block + status_block + participants_block + wait_block

        elif cat == "spots":
            spot = str(data.get("spot_key", ""))
            req_default = SPOT_REQ.get(spot, "")
            req = req_text or req_default

            header = (
                f"**Suchender:** {owner_display}\n"
                f"**Kategorie:** Gruppenspots\n"
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
                + ("\n".join([f"• {x}" for x in part_lines])
                   if part_lines else "—")
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
                + ("\n".join([f"• {x}" for x in wait_lines])
                   if wait_lines else "—")
            )

            e.description = header + spot_block + times_block + \
                notes_block + status_block + participants_block + wait_block

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
                + ("\n".join([f"• {x}" for x in part_lines])
                   if part_lines else "—")
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
                + ("\n".join([f"• {x}" for x in wait_lines])
                   if wait_lines else "—")
            )

            e.description = header + times_block + notes_block + \
                status_block + participants_block + wait_block

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
        label = "Rollen-Ping"
        cat = str(data.get("category", ""))

        if cat == "muhhelfer":
            diff = str(data.get("difficulty", "normal"))
            label = f"Rollen-Ping ({'Schwer' if diff == 'schwer' else 'Normal'})"
        elif cat == "spots":
            spot = str(data.get("spot_key", ""))
            label = f"Rollen-Ping ({_spot_name(spot)})" if spot else "Rollen-Ping"
        elif cat == "pilafe":
            label = "Rollen-Ping (Pila Fe)"

        for item in view.children:
            if isinstance(item, discord.ui.Button) and str(item.custom_id or "").startswith("gst:pingtype:"):
                item.label = label
                item.emoji = "🔔"
                break

    # =========================
    # Create Public Post
    # =========================

    async def _create_public_post_from_session(self, interaction: discord.Interaction, session: WizardSession):
        guild = interaction.guild
        if guild is None:
            await self._ephemeral_notice(interaction, "Nur auf einem Server nutzbar.")
            return


        channel: Optional[discord.TextChannel] = None

        if FEATURE_POST_IN_CURRENT_CHANNEL:
            # bevorzugt dort posten, wo der Slash Command / Wizard gestartet wurde
            if isinstance(interaction.channel, discord.TextChannel):
                channel = interaction.channel
        else:
            # fallback: alter Test-Channel Modus
            ch = guild.get_channel(TEST_CHANNEL_ID)
            if isinstance(ch, discord.TextChannel):
                channel = ch

        if channel is None:
            # letzter Fallback: Systemchannel, falls vorhanden
            if isinstance(guild.system_channel, discord.TextChannel):
                channel = guild.system_channel

        if channel is None:
            await self._ephemeral_notice(
                interaction,
                "Ich konnte keinen Ziel-Textchannel bestimmen (kein Zugriff / falscher Channel-Typ).",
            )
            return



        day_iso = session.day_date_iso or _now_local().date().isoformat()
        max_players = int(session.max_players or 2)
        owner_id = interaction.user.id

        if session.category == "muhhelfer":
            ping_role_id = ROLE_SCHWER_ID if session.difficulty == "schwer" else ROLE_NORMAL_ID
        elif session.category == "spots":
            ping_role_id = SPOT_PING_ROLE.get(
                session.spot_key or "", TEST_ROLE_ID)
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
        allowed = discord.AllowedMentions(
            roles=True, users=False, everyone=False)

        msg = await channel.send(content=content, embed=embed, allowed_mentions=allowed)
        data["message_id"] = msg.id

        view = PublicPostView(self, msg.id)
        await self._apply_dynamic_button_labels(view, data)   # ✅ HIER
        await msg.edit(view=view)
        self.bot.add_view(view)

        async with self.config.guild(guild).searches() as searches:
            searches[str(msg.id)] = data

        self._dispatch_dashboard_update(guild.id)

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

    async def _reminder_loop(self):
        await self.bot.wait_until_red_ready()
        await self.bot.wait_until_ready()

        while True:
            try:
                await self._run_start_reminders()
            except Exception:
                pass

            await asyncio.sleep(30)  # alle 30s checken reicht völlig

    async def _run_start_reminders(self):
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return

        searches = await self.config.guild(guild).searches()
        if not searches:
            return

        now = _now_local()

        for mid_str, data in (searches or {}).items():
            try:
                if bool(data.get("is_closed", False)):
                    continue

                start_dt = _build_start_dt_if_possible(data)
                if not start_dt:
                    continue

                remind_at = start_dt - dt.timedelta(minutes=30)
                if now < remind_at or now >= start_dt:
                    continue

                reminders = data.get("reminders")
                if not isinstance(reminders, dict):
                    reminders = {}

                # bereits gesendet?
                if int(reminders.get("start_30m", 0)) > 0:
                    continue

                # senden + markieren
                await self._send_start_30m_reminder(guild, int(data.get("message_id", 0)), data)

                ts = int(_now_local().timestamp())
                reminders["start_30m"] = ts
                data["reminders"] = reminders
                data["updated_at"] = ts
                await self._set_search(int(data.get("message_id", 0)), data)

            except Exception:
                continue

    async def _send_start_30m_reminder(self, guild: discord.Guild, message_id: int, data: dict):
        channel = guild.get_channel(int(data.get("channel_id", 0)))
        jump = f"https://discord.com/channels/{guild.id}/{int(data.get('channel_id', 0))}/{message_id}"

        max_players = int(data.get("max_players", 2))
        participants = list(data.get("participants") or [])

        owner_id = int(data.get("owner_id", 0))  # <-- NEU (früher holen)

        free = max(0, max_players - len(participants))

        # Owner NICHT in Teilnehmer-DM aufnehmen (sonst 2x DM)
        participants_dm = [uid for uid in participants if int(
            uid) != owner_id]  # <-- NEU

        # schöner Text
        day_iso = data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_str = _format_day(dt.date.fromisoformat(day_iso))
        except Exception:
            day_str = str(day_iso)

        start_text = data.get("start_text") or "—"

        # 1) DM an Teilnehmer
        failed: list[int] = []
        for uid in participants_dm:
            m = guild.get_member(int(uid))
            if not m:
                continue
            try:
                await m.send(f"⏰ **Reminder:** In ~30 Minuten geht’s los.\n**Tag:** {day_str}\n**Start:** {start_text}\n{jump}")
            except Exception:
                failed.append(int(uid))

        # Fallback: wer DMs zu hat
        if failed and isinstance(channel, discord.TextChannel):
            mentions = " ".join(f"<@{uid}>" for uid in failed)
            try:
                await channel.send(
                    f"⏰ Reminder (DM fehlgeschlagen): {mentions}\n**Start:** {start_text} | {day_str}\n{jump}",
                    allowed_mentions=discord.AllowedMentions(
                        users=True, roles=False, everyone=False),
                )
            except Exception:
                pass

        # 2) Extra DM an Ersteller mit “es fehlen noch X”
        owner = guild.get_member(owner_id)
        if owner:
            try:
                extra = f"\n⚠️ Es fehlen noch **{free}** Teilnehmer." if free > 0 else "\n✅ Gruppe ist voll."
                await owner.send(
                    f"⏰ **Reminder (Host):** In ~30 Minuten.\n**Tag:** {day_str}\n**Start:** {start_text}{extra}\n{jump}"
                )
            except Exception:
                pass

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

            ap_map = data.get("participant_ap") or {}
            ap_map[str(uid)] = ap_val
            data["participant_ap"] = ap_map

            await self._save_refresh_dispatch(data)
            await interaction.response.send_message("✅ Du bist jetzt Teilnehmer.", ephemeral=True)
            return

        waitlist.append(uid)
        data["waitlist"] = waitlist
        data["updated_at"] = int(_now_local().timestamp())
        wl_map = data.get("waitlist_ap") or {}
        wl_map[str(uid)] = ap_val
        data["waitlist_ap"] = wl_map
        await self._save_refresh_dispatch(data)
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
        await self._save_refresh_dispatch(data)

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
                allowed_mentions=discord.AllowedMentions(
                    users=True, roles=False, everyone=False),
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

        type_map = cd.get("type")
        if not isinstance(type_map, dict):
            type_map = {}

        last = int(type_map.get(str(message_id), 0))
        diff = now_ts - last
        if diff < PING_COOLDOWN_SECONDS:
            remaining = PING_COOLDOWN_SECONDS - diff
            await interaction.followup.send(
                f"⏳ Ping-Cooldown aktiv. Du kannst das wieder {_format_remaining(remaining)} benutzen.",
                ephemeral=True,
            )
            return

        type_map[str(message_id)] = now_ts
        cd["type"] = type_map
        data["ping_cd"] = cd

        await self._save_refresh_dispatch(data, refresh_public=False)

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

        wait_map = cd.get("wait")
        if not isinstance(wait_map, dict):
            wait_map = {}

        last = int(wait_map.get(str(message_id), 0))
        diff = now_ts - last
        if diff < PING_COOLDOWN_SECONDS:
            remaining = PING_COOLDOWN_SECONDS - diff
            await interaction.followup.send(
                f"⏳ Ping-Cooldown aktiv. Du kannst das wieder {_format_remaining(remaining)} benutzen.",
                ephemeral=True,
            )
            return

        wait_map[str(message_id)] = now_ts
        cd["wait"] = wait_map
        data["ping_cd"] = cd

        await self._save_refresh_dispatch(data, refresh_public=False)

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
        await self._save_refresh_dispatch(data)

    async def _open_search(self, interaction: discord.Interaction, message_id: int):
        data = await self._get_search(message_id)
        if data is None:
            await interaction.response.send_message("Diese Suche existiert nicht mehr.", ephemeral=True)
            return
        data["is_closed"] = False
        await self._save_refresh_dispatch(data)

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
        self._dispatch_dashboard_update(int(data.get("guild_id", 0)))

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
            difficulty=str(data.get("difficulty")) if data.get(
                "category") == "muhhelfer" else None,
            boss_runs=dict(data.get("boss_runs") or {}),
            spot_key=str(data.get("spot_key")) if data.get(
                "category") == "spots" else None,
            max_players=int(data.get("max_players", 2)),
            scroll_amount=str(data.get("scroll_amount")) if data.get(
                "category") == "pilafe" else None,
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

        # ✅ Reminder reset, weil Tag geändert wurde
        rem = data.get("reminders")
        if not isinstance(rem, dict):
            rem = {}
        rem.pop("start_30m", None)
        data["reminders"] = rem

        await self._save_refresh_dispatch(data)

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
        # ✅ Admin-only Absicherung: 1 Teilnehmer nur für Admin-Testzwecke
        member = interaction.user if isinstance(
            interaction.user, discord.Member) else None
        if new_max == 1 and not (member and _is_admin_only(member)):
            await interaction.response.send_message(
                "1 Teilnehmer ist nur für Admin-Testzwecke erlaubt.",
                ephemeral=True,
            )
            return

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
        await self._save_refresh_dispatch(data)

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

        old_start = data.get("start_text")
        old_day = data.get("day_date_iso")  # optional

        data["duration_text"] = session.duration_text
        data["start_text"] = session.start_text
        data["req_text"] = session.req_text
        data["notes"] = session.notes

        # ✅ Reminder reset, wenn Startzeit (oder optional Tag) geändert wurde
        if (data.get("start_text") != old_start) or (data.get("day_date_iso") != old_day):
            rem = data.get("reminders")
            if not isinstance(rem, dict):
                rem = {}
            rem.pop("start_30m", None)
            data["reminders"] = rem

        await self._save_refresh_dispatch(data)

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
        await self._save_refresh_dispatch(data)

        await self._send_edit_menu(interaction, session)
