# Analyse V1

Stand: 2026-09-27

## 1. Geltungsbereich

Diese Datei dokumentiert ausschließlich den Ist-Stand des V1-Repositoryteils (`V1/`). V2 wird hier nicht mitgeführt; der V2-Ist-Stand steht in [`../V2/Analyse.md`](../V2/Analyse.md).

Der gemeinsame Stand vor der Repo-Trennung (27.09.2026) steht weiterhin im Archiv unter [`../Analyse.md`](../Analyse.md). Dort dokumentierte V1-Cogs, Doppelungen und Risiken gelten bis zum Trennungszeitpunkt unverändert fort und werden hier nicht erneut kopiert.

## 2. Fortführung

Ab dem Trennungszeitpunkt werden neue V1-spezifische Analyseergebnisse, Abweichungen und offene Entscheidungen ausschließlich hier ergänzt. Bestehende Einträge werden nicht gelöscht oder stillschweigend überschrieben.

## 3. Offene Punkte (übernommen aus dem Archiv)

- Gruppensuche ist weiterhin doppelt vorhanden: V1 live (`V1/gruppensuche/`) und V1 test (`V1/gruppensuche_test/`).
- `info.json` ist bei mehreren V1-Cogs nicht durchgehend vertrauenswürdig (siehe Archiv, Abschnitt 2).
- Mehrere V1-Cogs registrieren Slash-Commands weiterhin über `cog_load()` bzw. `tree.add_command()`.
