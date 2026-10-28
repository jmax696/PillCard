// PillCard LCD-Pintest für die Arduino IDE (ESP32).
// Prüft jede Leitung zwischen ESP32 und Display einzeln und schickt einen Testtext.
//
// Arduino IDE: Board "ESP32 Dev Module", Serieller Monitor auf 115200 Baud.
// Einen Buchstaben oder eine Zahl eintippen und Enter drücken.
//
// Messen: Multimeter auf Gleichspannung, schwarz an GND, rot an den Display-Pin.
// Oder LED-Prüfspitze: kurzes Bein an GND, langes Bein über 100 Ohm an den Display-Pin.
#include <LiquidCrystal.h>

// Gleiche Belegung wie im PillCard-Projekt (include/Hardware.h)
const uint8_t PIN_RS = 22;
const uint8_t PIN_E  = 21;
const uint8_t PIN_D4 = 32;
const uint8_t PIN_D5 = 33;
const uint8_t PIN_D6 = 14;
const uint8_t PIN_D7 = 15;
const uint8_t PIN_LED_GRUEN = 16;
const uint8_t PIN_LED_ROT   = 17;

const uint8_t LEITUNGEN[6]    = {PIN_RS, PIN_E, PIN_D4, PIN_D5, PIN_D6, PIN_D7};
const char*   NAMEN[6]        = {"RS", "E", "D4", "D5", "D6", "D7"};
const uint8_t DISPLAY_PIN[6]  = {4, 6, 11, 12, 13, 14};

LiquidCrystal lcd(PIN_RS, PIN_E, PIN_D4, PIN_D5, PIN_D6, PIN_D7);

int dauerhaft = -2;  // -2 = alles aus, -1 = blinken, 0..5 = nur diese Leitung an

/** Zeigt alle Befehle im Seriellen Monitor. */
void menueZeigen() {
  Serial.println();
  Serial.println("=== PillCard LCD-Pintest ===");
  Serial.println("1..6  nur eine Leitung dauerhaft auf 3.3V:");
  for (uint8_t i = 0; i < 6; i++) {
    Serial.printf("      %u = %-2s  (ESP32 IO%u -> Display-Pin %u)\n",
                  i + 1, NAMEN[i], LEITUNGEN[i], DISPLAY_PIN[i]);
  }
  Serial.println("0     alle Leitungen aus (0V)");
  Serial.println("b     blinken: RS 1x, E 2x, D4 3x, D5 4x, D6 5x, D7 6x, dann Pause");
  Serial.println("t     Testtext aufs Display schicken");
  Serial.println("g / r gruene / rote Status-LED 3 s an");
  Serial.println("?     dieses Menue");
}

/** Schaltet alle LCD-Leitungen als Ausgang auf LOW. */
void alleAus() {
  for (uint8_t i = 0; i < 6; i++) {
    pinMode(LEITUNGEN[i], OUTPUT);
    digitalWrite(LEITUNGEN[i], LOW);
  }
}

/** Richtet das Display ein und schreibt zwei Zeilen Text. */
void testtext() {
  lcd.begin(16, 2);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("PillCard");
  lcd.setCursor(0, 1);
  lcd.print("LCD laeuft :)");
  Serial.println("Testtext gesendet. Immer noch Kaestchen oben? Dann mit 1..6 die Leitungen messen.");
  dauerhaft = -3;  // Display behalten, nichts mehr an den Leitungen ändern
}

/** Lässt eine Status-LED 3 Sekunden leuchten. */
void ledTest(uint8_t pin, const char* name) {
  Serial.printf("LED %s an (IO%u) ...\n", name, pin);
  digitalWrite(pin, HIGH);
  delay(3000);
  digitalWrite(pin, LOW);
  Serial.println("aus.");
}

/** Verarbeitet einen Befehl aus dem Seriellen Monitor. */
void befehl(char c) {
  if (c >= '1' && c <= '6') {
    alleAus();
    dauerhaft = c - '1';
    digitalWrite(LEITUNGEN[dauerhaft], HIGH);
    Serial.printf("Nur %s ist an. Miss jetzt Display-Pin %u gegen GND: ca. 3.3V erwartet.\n",
                  NAMEN[dauerhaft], DISPLAY_PIN[dauerhaft]);
    Serial.println("Alle anderen Datenpins (4, 6, 11-14) sollten 0V haben.");
  } else if (c == '0') {
    alleAus();
    dauerhaft = -2;
    Serial.println("Alle Leitungen aus.");
  } else if (c == 'b') {
    alleAus();
    dauerhaft = -1;
    Serial.println("Blinken laeuft. LED-Pruefspitze an die Display-Pins halten und zaehlen.");
  } else if (c == 't') {
    testtext();
  } else if (c == 'g') {
    ledTest(PIN_LED_GRUEN, "gruen");
  } else if (c == 'r') {
    ledTest(PIN_LED_ROT, "rot");
  } else if (c == '?') {
    menueZeigen();
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  pinMode(PIN_LED_GRUEN, OUTPUT);
  pinMode(PIN_LED_ROT, OUTPUT);
  digitalWrite(PIN_LED_GRUEN, LOW);
  digitalWrite(PIN_LED_ROT, LOW);
  alleAus();
  menueZeigen();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c != '\n' && c != '\r' && c != ' ') befehl(c);
  }

  // Blinkmuster: bis zu 6 Blinker à 500 ms, dann 1.5 s Pause
  if (dauerhaft == -1) {
    unsigned long t = millis() % 4500UL;
    for (uint8_t i = 0; i < 6; i++) {
      bool an = t < (i + 1) * 500UL && (t % 500UL) < 250UL;
      digitalWrite(LEITUNGEN[i], an ? HIGH : LOW);
    }
  }
  delay(5);
}
