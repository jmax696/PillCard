// PillCard Kammer-1-Test für die Arduino IDE (ESP32, ohne Zusatzbibliothek).
// Der Servo fährt alle 3 Sekunden auf Ausgabeposition und zurück.
// Im Seriellen Monitor (115200 Baud) eine Zahl 0-180 eintippen + Enter: Servo fährt auf diesen Winkel
// und bleibt dort. So findet ihr den richtigen Winkel für den Schieber. "a" + Enter = wieder automatisch.
//
// Verkabelung Servo Kammer 1 (SG90):
//   orange (Signal) -> IO25
//   rot (+)         -> 5V-Schiene vom Netzteilmodul
//   braun (-)       -> GND-Schiene
//   GND des ESP32 muss an dieselbe GND-Schiene!

const uint8_t PIN_SERVO = 25;
const int WINKEL_RUHE    = 180;  // neue 3D-Version: Servo startet von der anderen Seite
const int WINKEL_AUSGABE = 90;

// 50 Hz Servosignal mit 16 Bit Auflösung: eine Periode = 20000 µs = 65535 Schritte
const uint32_t FREQ = 50;
const uint8_t  BITS = 16;

bool automatisch = true;
unsigned long letzteBewegung = 0;
String eingabe = "";

/** Stellt den Servo auf einen Winkel zwischen 0 und 180 Grad. */
void servoWinkel(int grad) {
  grad = constrain(grad, 0, 180);
  uint32_t mikros = map(grad, 0, 180, 500, 2400);  // SG90: ca. 0.5 ms bis 2.4 ms
  uint32_t duty = mikros * 65535UL / 20000UL;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_SERVO, duty);
#else
  ledcWrite(0, duty);
#endif
  Serial.printf("Servo Kammer 1 -> %d Grad\n", grad);
}

void setup() {
  Serial.begin(115200);
  delay(300);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(PIN_SERVO, FREQ, BITS);
#else
  ledcSetup(0, FREQ, BITS);
  ledcAttachPin(PIN_SERVO, 0);
#endif
  servoWinkel(WINKEL_RUHE);
  Serial.println("=== Kammer-1-Test ===");
  Serial.println("Automatisch: alle 3 s Ausgabe und zurueck.");
  Serial.println("Zahl 0-180 + Enter = fester Winkel, a + Enter = wieder automatisch.");
}

void loop() {
  // Eingabe aus dem Seriellen Monitor zeilenweise lesen
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      eingabe.trim();
      if (eingabe == "a") {
        automatisch = true;
        Serial.println("Automatisch an.");
      } else if (eingabe.length() > 0 && isDigit(eingabe[0])) {
        automatisch = false;
        servoWinkel(eingabe.toInt());
      }
      eingabe = "";
    } else {
      eingabe += c;
    }
  }

  if (automatisch && millis() - letzteBewegung > 3000) {
    letzteBewegung = millis();
    servoWinkel(WINKEL_AUSGABE);
    delay(700);
    servoWinkel(WINKEL_RUHE);
  }
}
