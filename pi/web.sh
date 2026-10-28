#!/bin/sh
# Startet die Website (web.py, Port 8080) und startet sie nach einem Absturz neu.
# Wird beim Hochfahren per crontab aufgerufen:  @reboot /home/admin/pillcard/web.sh
# Ausgaben stehen in web.log.
cd "$(dirname "$0")" || exit 1
while true; do
  echo "=== Start $(date '+%Y-%m-%d %H:%M:%S')" >> web.log
  venv/bin/python -u web.py >> web.log 2>&1
  sleep 5
done
