# Website

Die Website läuft auf dem Raspberry Pi neben `pillcard.py` und nutzt dieselbe Datenbank
([Datenbank.md](Datenbank.md)). Erreichbar im selben WLAN unter **http://192.168.31.142:8080**
(IP des Pi, `hostname -I`).

Code: [`pi/web.py`](../pi/web.py) (Flask, ausgeliefert mit waitress), Seiten in `pi/templates/`,
Aussehen in `pi/static/style.css`. Kein Internet nötig, alles liegt auf dem Pi.

## Verwaltung – `/admin`

- **Erster Aufruf:** Passwort für die Verwaltung festlegen (`/admin/einrichten`). Es liegt nur als
  Hash in der Tabelle `einstellungen`.
- **Übersicht:** alle Nutzer mit Karte, Plan und ob heute schon ausgegeben wurde; Vorrat jeder
  Kammer mit „reicht noch N Tage“ und Warnung, wenn er unter `warnen_ab` fällt.
- **＋ Neuen Nutzer anlernen:** Die Seite startet sofort einen Scan. Die nächste Karte am Leser
  gibt nichts aus, sondern meldet ihre UID an die Website (Display: „Karte erkannt“). Danach Name,
  Benutzername, Passwort und Dosierung pro Kammer eintragen (0–9 Tabletten je Kammer, frei
  wählbar, unabhängig von der Grenze für die Selbstanpassung). Gehört die Karte schon jemandem,
  zeigt die Seite das an. Ohne laufendes `pillcard.py` lässt sich die UID auch von Hand eintragen.
- **Bearbeiten:** Name, Karte (neu scannen), Passwort, Dosierung; Nutzer löschen.
- **Kammern:** Medikament, ob Nutzer selbst anpassen dürfen und bis zu welcher Menge
  („Selbst anpassen bis“), Vorrat, Nachfüllen (+), Warnschwelle.
- **Heute zurücksetzen** (für die Demo): löscht die heutigen Ausgaben.

## Nutzerbereich – `/`

- Login mit Benutzername und Passwort (vergibt die Verwaltung).
- **Heute:** ob schon ausgegeben wurde und wie viel aus jeder Kammer; sonst, was es heute gibt.
- **Vorratswarnung:** gelber Hinweis, wenn eine seiner Kammern knapp wird.
- **Dosis nach Tagesform:** anpassbare Medikamente mit − / + zwischen 0 und „Selbst anpassen bis“
  (liegt die verordnete Menge höher, bis zu ihr), für
  heute oder morgen. Nach dem Speichern bestätigt die Seite, was es geben wird. Ist heute schon
  ausgegeben, geht nur noch „Morgen“.
- **Kalender:** Monatsansicht, pro Tag ✓ mit Anzahl Tabletten, ! wenn weniger kam als geplant,
  ⚠ bei Fehler am Gerät, grau für nicht abgeholt. Ein Tag lässt sich antippen für die Details.

## Betrieb auf dem Pi

```bash
cd ~/pillcard
venv/bin/pip install flask waitress     # einmalig
./web.sh &                              # Website mit Neustart-Schleife, Ausgaben in web.log
```

Autostart: in `crontab -e` die Zeile `@reboot /home/admin/pillcard/web.sh` ergänzen
(neben der für `start.sh`).

Sicherheit: gedacht fürs Heimnetz. Passwörter nur als Hash, Formulare mit Token gegen fremde
Seiten, Cookie-Schlüssel in `geheim.key` (nur für `admin` lesbar). Kein HTTPS – nicht ins
Internet freigeben.
