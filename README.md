# PillCard

Ein Tablettenspender mit drei Kammern, den sich mehrere Personen teilen. Jede Person hält ihre RFID-Karte an das Gerät und bekommt die Tabletten, die heute für sie vorgesehen sind, in einen Becher, und zwar nur einmal pro Tag. Am Gerät selbst wird nichts eingestellt.

Projekt im Kurs **Hands-on HCI** (Universität St.Gallen, HS 2026), Team: Anastasia Eric, Max Jäckle, Kristian Suntev.

> Hinweis: Der erste Plan vom 27.10. (Arduino Uno, Plan auf der Karte, Lichtschranken) steht noch in `REQUIREMENTS.md`. Der fertige Prototyp ist anders aufgebaut, siehe unten.

## So funktioniert es

1. Die Person hält ihre Karte an das Lesefeld.
2. Der **Raspberry Pi** liest die Karte und prüft in der Datenbank: Ist die Karte bekannt? Gab es heute schon etwas? Was steht heute im Plan?
3. Wenn alles passt, schickt der Pi dem **ESP32** einen Auftrag, zum Beispiel `AUFTRAG 17 K1=1 K3=2`.
4. Der ESP32 wartet auf den Becher, dreht die Dosierscheiben Kammer für Kammer und prüft mit einem **Mikrofon**, ob jede Tablette gefallen ist.
5. Ein **Kontakt aus Kupferband** unter dem Becher merkt, wann der Becher abgeholt wird. Der Pi trägt die Abholung ein und kann Angehörigen eine Push-Mitteilung schicken.

Einstellen, Karten anlernen, Vorrat und Verlauf laufen über eine **lokale Website** auf dem Pi (Port 8080, nur im Heimnetz).

## Hardware

| Bauteil | Aufgabe |
|---|---|
| Raspberry Pi | liest die Karten (RC522), Datenbank (SQLite), Website |
| ESP32 (Keyestudio) | Servos, Mikrofon, Becherkontakt, Display, Lämpchen |
| RFID-Leser RC522 mit Karten und Chips | erkennt die Person |
| 3 Mikroservos SG90 | drehen die Dosierscheiben |
| Analoges Mikrofonmodul | hört jede fallende Tablette |
| Kupferband auf zwei Flächen | erkennt, ob der Becher steht |
| LCD 16×2, LEDs grün/rot, 3 Leer-LEDs | Rückmeldung am Gerät |
| Netzteilmodul 5 V | Strom für Servos und Display |
| Gehäuse | 4 mm Holz, lasergeschnitten; Innenteile 3D-gedruckt |

Pi und ESP32 sind über ein USB-Kabel verbunden (Strom und Textprotokoll, 115200 Baud).

## Ordner

| Pfad | Inhalt |
|---|---|
| `arduino-ide/PillCard_Demo/` | Firmware des ESP32 (aktueller Stand) |
| `arduino-ide/Kammer1_Test/`, `LCD_Test/`, `LCD_Pintest/`, `Kammer1_RFID/`, `Becher_Test/` | Einzeltests der Bauteile |
| `pi/pillcard.py` | Steuerprogramm: Karte lesen, entscheiden, Aufträge an den ESP32 |
| `pi/datenbank.py` | SQLite-Schema und Abfragen |
| `pi/web.py`, `pi/templates/`, `pi/static/` | Website |
| `pi/erezept.py` | QR-Code eines Schweizer E-Rezepts lesen (CHMED16A) |
| `pi/mitteilung.py` | Push-Mitteilung an Angehörige über ntfy |
| `pi/esp_befehl.py`, `pi/demo_nutzer.py` | Testen am ESP32, Demo-Ansicht |
| `pi/start.sh`, `web.sh`, `stop.sh`, `esp_flashen.sh` | Start mit Neustart nach Absturz, Beenden, ESP32 bespielen |
| `docs/Designentscheidungen.md` | warum Drehrad statt Kolben, Mikrofon statt Lichtschranken, Kupferkontakt |
| `docs/Verkabelung.md` | Pinbelegung, Strom, Aufbau |
| `docs/Schaltplan_ESP32.*`, `docs/Schaltplan_RaspberryPi.*` | Schaltpläne |
| `docs/Datenbank.md`, `docs/ER_Datenbank.*` | Datenbank |
| `docs/Website.md` | Website und Betrieb auf dem Pi |
| `docs/Test-Rezepte/` | selbst erzeugte Test-E-Rezepte (keine echten Rezepte) |
| `3D_Druckmodelle/` | STL-Dateien aller Druckteile mit Massen und Prüfskripten |
| `src/`, `lib/`, `include/`, `platformio.ini` | frühe PlatformIO-Variante (Arduino Uno), nicht mehr benutzt |

## Nachbauen

1. **Verkabeln** nach `docs/Verkabelung.md` und den Schaltplänen in `docs/`.
2. **ESP32 bespielen:** `arduino-ide/PillCard_Demo/PillCard_Demo.ino` in der Arduino IDE öffnen, Board „ESP32 Dev Module“.
3. **Raspberry Pi einrichten** nach `docs/Website.md` (Abschnitt „Betrieb auf dem Pi“). Steuerprogramm und Website starten über `pi/start.sh` und `pi/web.sh`.
4. **Innenteile drucken:** Druckdateien und Masse in `3D_Druckmodelle/README.md`. Die Laserdateien für das Holzgehäuse liegen noch nicht im Repository.

## Grenzen des Prototyps

PillCard ist ein Studienprototyp und kein Medizinprodukt. Das Gerät erkennt die Abholung, nicht die Einnahme. Die Website läuft ohne HTTPS und nur im Heimnetz, und die Signatur von E-Rezepten wird nicht geprüft.
