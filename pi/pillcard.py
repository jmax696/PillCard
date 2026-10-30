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
import re
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
LEER_PRUEFEN = 2       # s, so oft wird nachgesehen, ob eine Kammer leer ist oder nachgefüllt wurde
LEER_AUFFRISCHEN = 30  # s, so oft geht der Leer-Status auch ohne Änderung raus (falls der ESP32 neu gestartet ist)
# Nur diese Befehle der Website gehen an den ESP32: Servo auf einen Winkel stellen, Probe-Ausgabe
SERVO_BEFEHL = re.compile(r"(servo [1-3] (180|1[0-7][0-9]|[1-9]?[0-9])|probe [1-3])")
RF_CFG, TX_CONTROL, VERSION = 0x26, 0x14, 0x37   # Register des RC522
VERSTAERKUNG = 0x70    # RFCfgReg: Antennenverstärkung auf Maximum (48 dB), hilft bei kleinen Chips
ANTWORTEN = ("BEREIT", "OK", "TABLETTE", "FERTIG", "FEHLER", "BECHER")


def jetzt():
    return datetime.datetime.now()


class Esp:
    """Verbindung zum ESP32 über das USB-Kabel."""

    def __init__(self):
        port = (glob.glob("/dev/serial/by-id/*CP2102*") or ["/dev/ttyUSB0"])[0]
        self.seriell = serial.Serial(port, 115200, timeout=0.2)
        self.entnahmen = []   # (Auftragsnummer, Zeit) aus "BECHER 17 genommen", bis main() sie einträgt
        print(f"ESP32 an {port}")
        # Falls der ESP32 beim Verbinden neu startet: kurz warten und alte Zeilen verwerfen
        ende = time.time() + 3
        while time.time() < ende:
            if self.zeile_lesen() == "BEREIT":
                break
        self.seriell.reset_input_buffer()
        self.entnahmen.clear()   # alte Meldungen von vor dem Neustart gehören zu keinem Auftrag mehr

    def senden(self, zeile, leise=False):
        if not leise:
            print(f"  -> ESP32: {zeile}")
        self.seriell.write((zeile + "\n").encode())

    def leer_zeigen(self, leer, leise=False):
        """Schaltet die LEDs an den Einfüllstutzen, z. B. [False, True, False] -> "LEER 0 1 0"."""
        self.senden("LEER " + " ".join("1" if k else "0" for k in leer), leise)

    def zeile_lesen(self):
        """Eine Zeile vom ESP32; Hilfstexte für den Seriellen Monitor werden übersprungen."""
        zeile = self.seriell.readline().decode(errors="replace").strip()
        if zeile.split(" ")[0] in ANTWORTEN:
            print(f"  <- ESP32: {zeile}")
            teile = zeile.split()
            # "BECHER 17 genommen 10": vor 10 s hochgenommen und seitdem weg. Kann jederzeit kommen,
            # auch mitten in einem neuen Auftrag, darum erst sammeln
            if (len(teile) in (3, 4) and teile[0] == "BECHER" and teile[2] == "genommen"
                    and all(t.isdigit() for t in teile[1:2] + teile[3:])):
                vorher = int(teile[3]) if len(teile) == 4 else 0
                zeit = jetzt() - datetime.timedelta(seconds=vorher)
                self.entnahmen.append((int(teile[1]), f"{zeit:%Y-%m-%d %H:%M:%S}"))
            return zeile
        if zeile.startswith(("Mikrofon Kammer", "Verlauf ms")):
            print(f"     ESP32: {zeile}")   # Pegel je Tablette, zum Einstellen von MIC_SCHWELLE
        return ""

    def mitlesen(self):
        """Liest, was der ESP32 zwischen den Aufträgen schickt (z. B. BECHER 17 genommen), ohne zu warten."""
        while self.seriell.in_waiting:
            self.zeile_lesen()

    def entnahmen_abholen(self):
        entnahmen, self.entnahmen = self.entnahmen, []
        return entnahmen

    def auftrag(self, nummer, kammern):
        """Schickt einen Auftrag und wartet auf FERTIG.
        Rückgabe: ({Kammer: ausgegeben} oder None, Becher-Status für die Tabelle einnahmen)."""
        teile = [f"K{k}={n}" for k, n in sorted(kammern.items()) if n > 0]
        self.senden(f"AUFTRAG {nummer} " + " ".join(teile))
        ende = time.time() + AUFTRAG_GRUND + PRO_TABLETTE * sum(kammern.values())
        becher = "stand"   # FERTIG ohne BECHER ... abgebrochen: Becher stand die ganze Ausgabe über
        while time.time() < ende:
            zeile = self.zeile_lesen().split()
            if not zeile:
                continue
            if zeile[0] == "FEHLER":
                return None, ("fehlte" if zeile[1:] == ["kein_becher"] else None)
            if zeile[:3] == ["BECHER", str(nummer), "abgebrochen"]:
                becher = "abgebrochen"
            if zeile[0] == "FERTIG" and zeile[1] == str(nummer):
                # "K1=1" -> {1: 1}
                return {int(t[1:].split("=")[0]): int(t.split("=")[1]) for t in zeile[2:]}, becher
        print("  !! ESP32 hat nicht rechtzeitig FERTIG gemeldet")
        return None, None


class LeerAnzeige:
    """Hält die LEDs an den Einfüllstutzen auf dem Stand der Datenbank (Vorrat 0 = LED an).
    Fragt nur alle LEER_PRUEFEN Sekunden nach, damit auch Nachfüllen über die Website ankommt."""

    def __init__(self, esp, db):
        self.esp, self.db = esp, db
        self.zuletzt, self.gesendet, self.geprueft = None, 0.0, 0.0

    def pruefen(self, sofort=False):
        if not self.esp or (not sofort and time.time() - self.geprueft < LEER_PRUEFEN):
            return
        self.geprueft = time.time()
        leer = datenbank.leere_kammern(self.db)
        if leer != self.zuletzt:
            namen = ", ".join(f"K{nr}" for nr, ist_leer in enumerate(leer, 1) if ist_leer) or "keine"
            print(f"[{jetzt():%H:%M:%S}] Leere Kammern: {namen}", flush=True)
            self.esp.leer_zeigen(leer)
        elif time.time() - self.gesendet > LEER_AUFFRISCHEN:
            self.esp.leer_zeigen(leer, leise=True)
        else:
            return
        self.zuletzt, self.gesendet = leer, time.time()


class ServoAbgleich:
    """Hält die Servo-Winkel des ESP32 auf dem Stand der Datenbank ("WINKEL Ruhe1 Ausgabe1 ...")
    und gibt die Befehle der Kalibrier-Seite (servo 3 12, probe 3) an den ESP32 weiter."""

    def __init__(self, esp, db):
        self.esp, self.db = esp, db
        self.zuletzt, self.gesendet, self.geprueft = None, 0.0, 0.0

    def pruefen(self, sofort=False):
        if not self.esp:
            return
        for befehl in datenbank.servo_befehle_holen(self.db):
            if SERVO_BEFEHL.fullmatch(befehl):
                self.esp.senden(befehl)
            else:
                print(f"  !! unbekannter Servo-Befehl verworfen: {befehl!r}")

        if not sofort and time.time() - self.geprueft < LEER_PRUEFEN:
            return
        self.geprueft = time.time()
        winkel = [(k["ruhe"], k["ausgabe"]) for k in datenbank.servo_winkel(self.db)]
        zeile = "WINKEL " + " ".join(f"{r} {a}" for r, a in winkel)
        if winkel != self.zuletzt:
            self.esp.senden(zeile)
        elif time.time() - self.gesendet > LEER_AUFFRISCHEN:
            self.esp.senden(zeile, leise=True)  # falls der ESP32 neu gestartet ist
        else:
            return
        self.zuletzt, self.gesendet = winkel, time.time()


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
    ergebnis, becher = esp.auftrag(nummer, kammern)

    # Auch bei Fehlern eintragen (erhalten bleibt dann leer), damit nichts doppelt ausgegeben wird.
    # Wurde der Becher mittendrin weggenommen, ist das zugleich die Entnahme.
    entnommen = f"{jetzt():%Y-%m-%d %H:%M:%S}" if becher == "abgebrochen" else None
    einnahme_id = datenbank.einnahme_eintragen(db, nutzer["id"], zeit, nummer, becher, entnommen)
    datenbank.ausgabe_eintragen(db, nutzer["id"], zeit, kammern, ergebnis, einnahme_id)

    bestellt = " ".join(f"K{k}={n}" for k, n in sorted(kammern.items()))
    erhalten = " ".join(f"K{k}={n}" for k, n in sorted((ergebnis or {}).items()))
    print(f"  bestellt {bestellt}, erhalten {erhalten or 'FEHLER'}, Becher {becher or 'unbekannt'}")


def entnahmen_eintragen(esp, db):
    """Trägt ein, wann ein Becher nach der Ausgabe hochgenommen wurde (BECHER 17 genommen)."""
    if not esp:
        return
    esp.mitlesen()
    for nummer, zeit in esp.entnahmen_abholen():
        if datenbank.becher_entnommen(db, nummer, zeit):
            print(f"[{zeit[11:]}] Becher von Auftrag {nummer} entnommen", flush=True)
        else:
            print(f"  !! Entnahme für unbekannten Auftrag {nummer} gemeldet")


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
    leer = LeerAnzeige(esp, db)
    leer.pruefen(sofort=True)
    servos = ServoAbgleich(esp, db)
    servos.pruefen(sofort=True)
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
                leer.pruefen()
                servos.pruefen()
                entnahmen_eintragen(esp, db)
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
                entnahmen_eintragen(esp, db)  # kann während des Auftrags für den vorigen gekommen sein
                leer.pruefen(sofort=True)  # nach einer Ausgabe kann eine Kammer leer geworden sein
            letzte_zeit = time.time()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
