// PillCard Kammer-1-Test mit Karte für die Arduino IDE (ESP32).
// Beim Start erst Kalibrierung über den Seriellen Monitor, danach: Karte hinhalten -> Servo Kammer 1 gibt aus.
//
// Arduino IDE: Board "ESP32 Dev Module", Serieller Monitor auf 115200 Baud.
// Bibliothek nötig: "MFRC522" von GithubCommunity (Bibliotheksverwalter, NICHT "MFRC522v2").
// LiquidCrystal und Preferences sind beim ESP32 schon dabei.
//
// Befehle (eintippen + Enter), funktionieren JEDERZEIT, auch nach dem Start:
//   0-180  Servo auf diesen Winkel fahren
//   + / -  Servo 2 Grad weiter / zurück   (+10 / -10 = 10 Grad)
//   r      aktuellen Winkel als Ruheposition speichern
//   a      aktuellen Winkel als Ausgabeposition speichern
//   t      Testausgabe: Ruhe -> Ausgabe -> Ruhe
//   w      Wackeltest: 3x zwischen Ruhe und Ausgabe hin und her
//   s      Kalibrierung beenden, auf Karte warten
//   k      Kalibrierung wieder öffnen
//   ?      Befehle und gespeicherte Winkel anzeigen
// Tippt ihr nach dem Start 10 Sekunden nichts, wartet das Programm auf die Karte.
// Die Winkel bleiben im ESP32 gespeichert, auch ohne Strom.
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
#include <Preferences.h>

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

const unsigned long KALIBRIER_WARTEZEIT = 10000;  // ms ohne Eingabe, dann Autostart

MFRC522 rfid(PIN_RFID_SS, PIN_RFID_RST);
LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_E, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);
Preferences speicher;

int winkelRuhe    = 170; // Startwerte, bis etwas gespeichert ist (neue 3D-Version: andere Seite)
int winkelAusgabe = 90;
int winkelAktuell = 10;
bool imKalibrieren = false;
String eingabe = "";
unsigned long letztesZeichen = 0;

/** Schreibt zwei Zeilen aufs Display (je max. 16 Zeichen, keine Umlaute). */
void anzeigen(const char* zeile1, const char* zeile2) {
  lcd.begin(16, 2);  // jedes Mal neu einrichten, falls das Display später Strom bekommen hat
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(zeile1);
  lcd.setCursor(0, 1);
  lcd.print(zeile2);
}

/** Zeigt in der Kalibrierung den aktuellen Winkel und die gespeicherten Werte auf dem Display. */
void kalibrierAnzeige() {
  char zeile1[17], zeile2[17];
  snprintf(zeile1, sizeof(zeile1), "Kalib. jetzt %3d", winkelAktuell);
  snprintf(zeile2, sizeof(zeile2), "R %3d  A %3d", winkelRuhe, winkelAusgabe);
  anzeigen(zeile1, zeile2);
}

/** Stellt den Servo auf einen Winkel zwischen 0 und 180 Grad. */
void servoWinkel(int grad) {
  grad = constrain(grad, 0, 180);
  winkelAktuell = grad;
  uint32_t mikros = map(grad, 0, 180, 500, 2400);  // SG90: ca. 0.5 ms bis 2.4 ms
  uint32_t duty = mikros * 65535UL / 20000UL;      // 50 Hz, 16 Bit: 20000 µs = 65535 Schritte
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_SERVO, duty);
#else
  ledcWrite(0, duty);
#endif
  Serial.printf("Servo Kammer 1 -> %d Grad\n", grad);
  if (imKalibrieren) kalibrierAnzeige();
}

/** Fährt einmal Ruhe -> Ausgabe -> Ruhe. */
void ausfahren() {
  servoWinkel(winkelRuhe);
  delay(400);
  servoWinkel(winkelAusgabe);
  delay(700);
  servoWinkel(winkelRuhe);
  delay(700);
}

/** Liest eine Zeile aus dem Seriellen Monitor; klappt mit und ohne Zeilenende. "" = noch nichts fertig. */
String zeileLesen() {
  while (Serial.available()) {
    char c = Serial.read();
    letztesZeichen = millis();
    if (c == '\n' || c == '\r') {
      String fertig = eingabe;
      fertig.trim();
      eingabe = "";
      if (fertig.length() > 0) return fertig;
    } else {
      eingabe += c;
    }
  }
  // Ohne Zeilenende (Einstellung "Kein Zeilenende"): nach 300 ms Pause gilt die Eingabe als fertig
  if (eingabe.length() > 0 && millis() - letztesZeichen > 300) {
    String fertig = eingabe;
    fertig.trim();
    eingabe = "";
    return fertig;
  }
  return "";
}

/** Zeigt die Befehle und die gespeicherten Winkel. */
void hilfe() {
  Serial.println();
  Serial.println("=== Kalibrierung Kammer 1 ===");
  Serial.printf("Jetzt %d Grad. Gespeichert: Ruhe %d Grad, Ausgabe %d Grad\n",
                winkelAktuell, winkelRuhe, winkelAusgabe);
  Serial.println("0-180 = Winkel anfahren   + / - = 2 Grad weiter/zurueck (+10 = 10 Grad)");
  Serial.println("r = als Ruhe speichern   a = als Ausgabe speichern");
  Serial.println("t = Testausgabe   w = Wackeltest   s = auf Karte warten   k = Kalibrierung   ? = Hilfe");
}

/** Führt einen Befehl aus der Konsole aus; gibt true zurück, wenn die Kalibrierung enden soll. */
bool befehlAusfuehren(String befehl) {
  Serial.printf("> %s\n", befehl.c_str());

  if (isDigit(befehl[0])) {
    servoWinkel(befehl.toInt());
  } else if (befehl[0] == '+' || befehl[0] == '-') {
    // "+" / "-" allein = 2 Grad, "+10" / "-10" = so viele Grad
    int schritt = befehl.length() > 1 ? befehl.substring(1).toInt() : 2;
    servoWinkel(winkelAktuell + (befehl[0] == '+' ? schritt : -schritt));
  } else if (befehl == "r") {
    winkelRuhe = winkelAktuell;
    speicher.putInt("ruhe", winkelRuhe);
    Serial.printf("Ruheposition gespeichert: %d Grad (Servo bleibt stehen, weiter mit Zahl, +, - oder t)\n", winkelRuhe);
    if (imKalibrieren) kalibrierAnzeige();
  } else if (befehl == "a") {
    winkelAusgabe = winkelAktuell;
    speicher.putInt("ausgabe", winkelAusgabe);
    Serial.printf("Ausgabeposition gespeichert: %d Grad (Servo bleibt stehen, weiter mit Zahl, +, - oder t)\n", winkelAusgabe);
    if (imKalibrieren) kalibrierAnzeige();
  } else if (befehl == "t") {
    Serial.println("Testausgabe ...");
    ausfahren();
  } else if (befehl == "w") {
    Serial.println("Wackeltest ...");
    for (uint8_t i = 0; i < 3; i++) ausfahren();
  } else if (befehl == "s") {
    return true;
  } else {
    hilfe();
  }
  return false;
}

/** Kalibrierphase: bleibt offen, bis 's' kommt oder nach dem Start 10 s lang nichts eingetippt wurde. */
void kalibrieren(bool mitAutostart) {
  imKalibrieren = true;
  hilfe();
  if (mitAutostart) Serial.printf("Ohne Eingabe geht es in %lu Sekunden weiter.\n", KALIBRIER_WARTEZEIT / 1000);
  kalibrierAnzeige();
  unsigned long start = millis();
  bool benutzt = false;

  while (true) {
    // Autostart nur, solange noch niemand etwas eingetippt hat
    if (mitAutostart && !benutzt && millis() - start > KALIBRIER_WARTEZEIT) {
      Serial.println("Keine Eingabe, warte auf Karte. Befehle gehen trotzdem weiter, k = Kalibrierung.");
      break;
    }
    String befehl = zeileLesen();
    if (befehl == "") continue;
    benutzt = true;
    if (befehlAusfuehren(befehl)) break;
  }

  imKalibrieren = false;
  servoWinkel(winkelRuhe);
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
  ausfahren();

  anzeigen("Fertig!", "Bitte entnehmen");
  delay(3000);
  bereit();
}

void setup() {
  // Gespeicherte Winkel laden und Servo sofort in Ruhe, damit er beim Einschalten kaum zuckt
  speicher.begin("pillcard", false);
  winkelRuhe    = speicher.getInt("ruhe", winkelRuhe);
  winkelAusgabe = speicher.getInt("ausgabe", winkelAusgabe);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(PIN_SERVO, 50, 16);
#else
  ledcSetup(0, 50, 16);
  ledcAttachPin(PIN_SERVO, 0);
#endif

  Serial.begin(115200);
  servoWinkel(winkelRuhe);
  delay(300);

  pinMode(PIN_LED_GRUEN, OUTPUT);
  pinMode(PIN_LED_ROT, OUTPUT);

  SPI.begin();  // ESP32-Standardpins: SCK 18, MISO 19, MOSI 23
  rfid.PCD_Init();
  Serial.println("=== PillCard Kammer 1 mit Karte ===");
  Serial.print("RFID-Leser: ");
  rfid.PCD_DumpVersionToSerial();  // bei uns 0x18, das ist ok

  kalibrieren(true);
  bereit();
}

void loop() {
  // Alle Servo-Befehle gehen auch im Betrieb, k öffnet die Kalibrierung wieder
  String befehl = zeileLesen();
  if (befehl == "k") {
    kalibrieren(false);
    bereit();
  } else if (befehl != "") {
    befehlAusfuehren(befehl);
  }

  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  ausgabe();

  // Karte abmelden: erst nach erneutem Hinhalten gibt es die nächste Ausgabe
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}
