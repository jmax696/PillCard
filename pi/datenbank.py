"""SQLite-Datenbank für PillCard (Schema und ER-Diagramm in docs/Datenbank.md).

Aufruf (im Ordner ~/pillcard):
    venv/bin/python datenbank.py import    Nutzer und Pläne aus plaene.json übernehmen
                                           (beim ersten Mal auch das alte ausgaben.csv)
    venv/bin/python datenbank.py zeigen    Inhalt aller Tabellen anzeigen
"""
import csv
import json
import os
import sqlite3
import sys
from pathlib import Path

ORDNER = Path(__file__).resolve().parent
DB_DATEI = Path(os.environ.get("PILLCARD_DB", ORDNER / "pillcard.db"))  # zum Testen umlenkbar
PLAENE = ORDNER / "plaene.json"
ALT_CSV = ORDNER / "ausgaben.csv"

SCHEMA = """
CREATE TABLE IF NOT EXISTS nutzer (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  uid        TEXT UNIQUE NOT NULL,
  passwort   TEXT NOT NULL,
  wieder_um  TEXT
);
CREATE TABLE IF NOT EXISTS kammern (
  nr          INTEGER PRIMARY KEY,
  medikament  TEXT NOT NULL,
  anpassbar   INTEGER DEFAULT 0,
  max_pro_tag INTEGER DEFAULT 1          -- Obergrenze nur für die Selbstanpassung durch den Nutzer
);
CREATE TABLE IF NOT EXISTS plan (
  nutzer_id  INTEGER REFERENCES nutzer(id),
  kammer     INTEGER REFERENCES kammern(nr),
  anzahl     INTEGER NOT NULL,
  PRIMARY KEY (nutzer_id, kammer)
);
CREATE TABLE IF NOT EXISTS anpassung (
  nutzer_id  INTEGER REFERENCES nutzer(id),
  kammer     INTEGER REFERENCES kammern(nr),
  datum      TEXT NOT NULL,
  anzahl     INTEGER NOT NULL,
  PRIMARY KEY (nutzer_id, kammer, datum)
);
CREATE TABLE IF NOT EXISTS einnahmen (
  id          INTEGER PRIMARY KEY,
  nutzer_id   INTEGER REFERENCES nutzer(id),
  zeit        TEXT NOT NULL,             -- gleiche Zeit wie die Zeilen in ausgaben
  auftrag_nr  INTEGER,                   -- Nummer im AUFTRAG an den ESP32, kommt in BECHER-Meldungen zurück
  becher      TEXT,                      -- 'stand', 'abgebrochen', 'fehlte'; NULL = ESP32 hat nicht geantwortet
  entnommen   TEXT                       -- wann der Becher nach der Ausgabe hochgenommen wurde; NULL = (noch) nicht
);
CREATE TABLE IF NOT EXISTS ausgaben (
  id         INTEGER PRIMARY KEY,
  nutzer_id  INTEGER REFERENCES nutzer(id),
  zeit       TEXT NOT NULL,
  kammer     INTEGER REFERENCES kammern(nr),
  bestellt   INTEGER,
  erhalten   INTEGER
);
CREATE TABLE IF NOT EXISTS einstellungen (
  schluessel TEXT PRIMARY KEY,           -- z. B. 'admin_passwort' (Hash)
  wert       TEXT
);
CREATE TABLE IF NOT EXISTS scan_auftrag (
  id         INTEGER PRIMARY KEY,
  angefragt  TEXT NOT NULL,              -- von der Website beim Anlernen
  uid        TEXT                        -- trägt pillcard.py ein, sobald eine Karte kommt
);
CREATE TABLE IF NOT EXISTS rezepte (
  id          INTEGER PRIMARY KEY,
  eingelesen  TEXT NOT NULL,             -- wann die Kammer damit neu belegt wurde
  kammer      INTEGER REFERENCES kammern(nr),
  nutzer_id   INTEGER REFERENCES nutzer(id),
  medikament  TEXT NOT NULL,
  pro_tag     INTEGER NOT NULL,
  vorrat      INTEGER NOT NULL,          -- so viele Tabletten wurden eingefüllt
  rezept_id   TEXT,                      -- Id aus dem E-Rezept bzw. eMediplan
  roh         TEXT                       -- der gescannte QR-Text, unverändert
);
CREATE TABLE IF NOT EXISTS servo_befehl (
  id         INTEGER PRIMARY KEY,
  befehl     TEXT NOT NULL,              -- z. B. 'servo 3 12' beim Kalibrieren, pillcard.py schickt ihn weiter
  angefragt  TEXT NOT NULL
);
"""

# Spalten, die nach dem ersten Entwurf dazugekommen sind; werden in alten Datenbanken nachgetragen
NACHTRAG = [
    ("nutzer", "benutzername", "TEXT"),              # Login auf der Website
    ("kammern", "vorrat", "INTEGER DEFAULT 0"),      # Tabletten in der Kammer
    ("kammern", "warnen_ab", "INTEGER DEFAULT 10"),  # ab hier Hinweis "Vorrat geht zu Ende"
    ("kammern", "ruhe_winkel", "INTEGER"),           # Grundstellung des Servos (Kalibrieren auf der Website)
    ("kammern", "richtung", "INTEGER"),              # Ausgabe bei Grundstellung + Drehung (1) oder - Drehung (-1)
    ("kammern", "drehung", "INTEGER"),               # so weit dreht der Servo zur Ausgabe, z. B. 90 (Grad)
    ("ausgaben", "einnahme_id", "INTEGER REFERENCES einnahmen(id)"),  # zu welcher Einnahme die Zeile gehört
]

# Servo-Grundstellung und Drehrichtung, bis auf der Website kalibriert wurde (wie bisher im Sketch)
SERVO_START = {1: (170, -1), 2: (170, -1), 3: (10, 1)}
DREHUNG_START = 90                    # so weit dreht der Servo zur Ausgabe, bis kalibriert wurde
DREHUNG_MIN, DREHUNG_MAX = 10, 180    # mehr als 180° kann ein SG90 nicht
BEFEHL_GUELTIG = "DATETIME('now', 'localtime', '-10 seconds')"  # ältere Servo-Befehle verfallen

SCAN_GUELTIG = "DATETIME('now', 'localtime', '-2 minutes')"  # so lange wartet ein Scan-Auftrag

# Startbelegung der Kammern. Namen 2 und 3 sind Platzhalter, bis feststeht, was hineinkommt.
KAMMERN_START = [
    (1, "Magnesium", 1, 2),     # darf selbst angepasst werden, höchstens 2 pro Tag
    (2, "Medikament B", 0, 1),
    (3, "Medikament C", 0, 1),
]

HEUTE = "DATE('now', 'localtime')"

SQL_DOSIS = f"""
SELECT p.kammer,
       CASE WHEN k.anpassbar = 1 AND a.anzahl IS NOT NULL
            THEN MIN(a.anzahl, MAX(k.max_pro_tag, p.anzahl))
            ELSE p.anzahl END AS anzahl
FROM plan p
JOIN kammern k ON k.nr = p.kammer
LEFT JOIN anpassung a
       ON a.nutzer_id = p.nutzer_id AND a.kammer = p.kammer AND a.datum = {HEUTE}
WHERE p.nutzer_id = ?
ORDER BY p.kammer
"""


def oeffnen():
    """Nur die Verbindung, ohne Tabellen anzulegen (für jede Anfrage der Website)."""
    db = sqlite3.connect(DB_DATEI, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")   # Website und PillCard dürfen gleichzeitig zugreifen
    db.execute("PRAGMA synchronous = FULL")   # jede Änderung sofort fest auf die SD-Karte
    return db


def verbinden():
    """Öffnet die Datenbank, legt fehlende Tabellen an und füllt die Kammern beim ersten Start."""
    db = oeffnen()
    db.executescript(SCHEMA)
    for tabelle, spalte, typ in NACHTRAG:
        if spalte not in [r[1] for r in db.execute(f"PRAGMA table_info({tabelle})")]:
            db.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {typ}")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS nutzer_benutzername ON nutzer(benutzername)")
    db.execute("UPDATE OR IGNORE nutzer SET benutzername = LOWER(name) WHERE benutzername IS NULL")
    for nr, (ruhe, richtung) in SERVO_START.items():
        db.execute("UPDATE kammern SET ruhe_winkel = ? WHERE nr = ? AND ruhe_winkel IS NULL", (ruhe, nr))
        db.execute("UPDATE kammern SET richtung = ? WHERE nr = ? AND richtung IS NULL", (richtung, nr))
    if not db.execute("SELECT 1 FROM kammern").fetchone():
        with db:
            db.executemany("INSERT INTO kammern (nr, medikament, anpassbar, max_pro_tag) VALUES (?, ?, ?, ?)",
                           KAMMERN_START)
            for nr, (ruhe, richtung) in SERVO_START.items():
                db.execute("UPDATE kammern SET ruhe_winkel = ?, richtung = ? WHERE nr = ?", (ruhe, richtung, nr))
    db.commit()
    return db


def nutzer_zu_uid(db, uid):
    return db.execute("SELECT * FROM nutzer WHERE uid = ?", (uid,)).fetchone()


def heutige_dosis(db, nutzer_id):
    """Plan von heute als {Kammer: Anzahl}. Die Menge legt die Verwaltung fest; eine eigene Anpassung
    gewinnt bei anpassbaren Kammern, darf aber nicht über max_pro_tag (bzw. den Plan, falls höher)."""
    return {r["kammer"]: r["anzahl"] for r in db.execute(SQL_DOSIS, (nutzer_id,)) if r["anzahl"] > 0}


def heute_genommen_um(db, nutzer_id):
    """Uhrzeit der ersten Ausgabe heute als "HH:MM", sonst None."""
    zeit = db.execute(f"SELECT MIN(zeit) FROM ausgaben WHERE nutzer_id = ? AND DATE(zeit) = {HEUTE}",
                      (nutzer_id,)).fetchone()[0]
    return zeit[11:16] if zeit else None


def ausgabe_eintragen(db, nutzer_id, zeit, bestellt, erhalten, einnahme_id=None):
    """Eine Zeile pro Kammer und Vorrat abziehen. erhalten=None: ESP32 hat nicht geantwortet (bleibt leer)."""
    with db:
        for kammer, anzahl in bestellt.items():
            wert = None if erhalten is None else erhalten.get(kammer, 0)
            db.execute("""INSERT INTO ausgaben (nutzer_id, zeit, kammer, bestellt, erhalten, einnahme_id)
                          VALUES (?, ?, ?, ?, ?, ?)""",
                       (nutzer_id, zeit, kammer, anzahl, wert, einnahme_id))
            verbraucht = anzahl if wert is None else wert
            db.execute("UPDATE kammern SET vorrat = MAX(COALESCE(vorrat, 0) - ?, 0) WHERE nr = ?",
                       (verbraucht, kammer))


def einnahme_eintragen(db, nutzer_id, zeit, auftrag_nr, becher, entnommen=None):
    """Eine Zeile pro Auftrag mit dem Becher-Status; die Zeilen in ausgaben verweisen darauf."""
    with db:
        return db.execute("INSERT INTO einnahmen (nutzer_id, zeit, auftrag_nr, becher, entnommen) VALUES (?, ?, ?, ?, ?)",
                          (nutzer_id, zeit, auftrag_nr, becher, entnommen)).lastrowid


def becher_entnommen(db, auftrag_nr, zeit):
    """ESP32 meldet "BECHER 17 genommen": Entnahmezeit bei der jüngsten Einnahme mit dieser Nummer.
    False, wenn es keine offene Einnahme dazu gibt (z. B. schon eingetragen)."""
    with db:
        return db.execute("""UPDATE einnahmen SET entnommen = ?
                             WHERE id = (SELECT MAX(id) FROM einnahmen WHERE auftrag_nr = ?) AND entnommen IS NULL""",
                          (zeit, auftrag_nr)).rowcount > 0


def vorrat_status(db):
    """Pro Kammer: Vorrat, Bedarf aller Nutzer pro Tag, wie viele Tage er reicht, ob er knapp wird."""
    zeilen = []
    for k in db.execute("""SELECT k.*, COALESCE(SUM(p.anzahl), 0) AS bedarf
                           FROM kammern k LEFT JOIN plan p ON p.kammer = k.nr
                           GROUP BY k.nr ORDER BY k.nr"""):
        k = dict(k)
        k["vorrat"] = k["vorrat"] or 0
        k["reicht_tage"] = k["vorrat"] // k["bedarf"] if k["bedarf"] else None
        k["knapp"] = bool(k["bedarf"]) and k["vorrat"] <= (k["warnen_ab"] or 0)
        k["leer"] = k["vorrat"] <= 0   # dann leuchtet die LED am Einfüllstutzen
        zeilen.append(k)
    return zeilen


def leere_kammern(db):
    """Pro Kammer (nach Nummer sortiert) True, wenn kein Vorrat mehr da ist. Steuert die Leer-LEDs."""
    return [(k["vorrat"] or 0) <= 0 for k in db.execute("SELECT vorrat FROM kammern ORDER BY nr")]


def kammer_neu_belegen(db, kammer, medikament, vorrat, nutzer_id, pro_tag, rezept_id, roh):
    """Neues Medikament aus einem E-Rezept in eine Kammer. Weil dort jetzt etwas anderes liegt,
    fallen die alten Pläne und künftigen Anpassungen aller Nutzer für diese Kammer weg."""
    with db:
        db.execute("UPDATE kammern SET medikament = ?, vorrat = ?, anpassbar = 0, max_pro_tag = ? WHERE nr = ?",
                   (medikament, vorrat, max(1, pro_tag), kammer))
        db.execute(f"DELETE FROM anpassung WHERE kammer = ? AND datum >= {HEUTE}", (kammer,))
        db.execute("DELETE FROM plan WHERE kammer = ?", (kammer,))
        if pro_tag > 0:
            db.execute("INSERT INTO plan (nutzer_id, kammer, anzahl) VALUES (?, ?, ?)", (nutzer_id, kammer, pro_tag))
        db.execute("""INSERT INTO rezepte (eingelesen, kammer, nutzer_id, medikament, pro_tag, vorrat, rezept_id, roh)
                      VALUES (DATETIME('now', 'localtime'), ?, ?, ?, ?, ?, ?, ?)""",
                   (kammer, nutzer_id, medikament, pro_tag, vorrat, rezept_id, roh))


def heute_zuruecksetzen(db):
    """Löscht die heutigen Ausgaben, danach dürfen alle wieder (für Demo und Tests)."""
    with db:
        geloescht = db.execute(f"DELETE FROM ausgaben WHERE DATE(zeit) = {HEUTE}").rowcount
        db.execute(f"DELETE FROM einnahmen WHERE DATE(zeit) = {HEUTE}")
        return geloescht


def scan_anfragen(db):
    """Website: die nächste Karte am Leser soll angelernt statt ausgegeben werden."""
    with db:
        return db.execute("INSERT INTO scan_auftrag (angefragt) VALUES (DATETIME('now', 'localtime'))").lastrowid


def scan_offen(db):
    """pillcard.py: wartet gerade ein Scan-Auftrag der Website?"""
    return db.execute(f"SELECT id FROM scan_auftrag WHERE uid IS NULL AND angefragt >= {SCAN_GUELTIG} "
                      "ORDER BY id DESC LIMIT 1").fetchone()


def scan_erledigen(db, scan_id, uid):
    with db:
        db.execute("UPDATE scan_auftrag SET uid = ? WHERE id = ?", (uid, scan_id))


def scan_ergebnis(db, scan_id):
    """Website: UID zum Scan-Auftrag, sonst None. abgelaufen=True, wenn keine Karte mehr kommt."""
    zeile = db.execute(f"SELECT uid, angefragt < {SCAN_GUELTIG} AS abgelaufen FROM scan_auftrag WHERE id = ?",
                       (scan_id,)).fetchone()
    if not zeile:
        return None, True
    return zeile["uid"], bool(zeile["abgelaufen"]) and not zeile["uid"]


# ---------- Servos kalibrieren ----------

def ruhe_bereich(richtung, drehung):
    """Erlaubte Grundstellungen, damit die Ausgabe (um drehung weiter) noch zwischen 0 und 180° liegt."""
    return (drehung, 180) if richtung < 0 else (0, 180 - drehung)


def servo_winkel(db):
    """Pro Kammer (nach Nummer): Nummer, Grundstellung, Richtung und Ausgabewinkel."""
    zeilen = []
    for k in db.execute("SELECT nr, medikament, ruhe_winkel, richtung, drehung FROM kammern ORDER BY nr"):
        start_ruhe, start_richtung = SERVO_START.get(k["nr"], (90, 1))
        ruhe = k["ruhe_winkel"] if k["ruhe_winkel"] is not None else start_ruhe
        richtung = k["richtung"] or start_richtung
        drehung = k["drehung"] or DREHUNG_START
        # Passt die Ausgabe nicht (sollte nie vorkommen), lieber am Rand anhalten als falsch schicken
        ausgabe = max(0, min(180, ruhe + richtung * drehung))
        zeilen.append({"nr": k["nr"], "medikament": k["medikament"], "ruhe": ruhe, "richtung": richtung,
                       "drehung": drehung, "ausgabe": ausgabe, "bereich": ruhe_bereich(richtung, drehung)})
    return zeilen


def grundstellung_speichern(db, nr, ruhe, richtung, drehung):
    """Website: neue Grundstellung und Drehung. False, wenn die Ausgabe dann außerhalb 0–180° läge."""
    richtung = -1 if richtung < 0 else 1
    if not DREHUNG_MIN <= drehung <= DREHUNG_MAX:
        return False
    von, bis = ruhe_bereich(richtung, drehung)
    if not von <= ruhe <= bis:
        return False
    with db:
        db.execute("UPDATE kammern SET ruhe_winkel = ?, richtung = ?, drehung = ? WHERE nr = ?",
                   (ruhe, richtung, drehung, nr))
    return True


def servo_befehl(db, befehl):
    """Website: Befehl für den ESP32 einreihen, pillcard.py schickt ihn weiter."""
    with db:
        db.execute("INSERT INTO servo_befehl (befehl, angefragt) VALUES (?, DATETIME('now', 'localtime'))",
                   (befehl,))


def servo_befehle_holen(db):
    """pillcard.py: alle wartenden Befehle (älteste zuerst) und aus der Tabelle nehmen.
    Was älter als 10 s ist, verfällt, damit nach einem Neustart nichts Altes nachkommt."""
    with db:
        zeilen = db.execute(f"SELECT id, befehl FROM servo_befehl WHERE angefragt >= {BEFEHL_GUELTIG} "
                            "ORDER BY id").fetchall()
        db.execute("DELETE FROM servo_befehl")
    return [z["befehl"] for z in zeilen]


def servo_befehle_haengen(db):
    """Website: Anzahl Befehle, die seit über 3 s keiner abholt (dann läuft pillcard.py nicht)."""
    return db.execute("SELECT COUNT(*) FROM servo_befehl "
                      "WHERE angefragt < DATETIME('now', 'localtime', '-3 seconds')").fetchone()[0]


def import_plaene(db):
    """Übernimmt Nutzer und Pläne aus plaene.json. Passwörter, Anpassungen und Ausgaben bleiben."""
    nutzer = json.loads(PLAENE.read_text(encoding="utf-8"))["nutzer"]
    with db:
        for uid, p in nutzer.items():
            db.execute("""INSERT INTO nutzer (name, uid, passwort, wieder_um, benutzername) VALUES (?, ?, '', ?, ?)
                          ON CONFLICT(uid) DO UPDATE SET name = excluded.name, wieder_um = excluded.wieder_um""",
                       (p["name"], uid, p.get("wieder_um"), p["name"].lower()))
            db.execute("UPDATE nutzer SET benutzername = LOWER(name) WHERE uid = ? AND benutzername IS NULL", (uid,))
            nutzer_id = nutzer_zu_uid(db, uid)["id"]
            db.execute("DELETE FROM plan WHERE nutzer_id = ?", (nutzer_id,))
            for kammer, anzahl in p["kammern"].items():
                if int(anzahl) > 0:
                    db.execute("INSERT INTO plan VALUES (?, ?, ?)", (nutzer_id, int(kammer), int(anzahl)))
    print(f"{len(nutzer)} Nutzer aus plaene.json übernommen.")

    # Altes Protokoll nur übernehmen, solange die Tabelle noch leer ist
    if ALT_CSV.exists() and not db.execute("SELECT 1 FROM ausgaben").fetchone():
        anzahl = 0
        with ALT_CSV.open(encoding="utf-8") as datei:
            for zeile in csv.DictReader(datei, delimiter=";"):
                n = nutzer_zu_uid(db, zeile["uid"])
                if not n:
                    continue
                bestellt = {int(t[1:].split("=")[0]): int(t.split("=")[1]) for t in zeile["bestellt"].split()}
                erhalten = None if zeile["erhalten"] == "FEHLER" else \
                    {int(t[1:].split("=")[0]): int(t.split("=")[1]) for t in zeile["erhalten"].split()}
                ausgabe_eintragen(db, n["id"], zeile["zeit"], bestellt, erhalten)
                anzahl += 1
        print(f"{anzahl} alte Ausgaben aus ausgaben.csv übernommen.")


def zeigen(db):
    for tabelle in ("nutzer", "kammern", "plan", "anpassung", "einnahmen", "ausgaben", "scan_auftrag", "rezepte",
                    "servo_befehl"):
        zeilen = db.execute(f"SELECT * FROM {tabelle}").fetchall()
        print(f"\n== {tabelle} ({len(zeilen)})")
        for z in zeilen:
            werte = dict(z)
            if "passwort" in werte:
                werte["passwort"] = "gesetzt" if werte["passwort"] else "-"
            if werte.get("roh"):
                werte["roh"] = werte["roh"][:30] + "…"
            print("  ", werte)


if __name__ == "__main__":
    befehl = sys.argv[1] if len(sys.argv) > 1 else "zeigen"
    verbindung = verbinden()
    if befehl == "import":
        import_plaene(verbindung)
    elif befehl == "zeigen":
        zeigen(verbindung)
    else:
        print(__doc__)
