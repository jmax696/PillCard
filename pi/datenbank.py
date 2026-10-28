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
"""

# Spalten, die nach dem ersten Entwurf dazugekommen sind; werden in alten Datenbanken nachgetragen
NACHTRAG = [
    ("nutzer", "benutzername", "TEXT"),              # Login auf der Website
    ("kammern", "vorrat", "INTEGER DEFAULT 0"),      # Tabletten in der Kammer
    ("kammern", "warnen_ab", "INTEGER DEFAULT 10"),  # ab hier Hinweis "Vorrat geht zu Ende"
]

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
    if not db.execute("SELECT 1 FROM kammern").fetchone():
        with db:
            db.executemany("INSERT INTO kammern (nr, medikament, anpassbar, max_pro_tag) VALUES (?, ?, ?, ?)",
                           KAMMERN_START)
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


def ausgabe_eintragen(db, nutzer_id, zeit, bestellt, erhalten):
    """Eine Zeile pro Kammer und Vorrat abziehen. erhalten=None: ESP32 hat nicht geantwortet (bleibt leer)."""
    with db:
        for kammer, anzahl in bestellt.items():
            wert = None if erhalten is None else erhalten.get(kammer, 0)
            db.execute("INSERT INTO ausgaben (nutzer_id, zeit, kammer, bestellt, erhalten) VALUES (?, ?, ?, ?, ?)",
                       (nutzer_id, zeit, kammer, anzahl, wert))
            verbraucht = anzahl if wert is None else wert
            db.execute("UPDATE kammern SET vorrat = MAX(COALESCE(vorrat, 0) - ?, 0) WHERE nr = ?",
                       (verbraucht, kammer))


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
        zeilen.append(k)
    return zeilen


def heute_zuruecksetzen(db):
    """Löscht die heutigen Ausgaben, danach dürfen alle wieder (für Demo und Tests)."""
    with db:
        return db.execute(f"DELETE FROM ausgaben WHERE DATE(zeit) = {HEUTE}").rowcount


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
    for tabelle in ("nutzer", "kammern", "plan", "anpassung", "ausgaben", "scan_auftrag"):
        zeilen = db.execute(f"SELECT * FROM {tabelle}").fetchall()
        print(f"\n== {tabelle} ({len(zeilen)})")
        for z in zeilen:
            werte = dict(z)
            if "passwort" in werte:
                werte["passwort"] = "gesetzt" if werte["passwort"] else "-"
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
