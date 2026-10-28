// Wählt die passende RC522-Bibliothek: I2C-Leser (Keyestudio, 4 Pins) oder blaues SPI-Board.
// Umgeschaltet wird in platformio.ini über das Build-Flag PILLCARD_RFID_I2C.
#pragma once
#include <Arduino.h>

#ifdef PILLCARD_RFID_I2C
  #include <Wire.h>
  #include <MFRC522_I2C.h>
  typedef MFRC522_I2C RfidLeser;
#else
  #include <SPI.h>
  #include <MFRC522.h>
  typedef MFRC522 RfidLeser;
#endif
