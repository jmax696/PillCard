#!/bin/sh
# Startet pillcard.py und startet es nach einem Absturz neu (z. B. wenn der ESP32 noch nicht steckt).
# Wird beim Hochfahren per crontab aufgerufen:  @reboot /home/admin/pillcard/start.sh
# Ausgaben stehen in pillcard.log.
cd "$(dirname "$0")" || exit 1
while true; do
  echo "=== Start $(date '+%Y-%m-%d %H:%M:%S')" >> pillcard.log
  venv/bin/python -u pillcard.py >> pillcard.log 2>&1
  sleep 5
done
