# KUHMUH WORKMODE

## Zweck

Diese Datei beschreibt die Arbeitsweise fuer die Arbeit am V1-Repositoryteil (`V1/`) im VS-Code-Workspace. Sie ist keine Beschreibung des Bot-Runtime-Systems und ersetzt keine fachliche Dokumentation in `V1/Analyse.md`. V1 und V2 fungieren als eigenstaendige Repositories; diese Datei gilt ausschliesslich fuer V1.

## Grundsaetze

- Erst den realen Ist-Stand pruefen, dann entscheiden und aendern.
- Keine Annahmen ueber Dateien, Commands, Ladezustaende oder Abhaengigkeiten treffen.
- V1, V2 und separat verwaltete Repositories als unterschiedliche Staende behandeln.
- `V2/logging` und `V1/willkommen` sind als Arbeitsreferenzen festgelegt. Diese Einordnung ist keine ungepruefte Aussage ueber den vollstaendigen Runtime- oder Repository-Stand.
- Aenderungen auf den kleinstmoeglichen fachlich sinnvollen Bereich begrenzen.

### Annahmen und Schaetzungen

- Verifizierte Fakten, Zielvorgaben, Annahmen und offene Punkte werden sprachlich getrennt benannt.
- Unverifizierte Annahmen duerfen keine Implementierungsentscheidung begruenden. Sie werden zuerst lokal geprueft oder als offene Entscheidung dokumentiert.
- Aufwand, Dauer oder Reichweite werden nicht geschaetzt, wenn keine belastbare Grundlage vorliegt. Erforderliche Schaetzungen erhalten eine Grundlage, einen Unsicherheitsbereich und die Kennzeichnung `Schaetzung`.

## Arbeitsablauf

1. Anfrage und betroffenen Codepfad bestimmen.
2. Relevante Dateien, Symbole, Konfigurationen und angrenzende Abhaengigkeiten lesen.
3. Eine lokale Hypothese formulieren und einen guenstigen Gegencheck bestimmen.
4. Erst danach die kleinste passende Aenderung umsetzen.
5. Direkt anschliessend einen fokussierten Test, Syntaxcheck, Lint-/Typecheck oder eine andere ausfuehrbare Validierung durchfuehren.
6. Bei erfolgreicher Validierung die tatsaechliche Aenderung in `Änderungen.md` dokumentieren.

### Pflichtabfrage bei neuen Cogs

Vor dem ersten Edit an einem neu zu erstellenden Cog muss ich ausdrücklich fragen, ob dieser Cog in den V2-Admin-Hub aufgenommen werden soll.

- Die Antwort muss `Admin-Hub: Ja`, `Admin-Hub: Nein` oder eine bewusste Zurückstellung sein.
- Ohne diese Entscheidung beginnt keine Implementierung des neuen Cogs.
- `Admin-Hub: Ja` bedeutet: Der Cog erhält die vorgesehene Opt-in-Kennzeichnung und eine `get_admin_panel()`-Schnittstelle.
- `Admin-Hub: Nein` bedeutet: Der Cog wird nicht automatisch im Admin-Hub registriert.
- Eine spätere Migration eines bestehenden Cogs erfolgt erst nach Review und Test und wird als neue V2-Logik umgesetzt.
- V1-Dateien werden bei einer Migration weder gelöscht noch geändert.

Bei unklarem oder widerspruechlichem Ist-Stand wird nicht geraten. Stattdessen wird der naechste lokale Codepfad geprueft oder die offene Frage benannt.

## Aenderungen

- Bestehende Nutzer- oder Arbeitsstandsaenderungen nicht ungefragt zuruecksetzen.
- Keine unbeteiligten Refactorings, Formatierungswellen oder Architekturumbauten in einer Sachkorrektur.
- Bestehende oeffentliche Commands und Datenformate nur aendern, wenn die Aufgabe dies erfordert oder die Kompatibilitaet bewusst bewertet wurde.
- Codekommentare nur ergaenzen, wenn sie eine nicht offensichtliche Entscheidung erklaeren.
- Dateien im vorhandenen Stil bearbeiten.
- Deutsche Umlaute und das Eszett korrekt schreiben: `ä`, `ö`, `ü`, `ß` statt `ae`, `oe`, `ue`, `ss`. ASCII-Umschreibungen nur verwenden, wenn ein technisches Format sie zwingend verlangt.
- Keine Commits oder Branches anlegen, ausser dies wird ausdruecklich verlangt.

## Validierung

Jede Codeaenderung braucht mindestens einen passenden Nachweis:

- Verhaltenstest oder gezielter Test fuer die betroffene Funktion.
- ansonsten Syntaxcheck, Typecheck, Lint oder ein enger Build-/Importcheck.
- wenn keine ausfuehrbare Pruefung verfuegbar ist: gezielte Inhaltspruefung und klare Kennzeichnung der Restunsicherheit.

Schlaegt die erste Validierung fehl, bleibt die Arbeit im betroffenen Codepfad. Zuerst wird die lokale Ursache behoben und derselbe Check erneut ausgefuehrt.

## Dokumentation

`V1/Analyse.md` dokumentiert den Ist-Stand von V1, Runtime-Beobachtungen und offene Architekturentscheidungen. Der gemeinsame Stand vor der Repo-Trennung bleibt im Archiv `../Analyse.md` erhalten.

`V1/Änderungen.md` ist das chronologische technische Protokoll fuer V1. Nach einer erfolgreich umgesetzten und validierten Aenderung an V1 wird ein neuer Eintrag mit Datum, Uhrzeit und dem tatsaechlichen Ergebnis ergaenzt. Bestehende Eintraege werden nicht geloescht oder stillschweigend umgeschrieben. Aenderungen, die ausschliesslich V2 betreffen, gehoeren in `../V2/Änderungen.md`.

Datum und Uhrzeit fuer jeden neuen Eintrag in `V1/Änderungen.md` werden unmittelbar davor durch eine eigenstaendige Abfrage der lokalen Systemzeit ermittelt. Chatzeit, Editorzeit, Dateizeit oder eine geschaetzte Uhrzeit sind dafuer nicht zulaessig; die verwendete Zeitzone wird mitgefuehrt.

Wenn ein dokumentierter Stand spaeter geaendert, ersetzt oder zurueckgenommen wird, bleibt der urspruengliche Eintrag nachvollziehbar und erhaelt einen passenden Status sowie einen Verweis auf den Folgeeintrag.

`V1/Patchnotes.md` enthaelt nur veroeffentlichte V1-Zusammenfassungen und wird nicht automatisch bei jeder technischen Aenderung aktualisiert.

## Architekturleitlinien

- Eine fachliche Funktion soll eine erkennbare Verantwortlichkeit haben.
- Neue Cogs sollen Konfiguration, Berechtigungen, UI, Persistenz und Hintergrundaufgaben so trennen, wie es der lokale Bestand sinnvoll zulaesst.
- Die Aufnahme in den Admin-Hub ist Opt-in und niemals automatisch. Ein Cog wird nur aufgenommen, wenn `ADMIN_HUB_ENABLED = True` festgelegt und eine Panel-Schnittstelle bereitgestellt wurde.
- Member-facing Cogs, insbesondere die Gruppensuche, werden nicht allein wegen ihrer Existenz in den Admin-Hub aufgenommen.
- Neue serverinterne Slash-Commands sollen Guild-scoped sein und einen nachvollziehbaren Startup-Sync besitzen.
- Berechtigungen, Zielkanaele und externe Repository-Grenzen muessen explizit dokumentiert werden.
- Bestehende V1-Cogs werden nicht nachtraeglich als einheitliche Architektur ausgegeben. Verbesserungen erfolgen schrittweise und mit Ruecksicht auf laufende Commands und Daten.

## Umgang mit mehreren Repositories

- Der aktuelle Workspace ist nur ein Teil des laufenden Bot-Systems.
- `groupfinder` und `logging` laufen aus einem separaten Repository und muessen bei einer Gesamtbewertung getrennt abgefragt werden.
- Ein Screenshot oder Runtime-Bestand kann Cogs aus mehreren Repositories enthalten.
- Vor einer Bereinigung immer klären, ob ein Cog im aktuellen Workspace, in einem separaten Repository oder nur noch in der laufenden Runtime existiert.

## Ergebnisstandard

Am Ende einer Arbeit sollen kurz erkennbar sein:

- was geaendert wurde,
- welche Dateien oder Commands betroffen sind,
- wie die Aenderung validiert wurde,
- welche Risiken oder offenen Entscheidungen verbleiben.