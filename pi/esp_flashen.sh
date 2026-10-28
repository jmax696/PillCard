#!/bin/sh
# Spielt die Dateien aus ~/pillcard/firmware auf den ESP32 am USB.
cd "$(dirname "$0")/firmware" || exit 1
PORT=$(ls /dev/serial/by-id/*CP2102* 2>/dev/null | head -1)
[ -z "$PORT" ] && PORT=/dev/ttyUSB0
exec ../venv/bin/python -m esptool --chip esp32 --port "$PORT" --baud 460800 \
  write-flash 0x1000 bootloader.bin 0x8000 partitions.bin 0xe000 boot_app0.bin 0x10000 firmware.bin
