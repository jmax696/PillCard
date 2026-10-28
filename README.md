# PillCard

Ein Tablettenspender für Senioren, der über RFID-Karten programmiert wird.

Projekt im Kurs **Hands-on HCI** (HSG, Herbst 2026), Themenbereich 1: *Augmenting Humans in Everyday Life*.

## Idee

Viele ältere Menschen nehmen mehrere Medikamente zu unterschiedlichen Zeiten ein. Elektronische Spender gibt es bereits, aber sie müssen am Gerät eingestellt werden. Das ist für viele Senioren schwierig.

Bei PillCard ist der Medikamentenplan auf einer persönlichen RFID-Karte gespeichert. Pflegepersonal oder Angehörige richten die Karte einmal ein. Die Senioren halten danach nur noch ihre Karte an das Lesefeld.

## Was PillCard besonders macht

1. **Keine Programmierung durch Senioren.** Die Einstellungen kommen über die RFID-Karte und nicht über das Gerät.
2. **Mehrere Bewohner nutzen einen Spender.** Jede Person hat eine eigene Karte, alle nutzen dasselbe Gerät.
3. **Immer die verschriebene Kombination.** Wurden die Tabletten schon ausgegeben, gibt es keine weitere Ausgabe.

## Ablauf einer Ausgabe

1. Die Person hält ihre RFID-Karte an das Lesefeld.
2. Der Spender liest den Plan und prüft, ob die Dosis schon ausgegeben wurde.
3. Falls nicht: Die Servos geben die verschriebenen Tabletten aus den Kammern in den Becher aus, die Lichtschranken zählen mit, die grüne LED leuchtet.
4. Falls doch: Es gibt keine Ausgabe. Die rote LED leuchtet und das LCD-Display zeigt an, dass die Dosis schon genommen wurde.
5. Ein Kontaktsensor in der Schale erkennt, ob der Becher entnommen wurde.

## Aufbau

| Bauteil | Aufgabe |
|---|---|
| Arduino (Elegoo Uno R3) | Steuerung, Ausgaben speichern, Bestand zählen |
| RFID-RC522 und Karten | Person, Plan und verschriebene Menge lesen |
| 3 Servomotoren | je Kammer eine Ausgabe |
| 3 Lichtschranken (eine pro Kammer) | ausgegebene Tabletten zählen |
| Kontaktsensor aus Kupferband | erkennt, ob der Becher in der Schale steht |
| LCD-Display | Hinweise für den Nutzer |
| Grüne und rote LED | Statusanzeige |
| Gehäuse aus dem 3D-Drucker | 3 Kammern, Lesefeld, Ausgabeschale mit Becher |

Plan B für das Zählen: ein Mikrofon unter dem Becher, das die fallenden Tabletten erkennt.

Details zu Anforderungen, Sensoren und offenen Punkten: [REQUIREMENTS.md](REQUIREMENTS.md)

## Stand

- [x] Idee und Idea Pitch (27.10.2026)
- [x] 3D-Modell des Gehäuses
- [ ] Gehäuse drucken
- [ ] Elektronik aufbauen und einzeln testen
- [ ] Arduino-Code für den gesamten Ablauf
- [ ] Prototype Demo (29.10.2026)
- [ ] Video Showcase (30.10.2026)
- [ ] Portfolio-Abgabe: Bericht, Video, Code, Schaltpläne (20.11.2026)

## Repo-Struktur

PlatformIO-Projekt mit mehreren Programmen. In VS Code unten in der Statusleiste die
Umgebung wählen, dann hochladen und den Seriellen Monitor öffnen (9600 Baud).

| Umgebung | Ordner | Zweck |
|---|---|---|
| `env:rfidtest` | `src/rfidtest/` | RC522 dauerhaft abfragen und Fehler erklären, Kabeltest mit `k` |
| `env:bauteiltest` | `src/bauteiltest/` | jedes Bauteil einzeln prüfen (Menü im Seriellen Monitor) |
| `env:codieren` | `src/codieren/` | Medikamentenplan auf eine Karte schreiben (Profile 1–3) |
| `env:decodieren` | `src/decodieren/` | Karte lesen und Plan anzeigen |

- `include/Hardware.h`: Pinbelegung, Servowinkel, Sensorpegel
- `lib/PillCardFormat/`: Kartenformat, Lesen und Schreiben (von allen Programmen genutzt).
  Funktioniert mit dem I²C-Leser und dem SPI-Board, umgeschaltet in `platformio.ini`.
- `lib/MFRC522_I2C/`: Bibliothek für den I²C-Leser, Kopie von `kkloesener/MFRC522_I2C`
  (Public Domain) mit einer Korrektur, damit sie auf dem Uno kompiliert
- `docs/Verkabelung.md`: Verkabelung, Stromversorgung, Testreihenfolge
- `pi/`: Programm für den Raspberry Pi (RFID, Plan, Aufträge an den ESP32) und die lokale Website,
  siehe `docs/Datenbank.md` und `docs/Website.md`

### Kartenformat

Auf MIFARE-Classic-Karten in Sektor 1 (Blöcke 4–6, 48 Byte), Werksschlüssel `FF…FF`:

| Bytes | Inhalt |
|---|---|
| 0–1 | Kennung `PC` |
| 2 | Formatversion (1) |
| 3–4 | Personen-ID |
| 5–16 | Name (max. 11 Zeichen) |
| 17 | Anzahl Einnahmezeitpunkte (max. 4) |
| 18–37 | 4 × Einnahme: Stunde, Minute, Anzahl Kammer 1/2/3 |
| 38–43 | verschriebene Menge je Kammer (3 × 16 Bit) |
| 44–46 | reserviert |
| 47 | CRC-8-Prüfsumme |
