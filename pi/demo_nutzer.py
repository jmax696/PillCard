"""Erfundener Demo-Nutzer für die Demo-Seite (/admin/demo).

Die Daten stehen nicht in pillcard.db, sondern werden hier aus dem Datum erzeugt. Deshalb bleibt die
Demo-Seite gleich, egal ob in der Verwaltung jemand „Heute zurücksetzen“ drückt oder Nutzer löscht.
Jeder Tag bekommt seinen eigenen Zufallsgenerator (Seed = Datum): beim Neuladen ändert sich nichts,
und der Verlauf wandert mit dem Kalender mit, sieht also an jedem Tag aktuell aus.
"""
import datetime
import random

NUTZER = {"name": "Erika Muster", "benutzername": "erika", "uid": "A3 5F 12 C8", "alter": 78}
TAGE_DABEI = 60   # so lange nutzt Erika PillCard schon

# Wie im echten Plan: Kammer, Medikament, Anzahl pro Tag; anpassbar = darf Erika selbst ändern
MEDS = [
    {"nr": 1, "medikament": "Ramipril 5 mg", "wofuer": "Blutdruck", "plan": 1, "anpassbar": False, "grenze": 1},
    {"nr": 2, "medikament": "Metformin 500 mg", "wofuer": "Diabetes", "plan": 2, "anpassbar": False, "grenze": 2},
    {"nr": 3, "medikament": "Magnesium 300 mg", "wofuer": "Wadenkrämpfe", "plan": 1, "anpassbar": True, "grenze": 2},
]
VORRAT = {1: 41, 2: 74, 3: 5}   # Tabletten in der Kammer; Magnesium ist bald leer
WARNEN_AB_TAGEN = 7

# Gestellte Ereignisse, gezählt in Tagen vor heute
VERPASST = {9, 31}                       # Karte nicht vorgehalten
WENIGER = {4: (2, 1), 23: (2, 1)}        # Kammer: eine Tablette ist laut Mikrofon nicht herausgekommen
ANGEPASST = {2: 2, 13: 0, 20: 2, 21: 2}  # Magnesium selbst geändert (Plan 1)
MORGEN_MAGNESIUM = 2                     # für morgen schon angepasst


def _uhrzeit(tag):
    """Abholzeit für einen Tag, immer dieselbe für dasselbe Datum (meist kurz nach dem Frühstück)."""
    zufall = random.Random(tag.toordinal())
    minuten = 7 * 60 + 40 + zufall.randint(0, 45)
    return datetime.time(minuten // 60, minuten % 60, zufall.randint(0, 59))


def _ausgaben_am(tag, vor_tagen):
    """Die Ausgabe-Zeilen eines Tages, so wie pillcard.py sie in die Tabelle ausgaben schreibt."""
    if vor_tagen in VERPASST:
        return []
    zeit = _uhrzeit(tag)
    zeilen = []
    for m in MEDS:
        bestellt = ANGEPASST.get(vor_tagen, m["plan"]) if m["anpassbar"] else m["plan"]
        if bestellt == 0:
            continue
        erhalten = bestellt
        if vor_tagen in WENIGER and WENIGER[vor_tagen][0] == m["nr"]:
            erhalten = WENIGER[vor_tagen][1]
        zeilen.append({"datum": tag, "zeit": f"{zeit:%H:%M:%S}", "uhr": f"{zeit:%H:%M}", "kammer": m["nr"],
                       "medikament": m["medikament"], "bestellt": bestellt, "erhalten": erhalten,
                       "angepasst": bestellt != m["plan"], "becher": "erkannt"})
    return zeilen


def daten(jetzt):
    """Alles, was die Demo-Seite zeigt. jetzt = datetime.datetime.now()"""
    heute = jetzt.date()
    beginn = heute - datetime.timedelta(days=TAGE_DABEI)

    ausgaben, tage = [], {}
    for vor_tagen in range(TAGE_DABEI, -1, -1):
        tag = heute - datetime.timedelta(days=vor_tagen)
        zeilen = _ausgaben_am(tag, vor_tagen)
        if vor_tagen == 0 and datetime.datetime.combine(tag, _uhrzeit(tag)) > jetzt:
            zeilen = []   # heute noch nicht abgeholt, so früh am Morgen
        ausgaben += zeilen
        if zeilen:
            erhalten = sum(z["erhalten"] for z in zeilen)
            weniger = any(z["erhalten"] < z["bestellt"] for z in zeilen)
            tage[tag.isoformat()] = {"erhalten": erhalten, "status": "teil" if weniger else "ok"}
        elif vor_tagen > 0:
            tage[tag.isoformat()] = {"erhalten": 0, "status": "verpasst"}

    heute_ausgaben = [z for z in ausgaben if z["datum"] == heute]
    genommen_um = heute_ausgaben[0]["uhr"] if heute_ausgaben else None
    if not genommen_um:
        zustand = "offen"
    elif any(z["erhalten"] < z["bestellt"] for z in heute_ausgaben):
        zustand = "teil"
    else:
        zustand = "erledigt"

    meds = []
    for m in MEDS:
        m = dict(m)
        m["heute"] = ANGEPASST.get(0, m["plan"]) if m["anpassbar"] else m["plan"]
        m["morgen"] = MORGEN_MAGNESIUM if m["anpassbar"] else m["plan"]
        meds.append(m)

    # Vorrat wie datenbank.vorrat_status: reicht so viele Tage beim geplanten Bedarf
    vorrat = []
    for m in MEDS:
        reicht = VORRAT[m["nr"]] // m["plan"]
        vorrat.append({"nr": m["nr"], "medikament": m["medikament"], "vorrat": VORRAT[m["nr"]],
                       "bedarf": m["plan"], "reicht_tage": reicht, "knapp": reicht <= WARNEN_AB_TAGEN})

    # Selbst vorgenommene Anpassungen, neueste zuerst (jeweils am Vorabend eingestellt)
    anpassungen = [{"fuer": heute + datetime.timedelta(days=1), "anzahl": MORGEN_MAGNESIUM, "eingestellt": "heute"}]
    for vor_tagen, anzahl in sorted(ANGEPASST.items()):
        fuer = heute - datetime.timedelta(days=vor_tagen)
        vortag = fuer - datetime.timedelta(days=1)
        anpassungen.append({"fuer": fuer, "anzahl": anzahl,
                            "eingestellt": f"{vortag:%d.%m.} {random.Random(vortag.toordinal()).randint(18, 21)}:"
                                           f"{random.Random(-vortag.toordinal()).randint(0, 59):02d}"})

    return {"nutzer": dict(NUTZER, seit=beginn), "meds": meds, "ausgaben": ausgaben, "tage": tage,
            "heute_ausgaben": heute_ausgaben, "genommen_um": genommen_um, "zustand": zustand,
            "vorrat": vorrat, "knapp": [k for k in vorrat if k["knapp"]], "anpassungen": anpassungen}
