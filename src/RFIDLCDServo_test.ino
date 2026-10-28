// PillCard Kammer-1-Test mit Karte für die Arduino IDE (ESP32).
// Karte an den RFID-Leser halten -> Display meldet den Start, grüne LED an, Servo Kammer 1 gibt aus.
//
// Arduino IDE: Board "ESP32 Dev Module", Serieller Monitor auf 115200 Baud.
// Bibliothek nötig: "MFRC522" von GithubCommunity (Bibliotheksverwalter, NICHT "MFRC522v2").
// LiquidCrystal ist in der Arduino IDE schon dabei.
//
// Im Seriellen Monitor: Zahl 0-180 + Enter = Servo fährt auf diesen Winkel (zum Einstellen des Schiebers).
//
// Verkabelung (wie docs/Schaltplan_ESP32.svg):
//   RFID:   SDA->IO5  SCK->IO18  MOSI->IO23  MISO->IO19  RST->IO4  3.3V->3V3  GND->GND
//   LCD:    RS->IO22  E->IO21  D4->IO32  D5->IO33  D6->IO14  D7->IO15  R/W->GND
//   Servo:  orange->IO25  rot->5V-Schiene  braun->GND-Schiene
//   LEDs:   grün->IO16, rot->IO17 (je über 100 Ohm)
//   GND des ESP32 muss an die GND-Schiene!
#include <SPI.h>
#include <MFRC522.h>
#include <LiquidCrystal.h>

// RFID
const uint8_t PIN_RFID_SS  = 5;
const uint8_t PIN_RFID_RST = 4;

// Display
const uint8_t PIN_LCD_RS = 22, PIN_LCD_E = 21;
const uint8_t PIN_LCD_D4 = 32, PIN_LCD_D5 = 33, PIN_LCD_D6 = 14, PIN_LCD_D7 = 15;

// Servo und LEDs
const uint8_t PIN_SERVO     = 25;
const uint8_t PIN_LED_GRUEN = 16;
const uint8_t PIN_LED_ROT   = 17;
const int WINKEL_RUHE    = 0;
const int WINKEL_AUSGABE = 90;

MFRC522 rfid(PIN_RFID_SS, PIN_RFID_RST);
LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_E, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);
String eingabe = "";

/** Schreibt zwei Zeilen aufs Display (je max. 16 Zeichen, keine Umlaute). */
void anzeigen(const char* zeile1, const char* zeile2) {
  lcd.begin(16, 2);  // jedes Mal neu einrichten, falls das Display später Strom bekommen hat
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(zeile1);
  lcd.setCursor(0, 1);
  lcd.print(zeile2);
}

/** Stellt den Servo auf einen Winkel zwischen 0 und 180 Grad. */
void servoWinkel(int grad) {
  grad = constrain(grad, 0, 180);
  uint32_t mikros = map(grad, 0, 180, 500, 2400);  // SG90: ca. 0.5 ms bis 2.4 ms
  uint32_t duty = mikros * 65535UL / 20000UL;      // 50 Hz, 16 Bit: 20000 µs = 65535 Schritte
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_SERVO, duty);
#else
  ledcWrite(0, duty);
#endif
  Serial.printf("Servo Kammer 1 -> %d Grad\n", grad);
}

/** Wartebildschirm: Display fordert zum Hinhalten der Karte auf. */
void bereit() {
  digitalWrite(PIN_LED_GRUEN, LOW);
  digitalWrite(PIN_LED_ROT, LOW);
  anzeigen("PillCard", "Karte hinhalten");
  Serial.println("Bereit, warte auf Karte ...");
}

/** Ablauf nach dem Hinhalten: Meldung, grüne LED, Servo einmal ausfahren, Hinweis zum Entnehmen. */
void ausgabe() {
  Serial.print("Karte erkannt, UID:");
  for (uint8_t i = 0; i < rfid.uid.size; i++) Serial.printf(" %02X", rfid.uid.uidByte[i]);
  Serial.println();

  anzeigen("Medikamenten-", "ausgabe startet");
  digitalWrite(PIN_LED_GRUEN, HIGH);
  delay(1500);

  anzeigen("Kammer 1", "gibt aus ...");
  servoWinkel(WINKEL_AUSGABE);
  delay(700);
  servoWinkel(WINKEL_RUHE);
  delay(700);

  anzeigen("Fertig!", "Bitte entnehmen");
  delay(3000);
  bereit();
}

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(PIN_LED_GRUEN, OUTPUT);
  pinMode(PIN_LED_ROT, OUTPUT);

#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(PIN_SERVO, 50, 16);
#else
  ledcSetup(0, 50, 16);
  ledcAttachPin(PIN_SERVO, 0);
#endif
  servoWinkel(WINKEL_RUHE);

  SPI.begin();  // ESP32-Standardpins: SCK 18, MISO 19, MOSI 23
  rfid.PCD_Init();
  Serial.println("=== PillCard Kammer 1 mit Karte ===");
  Serial.print("RFID-Leser: ");
  rfid.PCD_DumpVersionToSerial();  // bei uns 0x18, das ist ok

  bereit();
}

void loop() {
  // Zahl 0-180 + Enter stellt den Servo von Hand
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      eingabe.trim();
      if (eingabe.length() > 0 && isDigit(eingabe[0])) servoWinkel(eingabe.toInt());
      eingabe = "";
    } else {
      eingabe += c;
    }
  }

  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  ausgabe();

  // Karte abmelden: erst nach erneutem Hinhalten gibt es die nächste Ausgabe
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}