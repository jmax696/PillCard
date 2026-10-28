# Verkabelung

Pinbelegung wie in [`include/Hardware.h`](../include/Hardware.h). Wer umsteckt, ändert es dort.

## ESP32 (aktuell benutzt)

![Verdrahtung mit ESP32](Schaltplan_ESP32.svg)

| Bauteil | Bauteil-Pin | ESP32 | Hinweis |
|---|---|---|---|
| **RFID-RC522** (blau, SPI) | SDA | IO5 | |
| | SCK | IO18 | |
| | MOSI | IO23 | |
| | MISO | IO19 | |
| | IRQ | – | frei lassen |
| | GND | GND-Schiene | |
| | RST | IO4 | |
| | 3.3V | **3V3 des ESP32** | nicht 5V |
| **LCD 16×2** (16 Pins, ohne I²C) | 1 VSS | GND-Schiene | Pin 1: von vorne gesehen ganz links; auf der Rückseite rechts, eckiges Lötpad |
| | 2 VDD | 5V-Schiene | |
| | 3 V0 (Kontrast) | erst frei lassen | Datenblatt: VDD−V0 ≈ 3.8 V, also V0 ≈ 1.2 V. Direkt an GND ist zu dunkel, 1 kΩ an GND passt meist |
| | 4 RS | IO22 | |
| | 5 R/W | **GND-Schiene** | Pflicht: sonst schickt das Display 5V an den ESP32 |
| | 6 E | IO21 | |
| | 7–10 DB0–DB3 | – | frei lassen (4-Bit-Modus) |
| | 11 DB4 / 12 DB5 | IO32 / IO33 | |
| | 13 DB6 / 14 DB7 | IO14 / IO15 | |
| | 15 LED+ | 5V-Schiene über 100 Ω | Hintergrundbeleuchtung |
| | 16 LED− | GND-Schiene | |
| **Servo Kammer 1 / 2 / 3** | Signal (orange) | IO25 / IO26 / IO27 | |
| | + (rot) / − (braun) | 5V-Schiene / GND-Schiene | |
| **LED grün** | + (langes Bein) | IO16 über 100 Ω (braun-schwarz-braun) | − an GND |
| **LED rot** | + (langes Bein) | IO17 über 100 Ω (braun-schwarz-braun) | − an GND |
| **Lichtschranke 1 / 2 / 3** | OUT | IO34 / IO35 / IO36 (VP) | VCC an **3.3V**, damit OUT max. 3.3V liefert |
| **Kupferband Schale** | Streifen A / B | IO13 / GND | interner Pull-up |
| **ESP32** | GND | GND-Schiene | gemeinsame Masse, Pflicht |

Strom: Das ESP32 läuft über USB. Servos und LCD hängen an der 5V-Schiene des
Elegoo-Netzteilmoduls (Jumper auf 5V, versorgt per 9V-Netzteil oder USB). Plus des Moduls
**nie** an 5V/VIN oder 3V3 des ESP32, nur GND wird gemeinsam verbunden.

## RFID-Leser: I²C-Variante (nur für 4-Pin-Module)

Nur für Leser mit genau 4 Pins (GND, VCC, SDA, SCL). In `platformio.ini` dafür die Zeile
`build_flags = -D PILLCARD_RFID_I2C` einkommentieren.

> [!warning] Das blaue 8-Pin-Board kann kein I²C
> Der Pin „SDA“ auf dem blauen RC522-Board ist bei SPI die Chip-Auswahl (SS), nicht die
> I²C-Datenleitung. Das Board braucht immer alle 7 Kabel (IRQ bleibt frei).

| Leser | Arduino Uno |
|---|---|
| GND | GND |
| VCC | **3.3V** (Beschriftung am Modul prüfen: nur 5V, wenn dort ausdrücklich 5V steht) |
| SDA | A4 (oder der Pin „SDA“ neben AREF) |
| SCL | A5 (oder der Pin „SCL“ neben AREF) |

Adresse ist normalerweise 0x28 (`RFID_I2C_ADRESSE` in `Hardware.h`). LCD und Uhrmodul hängen
an denselben zwei Leitungen, das geht, solange jedes Gerät eine andere Adresse hat.

## Arduino Uno (Ausweichvariante, `uno_*`-Umgebungen)

| Bauteil | Bauteil-Pin | Arduino Uno | Hinweis |
|---|---|---|---|
| **RFID-RC522** | SDA | D10 | |
| | SCK | D13 | |
| | MOSI | D11 | |
| | MISO | D12 | |
| | IRQ | – | frei lassen |
| | GND | GND | |
| | RST | D9 | |
| | 3.3V | **3.3V** | **nicht an 5V!** |
| **Servo Kammer 1** | Signal (orange/gelb) | D3 | |
| **Servo Kammer 2** | Signal | D5 | |
| **Servo Kammer 3** | Signal | D6 | |
| alle Servos | + (rot) | externe 5V | siehe „Strom“ |
| alle Servos | − (braun) | GND | gemeinsame Masse mit Arduino |
| **Lichtschranke Kammer 1** | OUT / DO | D2 | VCC an 5V, GND an GND |
| **Lichtschranke Kammer 2** | OUT / DO | D4 | |
| **Lichtschranke Kammer 3** | OUT / DO | D7 | |
| **Kupferband Schale** | Streifen A | D8 | interner Pull-up, kein Widerstand nötig |
| | Streifen B | GND | Becherboden mit Alufolie/Kupfer überbrückt A und B |
| **LED grün** | Anode (langes Bein) | A0 | über 220 Ω, Kathode an GND |
| **LED rot** | Anode | A1 | über 220 Ω, Kathode an GND |
| **LCD 16×2 mit I²C-Modul** | SDA | A4 | |
| | SCL | A5 | |
| | VCC / GND | 5V / GND | |
| *Uhrmodul (optional)* | SDA / SCL | A4 / A5 | teilt sich den Bus mit dem LCD |

Frei bleiben D0/D1 (USB-Seriell), A2 und A3 (z. B. Mikrofon für Plan B an A2).

## Strom

- Ein SG90 zieht beim Anlaufen bis ca. 650 mA, der USB-Port liefert 500 mA. Wenn mehrere
  Servos am 5V-Pin des Arduino hängen, bricht die Spannung ein und der RC522 oder der
  Arduino startet neu.
- Besser: Servos an eine eigene 5V-Quelle (Breadboard-Netzteilmodul aus dem Elegoo-Kit,
  5V-Netzteil oder 4×AA), **GND der Quelle mit GND des Arduino verbinden**.
- Für erste Tests reicht USB, solange immer nur ein Servo fährt (macht der Bauteiltest so).

### Variante: ESP32 als zweite 5V-Quelle

Das ESP32-Board (Keyestudio) dient hier nur als „zweiter USB-Anschluss“, es läuft kein Programm darauf.

| von | nach |
|---|---|
| ESP32 Pin **5V** bzw. **VIN** | Plus-Schiene Breadboard → rotes Kabel aller 3 Servos |
| ESP32 **GND** | Minus-Schiene Breadboard → braunes Kabel der Servos **und** GND des Arduino |
| Arduino D3 / D5 / D6 | Signal der Servos (wie oben) |

- ESP32 per USB versorgen (zweiter Laptop-Port, Powerbank oder USB-Netzteil).
- Vorher mit dem Multimeter messen: zwischen 5V/VIN und GND sollten ca. 4.7–5 V anliegen.
  **Nicht den 3.3V-Pin nehmen**, der Regler schafft keine Servos.
- **5V des ESP32 nie mit 5V des Arduino verbinden**, nur GND gemeinsam.
- Mehr als USB-Strom (ca. 500 mA) gibt es so auch nicht. Servos deshalb weiterhin nacheinander
  fahren lassen. Ein Elko (100–1000 µF) zwischen Plus- und Minus-Schiene fängt Stromspitzen ab.

## Reihenfolge beim Aufbauen

Jedes Teil einzeln anschliessen und sofort mit `env:bauteiltest` prüfen:

1. **RC522** → Taste `r`. Bei „Firmware Version: 0x92“ (oder 0x91/0x88/0xB2) ist alles gut.
   `0x00` oder `0xFF` heisst: Verkabelung prüfen, meist SDA/RST vertauscht oder 3.3V fehlt.
2. **LEDs** → `l`.
3. **LCD** → `d`. Leer? V0 (Pin 3) an GND. Nur Kästchen? 1 kΩ zwischen V0 und GND.
4. **Servos** → `s`. Winkel in `Hardware.h` (`SERVO_RUHE`, `SERVO_AUSGABE`) an den Schieber anpassen.
5. **Lichtschranken und Kupferband** → `z`. Beobachten, ob „unterbrochen“ HIGH oder LOW ist,
   und `LICHTSCHRANKE_UNTERBROCHEN` in `Hardware.h` passend setzen.

## Annahmen, die ihr prüfen müsst

- **LCD hat kein I²C-Modul** (16 Pins). Mit ESP32 kein Problem, der Arduino Uno hätte dafür
  nicht genug freie Pins.
- **Lichtschranken sind Module mit Digitalausgang** (3 Pins: VCC, GND, OUT). Wenn ihr eine
  nackte IR-LED mit Fototransistor habt, braucht es Widerstände und ggf. Analogpins.
- **Karten sind MIFARE Classic 1K** (die weissen Karten und blauen Schlüsselanhänger aus dem
  Elegoo-Kit sind das). NTAG-Sticker gehen mit dem Codierer nicht.
