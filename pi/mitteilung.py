"""Push-Mitteilungen an Angehörige über ntfy (kostenlose App "ntfy" im App Store / Play Store).

Das Thema steht in ntfy_thema.txt neben dieser Datei (nur auf dem Pi, nicht im Repo). Wer das
Thema kennt, kann mitlesen, deshalb ein langes, zufälliges Wort nehmen. In der App unter
"Thema abonnieren" genau dieses Wort eintragen. Ohne die Datei wird nichts verschickt.

Test (im Ordner ~/pillcard):
    venv/bin/python mitteilung.py "Testmitteilung"
"""
import json
import sys
import threading
import urllib.request
from pathlib import Path

SERVER = "https://ntfy.sh"
THEMA_DATEI = Path(__file__).resolve().parent / "ntfy_thema.txt"


def thema():
    try:
        return THEMA_DATEI.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None


def senden(text, titel="PillCard", tags=("pill",)):
    """Schickt die Mitteilung und wartet auf ntfy. True, wenn sie angenommen wurde."""
    ziel = thema()
    if not ziel:
        return False
    # Als JSON, weil ntfy Umlaute in Kopfzeilen nicht sicher annimmt
    daten = json.dumps({"topic": ziel, "title": titel, "message": text, "tags": list(tags)}).encode()
    anfrage = urllib.request.Request(SERVER, data=daten, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            return antwort.status == 200
    except OSError as fehler:
        print(f"  !! Mitteilung nicht verschickt: {fehler}", flush=True)
        return False


def im_hintergrund(text, **optionen):
    """Wie senden(), aber ohne auf das Netz zu warten, damit PillCard sofort weiterläuft."""
    threading.Thread(target=senden, args=(text,), kwargs=optionen, daemon=True).start()


if __name__ == "__main__":
    if not thema():
        sys.exit(f"Kein Thema: {THEMA_DATEI} anlegen und das Thema hineinschreiben.")
    print("verschickt" if senden(" ".join(sys.argv[1:]) or "Testmitteilung von PillCard") else "fehlgeschlagen")
