"""
Export Cog - Exportiert die Member-Liste als Excel-Datei.
Folgt den KUHMUH-Regelwerken fuer Slash-Commands und Guild-Scope.
"""

import io
import logging
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

import discord  # pyright: ignore[reportMissingImports]
from discord import app_commands  # pyright: ignore[reportMissingImports]
from redbot.core import commands  # pyright: ignore[reportMissingImports]
from redbot.core.bot import Red  # pyright: ignore[reportMissingImports]

# ====== Server-spezifische IDs (aus RULEBOOK) ======
GUILD_ID = 1198649628787212458
OWNER_ID = 359447597427064833
ADMIN_ROLE_ID = 1198650646786736240
OFFIZIER_ROLE_ID = 1198652039312453723

MUHKUH_EMOJI = "<:muhkuh:1207038544510586890>"

log = logging.getLogger("red.kuhmuh.export")


def _excel_col_name(index: int) -> str:
    """Wandelt 1-basierte Spaltennummern in Excel-Spaltennamen um."""
    out = []
    current = int(index)
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        out.append(chr(65 + remainder))
    return "".join(reversed(out))


def _xml_cell(cell_ref: str, value: object, style_id: int | None = None) -> str:
    """Erzeugt eine einzelne XLSX-Zelle mit Inline-String oder Zahl."""
    style_attr = f' s="{style_id}"' if style_id is not None else ""

    if isinstance(value, bool):
        value = "Ja" if value else "Nein"

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{cell_ref}"{style_attr}><v>{value}</v></c>'

    safe = escape(str(value))
    return f'<c r="{cell_ref}"{style_attr} t="inlineStr"><is><t>{safe}</t></is></c>'


def _xml_sheet(
    rows: list[list[object]],
    vertical_header_cols: set[int] | None = None,
    compact_cols: set[int] | None = None,
) -> str:
    """Erzeugt den XML-Inhalt fuer ein Worksheet."""
    vertical_header_cols = vertical_header_cols or set()
    compact_cols = compact_cols or set()

    cols_xml = ""
    if rows:
        col_defs = []
        for col_idx in range(1, len(rows[0]) + 1):
            width = 4 if col_idx in compact_cols else 22
            col_defs.append(
                f'<col min="{col_idx}" max="{col_idx}" width="{width}" customWidth="1"/>'
            )
        cols_xml = f"<cols>{''.join(col_defs)}</cols>"

    row_xml: list[str] = []
    for row_idx, row in enumerate(rows, start=1):
        row_attrs = f' r="{row_idx}"'
        if row_idx == 1 and vertical_header_cols:
            row_attrs += ' ht="120" customHeight="1"'

        cells = [
            _xml_cell(
                f"{_excel_col_name(col_idx)}{row_idx}",
                value,
                style_id=1 if row_idx == 1 and col_idx in vertical_header_cols else None,
            )
            for col_idx, value in enumerate(row, start=1)
        ]
        row_xml.append(f"<row{row_attrs}>{''.join(cells)}</row>")

    sheet_data = "".join(row_xml)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"{cols_xml}"
        f"<sheetData>{sheet_data}</sheetData>"
        "</worksheet>"
    )


def _build_xlsx_workbook(
    sheets: list[tuple[str, list[list[object]], set[int], set[int]]]
) -> bytes:
    """Erzeugt eine minimale XLSX-Datei mit mehreren Worksheets."""
    workbook_sheets = []
    workbook_rels = []
    content_types = [
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    ]

    for idx, (name, _rows, _vertical_header_cols, _compact_cols) in enumerate(sheets, start=1):
        safe_name = escape(name)
        workbook_sheets.append(
            f'<sheet name="{safe_name}" sheetId="{idx}" r:id="rId{idx}"/>'
        )
        workbook_rels.append(
            '<Relationship '
            f'Id="rId{idx}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{idx}.xml"/>'
        )
        content_types.append(
            '<Override '
            f'PartName="/xl/worksheets/sheet{idx}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
    content_types.append(
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook '
        'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{''.join(workbook_sheets)}</sheets>"
        "</workbook>"
    )

    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(workbook_rels)}"
        '<Relationship '
        f'Id="rId{len(sheets) + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        "</Relationships>"
    )

    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship '
        'Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f"{''.join(content_types)}"
        "</Types>"
    )

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
        '<alignment textRotation="180" horizontal="center" vertical="top" wrapText="1"/>'
        '</xf>'
        '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/styles.xml", styles_xml)
        for idx, (_name, rows, vertical_header_cols, compact_cols) in enumerate(sheets, start=1):
            zf.writestr(
                f"xl/worksheets/sheet{idx}.xml",
                _xml_sheet(rows, vertical_header_cols, compact_cols),
            )

    return buffer.getvalue()


class Export(commands.Cog):
    """Cog fuer Export der Memberliste und Rollenrechte."""

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self._startup_task = self.bot.loop.create_task(self._startup_guild_sync())

    async def _startup_guild_sync(self) -> None:
        """Synchronisiert den guild-scoped Slash-Command beim Start."""
        try:
            await self.bot.wait_until_red_ready()
            await self.bot.wait_until_ready()
            await self.bot.tree.sync(guild=discord.Object(id=GUILD_ID))
            log.info("[export] Slash-Command fuer Guild %s synchronisiert.", GUILD_ID)
        except Exception:
            log.exception("[export] Slash-Sync fuer Guild %s fehlgeschlagen.", GUILD_ID)

    def cog_unload(self) -> None:
        if self._startup_task and not self._startup_task.done():
            self._startup_task.cancel()

    def _has_export_permission(self, user: discord.User | discord.Member) -> bool:
        """Prueft, ob der Nutzer Export-Berechtigung hat."""
        if not isinstance(user, discord.Member):
            return False

        if user.id == OWNER_ID:
            return True

        return any(role.id in {ADMIN_ROLE_ID, OFFIZIER_ROLE_ID} for role in user.roles)

    def _get_join_method(self, member: discord.Member) -> str:
        """
        Versucht, die Beitrittsmethode zu ermitteln.
        Discord stellt diese Info nicht direkt bereit; aktuell liefern wir
        daher den definierten Fallback.
        """
        _ = member
        return "Invite"

    def _build_member_rows(
        self,
        members: list[discord.Member],
        guild: discord.Guild,
    ) -> tuple[list[list[object]], set[int], set[int]]:
        roles = [role for role in guild.roles if role.name != "@everyone"]
        roles.sort(key=lambda role: role.position, reverse=True)

        rows: list[list[object]] = [
            [
                "Nickname",
                "Discord-Name",
                "Beitrittsdatum Server",
                "Beitrittsmethode",
                *[role.name for role in roles],
            ]
        ]

        for member in sorted(members, key=lambda m: m.joined_at or datetime.now()):
            discord_name = (
                f"{member.name}#{member.discriminator}"
                if member.discriminator
                else member.name
            )

            join_date = (
                member.joined_at.strftime("%d.%m.%Y %H:%M:%S")
                if member.joined_at
                else "Unbekannt"
            )
            member_role_ids = {role.id for role in member.roles}

            rows.append(
                [
                    member.display_name,
                    discord_name,
                    join_date,
                    self._get_join_method(member),
                    *["X" if role.id in member_role_ids else "" for role in roles],
                ]
            )

        role_column_start = 5
        role_columns = set(range(role_column_start, role_column_start + len(roles)))
        return rows, role_columns, role_columns

    def _build_role_rows(self, guild: discord.Guild) -> list[list[object]]:
        permission_flags = sorted(discord.Permissions.VALID_FLAGS.keys())
        rows: list[list[object]] = [
            [
                "Rollenname",
                "Rollen-ID",
                "Farbe",
                "Position",
                "Erwaehnbar",
                "Getrennt angezeigt",
                "Managed",
                "Mitglieder mit Rolle",
                "Aktive Rechte",
                *permission_flags,
            ]
        ]

        roles = [role for role in guild.roles if role.name != "@everyone"]
        roles.sort(key=lambda role: role.position, reverse=True)

        for role in roles:
            permissions_map = dict(role.permissions)
            active_permissions = [
                name for name in permission_flags if permissions_map.get(name, False)
            ]

            rows.append(
                [
                    role.name,
                    role.id,
                    str(role.color),
                    role.position,
                    role.mentionable,
                    role.hoist,
                    role.managed,
                    len(role.members),
                    "; ".join(active_permissions) if active_permissions else "Keine",
                    *[permissions_map.get(name, False) for name in permission_flags],
                ]
            )

        return rows

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="export", description="Exportiert Mitglieder und Rollenrechte als Excel-Datei")
    @app_commands.choices(
        format=[
            app_commands.Choice(name="Excel-Datei", value="xlsx"),
        ]
    )
    async def export_member(
        self,
        interaction: discord.Interaction,
        format: str = "xlsx",
    ) -> None:
        """
        Exportiert die Memberliste sowie eine separate Tabelle aller Rollen
        inklusive ihrer Rechte.
        """
        if not interaction.guild or interaction.guild.id != GUILD_ID:
            await interaction.response.send_message(
                "❌ Dieser Command ist nur in der Kuhmuh-Guild verfuegbar.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Dieser Command kann nur innerhalb des Servers verwendet werden.",
                ephemeral=True,
            )
            return

        if format != "xlsx":
            await interaction.response.send_message(
                "❌ Aktuell wird nur das Format Excel (.xlsx) unterstuetzt.",
                ephemeral=True,
            )
            return

        if not self._has_export_permission(interaction.user):
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung fuer diesen Command. "
                "Nur Admins und Offiziere koennen exportieren.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            members = list(guild.members)
            if not members:
                await interaction.followup.send("❌ Keine Member gefunden.", ephemeral=True)
                return

            member_rows, member_vertical_cols, member_compact_cols = self._build_member_rows(
                members,
                guild,
            )
            role_rows = self._build_role_rows(guild)
            workbook_bytes = _build_xlsx_workbook(
                [
                    ("Mitglieder", member_rows, member_vertical_cols, member_compact_cols),
                    ("Rollenrechte", role_rows, set(), set()),
                ]
            )

            export_file = discord.File(
                io.BytesIO(workbook_bytes),
                filename=f"server_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            )

            embed = discord.Embed(
                title=f"{MUHKUH_EMOJI} Export erfolgreich",
                description=(
                    f"**{len(members)}** Member und **{len(guild.roles) - 1}** Rollen "
                    "wurden exportiert."
                ),
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="Tabellenblaetter",
                value=(
                    "• Mitglieder\n"
                    "• Rollenrechte"
                ),
                inline=False,
            )
            embed.set_footer(text=f"Exportiert von {interaction.user.display_name}")

            await interaction.followup.send(
                embed=embed,
                file=export_file,
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Fehler beim Export: {str(e)}",
                ephemeral=True,
            )
