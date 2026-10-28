"""PillCard auf dem Raspberry Pi: Karte lesen, Plan nachschlagen, Auftrag an den ESP32 schicken.

Der Pi entscheidet, wer was bekommt und ob heute schon genommen wurde.
Der ESP32 fährt die Servos, prüft mit dem Mikrofon und zeigt alles auf dem Display.

Start (im Ordner ~/pillcard):
    venv/bin/python pillcard.py            normaler Betrieb
    venv/bin/python pillcard.py --uids     nur UIDs anzeigen (zum Eintragen in plaene.json)
    venv/bin/python pillcard.py --reset    "heute schon genommen" für alle zurücksetzen
"""
import argparse
import datetime
import glob
import json
import os
import time
from pathlib import Path

import RPi.GPIO as GPIO
import serial
from mfrc522 import MFRC522

ORDNER = Path(__file__).resolve().parent
PLAENE = ORDNER / "plaene.json"          # wer bekommt was (später von der Website bearbeitet)
STAND = ORDNER / "stand.json"            # wer hat heute schon genommen
PROTOKOLL = ORDNER / "ausgaben.csv"      # jede Ausgabe mit Uhrzeit
UNBEKANNT = ORDNER / "unbekannte_uids.txt"

AUFTRAG_TIMEOUT = 60   # s, so lange darf der ESP32 für einen Auftrag brauchen
KARTE_SPERRE = 3       # s, so lange zählt dieselbe Karte nicht noch einmal
ANTWORTEN = ("BEREIT", "OK", "TABLETTE", "FERTIG", "FEHLER")


def jetzt():
    return datetime.datetime.now()


def json_lesen(pfad, standard):
    """Liest eine JSON-Datei; fehlt sie oder ist sie kaputt (z. B. Stromausfall), gibt es den Standardwert."""
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError) as fehler:
        if not isinstance(fehler, FileNotFoundError):
            print(f"  !! {pfad.name} ist beschädigt, nehme Standardwert")
        return standard


def json_schreiben(pfad, daten):
    """Schreibt erst in eine Hilfsdatei und benennt dann um, damit nie eine halbe Datei entsteht."""
    tmp = pfad.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as datei:
        datei.write(json.dumps(daten, indent=2, ensure_ascii=False))
        datei.flush()
        os.fsync(datei.fileno())  # sofort auf die SD-Karte, nicht erst irgendwann
    tmp.replace(pfad)


def stand_heute():
    """Gibt zurück, wer heute schon genommen hat; ab Mitternacht ist die Liste wieder leer."""
    stand = json_lesen(STAND, {})
    heute = jetzt().date().isoformat()
    if stand.get("datum") != heute:
        stand = {"datum": heute, "genommen": {}}
    return stand


class Esp:
    """Verbindung zum ESP32 über das USB-Kabel."""

    def __init__(self):
        port = (glob.glob("/dev/serial/by-id/*CP2102*") or ["/dev/ttyUSB0"])[0]
        self.seriell = serial.Serial(port, 115200, timeout=0.2)
        print(f"ESP32 an {port}")
        # Falls der ESP32 beim Verbinden neu startet: kurz warten und alte Zeilen verwerfen
        ende = time.time() + 3
        while time.time() < ende:
            if self.zeile_lesen() == "BEREIT":
                break
        self.seriell.reset_input_buffer()

    def senden(self, zeile):
        print(f"  -> ESP32: {zeile}")
        self.seriell.write((zeile + "\n").encode())

    def zeile_lesen(self):
        """Eine Zeile vom ESP32; Hilfstexte für den Seriellen Monitor werden übersprungen."""
        zeile = self.seriell.readline().decode(errors="replace").strip()
        if zeile.split(" ")[0] in ANTWORTEN:
            print(f"  <- ESP32: {zeile}")
            return zeile
        return ""

    def auftrag(self, nummer, kammern):
        """Schickt einen Auftrag und wartet auf FERTIG. Rückgabe: {Kammer: ausgegeben} oder None."""
        teile = [f"K{k}={n}" for k, n in sorted(kammern.items()) if n > 0]
        self.senden(f"AUFTRAG {nummer} " + " ".join(teile))
        ende = time.time() + AUFTRAG_TIMEOUT
        while time.time() < ende:
            zeile = self.zeile_lesen().split()
            if not zeile:
                continue
            if zeile[0] == "FEHLER":
                return None
            if zeile[0] == "FERTIG" and zeile[1] == str(nummer):
                # "K1=1" -> {"1": 1}
                return {t[1:].split("=")[0]: int(t.split("=")[1]) for t in zeile[2:]}
        print("  !! ESP32 hat nicht rechtzeitig FERTIG gemeldet")
        return None


def uid_lesen(leser):
    """Liest die UID einer Karte im Feld als Text wie "3D AB 09 01", sonst None."""
    status, _ = leser.MFRC522_Request(leser.PICC_REQIDL)
    if status != leser.MI_OK:
        return None
    status, uid = leser.MFRC522_Anticoll()
    if status != leser.MI_OK:
        return None
    return " ".join(f"{b:02X}" for b in uid[:4])


def karte_bearbeiten(uid, esp):
    """Entscheidet für eine Karte: unbekannt, heute schon genommen oder Ausgabe."""
    nutzer = json_lesen(PLAENE, {"nutzer": {}})["nutzer"]
    plan = nutzer.get(uid)
    print(f"[{jetzt():%H:%M:%S}] Karte {uid}" + (f" = {plan['name']}" if plan else " (unbekannt)"))

    if not plan:
        with UNBEKANNT.open("a", encoding="utf-8") as datei:
            datei.write(f"{jetzt():%Y-%m-%d %H:%M:%S} {uid}\n")
        esp.senden("MELDUNG unbekannt")
        return

    stand = stand_heute()
    if uid in stand["genommen"]:
        print(f"  heute schon um {stand['genommen'][uid]} genommen")
        esp.senden(f"MELDUNG schon_genommen {plan.get('wieder_um', '')}".strip())
        return

    kammern = {k: int(n) for k, n in plan["kammern"].items()}
    nummer = int(time.time()) % 100000
    ergebnis = esp.auftrag(nummer, kammern)

    # Auch bei Fehlern als genommen eintragen, damit nichts doppelt ausgegeben wird
    stand["genommen"][uid] = f"{jetzt():%H:%M}"
    json_schreiben(STAND, stand)

    bestellt = " ".join(f"K{k}={n}" for k, n in sorted(kammern.items()) if n > 0)
    erhalten = " ".join(f"K{k}={n}" for k, n in sorted((ergebnis or {}).items()))
    neu = not PROTOKOLL.exists()
    with PROTOKOLL.open("a", encoding="utf-8") as datei:
        if neu:
            datei.write("zeit;uid;name;bestellt;erhalten\n")
        datei.write(f"{jetzt():%Y-%m-%d %H:%M:%S};{uid};{plan['name']};{bestellt};{erhalten or 'FEHLER'}\n")
    print(f"  bestellt {bestellt}, erhalten {erhalten or 'FEHLER'}")


def main():
    parser = argparse.ArgumentParser(description="PillCard auf dem Raspberry Pi")
    parser.add_argument("--uids", action="store_true", help="nur UIDs anzeigen")
    parser.add_argument("--reset", action="store_true", help="heute schon genommen zurücksetzen")
    args = parser.parse_args()

    if args.reset:
        json_schreiben(STAND, {"datum": jetzt().date().isoformat(), "genommen": {}})
        print("Zurückgesetzt: alle dürfen heute wieder.")
        return

    leser = MFRC522()  # SPI0, RST an Pin 22 (GPIO25)
    leser.Write_MFRC522(0x26, 0x70)  # RFCfgReg: Antennenverstärkung auf Maximum (48 dB), hilft bei kleinen Chips
    esp = None if args.uids else Esp()
    print("Bereit, Karte hinhalten ... (Strg+C beendet)")

    letzte_uid, letzte_zeit = None, 0.0
    try:
        while True:
            uid = uid_lesen(leser)
            if not uid:
                time.sleep(0.1)
                continue
            # Liegt die Karte noch auf, zählt sie nicht noch einmal
            if uid == letzte_uid and time.time() - letzte_zeit < KARTE_SPERRE:
                letzte_zeit = time.time()
                continue
            letzte_uid = uid

            if args.uids:
                name = json_lesen(PLAENE, {"nutzer": {}})["nutzer"].get(uid, {}).get("name", "unbekannt")
                print(f"UID {uid}  ({name})", flush=True)
            else:
                karte_bearbeiten(uid, esp)
            letzte_zeit = time.time()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
