# Übergabe an neuen Agenten – PillCard (Stand 28.10.2026)

Projekt: **PillCard**, Prototyp im Kurs Hands-on HCI (HSG). Ein Tablettenspender, der über eine
RFID-Karte gesteuert wird: Karte hinhalten → fällige Medikamente werden über Servos ausgegeben;
Karte nochmal hinhalten → „bereits ausgegeben, kommen Sie um xx:00 Uhr wieder“.

Repo: `/Users/maxjackle/Projekte/HCI/PillCard` (Git, bisher kaum committet, siehe unten).

## Arbeitsweise mit dem Nutzer

- **Antworten auf Deutsch**, Schritt für Schritt, einfache Sprache. Der Nutzer verkabelt live am Tisch.
- Der Nutzer will **kopierbare Arduino-IDE-Sketches** (vollständiger Code im Chat + Datei unter `arduino-ide/<Name>/<Name>.ino`).
- Code-Kommentare deutsch, kurz, ein Satz über jeder Funktion (`/** ... */`).
- **Nie ohne ausdrückliches Ja committen oder pushen**, keine Co-Authored-By-Zeile.
- Zwischendateien ins Scratchpad, nicht ins Repo.
- Vor dem Abgeben jeden Sketch probeweise kompilieren (siehe „Kompilieren“).

## Hardware (aktuell benutzt)

| Teil | Details |
|---|---|
| Mikrocontroller | **ESP32-WROOM von Keyestudio**, Arduino IDE Board „ESP32 Dev Module“, ESP32-Core 3.3.x, USB-Chip CP2102, Port `/dev/cu.usbserial-0001`, 115200 Baud |
| RFID | RC522 (blaues Board, SPI, Klonchip meldet VersionReg **0x18** – funktioniert). Testkarte UID `3D AB 09 01` (MIFARE Classic) |
| Display | SunFounder LCD-1602A, 16 Pins, **ohne I2C**, 4-Bit-Modus, Bibliothek `LiquidCrystal` |
| Servos | 3× SG90 (Kammer 1–3), Strom von der 5V-Schiene eines **Elegoo Breadboard-Netzteilmoduls** |
| LEDs | grün + rot, je 100 Ω |
| Später | 3 Lichtschranken, Kupferkontakt für Becher (noch nicht verbaut) |

Arduino Uno liegt als Reserve da, RC522 lief am Uno nie (0x00). Nicht mehr verfolgen.

### Pinbelegung ESP32 (auch in `include/Hardware.h`, `docs/Verkabelung.md`, `docs/Schaltplan_ESP32.svg`)

| Funktion | Pin |
|---|---|
| RFID-RC522 | hängt am Raspberry Pi; früher IO5 / IO18 / IO23 / IO19 / IO4 (nur noch in `include/Hardware.h`) |
| Leer-LED Kammer 1 / 2 / 3 (Einfüllstutzen) | IO18 / IO19 / IO23, je über 100 Ω an GND |
| LCD RS / E / D4 / D5 / D6 / D7 | IO22 / IO21 / IO32 / IO33 / IO14 / IO15; R/W → GND; VDD 5V; LED+ über 100 Ω an 5V; V0 über Poti B103 (10k) oder 1k nach GND |
| Servo Kammer 1 / 2 / 3 (Signal) | IO25 / IO26 / IO27 |
| LED grün / rot | IO16 / IO17 |
| Lichtschranken (später) | IO34 / IO35 / IO36 |
| Becherkontakt | IO13 (INPUT_PULLUP), Fläche A an GND, Fläche B über 1 kΩ; in `PillCard_Demo` eingebaut, Kupferband noch nicht verbaut |

Wichtig: Das Plus des Netzteilmoduls geht **nie** an den ESP32, aber **GND von ESP32 und Schiene müssen verbunden sein**.

## Was funktioniert

- RFID am ESP32 liest die Karte (UID kommt im Seriellen Monitor).
- `arduino-ide/Kammer1_Test/Kammer1_Test.ino`: **Servo Kammer 1 dreht laut Nutzer „super“**
  (LEDC ohne Bibliothek, 50 Hz, 16 Bit, 500–2400 µs, automatisch alle 3 s 0→90→0, Winkel per Konsole).

## Offene Probleme / Beobachtungen

- LCD zeigte bisher nur weiße Kästchen in Zeile 1 (nicht initialisiert). Verdacht: fehlende gemeinsame Masse oder Pins falsch gezählt. Nicht gelöst, aktueller Stand unklar.
- LEDs flackerten auch ohne Test (gleicher Verdacht: Masse).
- Einmal brach das Hochladen mit `termios.error: (22, 'Invalid argument')` ab. Ursache: CP2102 hing, Lösung: USB ab- und wieder anstecken.
- Arduino IDE 2 hält den Port mit dem Serial-Monitor-Hilfsprozess fest, solange der Monitor offen ist.
- ESP32 im `DOWNLOAD_BOOT` → BOOT war gedrückt, EN drücken.

## AKTUELLES PROBLEM (hier weitermachen)

Sketch: **`arduino-ide/Kammer1_RFID/Kammer1_RFID.ino`** (Version 3).
Inhalt: RFID + LCD + Servo Kammer 1 + Kalibrierung per Konsole, Winkel gespeichert mit `Preferences` (NVS, Namespace `pillcard`, Keys `ruhe`/`ausgabe`).
Befehle: Zahl 0–180, `+`/`-` (2°), `+10`, `r` (Ruhe speichern), `a` (Ausgabe speichern), `t` (Testausgabe), `w` (Wackeltest 3×), `s` (Kalibrierung beenden), `k` (Kalibrierung wieder öffnen), `?`.

**Nutzer meldet:** Mit dem Kalibrier-Sketch (Version 2, sehr ähnlich zu Version 3) bewegt sich der Servo nach Eingabe einer Zahl und dann `r` **nicht mehr**. Mit `Kammer1_Test.ino` drehte er vorher einwandfrei. Der Nutzer ist überzeugt, dass es am Programm liegt, nicht an der Hardware. Version 3 ist noch **nicht** auf der Hardware getestet.

Versionen:
1. V1: RFID + LCD + Servo, Winkel fest (0/90), Zahl über Konsole möglich.
2. V2: + Kalibrierphase mit 10 s Autostart; nach Autostart reagierte `loop()` nur auf `k` (Zahlen wurden ignoriert).
3. V3 (aktuell): alle Befehle auch in `loop()`, Echo `> befehl`, Winkel aufs LCD, Eingabe ohne Zeilenende nach 300 ms.

### Unterschiede zu `Kammer1_Test.ino` (funktionierte) – Verdachtsliste, nicht bewiesen

1. **`Preferences` / NVS-Schreiben bei `r`/`a`** (`speicher.putInt`). Flash-Schreiben pausiert kurz den Cache. Prüfen, ob der Servo nach `r` wirklich nicht mehr reagiert oder nur nichts tut, weil `r` absichtlich nicht bewegt.
2. **`lcd.begin()` bei jeder Servo-Bewegung** (`kalibrierAnzeige()` → `anzeigen()`). Der Aufruf ist langsam (mehrere ms Delays), und das LCD hängt evtl. ohne saubere Masse an den Pins. Testweise abschalten.
3. **`SPI.begin()` + `rfid.PCD_Init()`**: andere Pins (5/18/19/23/4) als Servo (25), sollte nicht stören. Trotzdem gegentesten.
4. **Busy-Wait-Schleife in `kalibrieren()`** ohne `delay()`/`yield()`. Watchdog-Reset prüfen: Serieller Monitor auf `rst:`-Meldungen achten. Testweise `delay(5)` einbauen.
5. **Reihenfolge in `setup()`**: `ledcAttach` und `servoWinkel` kommen jetzt vor `Serial.begin`. Gespeicherter Ruhewinkel kann z. B. 0 sein (Anschlag).
6. **Bedienung**: V2-Autostart nach 10 s; der Nutzer kann nach dem Timeout getippt haben (in V3 behoben). Zeilenende-Einstellung im Monitor (in V3 egal).
7. **Strom**: Mit LCD-Hintergrundlicht + RFID + Servo zieht alles mehr. Brownout (`rst:0xc` / `Brownout detector was triggered`) im Monitor suchen.

### Vorgeschlagenes Vorgehen

1. Den Nutzer bitten, die **komplette Ausgabe des Seriellen Monitors** zu kopieren (inkl. `rst:`-Zeilen, Echo `> ...`).
2. `Kammer1_Test.ino` noch einmal hochladen → dreht der Servo? Dann ist die Hardware okay.
3. Stückweise eingrenzen (Bisektion): Kalibrier-Sketch **ohne LCD**, dann **ohne RFID**, dann **ohne Preferences**, jeweils hochladen lassen.
4. Ursache benennen, Sketch reparieren, wieder als kopierbaren Code liefern.

## Dateien im Repo

- `platformio.ini`: Envs `codieren`, `decodieren`, `bauteiltest`, `rfidtest`, `esp32test` (ESP32) und `uno_*` (Uno). Default `decodieren`.
- `include/Hardware.h`: alle Pins, ESP32/Uno automatisch.
- `lib/PillCardFormat/`: Kartenformat. MIFARE Classic Sektor 1, Blöcke 4–6 = 48 Byte, `struct KartenDaten` (Magic, Version 1, PersonId, Name[12], bis 4 Einnahmen mit Uhrzeit + Anzahl je Kammer, verschriebene Mengen, CRC-8 Poly 0x07), Key FF×6. Funktionen `pcLesen`, `pcSchreiben` (mit Rücklesen), `pcLoeschen` usw.
- `lib/MFRC522_I2C/`: eingebettete I2C-Variante (nur falls I2C-Leser, aktuell nicht benutzt).
- `src/codieren/`: Seriell-Menü, schreibt Profile (1 Anna, 2 Bruno, 3 Clara) auf die Karte. **Noch nie erfolgreich eine Karte beschrieben.**
- `src/decodieren/`: liest Karte, zeigt Plan, LED grün/rot.
- `src/bauteiltest/`: Menü zum Testen von RFID, LEDs, Servos, LCD.
- `src/rfidtest/`, `src/esp32test/`: RFID-Diagnose.
- `arduino-ide/`: `Kammer1_Test`, `Kammer1_RFID`, `LCD_Test`, `LCD_Pintest`.
- `docs/Verkabelung.md`, `docs/Schaltplan_ESP32.svg` (Lichtschranken und Becherkontakt fehlen noch im Schaltplan).
- Git: nur 2 alte Commits; alles oben ist uncommittet.

## Kompilieren (Probe, ohne Hardware)

PlatformIO: `~/.platformio/penv/bin/pio`. Für Arduino-IDE-Sketches ein Scratch-Projekt anlegen:

```ini
[env:esp32]
platform = espressif32
board = esp32dev
framework = arduino
lib_deps =
    arduino-libraries/LiquidCrystal@^1.0.7
    miguelbalboa/MFRC522@^1.4.11
```

`src/main.cpp` = `#include <Arduino.h>` + Inhalt der `.ino`, dann `pio run`.
Hochladen aufs Board: `pio run -e <env> -t upload` (nur wenn die Arduino IDE den Port nicht belegt). Bei den `.ino`-Sketches lädt der Nutzer selbst über die Arduino IDE hoch.
esptool liegt unter `~/.platformio/packages/tool-esptool/esptool`.

## Danach (größere offene Aufgaben)

1. Profil auf eine Karte schreiben (`codieren`) und mit `decodieren` prüfen.
2. Hauptprogramm: fällige Einnahme nach Uhrzeit bestimmen (Uhr über WLAN/NTP oder per Konsole setzen), ausgeben, zweites Hinhalten → „bereits ausgegeben, kommen Sie um xx:00 Uhr wieder“.
3. Alle 3 Kammern, Lichtschranken als Zählkontrolle, Becherkontakt.
