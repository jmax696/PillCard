"""Erzeugt Test-QR-Codes im Format eines Schweizer E-Rezepts (CHMED16A1) für die Demo.

Das sind KEINE echten Rezepte: keine Signatur, erfundene Testpraxis, Bemerkung "TESTREZEPT".
Die Medikamente stehen meist als Freitext drin (IdType 1), damit die Website den Namen anzeigen kann.
Echte E-Rezepte enthalten nur GTIN oder Pharmacode, dann trägt die Verwaltung den Namen selbst ein
(so wie in 07_Anna_nur-GTIN).

Schreibt pro Rezept ein PNG und den QR-Text als TXT, dazu Druckblatt.pdf mit allen Codes.

Aufruf (auf dem Mac, braucht das Paket qrcode mit Pillow):
    python3 -m pip install "qrcode[pil]"
    python3 docs/Test-Rezepte/erzeugen.py
"""
import sys
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

ORDNER = Path(__file__).resolve().parent
sys.path.insert(0, str(ORDNER.parent.parent / "pi"))
import erezept  # noqa: E402

PRAXIS = {"Name": "PillCard Testpraxis", "Street": "Torstrasse 25", "Zip": "9000", "City": "St. Gallen", "Country": "CH"}
ARZT = {"Gln": "7601000000000", "FName": "Test", "LName": "Praxis"}
HINWEIS = "TESTREZEPT – kein echtes E-Rezept (PillCard-Prototyp, HSG Hands-on HCI)"


def med(mid, dosis=None, id_typ=1, zeiten=None, reserve=False, grund=None, anwendung=None):
    """Ein Medikament. dosis = [morgens, mittags, abends, nachts], zeiten = Einnahmezeiten (TT)."""
    pos = {}
    if dosis is not None:
        pos["D"] = dosis
    if zeiten:
        pos["TT"] = zeiten
    if reserve:
        pos["InRes"] = True
    m = {"Id": mid, "IdType": id_typ, "Unit": "STK", "NbPack": 1, "Pos": [pos]}
    if grund:
        m["TkgRsn"] = grund
    if anwendung:
        m["AppInstr"] = anwendung
    return m


def rezept(nummer, vorname, medikamente):
    return {
        "Id": f"00000000-0000-4000-8000-{nummer:012d}",
        "MedType": 3,
        "Auth": ARZT["Gln"],
        "Dt": "2026-10-29T12:00:00+01:00",
        "Rmk": HINWEIS,
        "HcPerson": ARZT,
        "HcOrg": PRAXIS,
        "Patient": {"FName": vorname, "LName": "Test", "BDt": "2000-01-01", "Gender": 2, "Lng": "DE"},
        "Medicaments": medikamente,
    }


REZEPTE = {
    # einfache Fälle, je ein Medikament pro Kammer
    "01_Anna_Eisen_Vitamin-C": rezept(1, "Anna", [med("Eisen 100 mg", [1, 0, 0, 0]),
                                                  med("Vitamin C 500 mg", [1, 0, 1, 0])]),
    "02_Kris_Zink": rezept(2, "Kris", [med("Zink 15 mg", [0, 0, 1, 0])]),
    "03_Bruno_Calcium": rezept(3, "Bruno", [med("Calcium 500 mg", [1, 0, 0, 0])]),
    "04_Anna_Magnesium": rezept(4, "Anna", [med("Magnesium 300 mg", [1, 0, 1, 0], grund="Muskelkrämpfe",
                                                anwendung="mit einem Glas Wasser")]),
    "05_Bruno_Vitamin-D": rezept(5, "Bruno", [med("Vitamin D3 1000 IE", [1, 0, 0, 0])]),
    "06_Kris_Omega-3": rezept(6, "Kris", [med("Omega-3 1000 mg", [0, 1, 0, 0], anwendung="zum Essen")]),
    # Sonderfälle
    "07_Anna_nur-GTIN": rezept(7, "Anna", [med("7680000000000", [1, 0, 0, 0], id_typ=2)]),
    "08_Bruno_drei-Medikamente": rezept(8, "Bruno", [
        med("Vitamin B12 500 µg", [1, 0, 0, 0]),
        med("Folsäure 0.4 mg", [1, 0, 0, 0]),
        med("Paracetamol 500 mg", [1, 1, 1, 0], reserve=True, grund="bei Schmerzen"),
    ]),
    "09_Kris_Uhrzeit_halbe-Tablette": rezept(9, "Kris", [
        med("Melatonin 2 mg", zeiten=[{"Off": 79200, "DoFrom": 1}], anwendung="um 22 Uhr"),
        med("Eisen 100 mg", [0.5, 0, 0, 0]),
    ]),
}


def beschreibung(daten):
    """Zeilen für das Druckblatt, aus den Rezeptdaten statt von Hand."""
    zeilen = []
    for m in daten["Medicaments"]:
        name = m["Id"] if m["IdType"] == 1 else f"GTIN {m['Id']} (Name von Hand eintragen)"
        pos = m["Pos"][0]
        if "D" in pos:
            dosis = "–".join(f"{x:g}" for x in pos["D"])
        else:
            dosis = ", ".join(f"{t['DoFrom']:g} um {t['Off'] // 3600:02d}:{t['Off'] % 3600 // 60:02d}" for t in pos["TT"])
        zusatz = " · nur bei Bedarf" if pos.get("InRes") else ""
        zeilen.append(f"{name}: {dosis}{zusatz}")
    return zeilen


def schrift(groesse, fett=False):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", groesse, index=1 if fett else 0)
    except OSError:
        return ImageFont.load_default(groesse)


def druckblatt(codes):
    """A4 bei 150 dpi, zwei Codes pro Seite, zum Ausdrucken oder Abfotografieren vom Bildschirm."""
    breite, hoehe, rand = 1240, 1754, 70
    seiten = []
    for i in range(0, len(codes), 2):
        seite = Image.new("RGB", (breite, hoehe), "white")
        zeichnen = ImageDraw.Draw(seite)
        for j, (name, daten, matrix) in enumerate(codes[i:i + 2]):
            oben = j * hoehe // 2 + rand
            zeichnen.text((rand, oben), name.replace("_", " "), font=schrift(40, True), fill="black")
            box = 600 // len(matrix)
            links = (breite - box * len(matrix)) // 2
            for y, reihe in enumerate(matrix):
                for x, schwarz in enumerate(reihe):
                    if schwarz:
                        zeichnen.rectangle([links + x * box, oben + 60 + y * box,
                                            links + (x + 1) * box - 1, oben + 60 + (y + 1) * box - 1], fill="black")
            zeile_y = oben + 70 + box * len(matrix)
            for text in beschreibung(daten):
                zeichnen.text((rand, zeile_y), text, font=schrift(28), fill="black")
                zeile_y += 38
            zeichnen.text((rand, zeile_y + 6), HINWEIS, font=schrift(22), fill="#666666")
        zeichnen.line([(rand, hoehe // 2), (breite - rand, hoehe // 2)], fill="#bbbbbb", width=2)
        seiten.append(seite)
    seiten[0].save(ORDNER / "Druckblatt.pdf", save_all=True, append_images=seiten[1:], resolution=150)


def main():
    codes = []
    for name, daten in REZEPTE.items():
        text = erezept.erzeugen(daten)
        assert erezept.lesen(text)["rezept_id"] == daten["Id"]  # muss sich selbst wieder lesen lassen
        (ORDNER / f"{name}.txt").write_text(text + "\n", encoding="utf-8")
        bild = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
        bild.add_data(text)
        bild.make(fit=True)
        bild.make_image().save(ORDNER / f"{name}.png")
        codes.append((name, daten, bild.get_matrix()))
        print(f"{name}: {len(text)} Zeichen, QR-Version {bild.version}")
    druckblatt(codes)
    print(f"Druckblatt.pdf: {(len(codes) + 1) // 2} Seiten")


if __name__ == "__main__":
    main()
