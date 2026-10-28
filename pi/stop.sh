#!/bin/sh
# Hält PillCard an, z. B. um mit esp_befehl.py zu testen oder den ESP32 neu zu bespielen.
# Wieder starten: ./start.sh &   (oder den Pi neu starten)
pkill -f "^/bin/sh (.*pillcard/|\./)start\.sh"  # erst die Neustart-Schleife, sonst startet sie sofort wieder
pkill -f "venv/bin/python -u pillcard\.py"
echo "PillCard angehalten."
