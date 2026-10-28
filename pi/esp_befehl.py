"""Schickt Befehle an den ESP32 und zeigt seine Antworten.

Aufruf: venv/bin/python esp_befehl.py "probe 1" [Sekunden]
Mehrere Befehle mit ; trennen, z. B. "schwelle 300; probe 1".
"""
import glob
import sys
import time

import serial

PORT = (glob.glob("/dev/serial/by-id/*CP2102*") or ["/dev/ttyUSB0"])[0]
befehle = [b.strip() for b in sys.argv[1].split(";")] if len(sys.argv) > 1 else ["?"]
dauer = float(sys.argv[2]) if len(sys.argv) > 2 else 5

esp = serial.Serial(PORT, 115200, timeout=0.2)

# Beim Öffnen startet der ESP32 neu: auf BEREIT warten
ende = time.time() + 3
while time.time() < ende:
    zeile = esp.readline().decode(errors="replace").rstrip()
    if zeile:
        print("  " + zeile)
    if zeile == "BEREIT":
        break
else:
    print("(kein Neustart beim Verbinden, ESP32 lief schon)")

for befehl in befehle:
    print(">> " + befehl)
    esp.write((befehl + "\n").encode())
    ende = time.time() + dauer
    while time.time() < ende:
        zeile = esp.readline().decode(errors="replace").rstrip()
        if zeile:
            print("  " + zeile)
esp.close()
