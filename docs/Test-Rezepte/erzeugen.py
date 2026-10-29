"""Erzeugt Test-QR-Codes im Format eines Schweizer E-Rezepts (CHMED16A1) für die Demo.

Das sind KEINE echten Rezepte: keine Signatur, erfundene Testpraxis, Bemerkung "TESTREZEPT".
Die Medikamente stehen als Freitext drin (IdType 1), damit die Website den Namen anzeigen kann.
Echte E-Rezepte enthalten nur GTIN oder Pharmacode, dann trägt die Verwaltung den Namen selbst ein.

Aufruf (auf dem Mac, braucht das Paket qrcode mit Pillow):
    python3 -m pip install "qrcode[pil]"
    python3 docs/Test-Rezepte/erzeugen.py
"""
import sys
from pathlib import Path

import qrcode

ORDNER = Path(__file__).resolve().parent
sys.path.insert(0, str(ORDNER.parent.parent / "pi"))
import erezept  # noqa: E402

PRAXIS = {"Name": "PillCard Testpraxis", "Street": "Torstrasse 25", "Zip": "9000", "City": "St. Gallen", "Country": "CH"}
ARZT = {"Gln": "7601000000000", "FName": "Test", "LName": "Praxis"}


def rezept(nummer, vorname, medikamente):
    return {
        "Id": f"00000000-0000-4000-8000-{nummer:012d}",
        "MedType": 3,
        "Auth": ARZT["Gln"],
        "Dt": "2026-10-29T12:00:00+01:00",
        "Rmk": "TESTREZEPT – kein echtes E-Rezept (PillCard-Prototyp, HSG Hands-on HCI)",
        "HcPerson": ARZT,
        "HcOrg": PRAXIS,
        "Patient": {"FName": vorname, "LName": "Test", "BDt": "2000-01-01", "Gender": 2, "Lng": "DE"},
        "Medicaments": [
            {"Id": name, "IdType": 1, "Unit": "STK", "NbPack": 1, "Pos": [{"D": dosis}]}
            for name, dosis in medikamente
        ],
    }


REZEPTE = {
    "01_Anna_Eisen_Vitamin-C": rezept(1, "Anna", [("Eisen 100 mg", [1, 0, 0, 0]), ("Vitamin C 500 mg", [1, 0, 1, 0])]),
    "02_Kris_Zink": rezept(2, "Kris", [("Zink 15 mg", [0, 0, 1, 0])]),
    "03_Bruno_Calcium": rezept(3, "Bruno", [("Calcium 500 mg", [1, 0, 0, 0])]),
}


def main():
    for name, daten in REZEPTE.items():
        text = erezept.erzeugen(daten)
        assert erezept.lesen(text)["rezept_id"] == daten["Id"]  # muss sich selbst wieder lesen lassen
        (ORDNER / f"{name}.txt").write_text(text + "\n", encoding="utf-8")
        bild = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
        bild.add_data(text)
        bild.make(fit=True)
        bild.make_image().save(ORDNER / f"{name}.png")
        print(f"{name}: {len(text)} Zeichen, QR-Version {bild.version}")


if __name__ == "__main__":
    main()
