# Änderungen V1

> Diese Datei protokolliert ausschließlich technische Änderungen am V1-Repositoryteil (`V1/`). Änderungen am V2-Teil gehören nicht hierher, sondern in [`../V2/Änderungen.md`](../V2/Änderungen.md).

Der gemeinsame Verlauf vor der Repo-Trennung steht weiterhin im Archiv unter [`../Änderungen.md`](../Änderungen.md), unter anderem die vollständige Historie zu `V1/gruppensuche` und `V1/gruppensuche_test` (Reservisten, negative AP, Altar des Blutes, Button-Verifikation) bis 12.09.2026, 13:31 Uhr.

## 27.09.2026, 21:31:01 +02:00

- AKTIV: V1 und V2 als eigenständige Repositories dokumentiert. `Analyse.md`, `Änderungen.md` und `Patchnotes.md` für V1 unter `V1/` neu angelegt.
- Die bisherigen Root-Dateien `Analyse.md`, `Änderungen.md` und `Patchnotes.md` gelten ab sofort als eingefrorenes Archiv des gemeinsamen Standes vor der Trennung und werden nicht weiter fortgeschrieben.
- `V1 KUHMUH_RULEBOOK.md` und `V1 KUHMUH_WORKMODE.md` wurden entsprechend auf die lokalen V1-Dokumente umgestellt.
- Validierung: Inhaltsprüfung der neu angelegten und geänderten Dokumente; keine Codeänderung.

## 03.10.2026, 16:02:58 +02:00

- AKTIV: Automatische Slash-Command-Syncs entfernt. Ursache: `gruppenübersicht` synchronisierte in `cog_load()` noch während des Ladens; `gruppensuche` (in `packages` später geladen) fehlte im Tree und wurde bei jedem Botstart in Discord gelöscht und mit neuer ID neu angelegt. Die Berechtigungen aus den Server-Integrationen gingen dabei verloren.
  - `gruppenübersicht/gruppenübersicht.py`: Sync und manuelles `add_command` in `cog_load()` sowie `remove_command` in `cog_unload()` entfernt. `/dashboard` wird weiterhin über `@app_commands.guilds` registriert.
  - `export/export.py`: Startup-Task entfernt (enthielt nur den Sync).
  - `gruppensuche/GruppensucheModule.py`, `gruppensuche_test/GruppensucheModule.py`: Sync aus `_startup_register_views` entfernt; View-Registrierung bleibt.
  - `kuhmuhupdate/` gelöscht (Entscheidung: Updates über separaten Test-Bot). Auf Live vorher `°cog uninstall kuhmuhupdate`.
  - Command-Namen unverändert, keine Datenformatänderung.
- AKTIV: `V1 KUHMUH_RULEBOOK.md` §4 neu gefasst: kein Sync im Code, Sync nur manuell per `[p]slash sync <GUILD_ID>`, Command-Namen sind stabil.
- Validierung: `ruff check --select F` vorher/nachher verglichen, keine neuen Befunde (5 bestehende bleiben); Grep findet keine `tree.sync`/`add_command`/`remove_command`-Aufrufe mehr.
- Offen: Runtime nicht getestet. Nach Deploy einmalig `[p]slash sync <GUILD_ID>` mit allen geladenen Cogs, danach Command-IDs vor/nach Neustart vergleichen. Berechtigungen für `/gruppensuche` einmalig neu setzen.
