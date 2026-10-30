# Test-Rezepte

QR-Codes im Format eines Schweizer E-Rezepts (CHMED16A1) für die Demo. **Keine echten Rezepte:**
erfundene Testpraxis, keine Signatur, Bemerkung „TESTREZEPT“. Die Medikamente stehen meist als Freitext
drin, damit die Website den Namen direkt anzeigt.

| Datei | Patient | Medikamente (morgens – mittags – abends – nachts) | Was man sieht |
|---|---|---|---|
| `01_Anna_Eisen_Vitamin-C.png` | Anna | Eisen 100 mg (1–0–0–0), Vitamin C 500 mg (1–0–1–0) | zwei Medikamente zur Wahl |
| `02_Kris_Zink.png` | Kris | Zink 15 mg (0–0–1–0) | einfacher Fall |
| `03_Bruno_Calcium.png` | Bruno | Calcium 500 mg (1–0–0–0) | einfacher Fall |
| `04_Anna_Magnesium.png` | Anna | Magnesium 300 mg (1–0–1–0) | 2 pro Tag, mit Grund und Anwendung |
| `05_Bruno_Vitamin-D.png` | Bruno | Vitamin D3 1000 IE (1–0–0–0) | einfacher Fall |
| `06_Kris_Omega-3.png` | Kris | Omega-3 1000 mg (0–1–0–0) | mit Anwendung „zum Essen“ |
| `07_Anna_nur-GTIN.png` | Anna | nur GTIN 7680000000000 (1–0–0–0), kein Name | wie ein echtes E-Rezept: Name von Hand eintragen |
| `08_Bruno_drei-Medikamente.png` | Bruno | Vitamin B12 500 µg (1–0–0–0), Folsäure 0.4 mg (1–0–0–0), Paracetamol 500 mg (1–1–1–0, nur bei Bedarf) | drei zur Wahl, Reserve-Medikament mit Vorschlag 0 pro Tag |
| `09_Kris_Uhrzeit_halbe-Tablette.png` | Kris | Melatonin 2 mg (1 um 22:00, als Einnahmezeit), Eisen 100 mg (½–0–0–0) | Uhrzeit wird zu 1 pro Tag, Warnung bei halber Tablette |

Die GTIN in 07 ist erfunden. Die Einnahmezeit in 09 steht im Feld `TT` so, wie `pi/erezept.py` es
liest (`Off` = Sekunden ab Mitternacht, `DoFrom` = Menge).

Neben jedem Bild liegt der QR-Text als `.txt` (zum Einfügen ins Textfeld, falls die Kamera streikt).
**`Druckblatt.pdf`** enthält alle Codes, zwei pro A4-Seite, je etwa 10 cm gross: zum Ausdrucken oder
zum Abfotografieren vom Laptop-Bildschirm.

## Ganzes A4-Rezept

**`A4_Rezept_Anna.pdf`** sieht aus wie ein ausgedrucktes E-Rezept vom Arzt: Praxis, Patientin,
Medikamente mit Dosierschema (Mo–Mi–Ab–Na), Stempel, Unterschrift und oben rechts der QR-Code
(CHMED16A1). Für die Demo ausdrucken und den QR-Code abfotografieren. Erfundene Praxis und Ärztin
(„Dr. med. Lena Muster“), Wasserzeichen „MUSTER“ und Vermerk „TESTREZEPT“, also kein echtes Rezept.

| Patientin | Medikamente | Was man sieht |
|---|---|---|
| Anna Test | Magnesium 300 mg (1–0–1–0, mit einem Glas Wasser), Vitamin D3 1000 IE (1–0–0–0, zum Frühstück) | Anna wird vorgeschlagen, zwei Medikamente zur Wahl |

QR-Text zum Einfügen: `A4_Rezept_Anna.txt`. Neu erzeugen mit `python3 docs/Test-Rezepte/a4_rezept.py`
(braucht zusätzlich `rsvg-convert`, `brew install librsvg`).

## Demo

1. Auf der Website unter **Kammern** den Vorrat einer Kammer auf 0 setzen → die LED am Einfüllstutzen
   geht an.
2. **E-Rezept scannen** → **QR-Code fotografieren** und eines der Bilder (am Laptop-Bildschirm oder
   ausgedruckt, möglichst gross) fotografieren.
3. Medikament wählen, eingefüllte Menge eintragen, **Kammer programmieren** → die LED geht nach ein
   paar Sekunden aus.

Neu erzeugen: `python3 docs/Test-Rezepte/erzeugen.py` (braucht `pip install "qrcode[pil]"`).
