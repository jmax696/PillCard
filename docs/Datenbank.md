# Datenbank (geplant)

Für die Website soll der Pi seine Daten in einer SQLite-Datei `pillcard.db` halten. Bis dahin
liegen sie in `pi/plaene.json` (Pläne), `stand.json` (heute genommen) und `ausgaben.csv`
(Protokoll) auf dem Pi.

![ER-Diagramm der PillCard-Datenbank](ER_Datenbank.svg)

| Tabelle | Inhalt |
|---|---|
| `nutzer` | Personen mit RFID-Karte oder Chip, Passwort (nur als Hash) für die Website |
| `kammern` | Was in Dispenser 1–3 liegt, ob man es selbst anpassen darf und bis zu welcher Menge |
| `plan` | Der normale Plan: wer bekommt wie viel aus welcher Kammer |
| `anpassung` | Änderung über die Website, gilt nur für ein Datum |
| `ausgaben` | Jede Ausgabe pro Kammer, mit der laut Mikrofon wirklich ausgegebenen Menge |

`plan` und `anpassung` lösen die n:m-Beziehung zwischen `nutzer` und `kammern` auf.

## Schema

```sql
CREATE TABLE nutzer (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  uid        TEXT UNIQUE NOT NULL,      -- RFID, z. B. '3D AB 09 01'
  passwort   TEXT NOT NULL,             -- nur als Hash, für die Website
  wieder_um  TEXT                       -- z. B. '18:00'
);

CREATE TABLE kammern (
  nr          INTEGER PRIMARY KEY,      -- 1, 2, 3
  medikament  TEXT NOT NULL,            -- z. B. 'Magnesium'
  anpassbar   INTEGER DEFAULT 0,        -- 1 = Nutzer darf selbst ändern
  max_pro_tag INTEGER DEFAULT 1         -- Obergrenze, z. B. 2
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
```

## Heutige Dosis für eine Karte

Die Anpassung von heute gewinnt gegen den normalen Plan, aber nur bis `max_pro_tag`:

```sql
SELECT p.kammer,
       MIN(COALESCE(a.anzahl, p.anzahl), k.max_pro_tag) AS anzahl
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

Die Website darf `anpassung` nur für Kammern mit `anpassbar = 1` schreiben und nur Werte
von 0 bis `max_pro_tag`.
