# Test-Rezepte

QR-Codes im Format eines Schweizer E-Rezepts (CHMED16A1) für die Demo. **Keine echten Rezepte:**
erfundene Testpraxis, keine Signatur, Bemerkung „TESTREZEPT“. Die Medikamente stehen als Freitext
drin, damit die Website den Namen direkt anzeigt.

| Datei | Patient | Medikamente (morgens – mittags – abends – nachts) |
|---|---|---|
| `01_Anna_Eisen_Vitamin-C.png` | Anna | Eisen 100 mg (1–0–0–0), Vitamin C 500 mg (1–0–1–0) |
| `02_Kris_Zink.png` | Kris | Zink 15 mg (0–0–1–0) |
| `03_Bruno_Calcium.png` | Bruno | Calcium 500 mg (1–0–0–0) |

Neben jedem Bild liegt der QR-Text als `.txt` (zum Einfügen ins Textfeld, falls die Kamera streikt).

## Demo

1. Auf der Website unter **Kammern** den Vorrat einer Kammer auf 0 setzen → die LED am Einfüllstutzen
   geht an.
2. **E-Rezept scannen** → **QR-Code fotografieren** und eines der Bilder (am Laptop-Bildschirm oder
   ausgedruckt, möglichst gross) fotografieren.
3. Medikament wählen, eingefüllte Menge eintragen, **Kammer programmieren** → die LED geht nach ein
   paar Sekunden aus.

Neu erzeugen: `python3 docs/Test-Rezepte/erzeugen.py` (braucht `pip install "qrcode[pil]"`).
