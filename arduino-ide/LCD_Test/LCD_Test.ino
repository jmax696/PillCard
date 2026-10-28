// PillCard Display-Test für die Arduino IDE (ESP32 + LCD 16x2 ohne I2C-Modul).
// Zeile 1 zeigt "PillCard", Zeile 2 zählt die Sekunden hoch.
//
// Arduino IDE: Board "ESP32 Dev Module", Serieller Monitor auf 115200 Baud.
//
// Verkabelung Display -> ESP32:
//   1 VSS -> GND        2 VDD -> 5V          3 V0 -> frei (oder 1 kOhm an GND)
//   4 RS  -> IO22       5 R/W -> GND         6 E  -> IO21
//   7-10 DB0-DB3 frei
//  11 DB4 -> IO32      12 DB5 -> IO33       13 DB6 -> IO14      14 DB7 -> IO15
//  15 LED+ -> 5V über 100 Ohm               16 LED- -> GND
//  GND des ESP32 muss mit GND des Displays verbunden sein!
#include <LiquidCrystal.h>

const uint8_t PIN_RS = 22;
const uint8_t PIN_E  = 21;
const uint8_t PIN_D4 = 32;
const uint8_t PIN_D5 = 33;
const uint8_t PIN_D6 = 14;
const uint8_t PIN_D7 = 15;

LiquidCrystal lcd(PIN_RS, PIN_E, PIN_D4, PIN_D5, PIN_D6, PIN_D7);

unsigned long letzteNeuinit = 0;

/** Richtet das Display neu ein und schreibt die erste Zeile. */
void displayEinrichten() {
  lcd.begin(16, 2);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("PillCard");
}

void setup() {
  Serial.begin(115200);
  delay(100);  // Datenblatt: nach dem Einschalten mind. 40 ms warten
  displayEinrichten();
  Serial.println("Display-Test laeuft. Oben 'PillCard', unten zaehlen die Sekunden.");
  Serial.println("Nur weisse Kaestchen oben? Dann kommen die Daten nicht an (Kabel RS/E/D4-D7, R/W, GND).");
}

void loop() {
  // Alle 5 s neu einrichten, falls das Display erst nach dem ESP32 Strom bekommen hat
  if (millis() - letzteNeuinit > 5000) {
    letzteNeuinit = millis();
    displayEinrichten();
  }

  unsigned long sekunden = millis() / 1000;
  lcd.setCursor(0, 1);
  lcd.print("Sekunden: ");
  lcd.print(sekunden);
  lcd.print("   ");  // Reste von längeren Zahlen überschreiben

  Serial.printf("Sekunden: %lu\n", sekunden);
  delay(1000);
}
