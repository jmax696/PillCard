"""PillCard auf dem Raspberry Pi: Karte lesen, Plan nachschlagen, Auftrag an den ESP32 schicken.

Der Pi entscheidet, wer was bekommt und ob heute schon genommen wurde.
Der ESP32 fährt die Servos, prüft mit dem Mikrofon und zeigt alles auf dem Display.

Pläne, Anpassungen und Ausgaben liegen in der SQLite-Datei pillcard.db (siehe datenbank.py).

Start (im Ordner ~/pillcard):
    venv/bin/python pillcard.py            normaler Betrieb
    venv/bin/python pillcard.py --uids     nur UIDs anzeigen (zum Eintragen in plaene.json)
    venv/bin/python pillcard.py --reset    heutige Ausgaben löschen, danach dürfen alle wieder
"""
import argparse
import datetime
import glob
import time
from pathlib import Path

import RPi.GPIO as GPIO
import serial
from mfrc522 import MFRC522

import datenbank

ORDNER = Path(__file__).resolve().parent
UNBEKANNT = ORDNER / "unbekannte_uids.txt"

AUFTRAG_GRUND = 20     # s Grundzeit für einen Auftrag ...
PRO_TABLETTE = 5       # ... plus so viel pro Tablette (Servo, Hinhören, zweiter Versuch)
KARTE_SPERRE = 3       # s, so lange zählt dieselbe Karte nicht noch einmal
LESER_PRUEFEN = 2      # s, so oft wird ohne Karte geprüft, ob der RC522 noch richtig eingestellt ist
RF_CFG, TX_CONTROL, VERSION = 0x26, 0x14, 0x37   # Register des RC522
VERSTAERKUNG = 0x70    # RFCfgReg: Antennenverstärkung auf Maximum (48 dB), hilft bei kleinen Chips
ANTWORTEN = ("BEREIT", "OK", "TABLETTE", "FERTIG", "FEHLER")


def jetzt():
    return datetime.datetime.now()


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
        ende = time.time() + AUFTRAG_GRUND + PRO_TABLETTE * sum(kammern.values())
        while time.time() < ende:
            zeile = self.zeile_lesen().split()
            if not zeile:
                continue
            if zeile[0] == "FEHLER":
                return None
            if zeile[0] == "FERTIG" and zeile[1] == str(nummer):
                # "K1=1" -> {1: 1}
                return {int(t[1:].split("=")[0]): int(t.split("=")[1]) for t in zeile[2:]}
        print("  !! ESP32 hat nicht rechtzeitig FERTIG gemeldet")
        return None


def leser_einrichten(leser):
    """Grundeinstellung des RC522: Antenne an, Verstärkung auf Maximum."""
    leser.MFRC522_Init()
    leser.Write_MFRC522(RF_CFG, VERSTAERKUNG)


def leser_ok(leser):
    """False, wenn der RC522 zwischendurch neu gestartet ist (z. B. Wackelkontakt, Spannungseinbruch).
    Danach ist die Antenne aus und er sieht keine Karte mehr, bis man ihn neu einrichtet."""
    return (leser.Read_MFRC522(RF_CFG) == VERSTAERKUNG
            and leser.Read_MFRC522(TX_CONTROL) & 0x03 == 0x03)


def uid_lesen(leser):
    """Liest die UID einer Karte im Feld als Text wie "3D AB 09 01", sonst None."""
    status, _ = leser.MFRC522_Request(leser.PICC_REQIDL)
    if status != leser.MI_OK:
        return None
    status, uid = leser.MFRC522_Anticoll()
    if status != leser.MI_OK:
        return None
    return " ".join(f"{b:02X}" for b in uid[:4])


def karte_bearbeiten(uid, esp, db):
    """Entscheidet für eine Karte: Anlernen, unbekannt, heute schon genommen oder Ausgabe."""
    scan = datenbank.scan_offen(db)
    if scan:
        # Die Website wartet auf eine Karte zum Anlernen: UID melden, nichts ausgeben
        datenbank.scan_erledigen(db, scan["id"], uid)
        print(f"[{jetzt():%H:%M:%S}] Karte {uid} für die Website angelernt")
        esp.senden("MELDUNG Karte erkannt")
        return

    nutzer = datenbank.nutzer_zu_uid(db, uid)
    print(f"[{jetzt():%H:%M:%S}] Karte {uid}" + (f" = {nutzer['name']}" if nutzer else " (unbekannt)"))

    if not nutzer:
        with UNBEKANNT.open("a", encoding="utf-8") as datei:
            datei.write(f"{jetzt():%Y-%m-%d %H:%M:%S} {uid}\n")
        esp.senden("MELDUNG unbekannt")
        return

    genommen_um = datenbank.heute_genommen_um(db, nutzer["id"])
    if genommen_um:
        print(f"  heute schon um {genommen_um} genommen")
        esp.senden(f"MELDUNG schon_genommen {nutzer['wieder_um'] or ''}".strip())
        return

    kammern = datenbank.heutige_dosis(db, nutzer["id"])
    if not kammern:
        print("  heute nichts im Plan")
        esp.senden("MELDUNG Heute nichts")
        return

    zeit = f"{jetzt():%Y-%m-%d %H:%M:%S}"
    nummer = int(time.time()) % 100000
    ergebnis = esp.auftrag(nummer, kammern)

    # Auch bei Fehlern eintragen (erhalten bleibt dann leer), damit nichts doppelt ausgegeben wird
    datenbank.ausgabe_eintragen(db, nutzer["id"], zeit, kammern, ergebnis)

    bestellt = " ".join(f"K{k}={n}" for k, n in sorted(kammern.items()))
    erhalten = " ".join(f"K{k}={n}" for k, n in sorted((ergebnis or {}).items()))
    print(f"  bestellt {bestellt}, erhalten {erhalten or 'FEHLER'}")


def main():
    parser = argparse.ArgumentParser(description="PillCard auf dem Raspberry Pi")
    parser.add_argument("--uids", action="store_true", help="nur UIDs anzeigen")
    parser.add_argument("--reset", action="store_true", help="heutige Ausgaben löschen")
    args = parser.parse_args()

    db = datenbank.verbinden()
    if not db.execute("SELECT 1 FROM nutzer").fetchone():
        datenbank.import_plaene(db)  # erster Start: Nutzer aus plaene.json übernehmen

    if args.reset:
        geloescht = datenbank.heute_zuruecksetzen(db)
        print(f"Zurückgesetzt: {geloescht} heutige Ausgaben gelöscht, alle dürfen wieder.")
        return

    leser = MFRC522()  # SPI0, RST an Pin 22 (GPIO25)
    leser_einrichten(leser)
    esp = None if args.uids else Esp()
    print("Bereit, Karte hinhalten ... (Strg+C beendet)")

    letzte_uid, letzte_zeit = None, 0.0
    geprueft = time.time()
    try:
        while True:
            uid = uid_lesen(leser)
            if not uid:
                if time.time() - geprueft > LESER_PRUEFEN:
                    geprueft = time.time()
                    if not leser_ok(leser):
                        version = leser.Read_MFRC522(VERSION)
                        print(f"[{jetzt():%H:%M:%S}] !! Kartenleser war zurückgesetzt (Version {version:#04x}), "
                              "richte ihn neu ein" + (" – keine Antwort, Kabel prüfen" if version in (0, 0xFF) else ""),
                              flush=True)
                        leser_einrichten(leser)
                time.sleep(0.1)
                continue
            # Liegt die Karte noch auf, zählt sie nicht noch einmal
            if uid == letzte_uid and time.time() - letzte_zeit < KARTE_SPERRE:
                letzte_zeit = time.time()
                continue
            letzte_uid = uid

            if args.uids:
                nutzer = datenbank.nutzer_zu_uid(db, uid)
                print(f"UID {uid}  ({nutzer['name'] if nutzer else 'unbekannt'})", flush=True)
            else:
                karte_bearbeiten(uid, esp, db)
            letzte_zeit = time.time()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
