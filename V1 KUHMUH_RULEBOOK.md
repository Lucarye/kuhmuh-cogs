📌 Kuhmuh – Discord Bot Governance & Architektur

Version 1.12 – Aktiv
Status: Aktiv

Dieses Dokument beschreibt die verbindlichen Governance- und Architekturziele für den V1-Repositoryteil der Discord-Bot-Umgebung von Kuhmuh. V1 und V2 fungieren als eigenständige Repositories mit jeweils eigener Analyse, Änderungshistorie und Patchnotes; dieses Rulebook gilt ausschließlich für `V1/`.

Der aktuelle Ist-Stand von V1 ist in `V1/Analyse.md` dokumentiert. Die Arbeitsweise für Änderungen im VS-Code-Workspace steht in `V1 KUHMUH_WORKMODE.md`. Der gemeinsame Stand vor der Repo-Trennung steht archiviert in `../Analyse.md`, `../Änderungen.md` und `../Patchnotes.md`.

## 1. Betrieb und Verantwortlichkeiten

### 1.1 Betriebsmodell

- serverintern betrieben (vorgegebene Betriebsannahme)
- vollständig eigenverwaltet (vorgegebene Betriebsannahme)
- keine externe Distribution (vorgegebene Betriebsannahme)
- Betrieb mit administrativen Serverrechten (vorgegebene Betriebsannahme)

### 1.2 Zugriffskontrolle

```text
OWNER_ID = 359447597427064833
ADMIN_ROLE_ID = 1198650646786736240
OFFIZIER_ROLE_ID = 1198652039312453723
```

- Administrative Aktionen benötigen eine passende Berechtigung.
- Automatisierte Massenänderungen benötigen eine bewusste Freigabe.
- Owner-, Administrator-, Rollen- und `manage_guild`-Prüfungen müssen im jeweiligen Cog nachvollziehbar bleiben.

## 2. Systemumgebung

```text
GUILD_ID = 1198649628787212458
BOT_KATEGORIE_ID = 1460005712041349201
TEST_CHANNEL_ID = 1199322485297000528
TEST_ROLE_ID = 1445018518562017373
MUHKUH_EMOJI = <:muhkuh:1207038544510586890>
```

Repository für diesen Workspace:

`https://github.com/Lucarye/kuhmuh-cogs/tree/main`

Das laufende Bot-System besteht aus mehreren Repositories. `groupfinder` und `logging` laufen aus einem separaten Repository und sind bei Gesamtanalysen getrennt zu berücksichtigen.

Eigene Cogs bilden die Kernarchitektur. Community-Cogs sind nicht Bestandteil dieser Richtlinien.

## 3. Architektur

### 3.0 Aussagen, Annahmen und Schaetzungen

- Gepruefte Ist-Fakten, verbindliche Zielvorgaben, Annahmen und offene Entscheidungen werden getrennt ausgewiesen.
- Eine Annahme darf keine konkrete Architektur- oder Implementierungsentscheidung begruenden, bevor sie am lokalen Codepfad, an der Konfiguration oder an der Runtime geprueft wurde.
- Aufwand, Dauer und Reichweite werden nicht als Tatsachen dargestellt. Eine erforderliche Schaetzung muss ihre Grundlage und ihren Unsicherheitsbereich nennen und als `Schaetzung` gekennzeichnet werden.

### 3.1 Verantwortlichkeit

- Ein Cog soll grundsätzlich eine erkennbare fachliche Verantwortung besitzen.
- Neue Funktionen sollen nicht ohne Grund in bestehende, fachfremde Cogs eingebaut werden.
- Konfiguration, Berechtigungen, UI, Persistenz und Hintergrundaufgaben sollen so getrennt werden, wie es der lokale Bestand sinnvoll zulässt.

### 3.2 Umgang mit V1 und V2

- V1 und V2 sind unterschiedliche Entwicklungsstände und werden nicht unkontrolliert vermischt.
- Der bestehende V1-Code wird nicht nachträglich als einheitlich geplante Architektur ausgegeben.
- Verbesserungen am gewachsenen Bestand erfolgen schrittweise und berücksichtigen laufende Commands, gespeicherte Daten und bestehende Integrationen.
- `V2/logging` und `V1/willkommen` gelten aktuell als Referenz-Cogs. Sie sind Referenzen für neue Arbeiten, aber keine Behauptung, dass V1 und V2 bereits dieselbe Struktur besitzen.

### 3.3 Konfiguration und Daten

- Systemweite Werte können global konfiguriert werden.
- Guild-spezifische Werte werden nur verwendet, wenn sie fachlich oder betrieblich erforderlich sind.
- Rollen-, Channel-, Guild- und externe Repository-Abhängigkeiten müssen im Code oder in der zugehörigen Dokumentation eindeutig erkennbar sein.
- Öffentliche Commands und gespeicherte Datenformate dürfen nur mit bewerteter Kompatibilität geändert werden.

### 3.4 Kontrollierte Automatisierung

- Automatisierung darf Kontrolle und Berechtigungsprüfung nicht ersetzen.
- Hintergrundtasks benötigen nachvollziehbare Start-, Stop- und Fehlerbehandlung.
- Wiederholungen, Locks, Cooldowns und Retry-Logik müssen begründet und möglichst begrenzt sein.

## 4. Slash-Commands und Registrierung

### 4.1 Zielstandard für neue Commands

Neue serverinterne Slash-Commands sollen:

- Guild-scoped registriert werden;
- einen nachvollziehbaren Startup-Sync besitzen;
- Berechtigungen und Guild-Grenzen prüfen;
- eine klare, stabile Beschreibung und eindeutige Optionen besitzen.

Der bevorzugte Zielaufbau ist eine direkte Command-Definition am Cog mit Guild-Scope und einem kontrollierten Startup-Sync.

### 4.2 Gewachsener Bestand

Der reale Bestand verwendet teilweise `cog_load()` und `bot.tree.add_command()`. Diese Registrierungen sind als bestehender Übergangscode zu behandeln, nicht als Anlass für ungeplante Sofortumbauten.

Bei einer Änderung an einem betroffenen Cog ist zu prüfen:

- ob der Command doppelt oder global registriert wird;
- ob Reloads alte Commands entfernen;
- ob der Sync nur für die Ziel-Guild erfolgt;
- ob die Runtime-Integration aus einem anderen Repository betroffen ist.

## 5. UI, Kommunikation und Logging

- Ausgaben sollen klar, knapp und administrierbar sein.
- Status-Icons `✅`, `⚠️`, `❌` und `⏭️` können für Statusmeldungen verwendet werden.
- `MUHKUH_EMOJI` ist das primäre Projekt-Emoji, sofern es fachlich passt.
- Fachliche Nutzerantworten, technische Serverkonsolenlogs und Discord-Logchannel-Embeds sind getrennte Ausgabepfade.
- Logs sollen verwertbare Ereignisse enthalten und nicht durch unnötige Wiederholungen unlesbar werden.
- Zielchannel, Logkategorie und Berechtigung müssen vor einer Änderung am Logging geprüft werden.

## 6. Mehrere Repositories und Runtime

- Der Workspace ist nur ein Teil des laufenden Bot-Systems.
- Screenshots und Runtime-Listen können Cogs aus mehreren Repositories enthalten.
- Ein Cog gilt erst dann als entfernt, wenn geklärt ist, aus welchem Repository und welchem Redbot-Ladezustand er stammt.
- Bei einer Gesamtanalyse sind Repository-Bestand, installierte Cogs, registrierte Commands und tatsächliche Runtime getrennt zu erfassen.
- `Analyse.md` ist die Stelle für solche Abweichungen und offenen Abgleich.

## 7. Entwicklung und Qualität

- Vor einer Umsetzung stehen Ist-Stand, Abgrenzung, Risiko und Entscheidung.
- Änderungen bleiben fachlich und räumlich so klein wie möglich.
- Unbeteiligte Refactorings, Formatierungswellen und Architekturumbauten gehören nicht in eine Sachkorrektur.
- Bestehende Nutzeränderungen werden nicht ungefragt zurückgesetzt.
- Deutsche Umlaute und das Eszett werden korrekt als `ä`, `ö`, `ü` und `ß` geschrieben. ASCII-Umschreibungen sind nur zulässig, wenn ein technisches Format sie verlangt.
- Es werden keine Commits oder Branches angelegt, sofern dies nicht ausdrücklich beauftragt wurde.

## 8. Validierung

Jede Codeänderung benötigt mindestens einen passenden Nachweis:

1. Verhaltenstest oder gezielter Test für die betroffene Funktion.
2. Falls nicht verfügbar: Syntaxcheck, Typecheck, Lint oder ein enger Build-/Importcheck.
3. Falls keine ausführbare Prüfung möglich ist: gezielte Inhaltsprüfung mit benannter Restunsicherheit.

Nach einem fehlgeschlagenen Check bleibt die Arbeit zunächst im betroffenen Codepfad. Die lokale Ursache wird behoben und derselbe Check erneut ausgeführt, bevor der Bereich erweitert wird.

## 9. Dokumentation

Alle folgenden Dokumente beziehen sich ausschließlich auf `V1/`. Änderungen am V2-Repositoryteil gehören nicht hierher, sondern in die entsprechenden Dokumente unter `V2/`.

### 9.1 `V1/Analyse.md`

Dokumentiert den Ist-Stand von V1, Runtime-Beobachtungen, Doppelungen und offene Architekturentscheidungen. Der gemeinsame Stand vor der Repo-Trennung bleibt im Archiv `../Analyse.md` erhalten.

### 9.2 `V1/Änderungen.md`

Ist das chronologische technische Änderungsprotokoll für V1.

- Einträge enthalten Datum, Uhrzeit und das tatsächlich umgesetzte Ergebnis.
- Datum und Uhrzeit werden unmittelbar vor jedem neuen Eintrag durch eine eigenständige Abfrage der lokalen Systemzeit ermittelt; Chat-, Editor- oder Dateizeiten sowie Schätzungen sind nicht zulässig.
- Die bei der Abfrage verwendete Zeitzone wird im Eintrag mitgeführt.
- Einträge werden ergänzt, nicht gelöscht oder stillschweigend überschrieben.
- Änderungen werden erst nach erfolgreicher Validierung als `AKTIV` dokumentiert.
- Bei Anpassung, Ersatz oder Rücknahme bleibt der ursprüngliche Eintrag nachvollziehbar und verweist auf den Folgeeintrag.
- Änderungen, die ausschließlich V2 betreffen, werden nicht in dieser Datei dokumentiert.

### 9.3 `V1/Patchnotes.md`

Enthält ausschließlich veröffentlichte, kompakte Zusammenfassungen bereits abgeschlossener V1-Änderungen. Interne Tests, verworfene Zwischenstände und zurückgenommene Änderungen gehören nur in `V1/Änderungen.md`.

## 10. Dokumentenrollen

- `V1 KUHMUH_RULEBOOK.md`: Governance und langfristige Architekturziele für V1.
- `V1 KUHMUH_WORKMODE.md`: aktuelle Arbeitsweise für die V1-Workspace-Arbeit.
- `V1/Analyse.md`: geprüfter Ist-Stand und Abweichungen für V1.
- `V1/Änderungen.md`: technisches Änderungsprotokoll für V1.
- `V1/Patchnotes.md`: veröffentlichte Änderungszusammenfassungen für V1.
- `../Analyse.md`, `../Änderungen.md`, `../Patchnotes.md`: eingefrorenes Archiv des gemeinsamen Standes vor der Repo-Trennung.

Dieses Rulebook beschreibt Ziele und verbindliche Leitlinien. Der tatsächliche Codebestand wird nicht durch die Dokumentation überschrieben, sondern bei jeder relevanten Entscheidung gegen sie geprüft und bei Bedarf schrittweise angenähert.

