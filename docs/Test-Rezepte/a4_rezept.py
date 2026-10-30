"""Erzeugt ein ganzes A4-Rezept (wie vom Arzt ausgedruckt) mit E-Rezept-QR-Code für die Demo.

Das Blatt ist KEIN echtes Rezept: erfundene Praxis und Ärztin, Wasserzeichen "MUSTER", Vermerk
"TESTREZEPT" auf dem Blatt und im QR-Code, keine Signatur. Gedacht zum Ausdrucken: In der Demo
fotografiert man den QR-Code oben rechts auf der Seite "E-Rezept scannen".

Aufruf (auf dem Mac, braucht qrcode mit Pillow und rsvg-convert aus Homebrew):
    python3 -m pip install "qrcode[pil]"
    brew install librsvg
    python3 docs/Test-Rezepte/a4_rezept.py
"""
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import qrcode

from erzeugen import HINWEIS, ORDNER, PRAXIS, med

sys.path.insert(0, str(ORDNER.parent.parent / "pi"))
import erezept  # noqa: E402

NAME = "A4_Rezept_Anna"
AERZTIN = {"Gln": "7601000000000", "FName": "Lena", "LName": "Muster"}

REZEPT = {
    "Id": "00000000-0000-4000-8000-000000000010",
    "MedType": 3,
    "Auth": AERZTIN["Gln"],
    "Dt": "2026-10-30T09:15:00+01:00",
    "Rmk": HINWEIS,
    "HcPerson": AERZTIN,
    "HcOrg": PRAXIS,
    "Patient": {"FName": "Anna", "LName": "Test", "BDt": "2000-01-01", "Gender": 2, "Lng": "DE"},
    "Medicaments": [
        med("Magnesium 300 mg Tabletten", [1, 0, 1, 0], grund="Muskelkrämpfe", anwendung="mit einem Glas Wasser"),
        med("Vitamin D3 1000 IE Tabletten", [1, 0, 0, 0], grund="Vitamin-D-Mangel", anwendung="zum Frühstück"),
    ],
}

# Farben und Schrift; Masse in mm, die SVG-Seite ist 210 x 297
TINTE, GRAU, LINIE, FLAECHE, AKZENT = "#1d1d1f", "#6e6e73", "#c7c7cc", "#f2f2f4", "#2f6b57"
SCHRIFT = "Helvetica, Arial, sans-serif"


def text(x, y, inhalt, groesse=3.6, fett=False, farbe=TINTE, anker="start"):
    gewicht = ' font-weight="bold"' if fett else ""
    return (f'<text x="{x}" y="{y}" font-family="{SCHRIFT}" font-size="{groesse}"{gewicht} '
            f'fill="{farbe}" text-anchor="{anker}">{escape(inhalt)}</text>')


def qr_svg(qr_text, x, y, groesse):
    """QR-Code als Rechtecke, damit er im PDF scharf bleibt (Ruhezone ist im Weissraum mit drin)."""
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
    code.add_data(qr_text)
    code.make(fit=True)
    matrix = code.get_matrix()
    zelle = groesse / len(matrix)
    teile = [f'<rect x="{x}" y="{y}" width="{groesse}" height="{groesse}" fill="white"/>']
    for r, reihe in enumerate(matrix):
        for s, schwarz in enumerate(reihe):
            if schwarz:
                teile.append(f'<rect x="{x + s * zelle:.3f}" y="{y + r * zelle:.3f}" '
                             f'width="{zelle + 0.02:.3f}" height="{zelle + 0.02:.3f}" fill="black"/>')
    return "\n".join(teile), code.version


def seite(qr_text):
    d = REZEPT
    p, a = d["Patient"], d["HcPerson"]
    qr, version = qr_svg(qr_text, 132, 10, 58)
    teile = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">',
        '<rect width="210" height="297" fill="white"/>',
        # Wasserzeichen, schräg über dem Medikamentenblock, nicht über dem QR-Code
        f'<text x="105" y="190" transform="rotate(-28 105 190)" font-family="{SCHRIFT}" font-size="46" '
        'font-weight="bold" fill="#d0302f" fill-opacity="0.09" text-anchor="middle" letter-spacing="4">MUSTER</text>',
        # Praxis
        f'<rect x="20" y="16" width="3" height="21" fill="{AKZENT}"/>',
        text(27, 21, PRAXIS["Name"], 5.2, True),
        text(27, 27, f"Dr. med. {a['FName']} {a['LName']}", 3.8),
        text(27, 32, "Fachärztin für Allgemeine Innere Medizin", 3.2, farbe=GRAU),
        text(27, 37, f"{PRAXIS['Street']} · {PRAXIS['Zip']} {PRAXIS['City']}", 3.2, farbe=GRAU),
        text(27, 44, f"GLN {a['Gln']}", 2.9, farbe=GRAU),
        text(27, 48.5, "Tel. 071 000 00 00 (Muster)", 2.9, farbe=GRAU),
        # QR-Code
        qr,
        text(161, 72, "E-Rezept · CHMED16A", 2.8, True, anker="middle"),
        text(161, 76, "Code mit der App scannen", 2.6, farbe=GRAU, anker="middle"),
        # Titel
        text(20, 86, "Rezept", 11, True),
        text(20, 93, f"Rezept-ID {d['Id']}", 2.8, farbe=GRAU),
        f'<line x1="20" y1="98" x2="190" y2="98" stroke="{TINTE}" stroke-width="0.5"/>',
        # Patientin und Ausstellung
        text(20, 106, "PATIENTIN", 2.6, True, GRAU),
        text(20, 112, f"{p['FName']} {p['LName']}", 4.6, True),
        text(20, 118, "geb. 01.01.2000 · weiblich", 3.3, farbe=GRAU),
        text(20, 123, "Versichertenkarte: Muster, nicht hinterlegt", 3.0, farbe=GRAU),
        text(120, 106, "AUSGESTELLT", 2.6, True, GRAU),
        text(120, 112, "30.10.2026, 09:15", 4.2),
        text(120, 118, "St. Gallen", 3.3, farbe=GRAU),
        f'<line x1="20" y1="130" x2="190" y2="130" stroke="{LINIE}" stroke-width="0.3"/>',
        # Tabelle
        text(20, 140, "VERORDNETE MEDIKAMENTE", 2.6, True, GRAU),
        f'<rect x="20" y="144" width="170" height="9" fill="{FLAECHE}"/>',
        text(23, 149.8, "Medikament", 3.0, True),
        text(105, 149.8, "Mo", 3.0, True, anker="middle"),
        text(115, 149.8, "Mi", 3.0, True, anker="middle"),
        text(125, 149.8, "Ab", 3.0, True, anker="middle"),
        text(135, 149.8, "Na", 3.0, True, anker="middle"),
        text(145, 149.8, "Hinweis", 3.0, True),
        text(187, 149.8, "Pkg.", 3.0, True, anker="end"),
    ]
    y = 153
    for m in d["Medicaments"]:
        dosis = m["Pos"][0]["D"]
        teile += [
            text(23, y + 7, m["Id"], 3.8, True),
            text(23, y + 12.5, f"Grund: {m.get('TkgRsn', '–')}", 3.0, farbe=GRAU),
            *[text(105 + 10 * i, y + 7, f"{wert:g}", 3.8, anker="middle") for i, wert in enumerate(dosis)],
            text(145, y + 7, m.get("AppInstr", ""), 3.1),
            text(187, y + 7, f"{m['NbPack']}", 3.8, anker="end"),
            f'<line x1="20" y1="{y + 17}" x2="190" y2="{y + 17}" stroke="{LINIE}" stroke-width="0.3"/>',
        ]
        y += 17
    teile += [
        text(20, y + 7, "Mengen in Tabletten (Stück): Mo = morgens, Mi = mittags, Ab = abends, Na = nachts.",
             2.9, farbe=GRAU),
        text(20, y + 12, "Dauertherapie bis auf Widerruf.", 2.9, farbe=GRAU),
        # Unterschrift und Stempel
        f'<path d="M128 236 c3 -9 6 -10 6 -3 c0 6 -3 9 -1 4 c2 -6 6 -9 8 -5 c1 3 -1 6 1 4 c3 -3 5 -7 7 -4 '
        f'c1 2 0 4 2 3 c3 -2 6 -5 9 -3 c2 1 3 2 8 -1" fill="none" stroke="#1f3f9a" stroke-width="0.55" '
        'stroke-linecap="round" stroke-linejoin="round"/>',
        f'<line x1="120" y1="241" x2="190" y2="241" stroke="{TINTE}" stroke-width="0.3"/>',
        text(120, 246, f"Dr. med. {a['FName']} {a['LName']}", 3.2),
        text(120, 250.5, "Unterschrift (Muster)", 2.8, farbe=GRAU),
        '<g transform="rotate(-8 52 232)" fill="none" stroke="#1f3f9a" stroke-opacity="0.7">',
        '<circle cx="52" cy="232" r="15" stroke-width="0.6"/>',
        '<circle cx="52" cy="232" r="12" stroke-width="0.3"/>',
        '</g>',
        f'<g transform="rotate(-8 52 232)" font-family="{SCHRIFT}" fill="#1f3f9a" fill-opacity="0.75" '
        'text-anchor="middle" font-weight="bold">',
        '<text x="52" y="229" font-size="3">PillCard</text>',
        '<text x="52" y="233.5" font-size="3">Testpraxis</text>',
        '<text x="52" y="238" font-size="2.3" font-weight="normal">St. Gallen</text>',
        '</g>',
        # Fuss
        f'<line x1="20" y1="268" x2="190" y2="268" stroke="{LINIE}" stroke-width="0.3"/>',
        text(20, 274, HINWEIS, 2.9, True, "#b42318"),
        text(20, 279, "Erfundene Praxis und Personen, keine elektronische Signatur. Nicht in einer Apotheke "
                      "einlösen.", 2.7, farbe=GRAU),
        text(20, 283.5, f"QR-Code: Schweizer E-Rezept-Format CHMED16A1 (Version {version}), "
                        "liest die PillCard-Website unter Kammern → E-Rezept scannen.", 2.7, farbe=GRAU),
        "</svg>",
    ]
    return "\n".join(teile)


def main(ziel=ORDNER):
    qr_text = erezept.erzeugen(REZEPT)
    gelesen = erezept.lesen(qr_text)
    assert gelesen["rezept_id"] == REZEPT["Id"] and len(gelesen["medikamente"]) == 2
    (ziel / f"{NAME}.txt").write_text(qr_text + "\n", encoding="utf-8")
    svg = Path(ziel / f"{NAME}.svg")
    svg.write_text(seite(qr_text), encoding="utf-8")
    subprocess.run(["rsvg-convert", "-f", "pdf", "-o", str(ziel / f"{NAME}.pdf"), str(svg)], check=True)
    svg.unlink()
    print(f"{NAME}.pdf: {len(qr_text)} Zeichen im QR-Code")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ORDNER)
