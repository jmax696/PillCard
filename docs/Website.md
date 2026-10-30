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
  („Selbst anpassen bis“), Vorrat, Nachfüllen (+), Warnschwelle. Eine leere Kammer (Vorrat 0) ist
  rot markiert, dann leuchtet auch die LED am Einfüllstutzen.
- **E-Rezept scannen** (`/admin/kammern/<nr>/rezept`): leere Kammer mit einem neuen Medikament belegen.
  1. QR-Code des E-Rezepts bzw. eMediplans fotografieren (am Handy öffnet sich die Kamera) oder den Text
     einfügen, z. B. von einem USB-QR-Scanner. Gelesen wird der Code im Browser (eingebaute Erkennung,
     sonst [jsQR](https://github.com/cozmo/jsQR) vom CDN). Eine Live-Kamera geht nicht, weil Browser die
     Kamera nur über HTTPS freigeben.
  2. Medikament aus dem Rezept wählen. Die Website schlägt Tabletten pro Tag (Summe aus morgens, mittags,
     abends, nachts) und den Nutzer vor, dessen Name zum Patienten passt.
  3. Namen ergänzen (echte E-Rezepte enthalten nur GTIN/Pharmacode), eingefüllte Menge eintragen,
     speichern. Pläne anderer Nutzer für diese Kammer fallen weg, „selbst anpassen“ ist aus.
  Test-Codes liegen in [`Test-Rezepte/`](Test-Rezepte/). Die Signatur des E-Rezepts wird nicht geprüft.
- **Heute zurücksetzen** (für die Demo): löscht die heutigen Ausgaben. Gibt es auf der Übersicht
  und im Demo-Dashboard.

## Servos kalibrieren – `/admin/servos`

Für jede Kammer: Bei **Grundstellung** fährt der Servo mit ◀ ▶ (1°) und « » (5°) live mit, bis die
Kammer genau in der Grundstellung steht. Bei **Drehung** stellt man ein, wie weit er zur Ausgabe
dreht (10–180°, Start 90°); dabei fährt er gleich zur neuen Ausgabeposition. Die Richtung (zu
kleineren oder größeren Winkeln) wählt man pro Kammer. „Ausgabe zeigen“ fährt probehalber dorthin,
„Zurück zur Grundstellung“ wieder zurück.
**Speichern** legt die Werte in `kammern` ab (`ruhe_winkel`, `drehung`, `richtung`); `pillcard.py`
schickt sie dem ESP32 (`WINKEL …`), der sie ab der nächsten Ausgabe nutzt. Nicht gespeicherte
Änderungen sind markiert. Läge die Ausgabe außerhalb 0–180°, lässt sich nicht speichern: dann die
Drehung verkleinern, die Richtung umstellen oder das Servohorn eine Zacke versetzen.

**Probe-Ausgabe** gibt mit den gespeicherten Werten einmal aus (fällt eine echte Tablette), ohne
Eintrag im Kalender und ohne den Vorrat zu ändern.

Die Website steuert den ESP32 nicht selbst: Sie legt Befehle in `servo_befehl` ab, `pillcard.py`
holt sie ab. Läuft PillCard nicht, zeigt die Seite einen Hinweis.

## Demo-Dashboard – `/admin/demo`

Für Präsentation und Beamer, nur mit dem Passwort der Verwaltung. Die Seite holt sich alle
2 Sekunden neue Daten (`/admin/demo/daten`, JSON, liest nur) und muss nicht neu geladen werden.

- **Kopf:** Datum, Uhr, „live“-Anzeige (rot, wenn die Website nicht erreichbar ist), Knopf
  **Vollbild** und **Heute zurücksetzen**.
- **Neue Ausgabe:** Hält jemand die Karte ans Gerät, erscheint oben ein großer Hinweis, z. B.
  „Anna hat um 08:12 Uhr 4 Tabletten bekommen“ (gelb bei weniger als geplant, rot bei Fehler am
  Gerät). Läuft gerade ein Anlernen, steht dort „der Leser wartet auf eine neue Karte“.
- **Kennzahlen:** heute abgeholt (x von y Nutzern mit Plan), Tabletten heute (laut Mikrofon),
  abgeholt in den letzten 7 Tagen (Anteil der Tage ab der ersten Ausgabe des Nutzers),
  Gerätefehler heute.
- **Nutzer heute:** Status mit Uhrzeit, heutige Dosis (angepasste Mengen markiert), die letzten
  7 Tage als Leiste.
- **Letzte Ausgaben:** die letzten 7 Ausgaben mit Zeit, Nutzer, Mengen und Ergebnis.
- **Tabletten pro Tag:** Säulen für die letzten 14 Tage, Wert beim Zeigen mit Maus oder Tab-Taste,
  darunter „Als Tabelle“.
- **Vorrat:** pro Kammer Anzahl, Balken für „reicht noch N Tage“ (voll = 30 Tage, Strich =
  Warnschwelle) und „bald leer“.

## Nutzerbereich – `/`

- Login mit Benutzername und Passwort (vergibt die Verwaltung). Die aktuelle Seite ist in der
  Navigation unterstrichen.
- **Heute** – von oben nach unten nach Wichtigkeit:
  1. Begrüßung mit Tageszeit und Datum.
  2. **Große Statuskarte:** „Ihre Tabletten liegen bereit – Karte ans Gerät halten“ mit der heutigen
     Menge (angepasste Mengen markiert), „Heute erledigt“ mit Uhrzeit, „weniger als geplant“ (gelb)
     oder „Das Gerät hat einen Fehler gemeldet“ (rot), jeweils mit Symbol und Text.
  3. **Vorratswarnung:** gelber Hinweis, wenn eine seiner Kammern knapp wird.
  4. **Morgen:** was es morgen gibt, angepasste Mengen markiert.
  5. **Letzte 7 Tage:** Leiste mit ✓ / ! / ⚠ / – pro Tag, Link zum Kalender.
  6. **Dosis nach Tagesform:** anpassbare Medikamente mit − / + zwischen 0 und „Selbst anpassen bis“
     (liegt die verordnete Menge höher, bis zu ihr), für heute oder morgen. Weicht der Wert vom
     normalen Plan ab, steht „geändert“ daneben. Nach dem Speichern bestätigt die Seite, was es
     geben wird. Ist heute schon ausgegeben, geht nur noch „Morgen“.
- **Kalender:** Monatsansicht, pro Tag ✓ mit Anzahl Tabletten, ! wenn weniger kam als geplant,
  ⚠ bei Fehler am Gerät, – (grau) für nicht abgeholt. Oben die Bilanz des Monats („an 26 von 29
  Tagen abgeholt“) und, in anderen Monaten, „Zum aktuellen Monat“. Ein Tag lässt sich antippen;
  die Details erscheinen direkt unter dem Kalender.

## Betrieb auf dem Pi

```bash
cd ~/pillcard
venv/bin/pip install flask waitress     # einmalig
./web.sh &                              # Website mit Neustart-Schleife, Ausgaben in web.log
```

Lokal am Mac testen (ohne Pi und Kartenleser): Flask und waitress in eine eigene venv, dann mit
einer Test-Datenbank starten – die UID beim Anlernen von Hand eintragen.

```bash
PILLCARD_DB=/tmp/test.db python pi/web.py --debug --port 8080
```

Autostart: in `crontab -e` die Zeile `@reboot /home/admin/pillcard/web.sh` ergänzen
(neben der für `start.sh`).

Sicherheit: gedacht fürs Heimnetz. Passwörter nur als Hash, Formulare mit Token gegen fremde
Seiten, Cookie-Schlüssel in `geheim.key` (nur für `admin` lesbar). Kein HTTPS – nicht ins
Internet freigeben.
