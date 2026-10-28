// Pinbelegung und Hardware-Einstellungen für alle PillCard-Programme.
// Wenn ihr etwas umsteckt, nur hier ändern. Der passende Block wird automatisch je nach Board gewählt.
#pragma once
#include <Arduino.h>

#if defined(ARDUINO_ARCH_ESP32)
// ===== ESP32 (Keyestudio, aktuell benutzt) =====
const uint32_t SERIELL_BAUD = 115200;

// RFID-RC522 über SPI. SCK 18, MOSI 23, MISO 19 sind die Standardpins des ESP32.
const uint8_t PIN_RFID_SS  = 5;   // am Board "SDA" beschriftet
const uint8_t PIN_RFID_RST = 4;

const uint8_t PIN_SERVO[3]         = {25, 26, 27};
const uint8_t PIN_LICHTSCHRANKE[3] = {34, 35, 36};  // reine Eingangspins, 36 heisst auf dem Board oft "VP"
const uint8_t PIN_BECHER           = 13;
const uint8_t PIN_LED_GRUEN        = 16;
const uint8_t PIN_LED_ROT          = 17;

// LCD 16x2 ohne I2C-Modul, 4-Bit-Modus. R/W (Pin 5) fest an GND, damit das Display nie 5V zurückschickt.
#define LCD_PARALLEL
const uint8_t PIN_LCD_RS = 22;
const uint8_t PIN_LCD_E  = 21;
const uint8_t PIN_LCD_D4 = 32;
const uint8_t PIN_LCD_D5 = 33;
const uint8_t PIN_LCD_D6 = 14;
const uint8_t PIN_LCD_D7 = 15;

#else
// ===== Arduino Uno (Ausweichvariante) =====
const uint32_t SERIELL_BAUD = 9600;

// RFID-RC522 über SPI. MOSI 11, MISO 12, SCK 13 sind beim Uno fest.
const uint8_t PIN_RFID_SS  = 10;
const uint8_t PIN_RFID_RST = 9;

const uint8_t PIN_SERVO[3]         = {3, 5, 6};
const uint8_t PIN_LICHTSCHRANKE[3] = {2, 4, 7};
const uint8_t PIN_BECHER           = 8;
const uint8_t PIN_LED_GRUEN        = A0;
const uint8_t PIN_LED_ROT          = A1;
// LCD nur mit I2C-Modul möglich (SDA A4, SCL A5), für 6 Datenpins reicht der Uno nicht
#endif

// ===== Für beide Boards gleich =====

const uint8_t SERVO_RUHE    = 0;   // Grad, Schieber zurück
const uint8_t SERVO_AUSGABE = 90;  // Grad, Schieber schiebt eine Tablette raus

// Pegel, wenn eine Tablette den Strahl unterbricht. Mit dem Bauteiltest prüfen,
// je nach Modul ist es HIGH oder LOW.
const uint8_t LICHTSCHRANKE_UNTERBROCHEN = HIGH;

// LCD 16x2. LCD_ADRESSE gilt nur mit I2C-Modul (meist 0x27 oder 0x3F, der I2C-Scanner im Bauteiltest zeigt sie).
const uint8_t LCD_ADRESSE = 0x27;
const uint8_t LCD_SPALTEN = 16;
const uint8_t LCD_ZEILEN  = 2;

// Nur für einen I2C-RFID-Leser mit 4 Pins (PILLCARD_RFID_I2C in platformio.ini)
const uint8_t RFID_I2C_ADRESSE = 0x28;

#ifdef PILLCARD_RFID_I2C
  #define RFID_ARGS RFID_I2C_ADRESSE, PIN_RFID_RST
#else
  #define RFID_ARGS PIN_RFID_SS, PIN_RFID_RST
#endif
