# Datenbank

Der Pi hält seine Daten in der SQLite-Datei `~/pillcard/pillcard.db`. Angelegt und befüllt wird
sie von [`pi/datenbank.py`](../pi/datenbank.py), `pi/pillcard.py` fragt dort die heutige Dosis ab
und trägt jede Ausgabe ein. Die Website ([Website.md](Website.md)) arbeitet auf derselben Datei.

Nutzer, Pläne und Kammern werden über die Website gepflegt. `pi/plaene.json` dient nur noch für
den allerersten Start (`venv/bin/python datenbank.py import`). `venv/bin/python datenbank.py zeigen`
zeigt den Inhalt der Tabellen.

![ER-Diagramm der PillCard-Datenbank](ER_Datenbank.svg)

| Tabelle | Inhalt |
|---|---|
| `nutzer` | Personen mit RFID-Karte oder Chip, Benutzername und Passwort (nur als Hash) für die Website |
| `kammern` | Was in Dispenser 1–3 liegt, ob Nutzer es selbst anpassen dürfen und bis zu welcher Menge, Vorrat |
| `plan` | Der normale Plan: wer bekommt wie viel aus welcher Kammer |
| `anpassung` | Änderung über die Website, gilt nur für ein Datum |
| `ausgaben` | Jede Ausgabe pro Kammer, mit der laut Mikrofon wirklich ausgegebenen Menge |
| `einstellungen` | Schlüssel/Wert, zurzeit nur das Passwort der Verwaltung (Hash) |
| `scan_auftrag` | Website wartet auf eine Karte zum Anlernen; `pillcard.py` trägt die UID ein |

`plan` und `anpassung` lösen die n:m-Beziehung zwischen `nutzer` und `kammern` auf.

## Schema

```sql
CREATE TABLE nutzer (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  uid        TEXT UNIQUE NOT NULL,      -- RFID, z. B. '3D AB 09 01'
  passwort   TEXT NOT NULL,             -- nur als Hash, '' = noch kein Login
  wieder_um  TEXT,                      -- z. B. '18:00'
  benutzername TEXT UNIQUE              -- Login auf der Website
);

CREATE TABLE kammern (
  nr          INTEGER PRIMARY KEY,      -- 1, 2, 3
  medikament  TEXT NOT NULL,            -- z. B. 'Magnesium'
  anpassbar   INTEGER DEFAULT 0,        -- 1 = Nutzer darf selbst ändern
  max_pro_tag INTEGER DEFAULT 1,        -- Grenze nur für die Selbstanpassung, z. B. 2
  vorrat      INTEGER DEFAULT 0,        -- jede Ausgabe zieht ab
  warnen_ab   INTEGER DEFAULT 10        -- ab hier Hinweis "Vorrat geht zu Ende"
);

CREATE TABLE plan (
  nutzer_id  INTEGER REFERENCES nutzer(id),
  kammer     INTEGER REFERENCES kammern(nr),
  anzahl     INTEGER NOT NULL,
  PRIMARY KEY (nutzer_id, kammer)
);

CREATE TABLE anpassung (
  nutzer_id  INTEGER REFERENCES nutzer(id),
  kammer     INTEGER REFERENCES kammern(nr),
  datum      TEXT NOT NULL,             -- '2026-10-29'
  anzahl     INTEGER NOT NULL,
  PRIMARY KEY (nutzer_id, kammer, datum)
);

CREATE TABLE ausgaben (
  id         INTEGER PRIMARY KEY,
  nutzer_id  INTEGER REFERENCES nutzer(id),
  zeit       TEXT NOT NULL,             -- '2026-10-29 08:01:12'
  kammer     INTEGER REFERENCES kammern(nr),
  bestellt   INTEGER,
  erhalten   INTEGER                    -- laut Mikrofon
);

CREATE TABLE einstellungen (
  schluessel TEXT PRIMARY KEY,          -- 'admin_passwort'
  wert       TEXT
);

CREATE TABLE scan_auftrag (
  id         INTEGER PRIMARY KEY,
  angefragt  TEXT NOT NULL,             -- gilt 2 Minuten
  uid        TEXT                       -- leer, bis eine Karte an den Leser kommt
);
```

Spalten, die später dazugekommen sind (`benutzername`, `vorrat`, `warnen_ab`), trägt
`datenbank.verbinden()` in einer älteren Datei automatisch nach.

## Heutige Dosis für eine Karte

Die Menge im Plan legt die Verwaltung frei fest (0–9 pro Kammer, mehr nimmt der ESP32 nicht an).
Eine Anpassung des Nutzers für heute gewinnt nur bei anpassbaren Kammern und nur bis `max_pro_tag`
– liegt der Plan höher, bis zum Plan:

```sql
SELECT p.kammer,
       CASE WHEN k.anpassbar = 1 AND a.anzahl IS NOT NULL
            THEN MIN(a.anzahl, MAX(k.max_pro_tag, p.anzahl))
            ELSE p.anzahl END AS anzahl
FROM nutzer n
JOIN plan p     ON p.nutzer_id = n.id
JOIN kammern k  ON k.nr = p.kammer
LEFT JOIN anpassung a
       ON a.nutzer_id = n.id AND a.kammer = p.kammer AND a.datum = DATE('now', 'localtime')
WHERE n.uid = :uid;
```

Schon genommen heute, wenn es dazu eine Zeile gibt:

```sql
SELECT 1 FROM ausgaben a JOIN nutzer n ON n.id = a.nutzer_id
WHERE n.uid = :uid AND DATE(a.zeit) = DATE('now', 'localtime') LIMIT 1;
```

Die Website schreibt `anpassung` nur für Kammern mit `anpassbar = 1` und nur Werte von 0 bis
`max_pro_tag` (bzw. bis zum Plan, falls der höher ist). Wurde heute schon ausgegeben, gilt eine Änderung erst für morgen.
