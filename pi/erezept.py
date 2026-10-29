"""Liest den QR-Code eines Schweizer E-Rezepts bzw. eMediplans (Format CHMED16A).

Aufbau laut IG eMediplan (github.com/ig-emediplan/specification, ChTransmissionFormat):
    CHMED16A0{JSON}            unkomprimiert
    CHMED16A1{Base64(gzip(JSON))}   komprimiert, so steht es im QR-Code
Beim E-Rezept steht davor ein Link zur Info-Seite und dahinter eine Signatur. Darum wird der
CHMED-Teil im Text gesucht, statt den ganzen Text zu lesen. Die Signatur prüfen wir nicht.

Der QR-Code enthält keinen Medikamentennamen, sondern nur GTIN oder Pharmacode. Nur bei
IdType 1 (Freitext) steht der Name direkt im Feld Id. Sonst trägt die Verwaltung den Namen ein.

Zum Testen (im Ordner pi/):
    python3 erezept.py "CHMED16A1H4sI..."     Code lesen und anzeigen
"""
import base64
import binascii
import datetime
import gzip
import json
import re
import sys
import urllib.parse

MUSTER = re.compile(r"CHMED16([A-Z])([01])", re.IGNORECASE)
BASE64 = re.compile(r"[A-Za-z0-9+/=_-]+")
ID_TYP = {1: "Freitext", 2: "GTIN", 3: "Pharmacode", 4: "Produktnummer"}
ZEITEN = ("morgens", "mittags", "abends", "nachts")
MED_TYP = {1: "Medikationsplan", 2: "Polymedikations-Check", 3: "Rezept"}


class RezeptFehler(ValueError):
    """Der Text ist kein lesbarer CHMED16A-Code. Die Meldung kann so auf der Website stehen."""


def json_holen(text):
    """Findet den CHMED16A-Teil im Text und gibt das JSON als dict zurück."""
    text = urllib.parse.unquote((text or "").strip())  # im Link kann der Code %-kodiert sein
    treffer = MUSTER.search(text)
    if not treffer:
        raise RezeptFehler("Im QR-Code steht kein E-Rezept bzw. eMediplan (CHMED16A) drin.")
    rest = text[treffer.end():]

    if treffer.group(2) == "0":
        try:
            daten, _ = json.JSONDecoder().raw_decode(rest)
        except ValueError:
            raise RezeptFehler("Der Rezept-Text ist unvollständig. Bitte noch einmal scannen.") from None
    else:
        teil = BASE64.match(rest)
        roh = teil.group(0) if teil else ""
        roh = roh.replace("-", "+").replace("_", "/")  # falls URL-sicheres Base64 benutzt wurde
        try:
            gepackt = base64.b64decode(roh + "=" * (-len(roh) % 4))
            daten = json.loads(gzip.decompress(gepackt).decode("utf-8"))
        except (binascii.Error, OSError, EOFError, ValueError):
            raise RezeptFehler("Der Rezept-Code ist beschädigt oder abgeschnitten. Bitte noch einmal scannen.") from None

    if not isinstance(daten, dict) or not isinstance(daten.get("Medicaments"), list):
        raise RezeptFehler("Im Rezept stehen keine Medikamente.")
    return daten


def zahl(wert):
    try:
        return float(wert)
    except (TypeError, ValueError):
        return 0.0


def posologie_heute(liste, heute):
    """Von mehreren Dosierungen die, die heute gilt. Sonst die erste."""
    liste = [p for p in (liste or []) if isinstance(p, dict)]
    for p in liste:
        von, bis = p.get("DtFrom") or "0000-00-00", p.get("DtTo") or "9999-99-99"
        if von <= heute <= bis:
            return p
    return liste[0] if liste else {}


def dosis_lesen(pos):
    """[morgens, mittags, abends, nachts] und die Menge pro Tag aus einer Posologie.
    D ist die einfache Form. TT (Einnahmezeiten mit Uhrzeit) wird nur zusammengezählt."""
    if pos.get("D"):
        d = [zahl(x) for x in pos["D"]][:4]
        d += [0.0] * (4 - len(d))
        return d, sum(d)
    zeiten = [t for t in (pos.get("TT") or []) if isinstance(t, dict)]
    if zeiten:
        menge = sum(zahl(t.get("DoFrom", t.get("A"))) for t in zeiten)
        tage = max(zahl(pos.get("CyDu")) / 86400, 1) if pos.get("CyDu") else 1
        return None, menge / tage
    return None, 0.0


def medikament_lesen(m, heute):
    id_typ = int(zahl(m.get("IdType")))
    pos = posologie_heute(m.get("Pos"), heute)
    dosis, pro_tag = dosis_lesen(pos)
    hinweise = []
    if pos.get("InRes"):
        hinweise.append("nur bei Bedarf (Reserve)")
    if pro_tag != int(pro_tag):
        hinweise.append("halbe Tabletten kann der Spender nicht ausgeben")
    if not pos:
        hinweise.append("keine Dosierung im Rezept")
    return {
        "id": str(m.get("Id", "")),
        "id_typ": ID_TYP.get(id_typ, f"Typ {id_typ}"),
        "name": str(m.get("Id", "")) if id_typ == 1 else "",
        "grund": m.get("TkgRsn") or "",
        "anwendung": m.get("AppInstr") or "",
        "einheit": m.get("Unit") or "",
        "dosis": dosis,
        "dosis_text": " – ".join(f"{x:g}" for x in dosis) if dosis else "",
        "pro_tag": pro_tag,
        "pro_tag_ganz": int(pro_tag) if pro_tag == int(pro_tag) else None,
        "reserve": bool(pos.get("InRes")),
        "bis": pos.get("DtTo") or "",
        "packungen": m.get("NbPack"),
        "hinweise": hinweise,
    }


def lesen(text, heute=None):
    """Liest den QR-Text. Rückgabe: dict mit patient, medikamente, rezept_id, ... (wirft RezeptFehler)."""
    heute = heute or datetime.date.today().isoformat()
    daten = json_holen(text)
    p = daten.get("Patient") or {}
    arzt = daten.get("HcPerson") or {}
    return {
        "rezept_id": str(daten.get("Id", "")),
        "art": MED_TYP.get(daten.get("MedType"), "Rezept"),
        "ausgestellt": str(daten.get("Dt", ""))[:10],
        "bemerkung": daten.get("Rmk") or "",
        "arzt": " ".join(x for x in (arzt.get("FName"), arzt.get("LName")) if x),
        "patient": {
            "vorname": p.get("FName") or "",
            "nachname": p.get("LName") or "",
            "geburtsdatum": p.get("BDt") or "",
        },
        "medikamente": [medikament_lesen(m, heute) for m in daten["Medicaments"] if isinstance(m, dict)],
    }


def erzeugen(daten):
    """Gegenstück zu lesen(): dict -> "CHMED16A1...". Nur für Test-Rezepte."""
    roh = json.dumps(daten, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "CHMED16A1" + base64.b64encode(gzip.compress(roh, mtime=0)).decode("ascii")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    try:
        print(json.dumps(lesen(sys.argv[1]), indent=2, ensure_ascii=False))
    except RezeptFehler as fehler:
        print("Fehler:", fehler)
        sys.exit(1)
