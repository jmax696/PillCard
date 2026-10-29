"""PillCard-Website auf dem Raspberry Pi, im Browser unter http://<Pi-IP>:8080

Verwaltung (/admin): neue Karten anlernen, Nutzer und Dosierung bearbeiten, Kammern und Vorrat.
Nutzerbereich (/):   Login, heutige Dosis je nach Tagesform anpassen, Kalender, Vorratswarnung.
Demo (/admin/demo):  Live-Dashboard für die Präsentation, holt sich alle 2 s neue Daten.

Beide Teile arbeiten auf derselben pillcard.db wie pillcard.py.

Start (im Ordner ~/pillcard):
    venv/bin/python web.py           normaler Betrieb (waitress)
    venv/bin/python web.py --debug   Entwicklungsserver mit automatischem Neuladen
"""
import argparse
import calendar
import datetime
import hmac
import os
import re
import secrets
import sqlite3
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import datenbank

ORDNER = Path(__file__).resolve().parent
SCHLUESSEL = ORDNER / "geheim.key"
PORT = 8080
MAX_PRO_KAMMER = 9   # mehr gibt der ESP32 pro Kammer und Auftrag nicht aus (MAX_PRO_KAMMER im Sketch)
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
WOCHENTAGE_LANG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
DEMO_AKTUALISIEREN = 2   # s, so oft holt das Demo-Dashboard neue Daten


def geheimer_schluessel():
    """Schlüssel für die Login-Cookies; wird beim ersten Start erzeugt und nur für admin lesbar abgelegt."""
    if not SCHLUESSEL.exists():
        fd = os.open(SCHLUESSEL, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as datei:
            datei.write(secrets.token_bytes(32))
    return SCHLUESSEL.read_bytes()


app = Flask(__name__)
app.secret_key = geheimer_schluessel()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=30))


# ---------- Hilfen ----------

def db():
    if "db" not in g:
        g.db = datenbank.oeffnen()
    return g.db


@app.teardown_appcontext
def db_schliessen(_fehler):
    verbindung = g.pop("db", None)
    if verbindung is not None:
        verbindung.close()


def heute():
    return datetime.date.today()


def zahl(text, standard=0):
    try:
        return int(text)
    except (TypeError, ValueError):
        return standard


def uid_normal(text):
    """'3dab0901' oder '3D:AB:09:01' -> '3D AB 09 01'; None, wenn es keine 4-Byte-UID ist."""
    hexa = re.sub(r"[^0-9A-Fa-f]", "", text or "").upper()
    if len(hexa) != 8:
        return None
    return " ".join(hexa[i:i + 2] for i in range(0, 8, 2))


def admin_passwort():
    zeile = db().execute("SELECT wert FROM einstellungen WHERE schluessel = 'admin_passwort'").fetchone()
    return zeile["wert"] if zeile else None


def plan_von(nutzer_id):
    return {r["kammer"]: r["anzahl"] for r in db().execute(
        "SELECT kammer, anzahl FROM plan WHERE nutzer_id = ?", (nutzer_id,))}


def kammern():
    return db().execute("SELECT * FROM kammern ORDER BY nr").fetchall()


def medikamente(nutzer_id):
    """Was der Nutzer laut Plan bekommt, mit den Anpassungen für heute und morgen."""
    tage = (heute().isoformat(), (heute() + datetime.timedelta(days=1)).isoformat())
    zeilen = []
    for r in db().execute("""
            SELECT k.nr, k.medikament, k.anpassbar, k.max_pro_tag, p.anzahl AS plan,
                   ah.anzahl AS heute, am.anzahl AS morgen
            FROM plan p JOIN kammern k ON k.nr = p.kammer
            LEFT JOIN anpassung ah ON ah.nutzer_id = p.nutzer_id AND ah.kammer = p.kammer AND ah.datum = ?
            LEFT JOIN anpassung am ON am.nutzer_id = p.nutzer_id AND am.kammer = p.kammer AND am.datum = ?
            WHERE p.nutzer_id = ? ORDER BY k.nr""", (*tage, nutzer_id)):
        m = dict(r)
        # Selbst wählbar ist 0 bis max_pro_tag; liegt der Plan der Verwaltung höher, bis zum Plan
        m["grenze"] = max(m["max_pro_tag"], m["plan"])
        for tag in ("heute", "morgen"):
            m[tag] = min(m[tag], m["grenze"]) if m["anpassbar"] and m[tag] is not None else m["plan"]
        zeilen.append(m)
    return zeilen


def tagesstatus(nutzer_id, von, bis):
    """Status je Tag von..bis (inkl.): {'2026-10-29': {'erhalten': 4, 'status': 'ok'}}.
    status: ok, teil (weniger als bestellt), fehler (Gerät hat nicht geantwortet) oder verpasst
    (keine Ausgabe, seit der ersten Ausgabe überhaupt und vor heute). Tage ohne Angabe fehlen."""
    tage = {}
    for r in db().execute(
            """SELECT DATE(zeit) AS tag, SUM(bestellt) AS bestellt, SUM(COALESCE(erhalten, 0)) AS erhalten,
                      SUM(erhalten IS NULL) AS fehler
               FROM ausgaben WHERE nutzer_id = ? AND DATE(zeit) BETWEEN ? AND ? GROUP BY tag""",
            (nutzer_id, von.isoformat(), bis.isoformat())):
        status = "fehler" if r["fehler"] else ("teil" if r["erhalten"] < r["bestellt"] else "ok")
        tage[r["tag"]] = {"erhalten": r["erhalten"], "status": status}

    beginn = db().execute("SELECT MIN(DATE(zeit)) FROM ausgaben WHERE nutzer_id = ?", (nutzer_id,)).fetchone()[0]
    if beginn:
        d = max(von, datetime.date.fromisoformat(beginn))
        while d <= bis and d < heute():
            tage.setdefault(d.isoformat(), {"erhalten": 0, "status": "verpasst"})
            d += datetime.timedelta(days=1)
    return tage


def woche(nutzer_id):
    """Die letzten 7 Tage bis heute, für die Wochenleiste."""
    erster = heute() - datetime.timedelta(days=6)
    tage = tagesstatus(nutzer_id, erster, heute())
    return [{"datum": d, "wt": WOCHENTAGE[d.weekday()], "heute": d == heute(),
             "eintrag": tage.get(d.isoformat())}
            for d in (erster + datetime.timedelta(days=i) for i in range(7))]


def datum_lang(d):
    return f"{WOCHENTAGE_LANG[d.weekday()]}, {d.day}. {MONATE[d.month - 1]} {d.year}"


def gruss():
    stunde = datetime.datetime.now().hour
    return "Guten Morgen" if stunde < 11 else ("Guten Abend" if stunde >= 18 else "Guten Tag")


def plan_text(nutzer_id):
    teile = [f"{r['anzahl']}× {r['medikament']}" for r in db().execute(
        """SELECT p.anzahl, k.medikament FROM plan p JOIN kammern k ON k.nr = p.kammer
           WHERE p.nutzer_id = ? ORDER BY k.nr""", (nutzer_id,))]
    return ", ".join(teile) or "kein Plan"


# ---------- Schutz: Formular-Token und Logins ----------

@app.before_request
def formular_pruefen():
    """Jedes Formular trägt ein Token aus dem Cookie; fremde Seiten können so nichts abschicken."""
    if request.method == "POST":
        token = request.form.get("csrf", "")
        if not session.get("csrf") or not hmac.compare_digest(token, session["csrf"]):
            abort(400)


@app.context_processor
def vorlagen_daten():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return {"csrf": session["csrf"], "ist_admin": session.get("admin", False),
            "angemeldet": session.get("nutzer_id")}


def nutzer_noetig(ansicht):
    @wraps(ansicht)
    def pruefen(*args, **kwargs):
        nutzer_id = session.get("nutzer_id")
        g.nutzer = nutzer_id and db().execute("SELECT * FROM nutzer WHERE id = ?", (nutzer_id,)).fetchone()
        if not g.nutzer:
            session.pop("nutzer_id", None)
            return redirect(url_for("login"))
        return ansicht(*args, **kwargs)
    return pruefen


def admin_noetig(ansicht):
    @wraps(ansicht)
    def pruefen(*args, **kwargs):
        if not admin_passwort():
            return redirect(url_for("admin_einrichten"))
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return ansicht(*args, **kwargs)
    return pruefen


# ---------- Nutzerbereich ----------

@app.route("/")
def start():
    return redirect(url_for("mein" if session.get("nutzer_id") else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("benutzername", "").strip().lower()
        nutzer = db().execute("SELECT * FROM nutzer WHERE benutzername = ?", (name,)).fetchone()
        if nutzer and nutzer["passwort"] and check_password_hash(nutzer["passwort"],
                                                                 request.form.get("passwort", "")):
            session["nutzer_id"] = nutzer["id"]
            session.permanent = True
            return redirect(url_for("mein"))
        flash("Benutzername oder Passwort stimmt nicht.", "fehler")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("nutzer_id", None)
    return redirect(url_for("login"))


@app.route("/mein")
@nutzer_noetig
def mein():
    n = g.nutzer
    genommen_um = datenbank.heute_genommen_um(db(), n["id"])
    meds = medikamente(n["id"])
    meine_kammern = {m["nr"] for m in meds}
    knapp = [k for k in datenbank.vorrat_status(db()) if k["knapp"] and k["nr"] in meine_kammern]
    heute_ausgaben = db().execute(
        """SELECT a.zeit, a.bestellt, a.erhalten, k.medikament FROM ausgaben a
           JOIN kammern k ON k.nr = a.kammer
           WHERE a.nutzer_id = ? AND DATE(a.zeit) = ? ORDER BY a.zeit, a.kammer""",
        (n["id"], heute().isoformat())).fetchall()

    # Was oben in der großen Karte steht
    if genommen_um:
        if any(a["erhalten"] is None for a in heute_ausgaben):
            zustand = "fehler"
        elif any(a["erhalten"] < a["bestellt"] for a in heute_ausgaben):
            zustand = "teil"
        else:
            zustand = "erledigt"
    else:
        zustand = "offen" if any(m["heute"] > 0 for m in meds) else "nichts"

    morgen = heute() + datetime.timedelta(days=1)
    return render_template("mein.html", nutzer=n, genommen_um=genommen_um, meds=meds, knapp=knapp,
                           heute_ausgaben=heute_ausgaben, zustand=zustand, gruss=gruss(),
                           datum_heute=datum_lang(heute()), datum_morgen=f"{morgen:%d.%m.}",
                           wochentag_morgen=WOCHENTAGE_LANG[morgen.weekday()],
                           woche=woche(n["id"]), anpassbar=[m for m in meds if m["anpassbar"]])


@app.route("/mein/anpassen", methods=["POST"])
@nutzer_noetig
def anpassen():
    n = g.nutzer
    tag = request.form.get("tag", "heute")
    if tag == "heute" and datenbank.heute_genommen_um(db(), n["id"]):
        flash("Heute wurde schon ausgegeben. Die Änderung gilt deshalb erst ab morgen – bitte „Morgen“ wählen.",
              "fehler")
        return redirect(url_for("mein"))
    datum = heute() if tag == "heute" else heute() + datetime.timedelta(days=1)

    bestaetigt = []
    with db():
        for m in medikamente(n["id"]):
            if not m["anpassbar"] or f"k{m['nr']}" not in request.form:
                continue
            anzahl = max(0, min(zahl(request.form[f"k{m['nr']}"], m["plan"]), m["grenze"]))
            if anzahl == m["plan"]:
                db().execute("DELETE FROM anpassung WHERE nutzer_id = ? AND kammer = ? AND datum = ?",
                             (n["id"], m["nr"], datum.isoformat()))
            else:
                db().execute("""INSERT INTO anpassung (nutzer_id, kammer, datum, anzahl) VALUES (?, ?, ?, ?)
                                ON CONFLICT(nutzer_id, kammer, datum) DO UPDATE SET anzahl = excluded.anzahl""",
                             (n["id"], m["nr"], datum.isoformat(), anzahl))
            bestaetigt.append(f"{anzahl}× {m['medikament']}")
    wann = "Heute" if tag == "heute" else f"Morgen ({datum:%d.%m.})"
    flash(f"Gespeichert. {wann} bekommen Sie: {', '.join(bestaetigt)}.", "ok")
    return redirect(url_for("mein"))


@app.route("/mein/kalender")
@nutzer_noetig
def kalender():
    n = g.nutzer
    try:
        erster = datetime.datetime.strptime(request.args.get("monat", ""), "%Y-%m").date()
    except ValueError:
        erster = heute().replace(day=1)

    gitter = calendar.Calendar().monthdatescalendar(erster.year, erster.month)
    tage = tagesstatus(n["id"], gitter[0][0], gitter[-1][-1])
    wochen = [[{"datum": d, "im_monat": d.month == erster.month, "heute": d == heute(),
                "eintrag": tage.get(d.isoformat())} for d in w] for w in gitter]

    # Kurz-Bilanz des Monats: an wie vielen Tagen abgeholt
    im_monat = [e for tag, e in tage.items() if tag.startswith(f"{erster:%Y-%m}")]
    bilanz = {"abgeholt": sum(e["status"] != "verpasst" for e in im_monat), "tage": len(im_monat),
              "probleme": sum(e["status"] in ("teil", "fehler") for e in im_monat)}

    gewaehlt = request.args.get("tag")
    try:
        datetime.date.fromisoformat(gewaehlt or "")
    except ValueError:
        gewaehlt = None
    details = []
    if gewaehlt:
        details = db().execute(
            """SELECT a.zeit, a.bestellt, a.erhalten, k.medikament FROM ausgaben a
               JOIN kammern k ON k.nr = a.kammer
               WHERE a.nutzer_id = ? AND DATE(a.zeit) = ? ORDER BY a.zeit, a.kammer""",
            (n["id"], gewaehlt)).fetchall()

    vorher = (erster - datetime.timedelta(days=1)).replace(day=1)
    nachher = (erster + datetime.timedelta(days=32)).replace(day=1)
    return render_template("kalender.html", nutzer=n, wochen=wochen, wochentage=WOCHENTAGE,
                           titel=f"{MONATE[erster.month - 1]} {erster.year}", monat=f"{erster:%Y-%m}",
                           vorher=f"{vorher:%Y-%m}", nachher=f"{nachher:%Y-%m}",
                           gewaehlt=gewaehlt, details=details, bilanz=bilanz,
                           ist_aktuell=erster == heute().replace(day=1),
                           gewaehlt_lang=datum_lang(datetime.date.fromisoformat(gewaehlt)) if gewaehlt else "")


# ---------- Verwaltung ----------

@app.route("/admin/einrichten", methods=["GET", "POST"])
def admin_einrichten():
    """Nur beim allerersten Aufruf: Passwort für die Verwaltung festlegen."""
    if admin_passwort():
        return redirect(url_for("admin"))
    if request.method == "POST":
        pw = request.form.get("passwort", "")
        if len(pw) < 6:
            flash("Das Passwort braucht mindestens 6 Zeichen.", "fehler")
        elif pw != request.form.get("wiederholung"):
            flash("Die beiden Passwörter sind nicht gleich.", "fehler")
        else:
            with db():
                db().execute("INSERT INTO einstellungen VALUES ('admin_passwort', ?)",
                             (generate_password_hash(pw),))
            session["admin"] = True
            flash("Verwaltung eingerichtet.", "ok")
            return redirect(url_for("admin"))
    return render_template("admin_einrichten.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if not admin_passwort():
        return redirect(url_for("admin_einrichten"))
    if request.method == "POST":
        if check_password_hash(admin_passwort(), request.form.get("passwort", "")):
            session["admin"] = True
            session.permanent = True
            return redirect(url_for("admin"))
        flash("Passwort stimmt nicht.", "fehler")
    return render_template("admin_login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_noetig
def admin():
    nutzer = []
    for n in db().execute("SELECT * FROM nutzer ORDER BY name"):
        nutzer.append({**dict(n), "plan": plan_text(n["id"]), "hat_passwort": bool(n["passwort"]),
                       "genommen_um": datenbank.heute_genommen_um(db(), n["id"])})
    return render_template("admin.html", nutzer=nutzer, vorrat=datenbank.vorrat_status(db()))


@app.route("/admin/scan", methods=["POST"])
@admin_noetig
def scan_starten():
    return jsonify(id=datenbank.scan_anfragen(db()))


@app.route("/admin/scan/<int:scan_id>")
@admin_noetig
def scan_abfragen(scan_id):
    uid, abgelaufen = datenbank.scan_ergebnis(db(), scan_id)
    vergeben = datenbank.nutzer_zu_uid(db(), uid) if uid else None
    return jsonify(uid=uid, abgelaufen=abgelaufen,
                   vergeben=vergeben["name"] if vergeben else None,
                   vergeben_id=vergeben["id"] if vergeben else None)


def formular_lesen(nutzer_id=None):
    """Liest das Nutzer-Formular. Rückgabe: (werte, plan, passwort, fehler)."""
    f = request.form
    werte = {"name": f.get("name", "").strip(), "benutzername": f.get("benutzername", "").strip().lower(),
             "uid": f.get("uid", "").strip(), "wieder_um": f.get("wieder_um", "").strip(), "id": nutzer_id}
    plan = {}
    for k in kammern():
        plan[k["nr"]] = max(0, min(zahl(f.get(f"k{k['nr']}")), MAX_PRO_KAMMER))  # Verwaltung: frei bis zum Gerätelimit

    fehler = []
    if not werte["name"]:
        fehler.append("Bitte einen Namen eintragen.")
    if not re.fullmatch(r"[a-z0-9._-]{2,30}", werte["benutzername"]):
        fehler.append("Benutzername: 2–30 Zeichen, nur Kleinbuchstaben, Ziffern, Punkt, Minus, Unterstrich.")
    uid = uid_normal(werte["uid"])
    if not uid:
        fehler.append("Keine gültige Karte: bitte scannen oder die UID als 8 Hex-Zeichen eintragen.")
    else:
        werte["uid"] = uid
    if werte["wieder_um"] and not re.fullmatch(r"\d{2}:\d{2}", werte["wieder_um"]):
        fehler.append("„Wieder um“ bitte als Uhrzeit wie 18:00.")
    pw = f.get("passwort", "")
    if pw and len(pw) < 4:
        fehler.append("Das Passwort braucht mindestens 4 Zeichen.")
    return werte, plan, pw, fehler


def nutzer_formular(werte, plan, neu):
    return render_template("admin_nutzer.html", werte=werte, plan=plan, neu=neu, kammern=kammern(),
                           max_pro_kammer=MAX_PRO_KAMMER)


def nutzer_schreiben(werte, plan, pw, nutzer_id=None):
    """Speichert Nutzer und Plan. Rückgabe: id oder None, wenn UID/Benutzername schon vergeben sind."""
    try:
        with db():
            if nutzer_id is None:
                nutzer_id = db().execute(
                    "INSERT INTO nutzer (name, benutzername, uid, wieder_um, passwort) VALUES (?, ?, ?, ?, ?)",
                    (werte["name"], werte["benutzername"], werte["uid"], werte["wieder_um"] or None,
                     generate_password_hash(pw) if pw else "")).lastrowid
            else:
                db().execute("UPDATE nutzer SET name = ?, benutzername = ?, uid = ?, wieder_um = ? WHERE id = ?",
                             (werte["name"], werte["benutzername"], werte["uid"], werte["wieder_um"] or None,
                              nutzer_id))
                if pw:
                    db().execute("UPDATE nutzer SET passwort = ? WHERE id = ?",
                                 (generate_password_hash(pw), nutzer_id))
            db().execute("DELETE FROM plan WHERE nutzer_id = ?", (nutzer_id,))
            for kammer, anzahl in plan.items():
                if anzahl > 0:
                    db().execute("INSERT INTO plan (nutzer_id, kammer, anzahl) VALUES (?, ?, ?)",
                                 (nutzer_id, kammer, anzahl))
        return nutzer_id
    except sqlite3.IntegrityError:
        return None


@app.route("/admin/neu", methods=["GET", "POST"])
@admin_noetig
def nutzer_neu():
    if request.method == "GET":
        return nutzer_formular({"name": "", "benutzername": "", "uid": "", "wieder_um": "18:00", "id": None},
                               {}, neu=True)
    werte, plan, pw, fehler = formular_lesen()
    if not fehler and nutzer_schreiben(werte, plan, pw) is None:
        fehler.append("Diese Karte oder dieser Benutzername ist schon vergeben.")
    if fehler:
        for f in fehler:
            flash(f, "fehler")
        return nutzer_formular(werte, plan, neu=True)
    flash(f"{werte['name']} ist angelegt." + ("" if pw else " Ohne Passwort ist noch kein Login möglich."), "ok")
    return redirect(url_for("admin"))


@app.route("/admin/nutzer/<int:nutzer_id>", methods=["GET", "POST"])
@admin_noetig
def nutzer_bearbeiten(nutzer_id):
    n = db().execute("SELECT * FROM nutzer WHERE id = ?", (nutzer_id,)).fetchone()
    if not n:
        abort(404)
    if request.method == "GET":
        werte = {k: n[k] or "" for k in ("name", "benutzername", "uid", "wieder_um")}
        werte["id"] = nutzer_id
        return nutzer_formular(werte, plan_von(nutzer_id), neu=False)
    werte, plan, pw, fehler = formular_lesen(nutzer_id)
    if not fehler and nutzer_schreiben(werte, plan, pw, nutzer_id) is None:
        fehler.append("Diese Karte oder dieser Benutzername gehört schon jemand anderem.")
    if fehler:
        for f in fehler:
            flash(f, "fehler")
        return nutzer_formular(werte, plan, neu=False)
    flash(f"Änderungen für {werte['name']} gespeichert.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/nutzer/<int:nutzer_id>/loeschen", methods=["POST"])
@admin_noetig
def nutzer_loeschen(nutzer_id):
    with db():
        for tabelle in ("anpassung", "plan", "ausgaben"):
            db().execute(f"DELETE FROM {tabelle} WHERE nutzer_id = ?", (nutzer_id,))
        db().execute("DELETE FROM nutzer WHERE id = ?", (nutzer_id,))
    flash("Nutzer gelöscht.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/kammern", methods=["GET", "POST"])
@admin_noetig
def admin_kammern():
    if request.method == "POST":
        f = request.form
        with db():
            for k in kammern():
                nr = k["nr"]
                name = f.get(f"medikament{nr}", "").strip() or k["medikament"]
                vorrat = max(0, zahl(f.get(f"vorrat{nr}"), k["vorrat"] or 0)) + max(0, zahl(f.get(f"nachfuellen{nr}")))
                db().execute("""UPDATE kammern SET medikament = ?, anpassbar = ?, max_pro_tag = ?,
                                vorrat = ?, warnen_ab = ? WHERE nr = ?""",
                             (name, 1 if f.get(f"anpassbar{nr}") else 0,
                              max(1, min(zahl(f.get(f"max{nr}"), 1), MAX_PRO_KAMMER)),
                              vorrat, max(0, zahl(f.get(f"warnen{nr}"), 10)), nr))
        flash("Kammern gespeichert.", "ok")
        return redirect(url_for("admin_kammern"))
    return render_template("admin_kammern.html", vorrat=datenbank.vorrat_status(db()), max_pro_kammer=MAX_PRO_KAMMER)


@app.route("/admin/reset", methods=["POST"])
@admin_noetig
def admin_reset():
    anzahl = datenbank.heute_zuruecksetzen(db())
    flash(f"Heutige Ausgaben gelöscht ({anzahl} Einträge). Alle dürfen heute wieder.", "ok")
    return redirect(url_for("demo" if request.form.get("weiter") == "demo" else "admin"))


# ---------- Demo-Dashboard (für Präsentation, aktualisiert sich selbst) ----------

@app.route("/admin/demo")
@admin_noetig
def demo():
    return render_template("demo.html", aktualisieren=DEMO_AKTUALISIEREN)


@app.route("/admin/demo/daten")
@admin_noetig
def demo_daten():
    """Alles, was das Dashboard zeigt, als JSON. Liest nur, ändert nichts."""
    d0 = heute()
    vor7 = d0 - datetime.timedelta(days=7)

    nutzer, abgeholt7, tage7 = [], 0, 0
    for n in db().execute("SELECT * FROM nutzer ORDER BY name"):
        meds = medikamente(n["id"])
        if not meds:
            continue   # ohne Plan nichts zu zeigen
        um = datenbank.heute_genommen_um(db(), n["id"])
        tage = tagesstatus(n["id"], vor7, d0)
        heute_e = tage.get(d0.isoformat())
        if um:
            status = heute_e["status"] if heute_e else "ok"
        else:
            status = "offen" if any(m["heute"] > 0 for m in meds) else "nichts"
        letzte7 = [e for t, e in tage.items() if t < d0.isoformat()]
        abgeholt7 += sum(e["status"] != "verpasst" for e in letzte7)
        tage7 += len(letzte7)
        nutzer.append({
            "name": n["name"], "status": status, "um": um,
            "dosis": [{"medikament": m["medikament"], "anzahl": m["heute"], "angepasst": m["heute"] != m["plan"]}
                      for m in meds if m["heute"] > 0],
            "woche": [{"wt": t["wt"], "nr": t["datum"].day, "heute": t["heute"],
                       "status": t["eintrag"]["status"] if t["eintrag"] else None} for t in woche(n["id"])],
        })

    heute_summe = db().execute(
        """SELECT COALESCE(SUM(erhalten), 0) AS tabletten,
                  COUNT(DISTINCT CASE WHEN erhalten IS NULL THEN nutzer_id || ' ' || zeit END) AS fehler
           FROM ausgaben WHERE DATE(zeit) = ?""", (d0.isoformat(),)).fetchone()

    pro_tag = {r["tag"]: r["tabletten"] for r in db().execute(
        """SELECT DATE(zeit) AS tag, COALESCE(SUM(erhalten), 0) AS tabletten FROM ausgaben
           WHERE DATE(zeit) >= ? GROUP BY tag""", ((d0 - datetime.timedelta(days=13)).isoformat(),))}
    verlauf = []
    for i in range(13, -1, -1):
        d = d0 - datetime.timedelta(days=i)
        verlauf.append({"wt": WOCHENTAGE[d.weekday()], "kurz": f"{d:%d.%m.}", "heute": i == 0,
                        "tabletten": pro_tag.get(d.isoformat(), 0)})

    # Eine Ausgabe = alle Zeilen eines Nutzers mit derselben Zeit
    ereignisse = [dict(r) for r in db().execute(
        """SELECT MAX(a.id) AS id, n.name, a.zeit, SUM(a.bestellt) AS bestellt,
                  SUM(COALESCE(a.erhalten, 0)) AS erhalten, SUM(a.erhalten IS NULL) AS fehler,
                  GROUP_CONCAT(COALESCE(a.erhalten, a.bestellt) || '× ' || k.medikament, ', ') AS teile
           FROM ausgaben a JOIN nutzer n ON n.id = a.nutzer_id JOIN kammern k ON k.nr = a.kammer
           GROUP BY a.nutzer_id, a.zeit ORDER BY a.zeit DESC, id DESC LIMIT 7""")]
    for e in ereignisse:
        e["status"] = "fehler" if e["fehler"] else ("teil" if e["erhalten"] < e["bestellt"] else "ok")
        e["uhr"] = e["zeit"][11:16]
        e["heute"] = e["zeit"][:10] == d0.isoformat()
        e["tag"] = "heute" if e["heute"] else f"{e['zeit'][8:10]}.{e['zeit'][5:7]}."

    return jsonify(
        uhrzeit=f"{datetime.datetime.now():%H:%M:%S}", datum=datum_lang(d0),
        kennzahlen={"versorgt": sum(n["um"] is not None for n in nutzer), "nutzer": len(nutzer),
                    "tabletten": heute_summe["tabletten"], "fehler": heute_summe["fehler"],
                    "abgeholt7": round(100 * abgeholt7 / tage7) if tage7 else None},
        nutzer=nutzer, vorrat=datenbank.vorrat_status(db()), verlauf=verlauf, ereignisse=ereignisse,
        scan_wartet=datenbank.scan_offen(db()) is not None,
    )


@app.template_filter("datum")
def datum_filter(wert):
    """'2026-10-28 08:01:12' -> '08:01'; date -> '28.10.2026'."""
    if isinstance(wert, datetime.date):
        return f"{wert:%d.%m.%Y}"
    return wert[11:16] if wert and len(wert) >= 16 else wert


def main():
    parser = argparse.ArgumentParser(description="PillCard-Website")
    parser.add_argument("--debug", action="store_true", help="Entwicklungsserver mit Neuladen")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    datenbank.verbinden().close()   # Tabellen und neue Spalten anlegen, falls noch nicht da
    if args.debug:
        app.run(host="0.0.0.0", port=args.port, debug=True)
    else:
        from waitress import serve
        print(f"PillCard-Website läuft auf Port {args.port}")
        serve(app, host="0.0.0.0", port=args.port, threads=4)


if __name__ == "__main__":
    main()
