from __future__ import annotations
import re
from typing import Callable, Union, Any
from zoneinfo import ZoneInfo
from discord import app_commands  # pyright: ignore[reportMissingImports]

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from discord import PartialEmoji  # pyright: ignore[reportMissingImports]

import discord  # pyright: ignore[reportMissingImports]
# pyright: ignore[reportMissingImports]
# pyright: ignore[reportMissingImports]
from redbot.core import commands, Config
import random
import logging


log = logging.getLogger("red.kuhmuh.gruppensuche")

# =========================
# IDs / Konfiguration
# =========================

TEST_CHANNEL_ID = 1199322485297000528
TEST_ROLE_ID = 1445018518562017373

LOG_CHANNEL_ID: int = 1460298038269575282
DEV_ALERT_ROLE_ID: int = 1445018518562017373

ROLE_NORMAL_ID = 1424768638157852682
ROLE_SCHWER_ID = 1424769286790054050

ROLE_OLUN_NORMAL_ID = 1471825236357025802
ROLE_OLUN_DEHKIA1_ID = 1471825732798779422
ROLE_OLUN_DEHKIA2_ID = 1471825918480875626

ROLE_MIRUMOK_ID = 1459832247405248707
ROLE_GYFIN_ID = 1459832490603708590
ROLE_EDANIA_ID = 1483214699754688562

ROLE_PILAFE_ID = 1458832343149318269
ROLE_ALTAR_ID = 1459833455369130140
ROLE_ATORAXXION_ID = 1463872163516911808

ADMIN_ROLE_ID: Optional[int] = 1452050940952838214
OFFIZIER_ROLE_ID: Optional[int] = 1198652039312453723

PING_COOLDOWN_SECONDS = 600
PARTICIPANT_PING_COOLDOWN_SECONDS = 60
WIZARD_TIMEOUT_SECONDS = 300  # 5 Minuten (oder 600 = 10 Minuten)

# "Gruppensuche DM-Funktion" (Reverse: hat Rolle => KEINE DM)
ROLE_NO_DM_ID = 1466761625158684817
# ROLE_NO_DM_ID LIVE = 1466752408779751509
# ROLE_NO_DM_ID TEST = 1466761625158684817


MUHKUH_EMOJI = "<:muhkuh:1207038544510586890>"
PILAFE_EMOJI = "<:pilafe:1450051653297504368>"
MIRUMOK_EMOJI = "<:Mirumok:1461101498954940428>"
GYFIN_EMOJI = "<:Gyfin:1461102103266066502>"
CHEER_EMOJI = "<:blackspiritcheer:1199730129476268183>"
OLUN_EMOJI = "<:olun:1471826612394655857>"
EDANIA_EMOJI = "<:edania:1483216698625753088>"

EASTER_EGG_AP = 396
EASTER_EGG_MARK = " ✨"  # oder f" {MUHKUH_EMOJI}" wenn du es cow-themed willst

EASTER_EGG_TEXT_POOL = [
    "hat wohl heimlich +AP im Stall gefunden",
    f"ist offiziell overcapped {MUHKUH_EMOJI}",
    "bringt Kuhkraft auf Maximum",
    "hat den Black Spirit überredet",
    "AP ist nicht alles… außer heute 😄",
    "rein statistisch beeindruckend",
    "overcap confirmed.",
    "die Herde beobachtet dich.",
    "vom Schwarzgeist gesegnet",
    "hat wohl einem GM geholfen 😉",
    "trägt die Hörner der Macht",
    "Softcap? Kenn ich nicht.",
    "lebt jenseits von Sheet-AP",
    "hat das Gras cap-optimiert",
    "ist offiziell im Endgame-Endgame",
    "steht jetzt im Heu-Archiv",
    "intern bekannt.",
    "wir prüfen das nochmal… vielleicht.",
    "offiziell nicht kommentiert.",
    "hat die Kuhmuh-Schwelle überschritten",
    "ist vermutlich noch im Tutorial.",
    "rein hypothetisch vollkommen angemessen.",
    "statistisch fragwürdig. Praktisch beeindruckend.",
    f"Heu-Level: Endstufe {MUHKUH_EMOJI}",
    "im internen Gras-Register vermerkt",
    "der Schwarzgeist schaut irritiert 👀",
    "RNG hat weggesehen 🎲",
    "Cronsteine wurden geopfert",
    "über dem empfohlenen Patchlevel",
    "Sheet-AP ist nur ein Vorschlag",
    "ist wohl die Katze über die Tastatur gelaufen..",
    "Legenden beginnen genau so."
]


GUILD_ID = 1198649628787212458

AKVK_NORMAL = "301 / 385"
AKVK_SCHWER = "330 / 401"

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
    ("olun", "Olun"),
    ("edania", "Edania"),
]


SPOT_REQ: Dict[str, str] = {
    "mirumok": "350 / 427",
    "gyfin": "370 / 440",
    "olun": "",  # bleibt leer, weil tier-basiert (siehe OLUN_REQ)
    "edania": "385 / 450",
}

OLUN_REQ: Dict[str, str] = {
    "normal": "290 / 380",
    "dehkia1": "325 / 400",
    "dehkia2": "340 / 430",
}

SPOT_TOTAL_AP: Dict[str, str] = {
    "mirumok": "Total AP 1565 - 1595",
    "gyfin": "Total AP 1650 - 1680",
    "olun": "",  # bleibt leer, weil tier-basiert (siehe OLUN_TOTAL_AP)
    "edania": "Total AP 1850 - 1880",
}

OLUN_TOTAL_AP: Dict[str, str] = {
    "normal": "Total AP 1000 - 1030",
    "dehkia1": "Total AP 1320 - 1350",
    "dehkia2": "Total AP 1460 - 1490",
}


ATORAXXION_DUNGEONS: List[Tuple[str, str]] = [
    ("vahmalkea", "Vahmalkea"),
    ("sycrakea", "Sycrakea"),
    ("yolunakea", "Yolunakea"),
    ("orzekea", "Orzekea"),
]


def _atoraxxion_dungeon_label(key: str) -> str:
    k = str(key or "").lower().strip()
    for kk, name in ATORAXXION_DUNGEONS:
        if kk == k:
            return name
    return key


def _atoraxxion_selected_keys(data: dict) -> list[str]:
    """
    Unterstützt beide Felder:
    - Neu: data["atoraxxion_runs"] = ["vahmalkea", ...]
    - Alt: data["atoraxxion_run"] = "complete_run" | "vahmalkea" | ...
    Regeln:
    - complete_run => alle 4
    - sonst => 1 oder mehrere, je nachdem was vorhanden ist
    """
    runs = data.get("atoraxxion_runs")
    if isinstance(runs, list) and runs:
        out: list[str] = []
        for x in runs:
            k = str(x or "").lower().strip()
            if k and k not in out:
                out.append(k)
        # Reihenfolge fixieren wie definiert
        order = [k for k, _ in ATORAXXION_DUNGEONS]
        out.sort(key=lambda z: order.index(z) if z in order else 999)
        # Wenn alle 4 gewählt -> wie kompletter Run behandeln
        if len(out) >= 4:
            return [k for k, _ in ATORAXXION_DUNGEONS]
        return out

    rk = str(data.get("atoraxxion_run") or "").lower().strip()
    if rk == "complete_run":
        return [k for k, _ in ATORAXXION_DUNGEONS]
    if rk:
        return [rk]
    return []


def _olun_tier_label(tier: str) -> str:
    return {"normal": "Normal", "dehkia1": "Dehkia 1", "dehkia2": "Dehkia 2"}.get(tier, tier)


SPOT_PING_ROLE: Dict[str, int] = {
    "mirumok": ROLE_MIRUMOK_ID,
    "gyfin": ROLE_GYFIN_ID,
    "edania": ROLE_EDANIA_ID,
}

# =========================
# Feature Flags
# =========================
FEATURE_MUHHILFER = True

FEATURE_SPOTS = True
# (falls du mal einzelne Spots togglen willst)
FEATURE_SPOTS_GYFIN = True
FEATURE_SPOTS_MIRUMOK = True
FEATURE_SPOTS_OLUN = True
FEATURE_SPOTS_EDANIA = True


FEATURE_PILAFE = True
FEATURE_ALTAR = True              # <- vorbereitet, aber nicht im Menü
FEATURE_ATORAXXION = True         # <- vorbereitet, aber nicht im Menü

FEATURE_POST_IN_CURRENT_CHANNEL = True  # statt TEST_CHANNEL_ID
FEATURE_DM_REMINDERS = True
FEATURE_AUTO_CLOSE = True  # ✅ Posts automatisch schließen (siehe Patch 5)

# Master für Spots (zusätzlich zu MIRU/GYFIN)


# =========================
# Wizard UI Schema (global)
# =========================


def _muh_title(session: "WizardSession") -> str:
    diff_label = "Schwer" if session.difficulty == "schwer" else "Normal"
    return f"{MUHKUH_EMOJI} Gruppensuche – Muhhelfer ({diff_label})"


def _spots_title(session: "WizardSession") -> str:
    spot = session.spot_key or ""
    if spot == "mirumok":
        emoji = MIRUMOK_EMOJI
    elif spot == "gyfin":
        emoji = GYFIN_EMOJI
    elif spot == "olun":
        emoji = OLUN_EMOJI
    elif spot == "edania":
        emoji = EDANIA_EMOJI
    else:
        emoji = CHEER_EMOJI

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
    "altar": {
        "party_min": 2,
        "party_max": 3,
        "party_text": "Wähle die maximale Teilnehmerzahl **2–3**.",
        "title_fn": lambda s: "🩸 Gruppensuche – Altar des Blutes",
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


def _parse_int_strict(val: object) -> Optional[int]:
    """
    Erlaubt nur Ziffern + gängige Trenner (., , und Leerzeichen).
    - "3245" -> 3245
    - "3.245" / "3,245" / "3 245" -> 3245
    Alles andere (Buchstaben etc.) -> None
    """
    s = str(val or "").strip()
    if not s:
        return None

    allowed = set("0123456789., ")
    if any(ch not in allowed for ch in s):
        return None

    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return None

    try:
        return int(digits)
    except Exception:
        return None


def _member_from_interaction(interaction: discord.Interaction) -> Optional[discord.Member]:
    if isinstance(interaction.user, discord.Member):
        return interaction.user
    if interaction.guild:
        return interaction.guild.get_member(int(interaction.user.id))
    return None


def _category_emoji(data: dict) -> str:
    cat = str(data.get("category") or "").lower()
    spot = str(data.get("spot_key") or "").lower()

    if cat == "muhhelfer":
        return MUHKUH_EMOJI

    if cat == "pilafe":
        return PILAFE_EMOJI

    if cat == "atoraxxion":
        return "🏛️"

    if cat == "altar":
        return "🩸"

    if cat == "spots":
        if spot == "mirumok":
            return MIRUMOK_EMOJI
        if spot == "gyfin":
            return GYFIN_EMOJI
        if spot == "olun":
            return OLUN_EMOJI
        if spot == "edania":
            return EDANIA_EMOJI

    return MUHKUH_EMOJI


def _get_post_lock(self, message_id: int) -> asyncio.Lock:
    lock = self._post_locks.get(message_id)
    if lock is None:
        lock = asyncio.Lock()
        self._post_locks[message_id] = lock
    return lock


def _fmt_number(val: Optional[int | str]) -> str:
    if val is None:
        return "—"

    try:
        n = int(val)
        return f"{n:,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(val)


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
    OLUN_TIER = "olun_tier"
    atoraxxion_runs = "atoraxxion_runs"
    ALTAR_STEP = "altar_step"


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
    OLUN_TIER = "olun_tier"
    atoraxxion_runs = "atoraxxion_runs"
    ALTAR_STEP = "altar_step"


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


def _fmt_thousands_de(val: object) -> str:
    """
    Formatiert Integers wie 4000 -> '4.000'
    Wenn nicht eindeutig int: gibt original als String zurück.
    """
    s = str(val or "").strip()
    if not s:
        return "—"

    # nur reine Zahl (optional mit + am Ende) formatieren
    plus = s.endswith("+")
    core = s[:-1] if plus else s

    if core.isdigit():
        n = int(core)
        out = f"{n:,}".replace(",", ".")
        return out + ("+" if plus else "")

    return s


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
    r"(?P<h>\d{1,2})(?:[:\.,](?P<m>\d{2}))?\s*(?:uhr)?", re.IGNORECASE
)

# ✅ "in 3h", "in 45m", "in 2 std", "in 30 min" (nur sinnvoll, wenn Tag = heute)
_REL_TIME_RE = re.compile(
    r"\bin\s*(?P<n>\d{1,4})\s*(?P<unit>h|std|stunde|stunden|m|min|mins|minute|minuten)\b",
    re.IGNORECASE,
)


_AP_NUM_RE = re.compile(r"(\d+)")


def _ap_triggers_easter_egg(ap_val: Optional[str]) -> bool:
    """Trigger: AP > 396 (weil 396 max ist)."""
    n = _parse_int_strict(ap_val)
    if n is None:
        return False
    return n > EASTER_EGG_AP


def _ensure_easter_egg_text(data: dict, user_id: int, ap_val: Optional[str]) -> Optional[str]:
    """
    Würfelt EINMALIG einen Text, wenn AP triggern.
    Speichert pro Post pro User in data['easter_egg_texts'].
    """
    if not _ap_triggers_easter_egg(ap_val):
        return None

    egg_map = data.get("easter_egg_texts")
    if not isinstance(egg_map, dict):
        egg_map = {}

    key = str(int(user_id))
    if key in egg_map and str(egg_map[key]).strip():
        return str(egg_map[key])

    # einmalig würfeln
    txt = random.choice(EASTER_EGG_TEXT_POOL) if EASTER_EGG_TEXT_POOL else "✨"
    egg_map[key] = txt
    data["easter_egg_texts"] = egg_map
    return txt


def _sync_easter_egg_text(data: dict, user_id: int, ap_val: Optional[str]) -> Optional[str]:
    """
    Stellt sicher:
    - AP triggert -> Text existiert (einmalig würfeln)
    - AP triggert NICHT -> Text wird entfernt (falls vorhanden)
    """
    egg_map = data.get("easter_egg_texts")
    if not isinstance(egg_map, dict):
        egg_map = {}

    key = str(int(user_id))

    if _ap_triggers_easter_egg(ap_val):
        # existiert schon? dann behalten, sonst würfeln
        if key in egg_map and str(egg_map.get(key) or "").strip():
            return str(egg_map[key])
        txt = random.choice(
            EASTER_EGG_TEXT_POOL) if EASTER_EGG_TEXT_POOL else "✨"
        egg_map[key] = txt
        data["easter_egg_texts"] = egg_map
        return txt

    # triggert nicht -> entfernen
    if key in egg_map:
        egg_map.pop(key, None)
        data["easter_egg_texts"] = egg_map
    return None


def _fmt_player_with_ap_and_egg(mention: str, ap_val: Optional[str], egg_text: Optional[str]) -> str:
    ap_disp = _fmt_thousands_de(ap_val) if ap_val else None
    base = f"{mention} ({ap_disp} AP)" if ap_disp else mention
    if egg_text:
        return f"{base} ✨ {egg_text}"
    return base


def _fmt_player_with_ap(mention: str, ap_val: Optional[str]) -> str:
    ap_disp = _fmt_thousands_de(ap_val) if ap_val else None
    return f"{mention} ({ap_disp} AP)" if ap_disp else mention


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
    """
    Extrahiert eine HH:MM (lokal) aus freiem Text.
    Relative Angaben ("in 3h") werden hier NICHT verarbeitet – das macht _extract_start_dt_from_start_text().
    """
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


def _extract_start_dt_from_start_text(day_d: dt.date, start_text: str) -> Optional[dt.datetime]:
    """
    Liefert ein konkretes start_dt (Europe/Berlin), wenn parsebar.
    Unterstützt zusätzlich:
      - "in 3h", "in 45m", "in 2 std", "in 30 min"
    ABER nur, wenn day_d == heute (sonst wird's semantisch komisch).
    """
    t = (start_text or "").strip().lower()
    if not t:
        return None

    today = _now_local().date()

    # ✅ Relative: "in X h/min" – nur wenn Tag == heute
    m = _REL_TIME_RE.search(t)
    if m:
        if day_d != today:
            return None

        n = int(m.group("n"))
        unit = (m.group("unit") or "").lower()

        now = _now_local()
        if unit in ("h", "std", "stunde", "stunden"):
            return (now + dt.timedelta(hours=n)).replace(second=0, microsecond=0)
        if unit in ("m", "min", "mins", "minute", "minuten"):
            return (now + dt.timedelta(minutes=n)).replace(second=0, microsecond=0)

        return None

    # ✅ Absolute / "jetzt" / Fenster / Fixzeit über bestehende Logik
    hm = _extract_start_time_from_start_text(start_text)
    if not hm:
        return None

    h, m2 = hm
    tz = BERLIN

    # 24:00 → nächster Tag 00:00 (lokale Zeit)
    if h == 24 and m2 == 0:
        return dt.datetime.combine(
            day_d + dt.timedelta(days=1),
            dt.time(0, 0),
            tzinfo=tz,
        )

    return dt.datetime.combine(
        day_d,
        dt.time(h, m2),
        tzinfo=tz,
    )


def _build_start_dt_if_possible(data: dict) -> Optional[dt.datetime]:
    day_iso = str(data.get("day_date_iso") or "").strip()
    if not day_iso:
        return None
    try:
        day_d = dt.date.fromisoformat(day_iso)
    except Exception:
        return None

    start_text = str(data.get("start_text") or "")
    return _extract_start_dt_from_start_text(day_d, start_text)


def _end_of_day_2359(day_d: dt.date) -> dt.datetime:
    """
    23:59 lokal (Europe/Berlin). Absichtlich ohne Sekunden.
    Beispiel: 15.02 23:59:59 -> Basis wird 15.02 23:59.
    """
    return dt.datetime.combine(day_d, dt.time(23, 59), tzinfo=BERLIN)


def _build_auto_close_dt(data: dict) -> Optional[dt.datetime]:
    """
    Auto-Close Regel:
    - wenn start_dt parsebar: start_dt + 24h
    - sonst: (day_d 23:59) + 24h
    """
    day_iso = str(data.get("day_date_iso") or "").strip()
    if not day_iso:
        return None
    try:
        day_d = dt.date.fromisoformat(day_iso)
    except Exception:
        return None

    start_dt = _build_start_dt_if_possible(data)
    base = start_dt if start_dt else _end_of_day_2359(day_d)

    return base + dt.timedelta(hours=24)


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


def _allowed_party_range(category: str, spot_key: Optional[str] = None) -> Tuple[int, int]:
    ui = _ui_for(category)
    return (int(ui["party_min"]), int(ui["party_max"]))


def _default_req_for(data: dict) -> str:
    cat = data.get("category")
    if cat == "muhhelfer":
        diff = data.get("difficulty", "normal")
        return AKVK_SCHWER if diff == "schwer" else AKVK_NORMAL

    if cat == "spots":
        spot = data.get("spot_key", "")
        if spot == "olun":
            tier = str(data.get("olun_tier") or "normal").lower()
            return OLUN_REQ.get(tier, "")
        return SPOT_REQ.get(spot, "")

    return ""


def _normalize_atoraxxion_runs(data: dict) -> list[str]:
    """
    Normalisiert die Atoraxxion-Auswahl zu Keys:
    vahmalkea / sycrakea / yolunakea / orzekea

    Unterstützt:
    - neue Form:  atoraxxion_runs: list[str]
    - legacy:     atoraxxion_run: str
    - legacy:     "full" => kompletter Run
    """
    ALL_KEYS = ["vahmalkea", "sycrakea", "yolunakea", "orzekea"]

    raw = data.get("atoraxxion_runs")
    if raw is None:
        raw = data.get("atoraxxion_run")  # legacy single

    # String-Fälle (legacy)
    if isinstance(raw, str):
        v = raw.strip().lower()
        if not v:
            return []
        if v in ("full", "komplett", "complete", "all"):
            return ALL_KEYS.copy()
        return [v]

    # Listen/Set/Tuple
    if isinstance(raw, (list, tuple, set)):
        out: list[str] = []
        for x in raw:
            if x is None:
                continue
            s = str(x).strip().lower()
            if s:
                out.append(s)

        # Wenn irgendwo "full" drin steckt -> Full Run
        if "full" in out:
            return ALL_KEYS.copy()

        # Optional: Dedupe bei Mehrfachauswahl
        seen = set()
        deduped: list[str] = []
        for k in out:
            if k not in seen:
                seen.add(k)
                deduped.append(k)
        return deduped

    return []

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
    olun_tier: Optional[str] = None  # spots/olun: "normal"|"dehkia1"|"dehkia2"

    max_players: Optional[int] = None

    scroll_amount: Optional[str] = None  # pilafe required on create
    duration_text: Optional[str] = None
    start_text: Optional[str] = None
    req_text: Optional[str] = None
    notes: Optional[str] = None
    own_ap: Optional[str] = None

    # Atoraxxion: 4 Einzelstufen + 1 Komplett-Run
    # "t1" | "t2" | "t3" | "t4" | "full"
    atoraxxion_runs: List[str] = field(default_factory=list)

    # Altar des Blutes
    altar_cleared_step: Optional[int] = None
    altar_target_step: Optional[int] = None


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
            await self.on_done.__self__._ephemeral_notice(interaction, "Ungültiges Datum. Bitte versuche es erneut.")
            return

        today = _now_local().date()
        if d < today:
            await self.on_done.__self__._ephemeral_notice(interaction, "Das Datum darf nicht in der Vergangenheit liegen.")
            return

        await self.on_done(interaction, d)


class DetailsModal(discord.ui.Modal):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession, defaults: Optional[dict] = None):
        super().__init__(title="Details zur Gruppensuche")
        self.cog = cog
        self.session = session
        self.defaults = defaults or {}
        current_own_ap = self.defaults.get("own_ap") or ""
        # ✅ AP nur im Create-Wizard anzeigen (Edit bekommt AP separat als Button)
        if session.mode == "create":
            self.own_ap = discord.ui.TextInput(
                label="Deine AP",
                placeholder="z.B. 301",
                required=True,
                default=str(session.own_ap or ""),
                max_length=10,
            )
        if hasattr(self, "own_ap"):
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
            default=_fmt_thousands_de(current_amount) if str(
                current_amount or "").strip() else None
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
        req_default_value = None
        if session.mode == "edit":
            existing_req = str(self.defaults.get("req_text") or "").strip()
            if existing_req:
                req_default_value = existing_req

        cat = (session.category or "").lower()

        # Standard (muhhelfer/spots): AK/VK
        req_label = "Gewünschte AK/VK (optional)"
        req_placeholder = f"Empfohlen: {current_req}" if current_req else "z.B. 370+ AP / 440+ VK"

        # ✅ Atoraxxion/Altar: gewünschte AP
        if cat in ("atoraxxion", "altar"):
            req_label = "Gewünschte AP (optional)"
            # current_req kommt ggf. aus defaults/req_default (bei atto oft leer) – das ist ok
            req_placeholder = "z.B. 300+ (oder 301+)" if not current_req else f"Empfohlen: {current_req}"

        self.req_text = discord.ui.TextInput(
            label=req_label,
            placeholder=req_placeholder,
            required=False,
            max_length=60,
            default=req_default_value,
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
        # ✅ NICHT sofort defer() – erst validieren!

        def _invalid_number(msg: str):
            return interaction.response.send_message(
                msg,
                ephemeral=True,
                view=_ReopenModalView(lambda: type(self)(
                    self.cog, self.session, defaults=self.defaults)),
            )

        # ---------- AP ----------
        own_ap_val = str(self.own_ap.value).strip(
        ) if hasattr(self, "own_ap") else ""

        # Create: Pflicht
        if self.session.mode == "create" and not own_ap_val:
            await _invalid_number("❌ **AP ist Pflicht.** Bitte nur Zahlen eintragen (z.B. `301`).")
            return

        # Wenn gesetzt: Zahlenformat prüfen
        if own_ap_val:
            ap_int = _parse_int_strict(own_ap_val)
            if ap_int is None:
                await _invalid_number("❌ **AP ungültig.** Beispiele: `300`, `396`, `250`, ...")
                return
            # ✅ Speichern wie bisher als digits-only string (kompatibel zu deinem Restcode)
            self.session.own_ap = str(ap_int)

        # ---------- PilaFe Menge ----------
        if self.session.category == "pilafe":
            raw = str(self.scroll_amount.value).strip()

            if self.session.mode == "create" and not raw:
                await _invalid_number("❌ **Bei Pila Fe ist die Menge Pflicht.**")
                return

            if raw:
                amt = _parse_int_strict(raw)
                if amt is None:
                    await _invalid_number("❌ **Menge ungültig.** Erlaubt: `10`, `1.000`, `1 000`, `1,000`.")
                    return
                self.session.scroll_amount = str(amt)

        # ✅ ab hier "acknowledge" (Modal schließt zuverlässig)
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        duration_val = str(self.duration_text.value).strip()
        start_val = str(self.start_text.value).strip()
        req_val = str(self.req_text.value).strip()
        notes_val = str(self.notes.value).strip()

        if self.session.mode == "create":
            self.session.duration_text = duration_val or None
            self.session.start_text = start_val or None
            self.session.req_text = req_val or None
            self.session.notes = notes_val or None
        else:
            # Edit: nur überschreiben, wenn User etwas eingibt
            if duration_val != "":
                self.session.duration_text = duration_val
            if start_val != "":
                self.session.start_text = start_val
            if req_val != "":
                self.session.req_text = req_val
            if notes_val != "":
                self.session.notes = notes_val

        # Ab hier NICHT die Modal-Interaction verwenden,
        # sondern die Interaction, die das Wizard-Ephemeral besitzt.
        base_interaction = self.session.wizard_interaction or interaction

        if self.session.mode == "create":
            await self.cog._create_public_post_from_session(base_interaction, self.session)
            return

        await self.cog._apply_edit_details(base_interaction, self.session)


class _ReopenModalView(discord.ui.View):
    def __init__(self, modal_factory, *, timeout: int = 60):
        super().__init__(timeout=timeout)
        self._modal_factory = modal_factory

    @discord.ui.button(label="Eingabe korrigieren", style=discord.ButtonStyle.primary, emoji="✏️")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(self._modal_factory())
        except discord.InteractionResponded:
            await interaction.followup.send_modal(self._modal_factory())


class EditDetailsModal(discord.ui.Modal):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(title="Details zur Gruppensuche")
        self.cog = cog
        self.session = session

        # ⚠️ KEIN own_ap hier!

        self.duration = discord.ui.TextInput(
            label="Geplante Dauer",
            placeholder="z.B. 30min, 90min, 2h",
            required=False,
            max_length=50,
            default=str(session.duration_text or ""),
        )
        self.start = discord.ui.TextInput(
            label="Startzeit",
            placeholder="z.B. jetzt, 20Uhr, später",
            required=False,
            max_length=60,
            default=str(session.start_text or ""),
        )
        self.desired_ap = discord.ui.TextInput(
            label="Gewünschte AP (optional)",
            placeholder="z.B. 300+ (oder 301+)",
            required=False,
            max_length=32,
            default=str(session.req_text or ""),
        )
        self.note = discord.ui.TextInput(
            label="Optionale Notizen",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=800,
            default=str(session.notes or ""),
        )

        self.add_item(self.duration)
        self.add_item(self.start)
        self.add_item(self.desired_ap)
        self.add_item(self.note)

        # PilaFe: Scroll-Menge (editierbar) -> nur wenn Kategorie pilafe
        if (session.category or "").lower() == "pilafe":
            self.scroll_amount = discord.ui.TextInput(
                label="Menge an Schriftrollen",
                placeholder="z.B. 1000",
                required=True,
                max_length=16,
                default=str(session.scroll_amount or ""),
            )
            self.add_item(self.scroll_amount)

    async def on_submit(self, interaction: discord.Interaction):
        # numeric check: scroll_amount (falls vorhanden)
        if hasattr(self, "scroll_amount"):
            amt = _parse_int_strict(getattr(self, "scroll_amount").value)
            if amt is None:
                await interaction.response.send_modal(EditDetailsModal(self.cog, self.session))
                return
            self.session.scroll_amount = int(amt)

        self.session.duration_text = str(self.duration.value or "").strip()
        self.session.start_text = str(self.start.value or "").strip()
        self.session.req_text = str(self.desired_ap.value or "").strip()
        self.session.notes = str(self.note.value or "").strip()

        await self.cog._apply_edit_details(interaction, self.session)


class APAdjustModal(discord.ui.Modal):
    def __init__(self, cog: "GruppensucheTest", message_id: int):
        super().__init__(title="AP anpassen")
        self.cog = cog
        self.message_id = int(message_id)

        self.ap_value = discord.ui.TextInput(
            label="Deine AP (nur Zahlen)",
            placeholder="z.B. 301",
            required=True,
            max_length=16,
        )
        self.add_item(self.ap_value)

    async def on_submit(self, interaction: discord.Interaction):
        ap_val = _parse_int_strict(self.ap_value.value)
        if ap_val is None:
            # Modal direkt erneut öffnen (so “fühlt” es sich wie ein Feld-Fehler an)
            await interaction.response.send_modal(APAdjustModal(self.cog, self.message_id))
            return

        await self.cog._apply_ap_adjust(interaction, self.message_id, ap_val)


class JoinApModal(discord.ui.Modal):
    def __init__(self, cog, on_done):
        super().__init__(title="AP bei Anmeldung")
        self.cog = cog
        self.on_done = on_done

        self.ap = discord.ui.TextInput(
            label="Deine AP (Pflicht)",
            placeholder="z.B. 301",
            required=True,
            max_length=16,
        )
        self.add_item(self.ap)

    async def on_submit(self, interaction: discord.Interaction):
        raw = str(self.ap.value).strip()
        ap_int = _parse_int_strict(raw)
        if ap_int is None:
            await interaction.response.send_message(
                "❌ **AP ungültig.** Erlaubt: `3245`, `3.245`, `3 245`, `3,245`.",
                ephemeral=True,
                view=_ReopenModalView(
                    lambda: JoinApModal(self.cog, self.on_done)),
            )
            return

        await self.on_done(interaction, str(ap_int))


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
        options = []

        if FEATURE_MUHHILFER:
            options.append(discord.SelectOption(
                label="Muhhelfer (LoML Bosse)",
                value="muhhelfer",
                emoji=MUHKUH_EMOJI,
            ))

        # Spots nur wenn Master an + mindestens ein Spot an
        if FEATURE_SPOTS and (FEATURE_SPOTS_MIRUMOK or FEATURE_SPOTS_GYFIN or FEATURE_SPOTS_OLUN or FEATURE_SPOTS_EDANIA):
            options.append(discord.SelectOption(
                label="Gruppenspots (Mirumok / Gyfin / Olun / Edania)",
                value="spots",
                emoji=CHEER_EMOJI,
            ))
        if FEATURE_PILAFE:
            options.append(discord.SelectOption(
                label="Pila Fe Schriftrollen",
                value="pilafe",
                emoji=PILAFE_EMOJI,
            ))

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
            await self.host_view.cog._ephemeral_notice(interaction, "Das kannst nur du bedienen.")
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
        self.host_view.session.olun_tier = None
        self.host_view.session.atoraxxion_runs.clear()
        self.host_view.session.altar_cleared_step = None
        self.host_view.session.altar_target_step = None

        # und weiter im Flow (zentraler Router)
        await self.host_view.cog._goto_next(interaction, self.host_view.session, Step.START)


class StartView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(cog, session)
        self.add_item(StartSelect(self))

    def embed(self) -> discord.Embed:
        lines = []

        # Muhhelfer
        if FEATURE_MUHHILFER:
            lines.append("• **Muhhelfer (LoML Bosse)**")
        else:
            lines.append("• ~~Muhhelfer (LoML Bosse)~~ *(Wartung)*")

        # Gruppenspots (Master + mindestens ein Spot aktiv)
        spots_enabled = FEATURE_SPOTS and (
            FEATURE_SPOTS_MIRUMOK or FEATURE_SPOTS_GYFIN or FEATURE_SPOTS_OLUN or FEATURE_SPOTS_EDANIA)
        if spots_enabled:
            lines.append(
                "• **Gruppenspots (Mirumok / Gyfin / Olun / Edania)**")
        else:
            lines.append(
                "• ~~Gruppenspots (Mirumok / Gyfin / Olun / Edania)~~ *(Wartung)*")

        # Pila Fe
        if FEATURE_PILAFE:
            lines.append("• **Pila Fe Schriftrollen**")
        else:
            lines.append("• ~~Pila Fe Schriftrollen~~ *(Wartung)*")

        # Altar (immer anzeigen, aber Wartung wenn aus)
        if FEATURE_ALTAR:
            lines.append("• **Altar des Blutes**")
        else:
            lines.append("• ~~Altar des Blutes~~ *(Wartung)*")

        # Atoraxxion (immer anzeigen, aber Wartung wenn aus)
        if FEATURE_ATORAXXION:
            lines.append("• **Atoraxxion**")
        else:
            lines.append("• ~~Atoraxxion~~ *(Wartung)*")

        desc = (
            "Wähle, wofür du eine Gruppe suchst.\n\n"
            + "\n".join(lines)
            + "\n\nNach der Auswahl kannst du Details wie **Menge**, **Geplante Dauer** und **Startzeit** angeben."
        )

        return discord.Embed(
            title=f"{MUHKUH_EMOJI} Gruppensuche erstellen",
            description=desc,
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

                self.session.day_date_iso = iso_val
                self._refresh_day_styles()

                if self.session.mode == "edit":
                    await interaction.response.edit_message(embed=self.embed(), view=self)
                    await self.cog._apply_edit_day(interaction, self.session)
                    return

                # ✅ create-mode: nicht edit_message + goto_next
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

        self.add_item(build_back_button("Schwierigkeit",
                      BackTarget.DIFFICULTY, self, row=2))

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
                    await self.cog._ephemeral_notice(interaction, "Maximal 5 Runs insgesamt möglich.", ephemeral=True)
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
            await self.cog._ephemeral_notice(interaction, "Bitte wähle mindestens 1 Boss.", ephemeral=True)
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

        self.add_item(build_back_button(
            "Bosse", BackTarget.BOSSES, self, row=2))

        next_label = "Speichern" if session.mode == "edit" else "Weiter"
        next_btn = discord.ui.Button(
            label=next_label, style=discord.ButtonStyle.success, row=2)
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
                    await self.cog._ephemeral_notice(interaction, "Keine freien Runs mehr. Maximal 5 Runs insgesamt.", ephemeral=True)
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

        # Wenn nur genau ein Spot aktiv ist, auto-auswählen und direkt weiter
        active_spots = []
        if FEATURE_SPOTS_MIRUMOK:
            active_spots.append("mirumok")
        if FEATURE_SPOTS_GYFIN:
            active_spots.append("gyfin")
        if FEATURE_SPOTS_OLUN:
            active_spots.append("olun")
        if FEATURE_SPOTS_EDANIA:
            active_spots.append("edania")

        # Keine Spots aktiv -> zurück ins Start-Menü
        if not active_spots:
            session.spot_key = None
            # Hier kein interaction verfügbar, also nur UI bauen (wird eh durch Router abgefangen)
        elif len(active_spots) == 1:
            session.spot_key = active_spots[0]
            # Der eigentliche "weiter" passiert über Router nach Auswahl –
            # das Auto-Weiter kannst du optional in _send_spot_select machen (siehe unten).

        # Buttons nur für aktive Spots
        if FEATURE_SPOTS_MIRUMOK:
            miru_btn = discord.ui.Button(
                label="Mirumok", style=discord.ButtonStyle.primary, row=0)
            miru_btn.callback = self._pick_miru
            self.add_item(miru_btn)

        if FEATURE_SPOTS_GYFIN:
            gyfin_btn = discord.ui.Button(
                label="Gyfin", style=discord.ButtonStyle.primary, row=0)
            gyfin_btn.callback = self._pick_gyfin
            self.add_item(gyfin_btn)

        if FEATURE_SPOTS_OLUN:
            olun_btn = discord.ui.Button(
                label="Olun", style=discord.ButtonStyle.primary, row=0)
            olun_btn.callback = self._pick_olun
            self.add_item(olun_btn)

        if FEATURE_SPOTS_EDANIA:
            edania_btn = discord.ui.Button(
                label="Edania", style=discord.ButtonStyle.primary, row=0)
            edania_btn.callback = self._pick_edania
            self.add_item(edania_btn)

        self.add_item(build_back_button(
            "Kategorie", BackTarget.START, self, row=1))

    async def _pick_miru(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        if not FEATURE_SPOTS_MIRUMOK:
            await self.cog._ephemeral_notice(interaction, "Mirumok ist aktuell deaktiviert.", ephemeral=True)
            return
        self.session.spot_key = "mirumok"
        await self.cog._goto_next(interaction, self.session, Step.SPOT)

    async def _pick_gyfin(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        if not FEATURE_SPOTS_GYFIN:
            await self.cog._ephemeral_notice(interaction, "Gyfin ist aktuell deaktiviert.", ephemeral=True)
            return
        self.session.spot_key = "gyfin"
        await self.cog._goto_next(interaction, self.session, Step.SPOT)

    def embed(self) -> discord.Embed:
        lines = ["Wähle den Spot, für den du eine Gruppe suchst.\n"]

        if FEATURE_SPOTS_MIRUMOK:
            lines.append(
                f"**Mirumok**\n• Empfohlen mind. {SPOT_REQ['mirumok']}\n• {SPOT_TOTAL_AP['mirumok']}\n"
            )
        if FEATURE_SPOTS_GYFIN:
            lines.append(
                f"**Gyfin**\n• Empfohlen mind. {SPOT_REQ['gyfin']}\n• {SPOT_TOTAL_AP['gyfin']}\n"
            )
        if FEATURE_SPOTS_OLUN:
            lines.append(
                "**Olun**\n"
                f"• Normal → Empfohlen mind. {OLUN_REQ['normal']} | {OLUN_TOTAL_AP['normal']}\n"
                f"• Dehkia 1 → Empfohlen mind. {OLUN_REQ['dehkia1']} | {OLUN_TOTAL_AP['dehkia1']}\n"
                f"• Dehkia 2 → Empfohlen mind. {OLUN_REQ['dehkia2']} | {OLUN_TOTAL_AP['dehkia2']}\n"
            )

        if FEATURE_SPOTS_EDANIA:
            lines.append(
                f"**Edania**\n• Empfohlen mind. {SPOT_REQ['edania']}\n• {SPOT_TOTAL_AP['edania']}\n"
            )

        # Wenn nur einer aktiv ist, Text sauber halten
        desc = "\n".join(lines).strip()

        return discord.Embed(
            title=f"{CHEER_EMOJI} Gruppensuche – Spots",
            description=desc,
        )

    async def _pick_olun(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        self.session.spot_key = "olun"
        self.session.olun_tier = None  # wichtig: Stufe danach wählen
        await self.cog._goto_next(interaction, self.session, Step.SPOT)

    async def _pick_edania(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        if not FEATURE_SPOTS_EDANIA:
            await self.cog._ephemeral_notice(interaction, "Edania ist aktuell deaktiviert.", ephemeral=True)
            return
        self.session.spot_key = "edania"
        await self.cog._goto_next(interaction, self.session, Step.SPOT)


class OlunTierView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(cog, session)

        self.btn_normal = discord.ui.Button(
            label="Normal", style=discord.ButtonStyle.primary, row=0
        )
        self.btn_d1 = discord.ui.Button(
            label="Dehkia 1", style=discord.ButtonStyle.primary, row=0
        )
        self.btn_d2 = discord.ui.Button(
            label="Dehkia 2", style=discord.ButtonStyle.primary, row=0
        )

        self.btn_normal.callback = self._pick("normal")
        self.btn_d1.callback = self._pick("dehkia1")
        self.btn_d2.callback = self._pick("dehkia2")

        self.add_item(self.btn_normal)
        self.add_item(self.btn_d1)
        self.add_item(self.btn_d2)

        self.add_item(build_back_button("Spot", BackTarget.SPOT, self, row=1))

        self._refresh_styles()

    def _refresh_styles(self):
        chosen = (self.session.olun_tier or "").lower()

        # default: alles blau (damit es sich vom Zurück-Button unterscheidet)
        self.btn_normal.style = discord.ButtonStyle.primary
        self.btn_d1.style = discord.ButtonStyle.primary
        self.btn_d2.style = discord.ButtonStyle.primary

        # selected: grün
        if chosen == "normal":
            self.btn_normal.style = discord.ButtonStyle.success
        elif chosen == "dehkia1":
            self.btn_d1.style = discord.ButtonStyle.success
        elif chosen == "dehkia2":
            self.btn_d2.style = discord.ButtonStyle.success

    def _pick(self, tier: str):
        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.session.user_id:
                await interaction.response.defer()
                return

            self.session.olun_tier = tier
            # ✅ kein edit_message als "Feedback" hier
            await self.cog._goto_next(interaction, self.session, Step.OLUN_TIER)
        return _cb

    def embed(self) -> discord.Embed:
        tier = (self.session.olun_tier or "").lower()

        def _line(key: str, label: str) -> str:
            req = OLUN_REQ.get(key, "—")
            total = OLUN_TOTAL_AP.get(key, "—")
            picked = (tier == key)
            mark = "✅ " if picked else "• "
            return f"{mark}**{label}:** {req} | {total}"

        chosen_label = _olun_tier_label(tier) if tier else "—"

        info_block = "\n".join([
            _line("normal", "Normal"),
            _line("dehkia1", "Dehkia 1"),
            _line("dehkia2", "Dehkia 2"),
        ])

        return discord.Embed(
            title=f"{OLUN_EMOJI} Olun – Stufe",
            description=(
                "Wähle die Stufe für **Olun**.\n\n"
                f"**Auswahl:** {chosen_label}\n\n"
                f"{info_block}\n"
            ),
        )


class AtoraxxionRunView(WizardBaseView):
    """
    Atoraxxion: Mehrfachauswahl (4 Dungeons) + Schnellwahl "Kompletter Run".
    - Kein extra Ephemeral
    - Weiter nur wenn mind. 1 Dungeon gewählt
    - Wenn alle 4 gewählt -> wie "Kompletter Run" behandeln
    """

    def __init__(self, cog: "GruppensucheTest", session: WizardSession, back_target: str):
        super().__init__(cog, session, timeout_seconds=WIZARD_TIMEOUT_SECONDS)

        # nur die 4 Dungeons (ohne "full")
        self._dungeon_runs: list[tuple[str, str]] = [
            ("vahmalkea", "Vahmalkea"),
            ("sycrakea", "Sycrakea"),
            ("yolunakea", "Yolunakea"),
            ("orzekea", "Orzekea"),
        ]
        self._all_keys = {k for k, _ in self._dungeon_runs}

        if not isinstance(getattr(self.session, "atoraxxion_runs", None), list):
            self.session.atoraxxion_runs = []

        # Toggle-Buttons (Row 0)
        self._run_buttons: dict[str, discord.ui.Button] = {}
        for idx, (key, label) in enumerate(self._dungeon_runs):
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary,
                row=0,
            )
            btn.callback = self._make_toggle_cb(key)
            self._run_buttons[key] = btn
            self.add_item(btn)

        # Schnellwahl: Kompletter Run (Row 1, solo)
        full_btn = discord.ui.Button(
            label="Kompletter Run",
            style=discord.ButtonStyle.primary,
            row=1,
        )
        full_btn.callback = self._pick_full
        self.add_item(full_btn)

        next_label = "Speichern" if self.session.mode == "edit" else "Weiter"

        next_btn = discord.ui.Button(
            label=next_label,
            style=discord.ButtonStyle.success,
            row=1,
        )
        next_btn.callback = self._next
        self.add_item(next_btn)

        # Zurück (Row 2)
        self.add_item(build_back_button("Kategorie", back_target, self, row=2))

        self._refresh_styles()

    def embed(self) -> discord.Embed:
        chosen = set(self.session.atoraxxion_runs or [])
        chosen = chosen & self._all_keys

        if chosen == self._all_keys and len(self._all_keys) == 4:
            selection_line = "**Auswahl:** Kompletter Run"
        elif chosen:
            names = [label for (k, label) in self._dungeon_runs if k in chosen]
            selection_line = "**Auswahl:** " + " • ".join(names)
        else:
            selection_line = "**Auswahl:** —"

        return discord.Embed(
            title="🏛️ Gruppensuche – Atoraxxion",
            description=(
                "Wähle einen oder mehrere Dungeons.\n"
                "• **Kompletter Run** = alle 4\n"
                "• **Weiter** erst, wenn mindestens 1 Dungeon gewählt ist\n\n"
                f"{selection_line}"
            ),
        )

    def _refresh_styles(self):
        chosen = set(self.session.atoraxxion_runs or [])
        chosen = chosen & self._all_keys

        # wenn alle 4 gewählt: alles grün
        for k, btn in self._run_buttons.items():
            btn.style = discord.ButtonStyle.success if (
                k in chosen) else discord.ButtonStyle.secondary

    def _make_toggle_cb(self, key: str):
        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.session.user_id:
                await interaction.response.defer()
                return

            chosen = set(self.session.atoraxxion_runs or [])
            chosen = chosen & self._all_keys

            if key in chosen:
                chosen.remove(key)
            else:
                chosen.add(key)

            # wenn alle 4 -> wie kompletter Run behandeln
            if chosen == self._all_keys:
                self.session.atoraxxion_runs = list(self._all_keys)
            else:
                self.session.atoraxxion_runs = list(chosen)

            self._refresh_styles()
            await interaction.response.edit_message(embed=self.embed(), view=self)

        return _cb

    async def _pick_full(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        self.session.atoraxxion_runs = list(self._all_keys)
        self._refresh_styles()

        # ✅ EDIT: direkt speichern
        if self.session.mode == "edit":
            await self.cog._apply_edit_atoraxxion_runs(interaction, self.session)
            return

        await self.cog._goto_next(interaction, self.session, Step.atoraxxion_runs)

    async def _next(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        chosen = set(self.session.atoraxxion_runs or [])
        chosen = chosen & self._all_keys
        if not chosen:
            await self.cog._ephemeral_notice(interaction, "Bitte wähle mindestens einen Dungeon aus.", ephemeral=True)
            return

        if chosen == self._all_keys:
            self.session.atoraxxion_runs = list(self._all_keys)
        else:
            self.session.atoraxxion_runs = list(chosen)

        # ✅ EDIT: direkt speichern
        if self.session.mode == "edit":
            await self.cog._apply_edit_atoraxxion_runs(interaction, self.session)
            return

        await self.cog._goto_next(interaction, self.session, Step.atoraxxion_runs)


class AltarStepSelect(discord.ui.Select):
    def __init__(self, host_view: "AltarStepView", which: str, current: Optional[int] = None):
        self.host_view = host_view
        self.which = which

        options = []
        for n in range(1, 22):
            label = f"Step {n}"
            if which == "cleared":
                desc = "Höchster bereits geclearter Step"
            else:
                desc = "Geplanter Ziel-Step"
            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(n),
                    description=desc,
                    default=(current == n),
                )
            )

        placeholder = "Höchster geclearter Step..." if which == "cleared" else "Geplanter Ziel-Step..."
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
            row=0 if which == "cleared" else 1,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.host_view.session.user_id:
            await self.host_view.cog._ephemeral_notice(interaction, "Das kannst nur du bedienen.")
            return

        picked = int(self.values[0])

        if self.which == "cleared":
            self.host_view.session.altar_cleared_step = picked
        else:
            self.host_view.session.altar_target_step = picked

        await interaction.response.edit_message(
            embed=self.host_view.embed(),
            view=self.host_view,
        )


class AltarStepView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession):
        super().__init__(cog, session)

        self.add_item(AltarStepSelect(self, "cleared", session.altar_cleared_step))
        self.add_item(AltarStepSelect(self, "target", session.altar_target_step))

        self.add_item(build_back_button("Größe", BackTarget.DAY, self, row=2))

        next_label = "Speichern" if session.mode == "edit" else "Weiter"
        next_btn = discord.ui.Button(
            label=next_label,
            style=discord.ButtonStyle.success,
            row=2,
        )
        next_btn.callback = self._next
        self.add_item(next_btn)

    async def _next(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        if self.session.altar_cleared_step is None:
            await self.cog._ephemeral_notice(interaction, "Bitte wähle den höchsten geclearten Step.")
            return

        if self.session.altar_target_step is None:
            await self.cog._ephemeral_notice(interaction, "Bitte wähle den Ziel-Step.")
            return

        if self.session.altar_target_step <= self.session.altar_cleared_step:
            await self.cog._ephemeral_notice(
                interaction,
                "Der Ziel-Step muss höher sein als der bereits geclearte Step.",
            )
            return

        if self.session.mode == "edit":
            await self.cog._apply_edit_altar_steps(interaction, self.session)
            return

        await self.cog._goto_next(interaction, self.session, Step.ALTAR_STEP)

    def embed(self) -> discord.Embed:
        cleared = self.session.altar_cleared_step
        target = self.session.altar_target_step

        cleared_txt = f"Step {cleared}" if cleared is not None else "—"
        target_txt = f"Step {target}" if target is not None else "—"

        return discord.Embed(
            title="🩸 Gruppensuche – Altar des Blutes",
            description=(
                "Wähle den Gruppenfortschritt für den Altar.\n\n"
                f"**Höchster geclearter Step:** {cleared_txt}\n"
                f"**Geplanter Ziel-Step:** {target_txt}\n\n"
                "Regel: Der Ziel-Step muss höher sein als der bereits geclearte Step."
            ),
        )

class PartySizeSelect(discord.ui.Select):
    def __init__(self, host_view: "PartySizeView", min_n: int, max_n: int, current: Optional[int]=None):
        options=[]
        for n in range(min_n, max_n + 1):
            opt=discord.SelectOption(
                label=str(n), value=str(n), default=(current == n))
            options.append(opt)

        super().__init__(
            placeholder="Wähle die maximale Teilnehmerzahl (inkl. dir)...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.host_view=host_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.host_view.session.user_id:
            await self.host_view.cog._ephemeral_notice(interaction, "Das kannst nur du bedienen.")
            return

        self.host_view.session.max_players=int(self.values[0])

        # ✅ Create: Flow zentral über Router
        if self.host_view.session.mode == "create":
            await self.host_view.cog._goto_next(interaction, self.host_view.session, Step.PARTY)
            return

        # ✅ Edit: ACK-sicher, damit Discord kein "Interaktion fehlgeschlagen" zeigt
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        await self.host_view.cog._apply_edit_max_players(interaction, self.host_view.session)

# 1) PartySizeView: Minimum für Admins auf 1 runterziehen (für ALLES)


class PartySizeView(WizardBaseView):
    def __init__(
        self,
        cog: "GruppensucheTest",
        session: WizardSession,
        current: Optional[int]=None,
        *,
        allow_one: bool=False,
    ):
        super().__init__(cog, session)
        self.allow_one=bool(allow_one)

        mn, mx=_allowed_party_range(session.category or "", session.spot_key)

        # ✅ Admin-only: 1 immer erlauben (kategorieneutral)
        if self.allow_one:
            mn=1

        self.add_item(PartySizeSelect(self, mn, mx, current=current))
        self.add_item(build_back_button("Tag", BackTarget.DAY, self, row=1))

    def embed(self) -> discord.Embed:
        mn, mx=_allowed_party_range(
            self.session.category or "", self.session.spot_key)

        # ✅ Text soll die gleiche Range zeigen wie das Select
        if self.allow_one:
            mn=1

        if self.session.category == "muhhelfer":
            diff="Schwer" if self.session.difficulty == "schwer" else "Normal"
            req=AKVK_SCHWER if self.session.difficulty == "schwer" else AKVK_NORMAL
            return discord.Embed(
                title=f"{MUHKUH_EMOJI} Muhhelfer – Gruppengröße",
                description=(
                    f"Schwierigkeit: {diff}\n"
                    f"Empfohlen mind. AK/VK: {req}\n\n"
                    f"{_party_size_help_text(mn, mx)}"
                ),
            )

        if self.session.category == "spots" and self.session.spot_key:
            spot=self.session.spot_key
            if spot == "mirumok":
                emoji=MIRUMOK_EMOJI
            elif spot == "gyfin":
                emoji=GYFIN_EMOJI
            elif spot == "olun":
                emoji=OLUN_EMOJI
            else:
                emoji=CHEER_EMOJI

            if spot == "olun":
                tier=(self.session.olun_tier or "normal").lower()
                req=OLUN_REQ.get(tier, "")
                total=OLUN_TOTAL_AP.get(tier, "")
                tier_label=_olun_tier_label(tier)

                return discord.Embed(
                    title=f"{emoji} Olun ({tier_label}) – Gruppengröße",
                    description=(
                        f"• Empfohlen mind. {req}\n"
                        f"• {total}\n\n"
                        f"{_party_size_help_text(mn, mx)}"
                    ),
                )

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

        # ✅ Altar / Atoraxxion: gleiche Party-UI wie Standard
        if (self.session.category or "").lower() == "altar":
            return discord.Embed(
                title="🩸 Gruppensuche – Altar des Blutes",
                description=_party_size_help_text(mn, mx),
            )

        if (self.session.category or "").lower() == "atoraxxion":
            return discord.Embed(
                title="🏛️ Gruppensuche – Atoraxxion",
                description=_party_size_help_text(mn, mx),
            )

        return discord.Embed(title="Gruppengröße", description=_party_size_help_text(mn, mx))

# =========================
# Edit Menu (ephemeral)
# =========================


class EditMenuView(WizardBaseView):
    def __init__(self, cog: "GruppensucheTest", session: WizardSession, post_data: dict):
        super().__init__(cog, session)
        self.post_data=post_data
        self.message_id=int(session.edit_message_id or 0)

        tag_btn=discord.ui.Button(
            label="Tag ändern", style=discord.ButtonStyle.secondary, row=0)
        size_btn=discord.ui.Button(
            label="Max. Teilnehmer ändern", style=discord.ButtonStyle.secondary, row=0)
        details_btn=discord.ui.Button(
            label="Zeiten & Notiz bearbeiten", style=discord.ButtonStyle.secondary, row=1)

        tag_btn.callback=self._tag
        size_btn.callback=self._size
        details_btn.callback=self._details

        self.add_item(tag_btn)
        self.add_item(size_btn)
        self.add_item(details_btn)

        if str(post_data.get("category", "")).lower() == "atoraxxion":
            dungeons_btn=discord.ui.Button(
                label="Dungeons bearbeiten", style=discord.ButtonStyle.secondary, row=1
            )
            dungeons_btn.callback=self._atoraxxion
            self.add_item(dungeons_btn)

        if str(post_data.get("category", "")).lower() == "altar":
            altar_btn = discord.ui.Button(
                label="Altar-Step bearbeiten", style=discord.ButtonStyle.secondary, row=1
            )
            altar_btn.callback = self._altar
            self.add_item(altar_btn)

        back_btn=discord.ui.Button(
            label="Bearbeitung beenden", style=discord.ButtonStyle.secondary, row=2)
        back_btn.callback=self._back
        self.add_item(back_btn)

    async def _altar(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        self.session.wizard_interaction = interaction
        await self.cog._send_altar_steps(interaction, self.session)


    @ discord.ui.button(label="AP anpassen", style=discord.ButtonStyle.secondary, row=1)
    async def edit_ap(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(APAdjustModal(self.cog, self.message_id))
        except discord.InteractionResponded:
            await interaction.followup.send_modal(APAdjustModal(self.cog, self.message_id))

    async def _tag(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        # ✅ wichtig: wizard_interaction auf die aktuelle Ephemeral-Message setzen
        self.session.wizard_interaction=interaction
        await self.cog._send_day_selection(interaction, self.session)

    # --- EditMenuView._size: allow_one berechnen und übergeben ---
    async def _size(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        self.session.wizard_interaction=interaction

        current=int(self.post_data.get("max_players", 2))

        member=interaction.user if isinstance(
            interaction.user, discord.Member) else None
        allow_one=bool(member and _is_admin_only(member))

        view=PartySizeView(self.cog, self.session,
                             current=current, allow_one=allow_one)
        await self.cog._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _details(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return

        # ✅ wichtig
        self.session.wizard_interaction=interaction

        defaults=dict(self.post_data)
        defaults["req_default"]=_default_req_for(self.post_data)

        try:
            await interaction.response.send_modal(DetailsModal(self.cog, self.session, defaults=defaults))
        except discord.InteractionResponded:
            await interaction.followup.send_modal(DetailsModal(self.cog, self.session, defaults=defaults))

    async def _atoraxxion(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.defer()
            return
        # ✅ wichtig
        self.session.wizard_interaction=interaction
        await self.cog._send_atoraxxion_runs(interaction, self.session, back_target=BackTarget.EDIT_MENU)

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
        self.cog=cog
        self.message_id=message_id
        self.action=action  # "close" | "delete"
        self.user_id=user_id

        if action == "close":
            self.text=(
                "Möchtest du diese Suche wirklich schließen?\n"
                "Danach sind keine Anmeldungen/Pings mehr möglich (du kannst sie später wieder öffnen)."
            )
            confirm_label="🔒 Ja, schließen"
        else:
            self.text=(
                "Möchtest du diese Suche wirklich endgültig löschen?\n"
                "⚠️ Dieser Vorgang kann nicht rückgängig gemacht werden."
            )
            confirm_label="🗑 Ja, endgültig löschen"

        confirm_btn=discord.ui.Button(
            label=confirm_label, style=discord.ButtonStyle.danger)
        cancel_btn=discord.ui.Button(
            label="❌ Abbrechen", style=discord.ButtonStyle.secondary)

        confirm_btn.callback=self._confirm
        cancel_btn.callback=self._cancel

        self.add_item(confirm_btn)
        self.add_item(cancel_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await self.cog._ephemeral_notice(interaction, "Das kannst nur du bedienen.")
            return False
        return True

    async def _safe_edit_self(self, interaction: discord.Interaction, content: str, view: Optional[discord.ui.View]=None):
        # Primär: die Message bearbeiten, auf der geklickt wurde (bei Ephemeral zuverlässig)
        try:
            if interaction.message:
                await interaction.message.edit(content=content, view=view)
                return
        except Exception:
            pass

        # Falls Interaction noch offen ist: edit_message versuchen
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(content=content, view=view)
                return
        except Exception:
            pass

        # Fallback: Original response
        try:
            await interaction.edit_original_response(content=content, view=view)
        except Exception:
            pass

    async def _cancel(self, interaction: discord.Interaction):
        await self._safe_edit_self(interaction, "Abgebrochen.", view=None)

    async def _confirm(self, interaction: discord.Interaction):
        if self.action == "close":
            # UI sofort "busy" machen (Buttons weg), dann schließen, dann finaler Text
            await self._safe_edit_self(interaction, "Suche wird geschlossen…", view=None)
            await self.cog._close_search(interaction, self.message_id)
            await self._safe_edit_self(interaction, "Suche wurde geschlossen.", view=None)
            self.cog._cleanup_post_lock(self.message_id)
            return

        # delete
        await self._safe_edit_self(interaction, "Suche wird gelöscht…", view=None)
        await self.cog._delete_search(interaction, self.message_id)
        await self._safe_edit_self(interaction, "Suche wurde gelöscht.", view=None)
        self.cog._cleanup_post_lock(self.message_id)


class PublicPostView(discord.ui.View):
    def __init__(self, cog: "GruppensucheTest", message_id: int):
        super().__init__(timeout=None)
        self.cog=cog
        self.message_id=message_id

        join_btn=discord.ui.Button(
            label="Ich bin dabei",
            emoji="✅",
            style=discord.ButtonStyle.success,
            row=0,
            custom_id=f"gst:join:{message_id}",
        )

        leave_btn=discord.ui.Button(
            label="Abmelden",
            emoji="⛔",
            style=discord.ButtonStyle.danger,
            row=0,
            custom_id=f"gst:leave:{message_id}",
        )
        ping_part_btn=discord.ui.Button(
            label="Ping Teilnehmer",
            emoji="📣",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id=f"gst:pingparts:{message_id}",
        )
        ping_part_btn.callback=self._on_ping_participants
        self.add_item(ping_part_btn)

        ping_type_btn=discord.ui.Button(
            label="Ping",
            emoji="🔔",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id=f"gst:pingtype:{message_id}",
        )

        ping_wait_btn=discord.ui.Button(
            label="Ping Warteschlange",
            emoji="🔔",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id=f"gst:pingwait:{message_id}",
        )

        edit_btn=discord.ui.Button(
            label="Bearbeiten",
            emoji="✏️",
            style=discord.ButtonStyle.secondary,
            row=2,
            custom_id=f"gst:edit:{message_id}",
        )

        close_btn=discord.ui.Button(
            label="Schließen",
            emoji="🔒",
            style=discord.ButtonStyle.secondary,
            row=2,
            custom_id=f"gst:close:{message_id}",
        )

        delete_btn=discord.ui.Button(
            label="Löschen",
            emoji="🗑️",
            style=discord.ButtonStyle.secondary,
            row=2,
            custom_id=f"gst:delete:{message_id}",
        )

        join_btn.callback=self._on_join
        leave_btn.callback=self._on_leave
        ping_type_btn.callback=self._on_ping_type
        ping_wait_btn.callback=self._on_ping_wait
        edit_btn.callback=self._on_edit
        close_btn.callback=self._on_close
        delete_btn.callback=self._on_delete

        self.add_item(join_btn)
        self.add_item(leave_btn)
        self.add_item(ping_type_btn)
        self.add_item(ping_wait_btn)
        self.add_item(edit_btn)
        self.add_item(close_btn)
        self.add_item(delete_btn)

    async def _ensure_owner_or_mod(self, interaction: discord.Interaction) -> Optional[dict]:
        data=await self.cog._get_search(self.message_id)
        if data is None:
            await self.cog._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.")
            return None

        owner_id=int(data.get("owner_id", 0))
        member=interaction.user if isinstance(
            interaction.user, discord.Member) else None
        if interaction.user.id != owner_id and not (member and _has_mod_rights(member)):
            await self.cog._ephemeral_notice(interaction, "Das darf nur der Ersteller (oder Admin/Offizier).")
            return None

        return data

    async def _on_join(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        mid=int(self.message_id)

        # AP Modal -> danach in cog._join speichern/refreshen
        async def _done(modal_interaction: discord.Interaction, ap_val: str):
            await self.cog._join(modal_interaction, mid, ap_val)

        try:
            await interaction.response.send_modal(JoinApModal(self.cog, _done))
        except discord.InteractionResponded:
            await interaction.followup.send_modal(JoinApModal(self.cog, _done))

    async def _on_leave(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        mid=int(self.message_id)
        await self.cog._leave(interaction, mid)

    async def _on_ping_participants(self, interaction: discord.Interaction):
        data=await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        await self.cog._ping_participants(interaction, self.message_id, data)

    async def _on_ping_type(self, interaction: discord.Interaction):
        data=await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        await self.cog._ping_type(interaction, self.message_id, data)

    async def _on_ping_wait(self, interaction: discord.Interaction):
        data=await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        await self.cog._ping_wait(interaction, self.message_id, data)

    async def _on_edit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        mid=int(self.message_id)
        await self.cog._start_edit_flow(interaction, mid)

    async def _on_close(self, interaction: discord.Interaction):
        data=await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        v=ConfirmView(self.cog, self.message_id,
                        "close", interaction.user.id)
        await self.cog._ephemeral_notice(interaction, v.text, view=v)

    async def _on_delete(self, interaction: discord.Interaction):
        data=await self._ensure_owner_or_mod(interaction)
        if not data:
            return
        v=ConfirmView(self.cog, self.message_id,
                        "delete", interaction.user.id)
        await self.cog._ephemeral_notice(interaction, v.text, view=v)


class ClosedPostView(discord.ui.View):
    def __init__(self, cog: "GruppensucheTest", message_id: int):
        super().__init__(timeout=None)
        self.cog=cog
        self.message_id=message_id

        open_btn=discord.ui.Button(
            label="Öffnen",
            style=discord.ButtonStyle.success,
            row=0,
            custom_id=f"gst:open:{message_id}",
        )
        open_btn.callback=self._on_open
        self.add_item(open_btn)

    async def _on_open(self, interaction: discord.Interaction):
        data=await self.cog._get_search(self.message_id)
        if data is None:
            await self.cog._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.")
            return

        owner_id=int(data.get("owner_id", 0))
        member=interaction.user if isinstance(
            interaction.user, discord.Member) else None
        if interaction.user.id != owner_id and not (member and _has_mod_rights(member)):
            await self.cog._ephemeral_notice(interaction, "Das darf nur der Ersteller (oder Admin/Offizier).")
            return

        await self.cog._open_search(interaction, self.message_id)


# =========================
# Cog
# =========================

class GruppensucheTest(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot=bot

        self.config=Config.get_conf(
            self, identifier=935771234123, force_registration=True)
        self.config.register_guild(searches={})

        self._sessions: Dict[int, WizardSession]={}
        # --- Concurrency Locks (per Post / message_id) ---
        self._post_locks: Dict[int, asyncio.Lock]={}
        # Lock "Last Used" für Garbage Collection
        self._post_lock_last_used: Dict[int, dt.datetime]={}

        # Optionaler GC Task (räumt alte Locks weg)
        self._locks_gc_task: Optional[asyncio.Task]=self.bot.loop.create_task(
            self._locks_gc_loop())
        # --- Dashboard Debounce ---
        self._dashboard_refresh_tasks: Dict[int, asyncio.Task]={}
        self._dashboard_refresh_pending: Dict[int, bool]={}
        self._dashboard_refresh_delay=2  # Sekunden
        self._dashboard_refresh_retry_delay=5  # Sekunden
        self._startup_task: Optional[asyncio.Task]=self.bot.loop.create_task(
            self._startup_register_views())
        self._reminder_task: Optional[asyncio.Task]=self.bot.loop.create_task(
            self._reminder_loop())
        # --- Edit Notify Debounce (per Post) ---
        self._edit_notify_tasks: Dict[int, asyncio.Task]={}
        self._edit_notify_delay=45  # Sekunden

        # --- Kurzer Interaction-Guard gegen Doppelklicks / Duplicate Interactions ---
        self._interaction_guard: Dict[str, float]={}
        self._interaction_guard_window=2.5

    def cog_unload(self):
        if getattr(self, "_locks_gc_task", None):
            self._locks_gc_task.cancel()
        if self._startup_task and not self._startup_task.done():
            self._startup_task.cancel()
        if self._reminder_task and not self._reminder_task.done():
            self._reminder_task.cancel()
        for t in list(self._edit_notify_tasks.values()):
            if t and not t.done():
                t.cancel()
        self._edit_notify_tasks.clear()

    def _log_console(self, level: str, module: str, event: str, **kwargs):
        base=f"[KUHMUH][{module.upper()}][{event.upper()}][{level.upper()}]"
        if kwargs:
            details=" ".join(f"{k}={v}" for k, v in kwargs.items())
            getattr(log, level.lower(), log.info)(f"{base} {details}")
        else:
            getattr(log, level.lower(), log.info)(base)

    async def _log_event(
        self,
        guild: discord.Guild,
        level: str,
        module: str,
        event: str,
        description: str,
        *,
        channel: Optional[discord.TextChannel]=None,
    ):
        self._log_console(level, module, event, guild_id=guild.id)

        ch=guild.get_channel(LOG_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            return

        emoji_map={
            "info": "ℹ️",
            "warn": "⚠️",
            "error": "❌",
        }
        emoji=emoji_map.get(level.lower(), "ℹ️")

        embed=discord.Embed(
            title=f"{emoji} Kuhmuh System Log",
            description=description + "\n\nTechnische Details siehe Serverkonsole.",
            color=discord.Color.orange() if level.lower() != "error" else discord.Color.red(),
        )

        embed.add_field(name="Modul", value=module, inline=True)
        embed.add_field(name="Event", value=event, inline=True)
        embed.add_field(name="Server", value=guild.name, inline=True)

        if channel:
            embed.add_field(name="Channel", value=channel.mention, inline=True)

        embed.set_footer(text="Kuhmuh Bot • Systemmeldung")

        content=None
        if level.lower() == "error" and DEV_ALERT_ROLE_ID:
            content=f"<@&{DEV_ALERT_ROLE_ID}>"

        try:
            await ch.send(
                content=content,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        except Exception:
            pass

    def _log_info(self, log_category: str, message: str, **fields):
        parts=[f"{k}={v}" for k, v in fields.items()]
        suffix=f" | {' '.join(parts)}" if parts else ""
        log.info(f"[Kuhmuh-Gruppensuche][{log_category}] {message}{suffix}")

    def _log_warning(self, log_category: str, message: str, **fields):
        parts=[f"{k}={v}" for k, v in fields.items()]
        suffix=f" | {' '.join(parts)}" if parts else ""
        log.warning(f"[Kuhmuh-Gruppensuche][{log_category}] {message}{suffix}")

    def _log_error(self, log_category: str, message: str, **fields):
        parts=[f"{k}={v}" for k, v in fields.items()]
        suffix=f" | {' '.join(parts)}" if parts else ""
        log.error(f"[Kuhmuh-Gruppensuche][{log_category}] {message}{suffix}")

    async def _startup_register_views(self):
        await self.bot.wait_until_red_ready()
        await self.bot.wait_until_ready()

        await self._register_all_persistent_views()
        try:
            await self._resume_pending_edit_notifications()
        except Exception:
            pass

        try:
            guild_obj=discord.Object(id=GUILD_ID)
            await self.bot.tree.sync(guild=guild_obj)
        except Exception:
            pass

    async def _register_all_persistent_views(self):
        guild=self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        data=await self.config.guild(guild).searches()
        if not data:
            return

        for mid_str, post in data.items():
            mid=int(mid_str)
            if bool(post.get("is_closed", False)):
                self.bot.add_view(ClosedPostView(self, mid))
            else:
                self.bot.add_view(PublicPostView(self, mid))

    def _expire_session(self, user_id: int):
        if user_id in self._sessions:
            del self._sessions[user_id]

    def _interaction_guard_key(
        self,
        *,
        action: str,
        user_id: int,
        message_id: int=0,
    ) -> str:
        return f"{action}:{int(user_id)}:{int(message_id)}"

    def _interaction_guard_hit(
        self,
        *,
        action: str,
        user_id: int,
        message_id: int=0,
    ) -> bool:
        now_ts=_now_local().timestamp()
        key=self._interaction_guard_key(
            action=action,
            user_id=user_id,
            message_id=message_id,
        )

        last_ts=float(self._interaction_guard.get(key, 0.0))
        if (now_ts - last_ts) < float(self._interaction_guard_window):
            return True

        self._interaction_guard[key]=now_ts

        # kleine opportunistische Bereinigung
        cutoff=now_ts - max(30.0, float(self._interaction_guard_window) * 4.0)
        stale_keys=[k for k, ts in self._interaction_guard.items()
                                                                 if float(ts) < cutoff]
        for stale in stale_keys:
            self._interaction_guard.pop(stale, None)

        return False

    def _lock_for(self, message_id: int) -> asyncio.Lock:
        mid=int(message_id)
        lock=self._post_locks.get(mid)
        if lock is None:
            lock=asyncio.Lock()
            self._post_locks[mid]=lock
        # Last used updaten
        self._post_lock_last_used[mid]=discord.utils.utcnow()
        return lock

    def _cleanup_post_lock(self, message_id: int) -> None:
        mid=int(message_id)
        self._post_locks.pop(mid, None)
        self._post_lock_last_used.pop(mid, None)

    async def _locks_gc_loop(self) -> None:
        # Räumt alte Locks weg, damit die Map nicht wächst.
        await self.bot.wait_until_red_ready()
        await self.bot.wait_until_ready()

        while True:
            try:
                now=discord.utils.utcnow()

                # Alles, was seit 6h nicht genutzt wurde, kann weg
                cutoff=now - dt.timedelta(hours=6)

                stale=[
                    mid for mid, last in self._post_lock_last_used.items() if last < cutoff]
                for mid in stale:
                    self._cleanup_post_lock(mid)

            except Exception:
                pass

            await asyncio.sleep(60 * 60)  # 1h

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
        if target == BackTarget.OLUN_TIER:
            await self._send_step(interaction, session, Step.OLUN_TIER)
            return
        if target == BackTarget.atoraxxion_runs:
            await self._send_step(interaction, session, Step.atoraxxion_runs)
            return
        if target == BackTarget.ALTAR_STEP:
            await self._send_step(interaction, session, Step.ALTAR_STEP)
            return

    # =========================
    # Command (Test)
    # =========================

    @ app_commands.guilds(discord.Object(id=GUILD_ID))
    @ app_commands.command(name="gs_test", description="TEST: Starte eine neue Gruppensuche (Wizard).")
    async def gs_test_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        session=WizardSession(
            user_id=interaction.user.id,
            guild_id=interaction.guild_id or 0,
            mode="create",
        )
        session.wizard_interaction=interaction
        self._sessions[interaction.user.id]=session

        # nach defer musst du über followup oder edit_original_response arbeiten:
        view=StartView(self, session)
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

        if step == Step.ALTAR_STEP:
            await self._send_altar_steps(interaction, session)
            return

        if step == Step.DETAILS:
            await self._send_final_form(interaction, session)
            return

        if step == Step.OLUN_TIER:
            await self._send_olun_tier(interaction, session)
            return

        if step == Step.EDIT_MENU:
            await self._send_edit_menu(interaction, session)
            return

        if step == Step.atoraxxion_runs:
            await self._send_atoraxxion_runs(interaction, session)
            return

        # Fallback (ACK-safe)
        await self._ephemeral_notice(interaction, "Unbekannter Step.")

    def _resolve_back_target_for_day(self, session: WizardSession) -> str:
        """
        Wenn wir DAY anzeigen: Wohin zeigt der Zurück-Button?
        Das hängt von Kategorie / Flow ab.
        """
        if session.mode == "edit":
            return BackTarget.EDIT_MENU

        cat=(session.category or "").lower()

        # ✅ Atoraxxion: zurück zur Dungeon-Auswahl (nicht ins Hauptmenü)
        if cat == "atoraxxion":
            return BackTarget.atoraxxion_runs

        # ✅ Altar: bleibt vorerst Hauptmenü (bis wir den Stufen-Step einbauen)
        if cat == "altar":
            return BackTarget.START

        if cat == "spots":
            if (session.spot_key or "") == "olun":
                return BackTarget.OLUN_TIER
            return BackTarget.SPOT

        if cat == "pilafe":
            return BackTarget.START

        # muhhelfer
        total=_sum_runs(session.boss_runs)
        prev=BackTarget.BOSSES if total >= 5 else BackTarget.DOUBLE
        return prev

    def _resolve_next_step(self, session: WizardSession, current_step: str) -> str:
        """
        Zentrale Next-Entscheidung.
        Gibt den nächsten Step zurück.
        """
        # Edit-Mode: “Back-Regel” bleibt separat (über build_back_button). Next-Flow bleibt hier zentral steuerbar.
        cat=session.category or ""

        # --- Feature-Guard (hart) ---
        if cat == "muhhelfer" and not FEATURE_MUHHILFER:
            session.category=None
            return Step.START

        if cat == "pilafe" and not FEATURE_PILAFE:
            session.category=None
            return Step.START

        if cat == "spots":
            if not FEATURE_SPOTS:
                session.category=None
                return Step.START
            if not (FEATURE_SPOTS_MIRUMOK or FEATURE_SPOTS_GYFIN or FEATURE_SPOTS_OLUN or FEATURE_SPOTS_EDANIA):
                session.category=None
                return Step.START
            # falls Spot schon gesetzt, aber Flag ist aus:
            if session.spot_key == "mirumok" and not FEATURE_SPOTS_MIRUMOK:
                session.spot_key=None
                return Step.SPOT
            if session.spot_key == "gyfin" and not FEATURE_SPOTS_GYFIN:
                session.spot_key=None
                return Step.SPOT
            if session.spot_key == "olun" and not FEATURE_SPOTS_OLUN:
                session.spot_key=None
                return Step.SPOT
            if session.spot_key == "edania" and not FEATURE_SPOTS_EDANIA:
                session.spot_key=None
                return Step.SPOT

        if cat == "altar" and not FEATURE_ALTAR:
            session.category=None
            return Step.START

        if cat == "atoraxxion" and not FEATURE_ATORAXXION:
            session.category=None
            return Step.START

        # -------- ALTAR --------
        if cat == "altar":
            if current_step == Step.DAY:
                return Step.PARTY
            if current_step == Step.PARTY:
                return Step.ALTAR_STEP
            if current_step == Step.ALTAR_STEP:
                return Step.DETAILS if session.mode == "create" else Step.EDIT_MENU

        # -------- START --------
        if current_step == Step.START:
            if cat == "muhhelfer":
                return Step.DIFFICULTY
            if cat == "spots":
                return Step.SPOT
            if cat == "pilafe":
                return Step.DAY
            if cat == "altar":
                return Step.DAY
            if cat == "atoraxxion":
                # ✅ Atto: erst Run-Auswahl, dann Tag
                return Step.atoraxxion_runs
            return Step.START

        # -------- ATORAXXION --------
        if cat == "atoraxxion":
            if current_step == Step.atoraxxion_runs:
                return Step.EDIT_MENU if session.mode == "edit" else Step.DAY
            if current_step == Step.DAY:
                return Step.PARTY
            if current_step == Step.PARTY:
                return Step.DETAILS if session.mode == "create" else Step.EDIT_MENU

        # -------- MUHHELFER --------
        if cat == "muhhelfer":
            if current_step == Step.DIFFICULTY:
                return Step.BOSSES

            if current_step == Step.BOSSES:
                total=_sum_runs(session.boss_runs)
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
                # ✅ Olun braucht Stufe
                if (session.spot_key or "") == "olun":
                    return Step.OLUN_TIER
                return Step.DAY

            if current_step == Step.OLUN_TIER:
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

    async def _goto_next(self, interaction: discord.Interaction, session: WizardSession, current_step: str):
        next_step=self._resolve_next_step(session, current_step)
        await self._send_step(interaction, session, next_step)

    async def _send_start(self, interaction: discord.Interaction, session: WizardSession):
        view=StartView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_day_selection(self, interaction: discord.Interaction, session: WizardSession):
        view=DaySelectView(self, session)
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
        if session.category in ("altar", "atoraxxion"):
            # ✅ beide starten über die Tag-Auswahl
            await self._send_day_selection(interaction, session)
            return

        await self._ephemeral_notice(
            interaction,
            "Ungültige Auswahl. Bitte neu starten.",
            ephemeral=True,
        )
        await self._send_start(interaction, session)

    async def _send_difficulty(self, interaction: discord.Interaction, session: WizardSession):
        view=DifficultyView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_boss_select(self, interaction: discord.Interaction, session: WizardSession):
        view=BossSelectView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_double_run(self, interaction: discord.Interaction, session: WizardSession):
        # ✅ Nur rendern. Flow-Entscheidung macht der Router.
        view=DoubleRunView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_spot_select(self, interaction: discord.Interaction, session: WizardSession):
        # Auto-pick wenn nur ein Spot aktiv ist
        active=[]
        if FEATURE_SPOTS_MIRUMOK:
            active.append("mirumok")
        if FEATURE_SPOTS_GYFIN:
            active.append("gyfin")
        if FEATURE_SPOTS_OLUN:
            active.append("olun")
        if FEATURE_SPOTS_EDANIA:
            active.append("edania")

        if len(active) == 1 and session.mode == "create":
            session.spot_key=active[0]
            await self._goto_next(interaction, session, Step.SPOT)
            return

        view=SpotSelectView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_party_size(self, interaction: discord.Interaction, session: WizardSession):
        member=interaction.user if isinstance(
            interaction.user, discord.Member) else None
        allow_one=bool(member and _is_admin_only(member))  # ✅ gilt für alles

        view=PartySizeView(
            self, session, current=session.max_players, allow_one=allow_one)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_altar_steps(self, interaction: discord.Interaction, session: WizardSession):
        view = AltarStepView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_atoraxxion_runs(self, interaction: discord.Interaction, session: WizardSession, back_target: str=BackTarget.START):
        view=AtoraxxionRunView(self, session, back_target=back_target)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _send_final_form(self, interaction: discord.Interaction, session: WizardSession):
        defaults={
            "req_default": _default_req_for(
                {
                    "category": session.category,
                    "difficulty": session.difficulty,
                    "spot_key": session.spot_key,
                    "olun_tier": session.olun_tier,  # ✅ wichtig für Olun
                }
            )
        }

        try:
            await interaction.response.send_modal(DetailsModal(self, session, defaults=defaults))
        except discord.InteractionResponded:
            await interaction.followup.send_modal(DetailsModal(self, session, defaults=defaults))

    async def _send_olun_tier(self, interaction: discord.Interaction, session: WizardSession):
        view=OlunTierView(self, session)
        await self._edit_or_send_ephemeral(interaction, view.embed(), view)

    async def _edit_or_send_ephemeral(self, interaction: discord.Interaction, embed: discord.Embed, view: discord.ui.View):
        msg=getattr(interaction, "message", None)

        # 🔒 Wenn Interaction vom PUBLIC POST kommt → NIEMALS editieren!
        if msg is not None and not getattr(msg.flags, "ephemeral", False):
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return

        # ✅ WICHTIG: Wenn wir eine Ephemeral-Message haben, editieren wir DIE direkt.
        # Das verhindert "zweites Ephemeral" nach Modal-Submit.
        if msg is not None and getattr(msg.flags, "ephemeral", False):
            try:
                await msg.edit(embed=embed, view=view)
                return
            except Exception:
                pass

        # Normalfall: Wizard-Ephemeral wird editiert
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def _ephemeral_notice(
        self,
        interaction: discord.Interaction,
        text: Optional[str]=None,
        *,
        embed: Optional[discord.Embed]=None,
        view: Optional[discord.ui.View]=None,
        allowed_mentions: Optional[discord.AllowedMentions]=None,
        ephemeral: bool=True,
    ):
        """
        Ack-sicherer Responder (ephemeral + nicht-ephemeral):
        - Wenn noch NICHT geantwortet: interaction.response.send_message(...)
        - Wenn schon geantwortet: interaction.followup.send(...)
        Unterstützt content / embed / view / allowed_mentions.
        """
        try:
            payload: dict={"ephemeral": ephemeral}

            if text is not None:
                payload["content"]=text
            if embed is not None:
                payload["embed"]=embed
            if view is not None:
                payload["view"]=view
            if allowed_mentions is not None:
                payload["allowed_mentions"]=allowed_mentions

            if interaction.response.is_done():
                await interaction.followup.send(**payload)
            else:
                await interaction.response.send_message(**payload)

        except Exception:
            # bewusst still
            pass

    async def _send_ephemeral_new(self, interaction: discord.Interaction, embed: discord.Embed, view: discord.ui.View):
        try:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def _ping_participants(self, interaction: discord.Interaction, message_id: int, data: dict):
        # ✅ ack-sicher (wie _ping_type/_ping_wait)
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        if bool(data.get("is_closed", False)):
            await self._ephemeral_notice(interaction, "Diese Suche ist geschlossen.", ephemeral=True)
            return

        # ========= Cooldown (pro Post) =========
        cd=data.get("ping_cd") or {}
        now_ts=int(_now_local().timestamp())
        last=int(cd.get("participants", 0))

        remaining=PARTICIPANT_PING_COOLDOWN_SECONDS - (now_ts - last)
        if remaining > 0:
            await self._ephemeral_notice(
                interaction, f"📣 Teilnehmer-Ping ist noch im Cooldown. Bitte warte **{remaining}s**.",
                ephemeral=True,
            )
            return

        cd["participants"]=now_ts
        data["ping_cd"]=cd
        data["updated_at"]=now_ts

        try:
            await self._set_search(message_id, data)
        except Exception:
            pass

        # =======================================

        guild=interaction.guild
        if guild is None:
            return

        channel=guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            return

        participants=list(data.get("participants") or [])
        if not participants:
            return

        mentions=" ".join(f"<@{uid}>" for uid in participants)
        jump=f"https://discord.com/channels/{guild.id}/{channel.id}/{message_id}"

        day_iso=data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_d=dt.date.fromisoformat(day_iso)
            day_str=_format_day(day_d)
        except Exception:
            day_str=str(day_iso)

        start_text=data.get("start_text") or "—"

        await channel.send(
            f"{mentions}\n📣 Teilnehmer-Ping | Start: {start_text} | {day_str}\n{jump}",
            allowed_mentions=discord.AllowedMentions(
                users=True, roles=False, everyone=False),
        )

    # =========================
    # Storage
    # =========================

    async def _get_search(self, message_id: int) -> Optional[dict]:
        guild=self.bot.get_guild(GUILD_ID)
        if guild is None:
            self._log_warning(
                "STORAGE",
                "guild not available while reading search",
                message_id=message_id,
                guild_id=GUILD_ID,
            )
            return None

        searches=await self.config.guild(guild).searches()
        data=(searches or {}).get(str(message_id))

        if data is None:
            self._log_warning(
                "STORAGE",
                "search entry missing",
                message_id=message_id,
                guild_id=guild.id,
            )
            try:
                await self._log_event(
                    guild,
                    "warn",
                    "Gruppensuche",
                    "Search Entry Missing",
                    (
                        "Ein Gruppensuche-Datensatz konnte nicht gefunden werden.\n\n"
                        "Der Post existiert möglicherweise noch, der zugehörige Storage-Eintrag fehlt jedoch.\n"
                        "Bitte Post und Storage prüfen."
                    ),
                )
            except Exception:
                pass

        return data

    async def _set_search(self, message_id: int, data: dict):
        guild=self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        async with self.config.guild(guild).searches() as searches:
            searches[str(message_id)]=data

    async def _del_search(self, message_id: int):
        guild=self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        async with self.config.guild(guild).searches() as searches:
            if str(message_id) in searches:
                del searches[str(message_id)]

    def _dispatch_dashboard_update(self, guild_id: int):
        try:
            self.bot.dispatch("gruppensuche_updated", int(guild_id))
        except Exception:
            pass

        # Debounced Refresh starten
        self._schedule_dashboard_refresh(int(guild_id))

    async def _is_owner_or_mod(self, interaction: discord.Interaction, message_id: int) -> bool:
        data=await self._get_search(int(message_id))
        if not data:
            return False

        uid=int(interaction.user.id)
        owner_id=int(data.get("owner_id") or 0)
        if uid == owner_id:
            return True

        member=_member_from_interaction(interaction)
        if member and _has_mod_rights(member):
            return True

        return False
    # =========================
    # Edit Notifications (DM, debounced)
    # =========================

    def _member_has_no_dm_role(self, member: discord.Member) -> bool:
        return any(r.id == ROLE_NO_DM_ID for r in getattr(member, "roles", []))

    def _collect_recipients(self, data: dict) -> list[int]:
        """Teilnehmer + Warteschlange, ohne Owner, unique, stable order."""
        owner_id=int(data.get("owner_id", 0))
        participants=[int(x) for x in (data.get("participants") or [])]
        waitlist=[int(x) for x in (data.get("waitlist") or [])]

        seen=set()
        out: list[int]=[]
        for uid in participants + waitlist:
            if uid == owner_id:
                continue
            if uid in seen:
                continue
            seen.add(uid)
            out.append(uid)
        return out

    def _build_jump(self, guild: discord.Guild, data: dict) -> str:
        mid=int(data.get("message_id", 0))
        cid=int(data.get("channel_id", 0))
        return f"https://discord.com/channels/{guild.id}/{cid}/{mid}"

    def _norm_text(self, v: object) -> str:
        s=str(v or "").strip()
        return s if s else "—"

    def _truncate(self, s: str, n: int=160) -> str:
        s=(s or "").strip()
        if len(s) <= n:
            return s
        return s[: n - 1].rstrip() + "…"

    def _schedule_edit_notify(self, message_id: int, data: dict, changes: list[dict]):
        """
        changes: list of {key, label, old, new}
        - debounced: sammelt pending und sendet nach self._edit_notify_delay
        - speichert pending in Config (best effort)
        """
        mid=int(message_id)
        if mid <= 0:
            return

        en=data.get("edit_notify")
        if not isinstance(en, dict):
            en={}

        pending=en.get("pending")
        if not isinstance(pending, dict):
            pending={}

        # Merge-Regel:
        # - wenn field schon pending: old bleibt der erste old, new wird überschrieben (letzter Stand)
        for ch in changes:
            key=str(ch.get("key") or "").strip()
            if not key:
                continue

            label=str(ch.get("label") or key)
            old=self._norm_text(ch.get("old"))
            new=self._norm_text(ch.get("new"))

            if key in pending and isinstance(pending.get(key), dict):
                # old behalten, new aktualisieren
                pending[key]["new"]=new
                pending[key]["label"]=label
            else:
                pending[key]={"label": label, "old": old, "new": new}

        en["pending"]=pending
        en["pending_updated_at"]=int(_now_local().timestamp())
        data["edit_notify"]=en

        # pending persistieren (ohne Public/Dashboard refresh)
        try:
            self.bot.loop.create_task(self._set_search(mid, data))
        except Exception:
            pass

        # Debounce-Task neu planen
        old_task=self._edit_notify_tasks.get(mid)
        if old_task and not old_task.done():
            old_task.cancel()

        async def _debounced_send():
            try:
                await asyncio.sleep(self._edit_notify_delay)
                await self._send_edit_notify(mid)
            except asyncio.CancelledError:
                return
            except Exception:
                return

        self._edit_notify_tasks[mid]=self.bot.loop.create_task(
            _debounced_send())

    async def _send_edit_notify(self, message_id: int):
        """Liest aktuellen Stand, verschickt DM an Teilnehmer+Warteschlange (ohne Owner), cleared pending."""
        data=await self._get_search(int(message_id))
        if not data:
            return

        guild=self.bot.get_guild(int(data.get("guild_id", 0)))
        if guild is None:
            return

        en=data.get("edit_notify")
        if not isinstance(en, dict):
            return

        pending=en.get("pending")
        if not isinstance(pending, dict) or not pending:
            return

        # Empfänger
        recipient_ids=self._collect_recipients(data)
        if not recipient_ids:
            # niemand zum informieren -> pending clear
            en["pending"]={}
            en["last_sent_at"]=int(_now_local().timestamp())
            data["edit_notify"]=en
            await self._set_search(int(message_id), data)
            return

        # Kontext
        day_iso=data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_str=_format_day(dt.date.fromisoformat(str(day_iso)))
        except Exception:
            day_str=str(day_iso)

        start_text=self._norm_text(data.get("start_text"))
        max_players=int(data.get("max_players", 2))
        participants=list(data.get("participants") or [])
        free=max(0, max_players - len(participants))

        jump=self._build_jump(guild, data)

        # --- Kuhmuh-DM (einheitlich + hübsch + konsistente Emojis) ---
        cat_emoji=_category_emoji(data)

        cat=str(data.get("category", "") or "").lower()
        change_type="Gruppensuche"
        if cat == "muhhelfer":
            diff=str(data.get("difficulty", "normal")).lower()
            diff_label="Schwer" if diff == "schwer" else "Normal"
            change_type=f"Muhhelfer ({diff_label})"
        elif cat == "spots":
            spot=str(data.get("spot_key", "") or "").lower()
            if spot == "olun":
                tier=str(data.get("olun_tier", "normal")).lower()
                tier_label=_olun_tier_label(tier)
                change_type=f"Gruppenspots – Olun ({tier_label})"
            else:
                change_type=f"Gruppenspots – {_spot_name(spot) if spot else '—'}"
        elif cat == "pilafe":
            change_type="Pila Fe"
        elif cat == "atoraxxion":
            change_type="Atoraxxion"
        elif cat == "altar":
            change_type="Altar des Blutes"

        def _pretty(v: object) -> str:
            """Kurze, saubere Anzeige. Zahlen DE-formatiert wenn möglich."""
            s=self._norm_text(v)
            # reine Zahlen hübsch formatieren
            try:
                if str(s).strip().isdigit():
                    return _fmt_number(int(s))
            except Exception:
                pass
            return s

        # Änderungen: Label normal, nur neuer Wert fett
        lines: list[str]=[]
        CHANGE_EMOJIS={
            "Tag": "📅",
            "Startzeit": "⏰",
            "Geplante Dauer": "⌛",
            "Max. Teilnehmer": "👥",
            "Gewünschte AP": "⚔️",
            "Host AP": "💪",
            "Notiz": "📝",
            "Run": "🏛️",
            "Menge": "📜",
        }
        for _, obj in pending.items():
            if not isinstance(obj, dict):
                continue

            label=str(obj.get("label") or "Änderung")
            old=self._truncate(self._norm_text(obj.get("old")), 180)
            new=self._truncate(self._norm_text(obj.get("new")), 180)

            if old == new:
                continue

            emoji=CHANGE_EMOJIS.get(label, "•")

            lines.append(
                f"{emoji} {label}: {old} → **{new}**"
            )

        if not lines:
            en["pending"]={}
            en["last_sent_at"]=int(_now_local().timestamp())
            data["edit_notify"]=en
            await self._set_search(int(message_id), data)
            return

        header=(
            f"{cat_emoji} **Die Herde hat etwas angepasst…** {MUHKUH_EMOJI}\n\n"
            f"Typ: {change_type}\n"
            f"📅 Tag: {day_str}\n"
            f"⏰ Start: {start_text or '—'}\n"
            f"👥 Frei: {_fmt_number(free)}\n"
            f"🔗 {jump}\n"
        )
        changes_header="\n── Geänderte Werte ──\n"
        text=header + changes_header + "\n".join(lines)

        channel=guild.get_channel(int(data.get("channel_id", 0)))
        failed: list[int]=[]

        for uid in recipient_ids:
            m=guild.get_member(int(uid))
            if not m:
                continue
            if self._member_has_no_dm_role(m):
                failed.append(int(uid))
                continue
            try:
                await m.send(text)
            except Exception:
                failed.append(int(uid))

        # Fallback: Ping im Channel, aber nur die, bei denen DM nicht ging / Opt-out
        if failed and isinstance(channel, discord.TextChannel):
            mentions=" ".join(f"<@{uid}>" for uid in failed)
            try:
                await channel.send(
                    f"✏️ Änderung (DM nicht möglich/opt-out): {mentions}\n{jump}",
                    allowed_mentions=discord.AllowedMentions(
                        users=True, roles=False, everyone=False),
                )
            except Exception:
                pass

        # pending clear + markieren
        en["pending"]={}
        en["last_sent_at"]=int(_now_local().timestamp())
        data["edit_notify"]=en
        await self._set_search(int(message_id), data)

    def _schedule_dashboard_refresh(self, guild_id: int):
        guild_id=int(guild_id)
        self._dashboard_refresh_pending[guild_id]=True

        log.info(
            f"[KUHMUH][DASHBOARD][DISPATCH][SCHEDULE] guild_id={guild_id}")

        existing=self._dashboard_refresh_tasks.get(guild_id)
        if existing and not existing.done():
            return

        async def _runner():
            try:
                while self._dashboard_refresh_pending.get(guild_id, False):
                    self._dashboard_refresh_pending[guild_id]=False

                    await asyncio.sleep(self._dashboard_refresh_delay)

                    try:
                        log.info(
                            f"[KUHMUH][DASHBOARD][DISPATCH][START] guild_id={guild_id}")

                        dash=self.bot.get_cog("Gruppenübersicht")
                        if dash is None:
                            log.warning(
                                f"[KUHMUH][DASHBOARD][DISPATCH][NO COG] guild_id={guild_id}")
                            self._dashboard_refresh_pending[guild_id]=True
                            await asyncio.sleep(self._dashboard_refresh_retry_delay)
                            continue

                        log.info(
                            f"[KUHMUH][DASHBOARD][DISPATCH][COG FOUND] guild_id={guild_id}")

                        await dash.force_refresh_all(guild_id)

                        log.info(
                            f"[KUHMUH][DASHBOARD][DISPATCH][DONE] guild_id={guild_id}")

                    except Exception as e:
                        log.exception(
                            f"[KUHMUH][DASHBOARD][DISPATCH][ERROR] guild_id={guild_id} error={e}"
                        )
                        self._dashboard_refresh_pending[guild_id]=True
                        await asyncio.sleep(self._dashboard_refresh_retry_delay)

            except asyncio.CancelledError:
                log.info(
                    f"[KUHMUH][DASHBOARD][DISPATCH][CANCELLED] guild_id={guild_id}")
                return
            finally:
                self._dashboard_refresh_tasks.pop(guild_id, None)
                self._dashboard_refresh_pending.pop(guild_id, None)

        task=self.bot.loop.create_task(_runner())
        self._dashboard_refresh_tasks[guild_id]=task

    async def _save_refresh_dispatch(self, data: dict):
        try:
            now_ts=int(_now_local().timestamp())
            data["updated_at"]=now_ts

            mid=int(data.get("message_id", 0))
            if mid:
                await self._set_search(mid, data)

        except Exception:
            pass

    async def _post_save_refresh_dispatch(self, data: dict):
        try:
            mid=int(data.get("message_id", 0))
            if mid:
                await self._refresh_public_message(data)

            gid=int(data.get("guild_id", 0))
            if gid:
                self._dispatch_dashboard_update(gid)

        except Exception:
            pass

    # =========================
    # Public Post Build/Refresh
    # =========================

    async def _build_public_embed(self, guild: discord.Guild, data: dict) -> discord.Embed:
        cat=str(data.get("category", "")).lower()
        owner_id=int(data.get("owner_id", 0))
        owner=guild.get_member(owner_id)

        day_iso=data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_d=dt.date.fromisoformat(day_iso)
            day_str=_format_day(day_d)
        except Exception:
            day_str=str(day_iso)

        max_players=int(data.get("max_players", 2))
        participants: List[int]=list(data.get("participants") or [])
        waitlist: List[int]=list(data.get("waitlist") or [])

        is_closed=bool(data.get("is_closed", False))
        is_full=len(participants) >= max_players

        if is_closed:
            status_line="🔴 Geschlossen"
        else:
            status_line="🔴 Voll" if is_full else "🟢 Offen"

        # Times / Notes (zentral)
        duration_text=data.get("duration_text") or "—"
        start_text=data.get("start_text") or "—"
        notes=data.get("notes") or "—"

        times_block=(
            f"**Tag:** {day_str}\n"
            f"**Start:** {start_text}\n"
            f"**Geplante Dauer:** {duration_text}\n\n"
        )
        notes_block=f"**Notiz:** {notes}\n\n"

        req_text=data.get("req_text") or ""

        # Easter Egg Map (optional)
        egg_map=data.get("easter_egg_texts")
        if not isinstance(egg_map, dict):
            egg_map={}

        def _egg_for(uid: int) -> Optional[str]:
            txt=str(egg_map.get(str(uid)) or "").strip()
            return txt or None

        def _build_user_lines(user_ids: list[int], ap_dict: dict) -> list[str]:
            lines_out: list[str]=[]
            for uid in user_ids:
                uid_int=int(uid)
                m=guild.get_member(uid_int)
                mention=(m.mention if m else f"<@{uid_int}>")
                ap=ap_dict.get(str(uid_int))
                lines_out.append(_fmt_player_with_ap_and_egg(
                    mention, ap, _egg_for(uid_int)))
            return lines_out

        # Kopfblock: Suchender (ohne Easter Egg)
        owner_txt=owner.mention if owner else f"<@{owner_id}>"
        owner_ap=data.get("owner_ap")
        owner_display=_fmt_player_with_ap(owner_txt, owner_ap)

        # Gemeinsame Blöcke (zentral, für alle Kategorien gleich)
        status_block=f"**Status**\n{status_line}\n\n"

        part_lines=_build_user_lines(
            participants, data.get("participant_ap") or {})
        participants_block=(
            f"**Teilnehmer ({len(participants)}/{max_players})**\n"
            + ("\n".join([f"• {x}" for x in part_lines])
               if part_lines else "—")
            + "\n\n"
        )

        wait_lines=_build_user_lines(waitlist, data.get("waitlist_ap") or {})
        wait_block=(
            f"**Warteschlange ({len(waitlist)})**\n"
            + ("\n".join([f"• {x}" for x in wait_lines])
               if wait_lines else "—")
        )

        # Titel
        if cat == "muhhelfer":
            diff=str(data.get("difficulty", "normal")).lower()
            diff_label="Schwer" if diff == "schwer" else "Normal"
            title=f"{MUHKUH_EMOJI} Gruppensuche – Muhhelfer ({diff_label})"
        elif cat == "spots":
            spot=str(data.get("spot_key", ""))
            if spot == "olun":
                tier=str(data.get("olun_tier", "normal"))
                tier_label=_olun_tier_label(tier)
                title=f"{OLUN_EMOJI} Gruppensuche – Olun ({tier_label})"
            else:
                if spot == "mirumok":
                    emoji=MIRUMOK_EMOJI
                elif spot == "gyfin":
                    emoji=GYFIN_EMOJI
                elif spot == "olun":
                    emoji=OLUN_EMOJI
                elif spot == "edania":
                    emoji=EDANIA_EMOJI
                else:
                    emoji=CHEER_EMOJI
                title=f"{emoji} Gruppensuche – {_spot_name(spot)}"
        else:
            if cat == "altar":
                title="🩸 Gruppensuche – Altar des Blutes"
            elif cat == "atoraxxion":
                title="🏛️ Gruppensuche – Atoraxxion"
            else:
                title=f"{PILAFE_EMOJI} Gruppensuche – Pila Fe"

        e=discord.Embed(title=title)

        # Kategorie-spezifische Description (JEWEILS genau einmal setzen)
        if cat == "muhhelfer":
            diff=str(data.get("difficulty", "normal")).lower()
            diff_label="Schwer" if diff == "schwer" else "Normal"
            diff_icon="🔴" if diff == "schwer" else "🟢"
            req_default=AKVK_SCHWER if diff == "schwer" else AKVK_NORMAL
            req=req_text or req_default

            header=(
                f"**Suchender:** {owner_display}\n"
                f"**Kategorie:** Muhhelfer (LoML Bosse)\n"
                f"**Schwierigkeit:** {diff_icon} {diff_label}\n"
                f"**Anforderung AK/VK:** {req}\n"
                f"**Max. Teilnehmer:** {max_players}\n\n"
            )

            boss_runs=data.get("boss_runs") or {}
            boss_lines=[]
            has_double=False
            for key, runs in boss_runs.items():
                name=_boss_name(str(key))
                if int(runs) >= 2:
                    has_double=True
                    boss_lines.append(f"• {name} **(Doppel Run)**")
                else:
                    boss_lines.append(f"• {name}")

            bosses_block="**Bosse:**\n" +
                ("\n".join(boss_lines) if boss_lines else "—") + "\n\n"
            if has_double:
                bosses_block += "⚠️ **2. Charakter erforderlich**\n\n"

            e.description=(
                header
                + bosses_block
                + times_block
                + notes_block
                + status_block
                + participants_block
                + wait_block
            )

        elif cat == "spots":
            spot=str(data.get("spot_key", ""))
            if spot == "olun":
                tier=str(data.get("olun_tier", "normal")).lower()
                req_default=OLUN_REQ.get(tier, "")
            else:
                req_default=SPOT_REQ.get(spot, "")
            req=req_text or req_default

            header=(
                f"**Suchender:** {owner_display}\n"
                f"**Kategorie:** Gruppenspots\n"
                f"**Anforderung AK/VK:** {req if req else '—'}\n"
                f"**Max. Teilnehmer:** {max_players}\n\n"
            )

            spot_block=""
            if spot == "olun":
                tier=str(data.get("olun_tier", "normal")).lower()
                tier_label=_olun_tier_label(tier)
                spot_block += (
                    f"**Spot:** Olun\n"
                    f"**Stufe:** {tier_label}\n"
                    f"{OLUN_TOTAL_AP.get(tier, '')}\n\n"
                )
            else:
                total_ap=SPOT_TOTAL_AP.get(spot, "")
                if total_ap:
                    spot_block += f"**Spot:** {_spot_name(spot)}\n{total_ap}\n\n"
                else:
                    spot_block += f"**Spot:** {_spot_name(spot)}\n\n"

            e.description=(
                header
                + spot_block
                + times_block
                + notes_block
                + status_block
                + participants_block
                + wait_block
            )

        elif cat == "altar":
            req_text = data.get("req_text") or ""
            req_line = f"**Gewünschte AP:** {req_text}\n" if req_text else "**Gewünschte AP:** —\n"

            cleared = data.get("altar_cleared_step")
            target = data.get("altar_target_step")

            cleared_txt = f"Step {cleared}" if cleared is not None else "—"
            target_txt = f"Step {target}" if target is not None else "—"

            header = (
                f"**Suchender:** {owner_display}\n"
                f"**Kategorie:** Altar des Blutes\n"
                + req_line +
                f"**Max. Teilnehmer:** {max_players}\n\n"
            )

            altar_block = (
                f"**Fortschritt:**\n"
                f"• Höchster geclearter Step: {cleared_txt}\n"
                f"• Ziel-Step: {target_txt}\n\n"
            )

            e.description = (
                header
                + altar_block
                + times_block
                + notes_block
                + status_block
                + participants_block
                + wait_block
            )

        elif cat == "atoraxxion":
            runs=_normalize_atoraxxion_runs(data)

            req_text=data.get("req_text") or ""
            req_line=f"**Gewünschte AP:** {req_text}\n" if req_text else "**Gewünschte AP:** —\n"

            header=(
                f"**Suchender:** {owner_display}\n"
                f"**Kategorie:** Atoraxxion\n"
                + req_line +
                f"**Max. Teilnehmer:** {max_players}\n\n"
            )

            all_keys={"vahmalkea", "sycrakea", "yolunakea", "orzekea"}
            ordered=["vahmalkea", "sycrakea", "yolunakea", "orzekea"]

            dungeon_map={
                "vahmalkea": "Vahmalkea",
                "sycrakea": "Sycrakea",
                "yolunakea": "Yolunakea",
                "orzekea": "Orzekea",
            }

            # Runs stabil & in fixer Reihenfolge (wie im Spiel / UI)
            runs_set={str(k).lower() for k in (runs or [])}
            runs_ordered=[k for k in ordered if k in runs_set]

            # Run-Typ + Zählung
            if runs_ordered and set(runs_ordered) == all_keys:
                run_label="Kompletter Run"
            elif runs_ordered:
                run_label="Teil-Run"
            else:
                run_label="—"

            run_count=len(runs_ordered)

            # Anzeige: eine klare Run-Zeile + darunter Dungeons fett
            selection_block=f"**🏛️ Run:** {run_label} ({run_count}/4)\n\n"
            if runs_ordered:
                lines_sel="\n".join(
                    [f"• **{dungeon_map[k]}**" for k in runs_ordered])
                selection_block += f"**Dungeons:**\n{lines_sel}\n\n"

            e.description=(
                header
                + selection_block
                + times_block
                + notes_block
                + status_block
                + participants_block
                + wait_block
            )

        else:
            # Pila Fe
            amount=_fmt_thousands_de(data.get("scroll_amount"))
            header=(
                f"**Suchender:** {owner_display}\n"
                f"**Kategorie:** Pila Fe Schriftrollen\n"
                f"**Menge:** {amount}\n"
                f"**Max. Teilnehmer:** {max_players}\n\n"
            )

            e.description=(
                header
                + times_block
                + notes_block
                + status_block
                + participants_block
                + wait_block
            )

        e.set_footer(text="Klicke auf „Ich bin dabei“, um dich einzutragen.")
        e.timestamp=discord.utils.utcnow()
        return e

    async def _refresh_public_post(self, *, guild: discord.Guild, channel: discord.abc.Messageable, message_id: int) -> None:
        """Baut Embed + View neu und editiert den Public-Post."""
        mid=int(message_id)
        data=await self._get_search(mid)
        if data is None:
            return

        embed=await self._build_public_embed(guild, data)
        view=ClosedPostView(self, mid) if bool(
            data.get("is_closed", False)) else PublicPostView(self, mid)

        if isinstance(view, PublicPostView):
            await self._apply_dynamic_button_labels(view, data)

        msg_obj=await channel.fetch_message(mid)
        await msg_obj.edit(embed=embed, view=view)

    async def _close_post_atomic(self, *, guild: discord.Guild, channel: discord.abc.Messageable, message_id: int) -> None:
        mid=int(message_id)

        async with self._lock_for(mid):
            data=await self._get_search(mid)
            if data is None:
                return

            if bool(data.get("is_closed", False)):
                return

            data["is_closed"]=True
            data["updated_at"]=int(_now_local().timestamp())
            await self._set_search(mid, data)

            # Post direkt refreshen (zeigt "Geschlossen" + passende View)
            try:
                await self._refresh_public_post(guild=guild, channel=channel, message_id=mid)
            except Exception:
                pass

        # Lock entfernen (außerhalb)
        self._cleanup_post_lock(mid)

    async def _refresh_public_message(self, data: dict):
        guild=self.bot.get_guild(int(data.get("guild_id", 0)))
        if guild is None:
            return

        channel=guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            self._log_warning(
                "REFRESH",
                "public post refresh aborted because channel is unavailable",
                guild_id=guild.id,
                channel_id=int(data.get("channel_id", 0)),
                message_id=int(data.get("message_id", 0)),
            )
            try:
                await self._log_event(
                    guild,
                    "error",
                    "Gruppensuche",
                    "Public Post Refresh Failed",
                    (
                        "Ein Gruppensuche-Post konnte nicht aktualisiert werden.\n\n"
                        "Der Ziel-Channel war nicht verfügbar.\n"
                        "Bitte Post und Channel prüfen."
                    ),
                )
            except Exception:
                pass
            return

        mid=int(data.get("message_id", 0))
        if mid == 0:
            self._log_warning(
                "REFRESH",
                "public post refresh aborted because message id is missing",
                guild_id=guild.id,
                channel_id=channel.id,
            )
            try:
                await self._log_event(
                    guild,
                    "error",
                    "Gruppensuche",
                    "Public Post Refresh Failed",
                    (
                        "Ein Gruppensuche-Post konnte nicht aktualisiert werden.\n\n"
                        "Die gespeicherte Message-ID fehlt.\n"
                        "Bitte Post und Storage prüfen."
                    ),
                    channel=channel,
                )
            except Exception:
                pass
            return

        try:
            msg=await channel.fetch_message(mid)
        except Exception:
            self._log_warning(
                "REFRESH",
                "public post refresh failed because message fetch failed",
                guild_id=guild.id,
                channel_id=channel.id,
                message_id=mid,
            )
            try:
                await self._log_event(
                    guild,
                    "error",
                    "Gruppensuche",
                    "Public Post Refresh Failed",
                    (
                        "Ein Gruppensuche-Post konnte nicht aktualisiert werden.\n\n"
                        "Die gespeicherte Nachricht konnte nicht geladen werden.\n"
                        "Bitte prüfen, ob der Post noch existiert."
                    ),
                    channel=channel,
                )
            except Exception:
                pass
            return

        embed=await self._build_public_embed(guild, data)

        try:
            if bool(data.get("is_closed", False)):
                view=ClosedPostView(self, mid)
                await msg.edit(embed=embed, view=view)
                return

            view=PublicPostView(self, mid)
            await self._apply_dynamic_button_labels(view, data)
            await msg.edit(embed=embed, view=view)

        except Exception:
            self._log_warning(
                "REFRESH",
                "public post refresh failed during message edit",
                guild_id=guild.id,
                channel_id=channel.id,
                message_id=mid,
            )
            try:
                await self._log_event(
                    guild,
                    "error",
                    "Gruppensuche",
                    "Public Post Refresh Failed",
                    (
                        "Ein Gruppensuche-Post konnte nicht aktualisiert werden.\n\n"
                        "Die bestehende Nachricht konnte nicht bearbeitet werden.\n"
                        "Bitte Post und Bot-Rechte prüfen."
                    ),
                    channel=channel,
                )
            except Exception:
                pass
            return

    async def _apply_dynamic_button_labels(self, view: discord.ui.View, data: dict):
        label="Rollen-Ping"
        cat=str(data.get("category", "")).lower()

        if cat == "muhhelfer":
            diff=str(data.get("difficulty", "normal")).lower()
            label=f"Rollen-Ping ({'Schwer' if diff == 'schwer' else 'Normal'})"

        elif cat == "spots":
            spot=str(data.get("spot_key", "")).lower()
            if spot == "olun":
                tier=str(data.get("olun_tier", "normal")).lower()
                tier_label={"normal": "Normal", "dehkia1": "Dehkia1",
                              "dehkia2": "Dehkia2"}.get(tier, tier)
                label=f"Rollen-Ping (Olun {tier_label})"
            else:
                label=f"Rollen-Ping ({_spot_name(spot)})" if spot else "Rollen-Ping"

        elif cat == "pilafe":
            label="Rollen-Ping (Pila Fe)"

        # ✅ NEU: kurze, feste Labels (wie gewünscht)
        elif cat == "atoraxxion":
            label="Rollen-Ping (Atoraxxion)"

        elif cat == "altar":
            label="Rollen-Ping (Altar)"

        for item in view.children:
            if isinstance(item, discord.ui.Button) and str(item.custom_id or "").startswith("gst:pingtype:"):
                item.label=label
                item.emoji="🔔"
                break

    # =========================
    # Create Public Post
    # =========================

    async def _create_public_post_from_session(self, interaction: discord.Interaction, session: WizardSession):
        guild=interaction.guild
        if guild is None:
            await self._ephemeral_notice(interaction, "Nur auf einem Server nutzbar.")
            return

        cat=session.category or ""

        if cat == "muhhelfer" and not FEATURE_MUHHILFER:
            await self._ephemeral_notice(interaction, "Muhhelfer ist aktuell deaktiviert.")
            return

        if cat == "pilafe" and not FEATURE_PILAFE:
            await self._ephemeral_notice(interaction, "Pila Fe ist aktuell deaktiviert.")
            return

        if cat == "spots":
            if not FEATURE_SPOTS:
                await self._ephemeral_notice(interaction, "Gruppenspots sind aktuell deaktiviert.")
                return
            if session.spot_key == "mirumok" and not FEATURE_SPOTS_MIRUMOK:
                await self._ephemeral_notice(interaction, "Mirumok ist aktuell deaktiviert.")
                return
            if session.spot_key == "gyfin" and not FEATURE_SPOTS_GYFIN:
                await self._ephemeral_notice(interaction, "Gyfin ist aktuell deaktiviert.")
                return
            if session.spot_key == "olun" and not FEATURE_SPOTS_OLUN:
                await self._ephemeral_notice(interaction, "Olun ist aktuell deaktiviert.")
                return
            if session.spot_key == "edania" and not FEATURE_SPOTS_EDANIA:
                await self._ephemeral_notice(interaction, "Edania ist aktuell deaktiviert.")
                return

        if cat == "altar" and not FEATURE_ALTAR:
            await self._ephemeral_notice(interaction, "Altar ist aktuell deaktiviert.")
            return

        if cat == "atoraxxion" and not FEATURE_ATORAXXION:
            await self._ephemeral_notice(interaction, "Atoraxxion ist aktuell deaktiviert.")
            return

        channel: Optional[discord.TextChannel]=None

        if FEATURE_POST_IN_CURRENT_CHANNEL:
            # bevorzugt dort posten, wo der Slash Command / Wizard gestartet wurde
            if isinstance(interaction.channel, discord.TextChannel):
                channel=interaction.channel
        else:
            # fallback: alter Test-Channel Modus
            ch=guild.get_channel(TEST_CHANNEL_ID)
            if isinstance(ch, discord.TextChannel):
                channel=ch

        if channel is None:
            # letzter Fallback: Systemchannel, falls vorhanden
            if isinstance(guild.system_channel, discord.TextChannel):
                channel=guild.system_channel

        if channel is None:
            await self._ephemeral_notice(
                interaction,
                "Ich konnte keinen Ziel-Textchannel bestimmen (kein Zugriff / falscher Channel-Typ).",
            )
            return

        day_iso=session.day_date_iso or _now_local().date().isoformat()
        max_players=int(session.max_players or 2)
        owner_id=interaction.user.id

        if session.category == "muhhelfer":
            ping_role_id=ROLE_SCHWER_ID if session.difficulty == "schwer" else ROLE_NORMAL_ID

        elif session.category == "spots":
            if (session.spot_key or "") == "olun":
                tier=(session.olun_tier or "").lower()
                if tier == "dehkia1":
                    ping_role_id=ROLE_OLUN_DEHKIA1_ID
                elif tier == "dehkia2":
                    ping_role_id=ROLE_OLUN_DEHKIA2_ID
                else:
                    ping_role_id=ROLE_OLUN_NORMAL_ID
            else:
                ping_role_id=SPOT_PING_ROLE.get(
                    session.spot_key or "", TEST_ROLE_ID)

        elif session.category == "atoraxxion":
            # ✅ eine gemeinsame Atoraxxion-Rolle (laut dir)
            ping_role_id=ROLE_ATORAXXION_ID

        elif session.category == "altar":
            # ✅ Altar-Rolle schon mal korrekt setzen (Flow/30 Stufen kommt danach)
            ping_role_id=ROLE_ALTAR_ID

        else:
            ping_role_id=ROLE_PILAFE_ID

        data={
            "guild_id": guild.id,
            "channel_id": channel.id,
            "message_id": 0,
            "owner_id": owner_id,
            "auto_closed_at": 0,
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
            "atoraxxion_runs": list(session.atoraxxion_runs or []),
            "altar_cleared_step": session.altar_cleared_step,
            "altar_target_step": session.altar_target_step,
        }
        # ✅ Easteregg beim Ersteller (nur wenn AP > 396)
        _ensure_easter_egg_text(data, owner_id, session.own_ap)

        if session.category == "muhhelfer":
            data["difficulty"]=session.difficulty or "normal"
            data["boss_runs"]=dict(session.boss_runs)
        if session.category == "spots":
            data["spot_key"]=session.spot_key
            if (session.spot_key or "") == "olun":
                data["olun_tier"]=session.olun_tier or "normal"

        if session.category == "pilafe":
            data["scroll_amount"]=session.scroll_amount

        embed=await self._build_public_embed(guild, data)

        content=f"<@&{ping_role_id}>"
        allowed=discord.AllowedMentions(
            roles=True, users=False, everyone=False)

        msg: Optional[discord.Message]=None

        try:
            # 1) Discord-Post senden
            msg=await channel.send(
                content=content,
                embed=embed,
                allowed_mentions=allowed,
            )
            data["message_id"]=msg.id
            self._log_info(
                "CREATE",
                "message created",
                message_id=msg.id,
                guild_id=guild.id,
                channel_id=channel.id,
                owner_id=owner_id,
                category=session.category,
            )

            # 2) View vorbereiten und am Post setzen
            view=PublicPostView(self, msg.id)
            await self._apply_dynamic_button_labels(view, data)
            await msg.edit(view=view)

            # 3) Erst jetzt persistent speichern
            async with self.config.guild(guild).searches() as searches:
                searches[str(msg.id)]=data
            self._log_info(
                "CREATE",
                "search entry saved",
                message_id=msg.id,
                guild_id=guild.id,
                channel_id=channel.id,
            )
            # 4) View erst nach erfolgreichem Save registrieren
            self.bot.add_view(view)

        except Exception:
            self._log_error(
                "CREATE",
                "create flow failed",
                message_id=(msg.id if msg is not None else 0),
                guild_id=guild.id,
                channel_id=channel.id,
                owner_id=owner_id,
                category=session.category,
            )

            try:
                await self._log_event(
                    guild,
                    "error",
                    "Gruppensuche",
                    "Create Failed",
                    (
                        "Eine Gruppensuche konnte nicht vollständig erstellt werden.\n\n"
                        "Der Bot hat versucht, den Vorgang zurückzurollen, damit kein unvollständiger Post bestehen bleibt."
                    ),
                    channel=channel,
                )
            except Exception:
                pass

            # Rollback:
            # Wenn der Discord-Post schon existiert, aber Save/Edit scheitert,
            # versuchen wir die Nachricht wieder zu entfernen, damit kein "toter" Post stehen bleibt.
            if msg is not None:
                try:
                    await msg.delete()
                except Exception:
                    pass

            await self._ephemeral_notice(
                interaction,
                "❌ Die Gruppensuche konnte nicht vollständig erstellt werden. Bitte versuche es erneut.",
                ephemeral=True,
            )
            return

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

            try:
                await self._run_auto_close()
            except Exception:
                pass

            await asyncio.sleep(30)  # alle 30s checken reicht völlig

    async def _run_start_reminders(self):
        if not FEATURE_DM_REMINDERS:
            return

        guild=self.bot.get_guild(GUILD_ID)
        if guild is None:
            return

        searches=await self.config.guild(guild).searches()
        if not searches:
            return

        now=_now_local()

        for mid_str, data in (searches or {}).items():
            try:
                if bool(data.get("is_closed", False)):
                    continue

                start_dt=_build_start_dt_if_possible(data)
                if not start_dt:
                    continue

                remind_at=start_dt - dt.timedelta(minutes=30)
                if now < remind_at or now >= start_dt:
                    continue

                reminders=data.get("reminders")
                if not isinstance(reminders, dict):
                    reminders={}

                # bereits gesendet?
                if int(reminders.get("start_30m", 0)) > 0:
                    continue

                # senden
                await self._send_start_30m_reminder(guild, int(data.get("message_id", 0)), data)

                # markieren
                ts=int(_now_local().timestamp())
                reminders["start_30m"]=ts
                data["reminders"]=reminders
                data["updated_at"]=ts
                await self._set_search(int(data.get("message_id", 0)), data)

            except Exception:
                continue

    async def _run_auto_close(self):
        if not FEATURE_AUTO_CLOSE:
            return

        guild=self.bot.get_guild(GUILD_ID)
        if guild is None:
            return

        searches=await self.config.guild(guild).searches()
        if not searches:
            return

        now=_now_local()

        for mid_str, data in (searches or {}).items():
            try:
                mid=int(mid_str)
                fresh: Optional[dict]=None

                # schon geschlossen? -> nix tun
                if bool(data.get("is_closed", False)):
                    continue

                # bereits auto-closed markiert? (Safety)
                if int(data.get("auto_closed_at", 0)) > 0:
                    continue

                close_dt=_build_auto_close_dt(data)
                if not close_dt:
                    continue

                if now < close_dt:
                    continue

                # ✅ Close unter Lock (Race-sicher)
                lock=self._lock_for(mid)
                async with lock:
                    fresh=await self._get_search(mid)
                    if not fresh:
                        continue

                    if bool(fresh.get("is_closed", False)):
                        continue
                    if int(fresh.get("auto_closed_at", 0)) > 0:
                        continue

                    fresh["is_closed"]=True
                    fresh["auto_closed_at"]=int(_now_local().timestamp())

                    await self._save_refresh_dispatch(fresh)

                await self._post_save_refresh_dispatch(fresh)

            except Exception:
                continue

    async def _send_start_30m_reminder(self, guild: discord.Guild, message_id: int, data: dict):
        if not FEATURE_DM_REMINDERS:
            return

        channel=guild.get_channel(int(data.get("channel_id", 0)))
        jump=f"https://discord.com/channels/{guild.id}/{int(data.get('channel_id', 0))}/{message_id}"

        max_players=int(data.get("max_players", 2))
        participants=list(data.get("participants") or [])

        owner_id=int(data.get("owner_id", 0))
        free=max(0, max_players - len(participants))

        def _member_has_no_dm_role(member: discord.Member) -> bool:
            return any(r.id == ROLE_NO_DM_ID for r in getattr(member, "roles", []))

        # Owner NICHT in Teilnehmer-DM aufnehmen (sonst 2x DM)
        participants_dm=[uid for uid in participants if int(uid) != owner_id]

        day_iso=data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_str=_format_day(dt.date.fromisoformat(day_iso))
        except Exception:
            day_str=str(day_iso)

        start_text=data.get("start_text") or "—"

        # 1) DM an Teilnehmer (opt-out respektieren)
        failed: list[int]=[]
        for uid in participants_dm:
            m=guild.get_member(int(uid))
            if not m:
                continue

            if _member_has_no_dm_role(m):
                continue

            try:
                await m.send(
                    f"⏰ **Reminder:** In ~30 Minuten geht’s los.\n"
                    f"**Tag:** {day_str}\n"
                    f"**Start:** {start_text}\n"
                    f"{jump}"
                )
            except Exception:
                failed.append(int(uid))

        # Fallback: wer DMs zu hat -> Ping im Channel
        if failed and isinstance(channel, discord.TextChannel):
            mentions=" ".join(f"<@{uid}>" for uid in failed)
            try:
                await channel.send(
                    f"⏰ Reminder (DM fehlgeschlagen): {mentions}\n"
                    f"**Start:** {start_text} | {day_str}\n{jump}",
                    allowed_mentions=discord.AllowedMentions(
                        users=True, roles=False, everyone=False),
                )
            except Exception:
                pass

        # 2) Extra DM an Ersteller (Host) – opt-out respektieren
        owner=guild.get_member(owner_id)
        if owner and not _member_has_no_dm_role(owner):
            try:
                extra=f"\n⚠️ Es fehlen noch **{free}** Teilnehmer." if free > 0 else "\n✅ Gruppe ist voll."
                await owner.send(
                    f"⏰ **Reminder (Host):** In ~30 Minuten.\n"
                    f"**Tag:** {day_str}\n"
                    f"**Start:** {start_text}"
                    f"{extra}\n{jump}"
                )
            except Exception:
                pass

    async def _join(self, interaction: discord.Interaction, message_id: int, ap_val: str):
        if self._interaction_guard_hit(
            action="join",
            user_id=int(interaction.user.id),
            message_id=int(message_id),
        ):
            await self._ephemeral_notice(
                interaction,
                "⏳ Deine letzte Anmeldung wird bereits verarbeitet.",
                ephemeral=True,
            )
            return

        data: Optional[dict]=None

        lock=self._lock_for(message_id)
        async with lock:
            data=await self._get_search(message_id)
            if data is None:
                await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.")
                return

            if bool(data.get("is_closed", False)):
                await self._ephemeral_notice(interaction, "Diese Suche ist geschlossen.")
                return

            ap_val=str(ap_val or "").strip()
            if not ap_val or not ap_val.isdigit():
                await self._ephemeral_notice(interaction, "Bitte nur Zahlen bei AP eintragen (z.B. 301).")
                return

            uid=interaction.user.id
            participants: List[int]=list(data.get("participants") or [])
            waitlist: List[int]=list(data.get("waitlist") or [])
            max_players=int(data.get("max_players", 2))

            # ✅ Wenn schon eingetragen: AP aktualisieren (Teilnehmer ODER Warteschlange)
            if uid in participants:
                ap_map=data.get("participant_ap") or {}
                ap_map[str(uid)]=ap_val
                data["participant_ap"]=ap_map
                _sync_easter_egg_text(data, uid, ap_val)

                if _ap_triggers_easter_egg(ap_val):
                    _ensure_easter_egg_text(data, uid, ap_val)
                else:
                    egg_map=data.get("easter_egg_texts")
                    if isinstance(egg_map, dict):
                        egg_map.pop(str(uid), None)
                        data["easter_egg_texts"]=egg_map

                await self._save_refresh_dispatch(data)

            elif uid in waitlist:
                wl_map=data.get("waitlist_ap") or {}
                wl_map[str(uid)]=ap_val
                data["waitlist_ap"]=wl_map

                if _ap_triggers_easter_egg(ap_val):
                    _ensure_easter_egg_text(data, uid, ap_val)
                else:
                    egg_map=data.get("easter_egg_texts")
                    if isinstance(egg_map, dict):
                        egg_map.pop(str(uid), None)
                        data["easter_egg_texts"]=egg_map

                await self._save_refresh_dispatch(data)

            elif len(participants) < max_players:
                participants.append(uid)
                data["participants"]=participants

                ap_map=data.get("participant_ap") or {}
                ap_map[str(uid)]=ap_val
                data["participant_ap"]=ap_map

                _ensure_easter_egg_text(data, uid, ap_val)

                await self._save_refresh_dispatch(data)

            else:
                waitlist.append(uid)
                data["waitlist"]=waitlist
                data["updated_at"]=int(_now_local().timestamp())

                wl_map=data.get("waitlist_ap") or {}
                wl_map[str(uid)]=ap_val
                data["waitlist_ap"]=wl_map

                _ensure_easter_egg_text(data, uid, ap_val)

                await self._save_refresh_dispatch(data)

        await self._post_save_refresh_dispatch(data)

        if uid in participants:
            self._log_info(
                "JOIN",
                "participant ap updated",
                message_id=message_id,
                user_id=uid,
                ap=ap_val,
            )
            await self._ephemeral_notice(interaction, "✅ AP aktualisiert (Teilnehmer).")
            return

        if uid in waitlist:
            self._log_info(
                "JOIN",
                "waitlist ap updated",
                message_id=message_id,
                user_id=uid,
                ap=ap_val,
            )
            await self._ephemeral_notice(interaction, "✅ AP aktualisiert (Warteschlange).")
            return

        if len(data.get("participants") or []) <= max_players and uid in list(data.get("participants") or []):
            self._log_info(
                "JOIN",
                "user joined as participant",
                message_id=message_id,
                user_id=uid,
                ap=ap_val,
                participants=len(data.get("participants") or []),
                max_players=max_players,
            )
            await self._ephemeral_notice(interaction, "✅ Du bist jetzt Teilnehmer.")
            return

        self._log_info(
            "JOIN",
            "user added to waitlist",
            message_id=message_id,
            user_id=uid,
            ap=ap_val,
            waitlist=len(data.get("waitlist") or []),
            max_players=max_players,
        )
        await self._ephemeral_notice(interaction, "ℹ️ Gruppe ist voll. Du bist in der Warteschlange.")

    async def _leave(self, interaction: discord.Interaction, message_id: int):
        if self._interaction_guard_hit(
            action="leave",
            user_id=int(interaction.user.id),
            message_id=int(message_id),
        ):
            await self._ephemeral_notice(
                interaction,
                "⏳ Deine letzte Abmeldung wird bereits verarbeitet.",
                ephemeral=True,
            )
            return

        # ✅ ACK-safe
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        data: Optional[dict]=None
        promoted_id: Optional[int]=None

        lock=self._lock_for(message_id)
        async with lock:
            data=await self._get_search(message_id)
            if data is None:
                await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.", ephemeral=True)
                return

            uid=interaction.user.id
            participants: List[int]=list(data.get("participants") or [])
            waitlist: List[int]=list(data.get("waitlist") or [])
            max_players=int(data.get("max_players", 2))

            was_participant=uid in participants
            was_wait=uid in waitlist

            if not was_participant and not was_wait:
                await self._ephemeral_notice(interaction, "Du bist nicht eingetragen.", ephemeral=True)
                return

            if was_participant:
                participants.remove(uid)
            if was_wait:
                waitlist.remove(uid)

            ap_map=data.get("participant_ap") or {}
            wl_map=data.get("waitlist_ap") or {}

            if was_participant:
                ap_map.pop(str(uid), None)
            if was_wait:
                wl_map.pop(str(uid), None)

            data["participant_ap"]=ap_map
            data["waitlist_ap"]=wl_map

            egg_map=data.get("easter_egg_texts")
            if isinstance(egg_map, dict):
                egg_map.pop(str(uid), None)
                data["easter_egg_texts"]=egg_map

            if was_participant and len(participants) < max_players and waitlist:
                promoted_id=int(waitlist.pop(0))
                participants.append(promoted_id)

                wl_map=data.get("waitlist_ap") or {}
                ap_map=data.get("participant_ap") or {}

                promoted_ap=wl_map.pop(str(promoted_id), None)
                if promoted_ap:
                    ap_map[str(promoted_id)]=promoted_ap

                data["waitlist_ap"]=wl_map
                data["participant_ap"]=ap_map

            data["participants"]=participants
            data["waitlist"]=waitlist

            await self._save_refresh_dispatch(data)

        await self._post_save_refresh_dispatch(data)

        self._log_info(
            "LEAVE",
            "user removed from search",
            message_id=message_id,
            user_id=uid,
            promoted_id=(promoted_id or 0),
        )

        await self._ephemeral_notice(interaction, "✅ Du wurdest abgemeldet.", ephemeral=True)

        if promoted_id:
            await self._notify_promotion(data, promoted_id)

    async def _apply_ap_adjust(self, interaction: discord.Interaction, message_id: int, ap_val: int):
        if self._interaction_guard_hit(
            action="ap_adjust",
            user_id=int(interaction.user.id),
            message_id=int(message_id),
        ):
            await self._ephemeral_notice(
                interaction,
                "⏳ Deine letzte AP-Änderung wird bereits verarbeitet.",
                ephemeral=True,
            )
            return

        # ACK-safe
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        data: Optional[dict]=None

        lock=self._lock_for(int(message_id))
        uid=int(interaction.user.id)

        async with lock:
            data=await self._get_search(int(message_id))
            if data is None:
                await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.", ephemeral=True)
                return

            participants: List[int]=list(data.get("participants") or [])
            waitlist: List[int]=list(data.get("waitlist") or [])

            is_participant=uid in participants
            is_wait=uid in waitlist

            if not is_participant and not is_wait:
                await self._ephemeral_notice(interaction, "Du bist nicht eingetragen.", ephemeral=True)
                return

            ap_map=data.get("participant_ap") or {}
            wl_map=data.get("waitlist_ap") or {}

            ap_clean=str(int(ap_val))

            if is_participant:
                ap_map[str(uid)]=ap_clean
            else:
                wl_map[str(uid)]=ap_clean

            data["participant_ap"]=ap_map
            data["waitlist_ap"]=wl_map

            _sync_easter_egg_text(data, uid, ap_clean)

            await self._save_refresh_dispatch(data)

        await self._post_save_refresh_dispatch(data)

        self._log_info(
            "AP_EDIT",
            "user ap adjusted",
            message_id=message_id,
            user_id=uid,
            ap=ap_clean,
            target=("participants" if is_participant else "waitlist"),
        )

        await self._ephemeral_notice(interaction, "✅ AP wurde aktualisiert.", ephemeral=True)

    async def _notify_promotion(self, data: dict, promoted_id: int):
        guild=self.bot.get_guild(int(data.get("guild_id", 0)))
        if guild is None:
            return
        channel=guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            return

        def _member_has_no_dm_role(member: discord.Member) -> bool:
            return any(r.id == ROLE_NO_DM_ID for r in getattr(member, "roles", []))

        owner_id=int(data.get("owner_id", 0))
        mid=int(data.get("message_id", 0))
        jump=f"https://discord.com/channels/{guild.id}/{channel.id}/{mid}"

        day_iso=data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_d=dt.date.fromisoformat(day_iso)
            day_str=_format_day(day_d)
        except Exception:
            day_str=str(day_iso)

        start_text=data.get("start_text") or "—"

        owner_member=guild.get_member(owner_id)
        promoted_member=guild.get_member(promoted_id)

        owner_dm_ok=False
        promoted_dm_ok=False

        if owner_member and not _member_has_no_dm_role(owner_member):
            try:
                await owner_member.send(
                    f"🔔 **Warteschlange aufgerückt**\n"
                    f"In deiner Suche ({day_str} / {start_text}) ist "
                    f"{promoted_member.mention if promoted_member else f'<@{promoted_id}>'} nachgerückt.\n"
                    f"Link: {jump}"
                )
                owner_dm_ok=True
            except Exception:
                owner_dm_ok=False

        if promoted_member and not _member_has_no_dm_role(promoted_member):
            try:
                await promoted_member.send(
                    f"❗ **Ein Teilnehmer hat abgesagt.**\n"
                    f"Du bist bei der Suche nachgerückt und jetzt **Teilnehmer**.\n\n"
                    f"⏰ Start: {day_str} / {start_text}\n"
                    f"Link: {jump}"
                )
                promoted_dm_ok=True
            except Exception:
                promoted_dm_ok=False

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
        # ✅ ack-sicher: erst defer, dann nur followup (und öffentliche Channel-Nachricht separat)
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        if bool(data.get("is_closed", False)):
            await self._ephemeral_notice(interaction, "Diese Suche ist geschlossen.", ephemeral=True)
            return

        cd=data.get("ping_cd") or {}
        now_ts=int(_now_local().timestamp())

        type_map=cd.get("type")
        if not isinstance(type_map, dict):
            type_map={}

        last=int(cd.get("type", 0))
        diff=now_ts - last
        if diff < PING_COOLDOWN_SECONDS:
            remaining=PING_COOLDOWN_SECONDS - diff
            await self._ephemeral_notice(
                interaction,
                f"⏳ Ping-Cooldown aktiv. Du kannst das wieder {_format_remaining(remaining)} benutzen.",
                ephemeral=True,
            )
            return

        cd["type"]=now_ts
        data["ping_cd"]=cd

        await self._save_refresh_dispatch(data)

        guild=interaction.guild
        if guild is None:
            await self._ephemeral_notice(interaction, "Nur auf Servern nutzbar.", ephemeral=True)
            return

        channel=guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            await self._ephemeral_notice(interaction, "Channel nicht gefunden.", ephemeral=True)
            return

        ping_role_id=int(data.get("ping_role_id", TEST_ROLE_ID))
        max_players=int(data.get("max_players", 2))
        participants=list(data.get("participants") or [])
        free=max(0, max_players - len(participants))

        day_iso=data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_d=dt.date.fromisoformat(day_iso)
            day_str=_format_day(day_d)
        except Exception:
            day_str=str(day_iso)

        start_text=data.get("start_text") or "—"
        jump=f"https://discord.com/channels/{guild.id}/{channel.id}/{message_id}"

        txt=f"<@&{ping_role_id}> | {day_str} | Start: {start_text} | Frei: {free}\n{jump}"
        await channel.send(
            txt,
            allowed_mentions=discord.AllowedMentions(
                roles=True, users=False, everyone=False),
        )

    async def _ping_wait(self, interaction: discord.Interaction, message_id: int, data: dict):
        # ✅ ack-sicher: erst defer, dann nur followup
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        if bool(data.get("is_closed", False)):
            await self._ephemeral_notice(interaction, "Diese Suche ist geschlossen.", ephemeral=True)
            return

        cd=data.get("ping_cd") or {}
        now_ts=int(_now_local().timestamp())

        wait_map=cd.get("wait")
        if not isinstance(wait_map, dict):
            wait_map={}

        last=int(cd.get("wait", 0))
        diff=now_ts - last
        if diff < PING_COOLDOWN_SECONDS:
            remaining=PING_COOLDOWN_SECONDS - diff
            await self._ephemeral_notice(
                interaction,
                f"⏳ Ping-Cooldown aktiv. Du kannst das wieder {_format_remaining(remaining)} benutzen.",
                ephemeral=True,
            )
            return

        cd["wait"]=now_ts
        data["ping_cd"]=cd

        await self._save_refresh_dispatch(data)

        guild=interaction.guild
        if guild is None:
            await self._ephemeral_notice(interaction, "Nur auf Servern nutzbar.", ephemeral=True)
            return

        channel=guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            await self._ephemeral_notice(interaction, "Channel nicht gefunden.", ephemeral=True)
            return

        day_iso=data.get("day_date_iso") or _now_local().date().isoformat()
        try:
            day_d=dt.date.fromisoformat(day_iso)
            day_str=_format_day(day_d)
        except Exception:
            day_str=str(day_iso)

        start_text=data.get("start_text") or "—"
        jump=f"https://discord.com/channels/{guild.id}/{channel.id}/{message_id}"

        txt=f"🔔 Ping Warteschlange | {day_str} | Start: {start_text}\n{jump}"
        await channel.send(txt, allowed_mentions=discord.AllowedMentions.none())

    async def _close_search(self, interaction: discord.Interaction, message_id: int):
        if self._interaction_guard_hit(
            action="close",
            user_id=int(interaction.user.id),
            message_id=int(message_id),
        ):
            await self._ephemeral_notice(
                interaction,
                "⏳ Die letzte Aktion zum Schließen wird bereits verarbeitet.",
                ephemeral=True,
            )
            return

        # ✅ ACK-safe
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        data: Optional[dict]=None

        lock=self._lock_for(int(message_id))
        async with lock:
            data=await self._get_search(int(message_id))
            if data is None:
                return

            data["is_closed"]=True
            await self._save_refresh_dispatch(data)

        await self._post_save_refresh_dispatch(data)

    async def _open_search(self, interaction: discord.Interaction, message_id: int):
        if self._interaction_guard_hit(
            action="open",
            user_id=int(interaction.user.id),
            message_id=int(message_id),
        ):
            await self._ephemeral_notice(
                interaction,
                "⏳ Die letzte Aktion zum Öffnen wird bereits verarbeitet.",
                ephemeral=True,
            )
            return

        # ✅ ACK-safe
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        data: Optional[dict]=None

        lock=self._lock_for(int(message_id))
        async with lock:
            data=await self._get_search(int(message_id))
            if data is None:
                await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.", ephemeral=True)
                return

            data["is_closed"]=False
            await self._save_refresh_dispatch(data)

        await self._post_save_refresh_dispatch(data)
        await self._ephemeral_notice(interaction, "✅ Suche wieder geöffnet.")

    async def _delete_search(self, interaction: discord.Interaction, message_id: int):
        if self._interaction_guard_hit(
            action="delete",
            user_id=int(interaction.user.id),
            message_id=int(message_id),
        ):
            await self._ephemeral_notice(
                interaction,
                "⏳ Die letzte Löschaktion wird bereits verarbeitet.",
                ephemeral=True,
            )
            return

        data=await self._get_search(message_id)
        if data is None:
            return

        guild=interaction.guild
        if guild is None:
            # Ohne Guild-Kontext nichts löschen:
            # sonst riskieren wir wieder "sichtbarer Post, aber Storage weg".
            self._log_warning(
                "DELETE",
                "delete aborted because guild is unavailable",
                message_id=message_id,
            )
            try:
                bot_guild=self.bot.get_guild(GUILD_ID)
                if bot_guild is not None:
                    await self._log_event(
                        bot_guild,
                        "error",
                        "Gruppensuche",
                        "Delete Failed",
                        (
                            "Eine Gruppensuche konnte nicht sicher gelöscht werden.\n\n"
                            "Der Guild-Kontext war nicht verfügbar.\n"
                            "Der Storage-Eintrag wurde nicht entfernt."
                        ),
                    )
            except Exception:
                pass

            await self._ephemeral_notice(
                interaction,
                "❌ Die Suche konnte nicht sicher gelöscht werden (Guild nicht verfügbar).",
                ephemeral=True,
            )
            return

        channel=guild.get_channel(int(data.get("channel_id", 0)))
        if not isinstance(channel, discord.TextChannel):
            self._log_warning(
                "DELETE",
                "delete aborted because channel is unavailable",
                message_id=message_id,
                guild_id=guild.id,
                channel_id=int(data.get("channel_id", 0)),
            )
            try:
                await self._log_event(
                    guild,
                    "error",
                    "Gruppensuche",
                    "Delete Failed",
                    (
                        "Eine Gruppensuche konnte nicht sicher gelöscht werden.\n\n"
                        "Der Ziel-Channel war nicht verfügbar.\n"
                        "Der Storage-Eintrag wurde nicht entfernt."
                    ),
                )
            except Exception:
                pass

            await self._ephemeral_notice(
                interaction,
                "❌ Die Suche konnte nicht sicher gelöscht werden (Channel nicht gefunden).",
                ephemeral=True,
            )
            return

        # Nachricht MUSS erfolgreich gelöscht werden,
        # bevor der Storage-Eintrag entfernt wird.
        try:
            msg=await channel.fetch_message(int(data.get("message_id", 0)))
            await msg.delete()
        except Exception:
            self._log_warning(
                "DELETE",
                "message delete failed, storage preserved",
                message_id=message_id,
                guild_id=guild.id,
                channel_id=channel.id,
            )
            try:
                await self._log_event(
                    guild,
                    "error",
                    "Gruppensuche",
                    "Delete Failed",
                    (
                        "Eine Gruppensuche konnte nicht vollständig gelöscht werden.\n\n"
                        "Die Discord-Nachricht konnte nicht entfernt werden.\n"
                        "Der Storage-Eintrag wurde deshalb bewusst beibehalten."
                    ),
                    channel=channel,
                )
            except Exception:
                pass

            await self._ephemeral_notice(
                interaction,
                "❌ Die Suche konnte nicht vollständig gelöscht werden. Der Post wurde nicht entfernt.",
                ephemeral=True,
            )
            return

        await self._del_search(message_id)
        self._log_info(
            "DELETE",
            "search deleted successfully",
            message_id=message_id,
            guild_id=guild.id,
            channel_id=channel.id,
        )
        self._dispatch_dashboard_update(int(data.get("guild_id", 0)))

    # =========================
    # Edit Flow
    # =========================

    async def _open_owner_edit_menu(self, interaction: discord.Interaction, message_id: int, data: dict):
        session=WizardSession(
            user_id=int(interaction.user.id),
            guild_id=int(interaction.guild_id or 0),
            mode="edit",
            edit_message_id=int(message_id),

            category=str(data.get("category") or ""),
            day_date_iso=str(data.get("day_date_iso") or ""),
            difficulty=str(data.get("difficulty") or "") if str(
                data.get("category")) == "muhhelfer" else None,
            boss_runs=dict(data.get("boss_runs") or {}),
            spot_key=str(data.get("spot_key") or "") if str(
                data.get("category")) == "spots" else None,
            olun_tier=str(data.get("olun_tier") or "") if str(
                data.get("spot_key")) == "olun" else None,
            max_players=int(data.get("max_players", 2)),
            scroll_amount=str(data.get("scroll_amount") or "") if str(
                data.get("category")) == "pilafe" else None,
            duration_text=data.get("duration_text"),
            start_text=data.get("start_text"),
            req_text=data.get("req_text"),
            notes=data.get("notes"),
            own_ap=str(data.get("owner_ap") or "") or None,
            atoraxxion_runs=list(_normalize_atoraxxion_runs(data)),
            altar_cleared_step=int(data.get("altar_cleared_step")) if data.get("altar_cleared_step") is not None else None,
            altar_target_step=int(data.get("altar_target_step")) if data.get("altar_target_step") is not None else None,
        )

        session.wizard_interaction=interaction
        self._sessions[int(interaction.user.id)]=session

        view=EditMenuView(self, session, data)
        embed=view.embed()

        # Ephemeral senden (ACK-safe)
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _start_edit_flow(self, interaction: discord.Interaction, message_id: int, data: Optional[dict]=None):
        if data is None:
            data=await self._get_search(int(message_id))

        if data is None:
            await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.", ephemeral=True)
            return
        self._log_info(
            "EDIT",
            "edit flow started",
            message_id=message_id,
            user_id=int(interaction.user.id),
        )
        # Owner/Admin/Offizier -> Owner Menü
        if await self._is_owner_or_mod(interaction, int(message_id)):
            await self._open_owner_edit_menu(interaction, int(message_id), data)
            return

        # Teilnehmer / Warteliste -> nur AP-Korrektur
        try:
            await interaction.response.send_modal(APAdjustModal(self, int(message_id)))
        except discord.InteractionResponded:
            await interaction.followup.send_modal(APAdjustModal(self, int(message_id)))

    async def _send_edit_menu(self, interaction: discord.Interaction, session: WizardSession):
        if not session.edit_message_id:
            await self._ephemeral_notice(interaction, "Edit-Session ungültig.", ephemeral=True)
            return

        data=await self._get_search(session.edit_message_id)
        if data is None:
            await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.")
            return

        view=EditMenuView(self, session, data)

        # ✅ wichtig: wenn möglich immer die Interaction nehmen,
        # die zur Wizard-Ephemeral-Message gehört
        base=session.wizard_interaction or interaction
        await self._edit_or_send_ephemeral(base, view.embed(), view)

    async def _apply_edit_day(self, interaction: discord.Interaction, session: WizardSession):
        if not session.edit_message_id:
            return

        data: Optional[dict]=None

        lock=self._lock_for(int(session.edit_message_id))
        async with lock:
            data=await self._get_search(int(session.edit_message_id))
            if data is None:
                await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.")
                return

            # --- alten Wert sichern (WICHTIG für "old -> new") ---
            old_day_iso=str(data.get("day_date_iso") or "")

            # --- neuen Wert setzen ---
            data["day_date_iso"]=session.day_date_iso

            # ✅ Reminder reset, weil Tag geändert wurde
            rem=data.get("reminders")
            if not isinstance(rem, dict):
                rem={}
            rem.pop("start_30m", None)
            data["reminders"]=rem

            # --- Edit Notify (debounced) ---
            try:
                old_fmt=_format_day(dt.date.fromisoformat(
                    old_day_iso)) if old_day_iso else "—"
            except Exception:
                old_fmt=old_day_iso or "—"

            try:
                new_fmt=_format_day(dt.date.fromisoformat(
                    str(session.day_date_iso or ""))) if session.day_date_iso else "—"
            except Exception:
                new_fmt=str(session.day_date_iso or "—")

            self._schedule_edit_notify(
                int(session.edit_message_id),
                data,
                changes=[{"key": "day", "label": "Tag",
                          "old": old_fmt, "new": new_fmt}],
            )

            await self._save_refresh_dispatch(data)

        await self._post_save_refresh_dispatch(data)

        self._log_info(
            "EDIT",
            "day updated",
            message_id=int(session.edit_message_id),
            user_id=int(interaction.user.id),
            old=old_fmt,
            new=new_fmt,
        )

        await self._send_edit_menu(interaction, session)

    async def _apply_edit_max_players(self, interaction: discord.Interaction, session: WizardSession):
        if not session.edit_message_id:
            return

        # ✅ ACK-safe
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        message_id=int(session.edit_message_id)
        desired_max=int(session.max_players or 0)
        data: Optional[dict]=None

        # ✅ Admin-only: 1 Teilnehmer nur für Admin-Testzwecke
        member=_member_from_interaction(interaction)
        allow_one=bool(member and _is_admin_only(member))

        # ✅ Range korrekt bestimmen (und Admin-Override sauber berücksichtigen)
        mn, mx=_allowed_party_range(session.category or "", session.spot_key)
        if allow_one:
            mn=1

        if desired_max < mn or desired_max > mx:
            await self._ephemeral_notice(
                interaction,
                "Ungültige Teilnehmerzahl.",
                ephemeral=True,
            )
            return

        lock=self._lock_for(message_id)

        async with lock:
            data=await self._get_search(message_id)
            if data is None:
                await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.")
                return

            # --- alte Werte sichern (für Change-Notify) ---
            old_max=int(data.get("max_players", 2))
            old_part_count=len(list(data.get("participants") or []))
            old_wait_count=len(list(data.get("waitlist") or []))

            # --- neue max setzen ---
            data["max_players"]=int(desired_max)

            participants=list(data.get("participants") or [])
            waitlist=list(data.get("waitlist") or [])

            ap_map=data.get("participant_ap") or {}
            wl_map=data.get("waitlist_ap") or {}

            # 1) Wenn new_max kleiner ist: zu viele Teilnehmer -> in Warteschlange schieben (letzte zuerst)
            while len(participants) > desired_max:
                demoted_id=int(participants.pop())
                demoted_ap=ap_map.pop(str(demoted_id), None)
                if demoted_ap is not None:
                    wl_map[str(demoted_id)]=demoted_ap
                waitlist.insert(0, demoted_id)

            # 2) Wenn new_max größer ist: aus Warteschlange auffüllen
            while len(participants) < desired_max and waitlist:
                pid=int(waitlist.pop(0))
                participants.append(pid)

                promoted_ap=wl_map.pop(str(pid), None)
                if promoted_ap is not None:
                    ap_map[str(pid)]=promoted_ap

            data["participants"]=participants
            data["waitlist"]=waitlist
            data["participant_ap"]=ap_map
            data["waitlist_ap"]=wl_map

            await self._save_refresh_dispatch(data)

            # --- neue Werte ---
            new_max=int(data.get("max_players", 2))
            new_part_count=len(list(data.get("participants") or []))
            new_wait_count=len(list(data.get("waitlist") or []))

            changes=[
                {"key": "max_players", "label": "Max. Teilnehmer",
                    "old": str(old_max), "new": str(new_max)},
            ]

            if (old_part_count, old_wait_count) != (new_part_count, new_wait_count):
                changes.append({
                    "key": "lists",
                    "label": "Teilnehmer/Warteschlange",
                    "old": f"{old_part_count} / {old_wait_count}",
                    "new": f"{new_part_count} / {new_wait_count}",
                })

            self._schedule_edit_notify(message_id, data, changes=changes)

        await self._post_save_refresh_dispatch(data)

        self._log_info(
            "EDIT",
            "max players updated",
            message_id=message_id,
            user_id=int(interaction.user.id),
            new_max=desired_max,
        )
        await self._send_edit_menu(interaction, session)

    async def _apply_edit_details(self, interaction: discord.Interaction, session: WizardSession):
        if not session.edit_message_id:
            return

        data: Optional[dict]=None

        lock=self._lock_for(int(session.edit_message_id))
        async with lock:
            data=await self._get_search(int(session.edit_message_id))
            if data is None:
                await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.")
                return

            cat=str(data.get("category", "")).lower()

            # --- alte Werte sichern ---
            old_duration=data.get("duration_text")
            old_start=data.get("start_text")
            old_req=data.get("req_text")
            old_notes=data.get("notes")
            old_day_iso=data.get("day_date_iso")
            old_amount=data.get("scroll_amount") if cat == "pilafe" else None
            old_owner_ap=data.get("owner_ap")

            # --- Änderungen anwenden ---
            if cat == "pilafe" and session.scroll_amount is not None:
                data["scroll_amount"]=session.scroll_amount

            if session.duration_text is not None:
                data["duration_text"]=session.duration_text

            if session.start_text is not None:
                data["start_text"]=session.start_text

            if session.req_text is not None:
                data["req_text"]=session.req_text

            if session.notes is not None:
                data["notes"]=session.notes

            # ✅ Host-AP korrekt übernehmen
            if session.own_ap is not None:
                owner_id=int(data.get("owner_id", 0))
                data["owner_ap"]=session.own_ap

                ap_map=data.get("participant_ap")
                if not isinstance(ap_map, dict):
                    ap_map={}

                ap_map[str(owner_id)]=session.own_ap
                data["participant_ap"]=ap_map

                # ✅ Easter-Egg Host: setzen ODER entfernen (bei AP-Korrektur)
                _sync_easter_egg_text(data, owner_id, session.own_ap)

            # ✅ Reminder reset bei Start/Tag-Änderung
            if (data.get("start_text") != old_start) or (data.get("day_date_iso") != old_day_iso):
                rem=data.get("reminders")
                if not isinstance(rem, dict):
                    rem={}
                rem.pop("start_30m", None)
                data["reminders"]=rem

            # --- Speichern ---
            await self._save_refresh_dispatch(data)

            # --- Change-Liste bauen ---
            changes: list[dict]=[]

            if cat == "pilafe":
                if old_amount != data.get("scroll_amount"):
                    changes.append({
                        "key": "scroll_amount",
                        "label": "Menge",
                        "old": old_amount,
                        "new": data.get("scroll_amount")
                    })

            if old_duration != data.get("duration_text"):
                changes.append({
                    "key": "duration",
                    "label": "Geplante Dauer",
                    "old": old_duration,
                    "new": data.get("duration_text")
                })

            if old_start != data.get("start_text"):
                changes.append({
                    "key": "start",
                    "label": "Startzeit",
                    "old": old_start,
                    "new": data.get("start_text")
                })

            # ✅ Kategorieabhängiges Label für req
            if old_req != data.get("req_text"):
                req_label="Gewünschte AP" if cat in (
                    "atoraxxion", "altar") else "Anforderung AK/VK"
                changes.append({
                    "key": "req",
                    "label": req_label,
                    "old": old_req,
                    "new": data.get("req_text")
                })

            if old_notes != data.get("notes"):
                changes.append({
                    "key": "notes",
                    "label": "Notiz",
                    "old": old_notes,
                    "new": data.get("notes")
                })

            # ✅ Host-AP Change-Notify
            if old_owner_ap != data.get("owner_ap"):
                changes.append({
                    "key": "owner_ap",
                    "label": "Host AP",
                    "old": old_owner_ap,
                    "new": data.get("owner_ap"),
                })

            if changes:
                self._schedule_edit_notify(
                    int(session.edit_message_id),
                    data,
                    changes=changes
                )

        await self._post_save_refresh_dispatch(data)

        self._log_info(
            "EDIT",
            "details updated",
            message_id=int(session.edit_message_id),
            user_id=int(interaction.user.id),
            category=cat,
        )

        # Zurück ins Edit-Menü (ohne neues Ephemeral)
        await self._send_edit_menu(interaction, session)

    async def _apply_edit_bosses(self, interaction: discord.Interaction, session: WizardSession):
        if not session.edit_message_id:
            return

        data: Optional[dict]=None

        lock=self._lock_for(int(session.edit_message_id))
        async with lock:
            data=await self._get_search(int(session.edit_message_id))
            if data is None:
                await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.")
                return

            if data.get("category") != "muhhelfer":
                await self._ephemeral_notice(interaction, "Bossbearbeitung ist nur für Muhhelfer.", ephemeral=True)
                return

            if not session.boss_runs:
                await self._ephemeral_notice(interaction, "Bitte mindestens 1 Boss auswählen.", ephemeral=True)
                return

            def _fmt_boss_runs(br: dict) -> str:
                if not isinstance(br, dict) or not br:
                    return "—"
                parts=[]
                for k, v in br.items():
                    name=_boss_name(str(k))
                    runs=int(v or 1)
                    parts.append(f"{name}{' (2x)' if runs >= 2 else ''}")
                return ", ".join(parts)

            old_bosses=_fmt_boss_runs(data.get("boss_runs") or {})
            data["boss_runs"]=dict(session.boss_runs)
            data["updated_at"]=int(_now_local().timestamp())
            await self._save_refresh_dispatch(data)
            new_bosses=_fmt_boss_runs(data.get("boss_runs") or {})
            self._schedule_edit_notify(
                int(session.edit_message_id),
                data,
                changes=[{"key": "bosses", "label": "Bosse",
                          "old": old_bosses, "new": new_bosses}],
            )

        await self._post_save_refresh_dispatch(data)
        await self._send_edit_menu(interaction, session)

    async def _apply_edit_altar_steps(self, interaction: discord.Interaction, session: WizardSession):
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        if not session.edit_message_id:
            return

        data: Optional[dict] = None

        lock = self._lock_for(int(session.edit_message_id))
        async with lock:
            data = await self._get_search(int(session.edit_message_id))
            if data is None:
                await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.")
                return

            if str(data.get("category", "")).lower() != "altar":
                await self._ephemeral_notice(interaction, "Step-Bearbeitung ist nur für Altar des Blutes.")
                return

            old_cleared = data.get("altar_cleared_step")
            old_target = data.get("altar_target_step")

            if session.altar_cleared_step is None:
                await self._ephemeral_notice(interaction, "Bitte wähle den höchsten geclearten Step.")
                return

            if session.altar_target_step is None:
                await self._ephemeral_notice(interaction, "Bitte wähle den Ziel-Step.")
                return

            if session.altar_target_step <= session.altar_cleared_step:
                await self._ephemeral_notice(
                    interaction,
                    "Der Ziel-Step muss höher sein als der bereits geclearte Step.",
                )
                return

            data["altar_cleared_step"] = int(session.altar_cleared_step)
            data["altar_target_step"] = int(session.altar_target_step)

            await self._save_refresh_dispatch(data)

            self._schedule_edit_notify(
                int(session.edit_message_id),
                data,
                changes=[
                    {
                        "key": "altar_cleared_step",
                        "label": "Altar gecleart",
                        "old": f"Step {old_cleared}" if old_cleared is not None else "—",
                        "new": f"Step {data['altar_cleared_step']}",
                    },
                    {
                        "key": "altar_target_step",
                        "label": "Altar Ziel",
                        "old": f"Step {old_target}" if old_target is not None else "—",
                        "new": f"Step {data['altar_target_step']}",
                    },
                ],
            )

        await self._post_save_refresh_dispatch(data)
        await self._send_edit_menu(interaction, session)

    async def _apply_edit_atoraxxion_runs(self, interaction: discord.Interaction, session: WizardSession):
        # ACK sichern (verhindert "Interaktion fehlgeschlagen")
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass

        if not session.edit_message_id:
            return

        data: Optional[dict]=None

        lock=self._lock_for(int(session.edit_message_id))
        async with lock:
            data=await self._get_search(int(session.edit_message_id))
            if data is None:
                await self._ephemeral_notice(interaction, "Diese Suche existiert nicht mehr.")
                return

            if str(data.get("category", "")).lower() != "atoraxxion":
                await self._ephemeral_notice(interaction, "Dungeon-Bearbeitung ist nur für Atoraxxion.", ephemeral=True)
                return

            # alte / neue Auswahl normalisieren
            old_runs=_normalize_atoraxxion_runs(data)
            new_runs=list(session.atoraxxion_runs or [])

            # nur erlaubte Keys + stabile Reihenfolge
            allowed_order=["vahmalkea", "sycrakea", "yolunakea", "orzekea"]
            new_runs=[k for k in allowed_order if k in {
                str(x).lower().strip() for x in new_runs}]

            # wenn nichts gewählt -> Fehlermeldung
            if not new_runs:
                await self._ephemeral_notice(interaction, "Bitte wähle mindestens einen Dungeon aus.", ephemeral=True)
                return

            data["atoraxxion_runs"]=new_runs
            data["updated_at"]=int(_now_local().timestamp())

            await self._save_refresh_dispatch(data)

            def _fmt(keys: list[str]) -> str:
                if set(keys) == set(allowed_order):
                    return "Kompletter Run"
                m={
                    "vahmalkea": "Vahmalkea",
                    "sycrakea": "Sycrakea",
                    "yolunakea": "Yolunakea",
                    "orzekea": "Orzekea",
                }
                return ", ".join(m.get(k, k) for k in keys) if keys else "—"

            self._schedule_edit_notify(
                int(session.edit_message_id),
                data,
                changes=[{
                    "key": "atoraxxion_runs",
                    "label": "Atoraxxion Auswahl",
                    "old": _fmt(old_runs),
                    "new": _fmt(new_runs),
                }],
            )

        await self._post_save_refresh_dispatch(data)
        await self._send_edit_menu(interaction, session)
