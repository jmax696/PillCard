// PillCard Demo für die Arduino IDE (ESP32).
// Karte oder Chip hinhalten -> der ESP32 gibt die Tabletten des passenden Nutzers aus.
// Nach jeder Servobewegung hört das Mikrofon unter den Kammern hin, ob wirklich eine Tablette gefallen ist.
//
// Arduino IDE: Board "ESP32 Dev Module", Serieller Monitor auf 115200 Baud und "Neue Zeile".
// Bibliothek nötig: "MFRC522" von GithubCommunity (Bibliotheksverwalter, NICHT "MFRC522v2").
//
// Aufteilung (später mit Raspberry Pi):
//   ESP32: Servos, Mikrofon-Prüfung, Display, LEDs. Bekommt Aufträge als Textzeilen.
//   Pi:    RFID, welche UID welchen Plan hat, schon genommen?, Website. Schickt Aufträge.
// Bis der Pi läuft, liest der ESP32 die Karte selbst (RFID_AUF_ESP) und nimmt die Tabelle NUTZER unten.
//
// Befehle im Seriellen Monitor (später kommen dieselben Zeilen vom Pi):
//   AUFTRAG 17 K1=1 K3=2      Auftrag 17: Kammer 1 eine Tablette, Kammer 3 zwei Tabletten
//   MELDUNG schon_genommen 18:00   Hinweis aufs Display
//   mikro          10 s lang den Mikrofonpegel anzeigen (zum Einstellen)
//   probe 2        Kammer 2 gibt einmal aus, Pegelverlauf wird angezeigt
//   schwelle 250   Schwelle für "Tablette gehört" setzen (danach oben in MIC_SCHWELLE eintragen)
//   servo 1 45     Servo Kammer 1 auf 45 Grad (zum Einstellen der Winkel)
//   reset          "heute schon genommen" für alle Karten zurücksetzen
//   ?              Hilfe
//
// Antworten an den Pi (stehen auch im Seriellen Monitor):
//   BEREIT | OK 17 | TABLETTE 17 K1 ok | TABLETTE 17 K3 fehlt | FERTIG 17 K1=1 K3=1 | FEHLER <grund>
//
// Verkabelung:
//   RFID:    SDA->IO5  SCK->IO18  MOSI->IO23  MISO->IO19  RST->IO4  3.3V->3V3  GND->GND
//   LCD:     RS->IO22  E->IO21  D4->IO32  D5->IO33  D6->IO14  D7->IO15  R/W->GND
//   Servos:  Signal Kammer 1/2/3 -> IO25/IO26/IO27, rot->5V-Schiene, braun->GND-Schiene
//   LEDs:    grün->IO16, rot->IO17 (je über 100 Ohm)
//   Mikrofon (analoges Modul): S->IO34, V->3V3 (NICHT 5V, sonst bis zu 5V am Pin!), G->GND
//   Pi (später): USB-Kabel vom ESP32 in eine USB-Buchse des Pi, sonst nichts.
//     Alternative mit 3 Kabeln: ESP IO2 (TX) -> Pi GPIO15/RXD, ESP IO39 (RX) <- Pi GPIO14/TXD, GND <-> GND
//   GND des ESP32 muss an die GND-Schiene!
#include <SPI.h>
#include <MFRC522.h>
#include <LiquidCrystal.h>
#include <stdarg.h>

// ===== Einstellungen =====

const bool RFID_AUF_ESP = false;  // true nur, wenn der RC522 wieder am ESP32 hängt
const bool PI_VERBUNDEN = false;  // nur bei der 3-Kabel-Alternative true; über USB bleibt es false

// Pläne für die Demo. Später kennt nur noch der Pi diese Zuordnung.
// UID unbekannt? Karte hinhalten, die UID steht dann im Seriellen Monitor. Hier eintragen.
struct Nutzer {
  const char* name;     // max. 10 Zeichen, keine Umlaute (Display)
  const char* uid;      // so wie im Seriellen Monitor, z. B. "3D AB 09 01"
  uint8_t anzahl[3];    // Tabletten aus Kammer 1, 2, 3
};
Nutzer NUTZER[] = {
  {"Anna",  "3D AB 09 01", {1, 0, 1}},  // Karte: Kammer 1 und 3
  {"Bruno", "?? ?? ?? ??", {0, 1, 1}},  // Chip:  Kammer 2 und 3
};
const uint8_t ANZAHL_NUTZER = sizeof(NUTZER) / sizeof(NUTZER[0]);

// Servowinkel je Kammer (mit "servo K W" ausprobieren, dann hier eintragen)
const uint8_t ANZAHL_KAMMERN = 3;
const int WINKEL_RUHE[ANZAHL_KAMMERN]    = {0, 0, 0};
const int WINKEL_AUSGABE[ANZAHL_KAMMERN] = {90, 90, 90};

const uint8_t  MAX_PRO_KAMMER   = 9;    // mehr Tabletten pro Kammer nimmt der ESP32 nicht an (einstellig fürs Display)
const uint8_t  VERSUCHE         = 2;    // so oft fährt der Servo, wenn das Mikrofon nichts hört
const uint16_t SERVO_ANFAHREN_MS = 300; // vor jeder Tablette erst in Ruhelage, falls er verschoben wurde
const uint16_t SERVO_ZURUECK_MS  = 800; // Zeit für den Rückweg; erst danach kommt die nächste Tablette

// Mikrofon: Ab dem Servo-Befehl wird MIC_FENSTER_MS lang gemessen, in Stücken von 50 ms.
// Die ersten MIC_IGNORIEREN_MS zählen nicht, da ist vor allem der Servo laut.
int            MIC_SCHWELLE      = 250;  // Pegel (Spitze-Spitze, 0-4095), ab dem eine Tablette zählt
const uint16_t MIC_FENSTER_MS    = 900;
const uint16_t MIC_IGNORIEREN_MS = 150;
const uint16_t MIC_STUECK_MS     = 50;

// ===== Pins =====

const uint8_t PIN_RFID_SS  = 5;
const uint8_t PIN_RFID_RST = 4;
const uint8_t PIN_LCD_RS = 22, PIN_LCD_E = 21;
const uint8_t PIN_LCD_D4 = 32, PIN_LCD_D5 = 33, PIN_LCD_D6 = 14, PIN_LCD_D7 = 15;
const uint8_t PIN_SERVO[ANZAHL_KAMMERN] = {25, 26, 27};
const uint8_t PIN_LED_GRUEN = 16;
const uint8_t PIN_LED_ROT   = 17;
const uint8_t PIN_MIKRO     = 34;  // ADC1, reiner Eingang
const uint8_t PIN_PI_TX     = 2;
const uint8_t PIN_PI_RX     = 39;  // reiner Eingang

MFRC522 rfid(PIN_RFID_SS, PIN_RFID_RST);
LiquidCrystal lcd(PIN_LCD_RS, PIN_LCD_E, PIN_LCD_D4, PIN_LCD_D5, PIN_LCD_D6, PIN_LCD_D7);

struct Auftrag {
  int id;
  const char* name;  // nur für die Begrüßung, bei Aufträgen vom Pi leer
  uint8_t anzahl[ANZAHL_KAMMERN];
};

bool heuteGenommen[ANZAHL_NUTZER];  // nur solange RFID_AUF_ESP, später weiß das der Pi
int naechsteId = 1;
String pufferMonitor = "";
String pufferPi = "";

// ===== Ausgabe an Monitor und Pi =====

/** Schickt eine Antwortzeile an den Seriellen Monitor und, falls verbunden, an den Pi. */
void melde(const char* format, ...) {
  char zeile[96];
  va_list args;
  va_start(args, format);
  vsnprintf(zeile, sizeof(zeile), format, args);
  va_end(args);
  Serial.println(zeile);
  if (PI_VERBUNDEN) Serial2.println(zeile);
}

/** Schreibt zwei Zeilen aufs Display (je max. 16 Zeichen, keine Umlaute). */
void anzeigen(const char* zeile1, const char* zeile2) {
  lcd.begin(16, 2);  // jedes Mal neu einrichten, falls das Display später Strom bekommen hat
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(zeile1);
  lcd.setCursor(0, 1);
  lcd.print(zeile2);
}

/** Schaltet die LEDs: grün, rot oder beide aus. */
void leds(bool gruen, bool rot) {
  digitalWrite(PIN_LED_GRUEN, gruen ? HIGH : LOW);
  digitalWrite(PIN_LED_ROT, rot ? HIGH : LOW);
}

/** Wartebildschirm. */
void bereit() {
  leds(false, false);
  anzeigen("PillCard", "Karte hinhalten");
  Serial.println("Bereit, warte auf Karte oder Auftrag ...");
}

// ===== Servos =====

/** Schickt einen Pulswert an den Servo einer Kammer (0 = keine Pulse, Servo ist locker). */
void servoPuls(uint8_t kammer, uint32_t duty) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_SERVO[kammer], duty);
#else
  ledcWrite(kammer, duty);
#endif
}

/** Stellt den Servo einer Kammer (0-2) auf einen Winkel zwischen 0 und 180 Grad. */
void servoWinkel(uint8_t kammer, int grad) {
  grad = constrain(grad, 0, 180);
  uint32_t mikros = map(grad, 0, 180, 500, 2400);  // SG90: ca. 0.5 ms bis 2.4 ms
  servoPuls(kammer, mikros * 65535UL / 20000UL);    // 50 Hz, 16 Bit: 20000 µs = 65535 Schritte
}

/** Lässt einen Servo los, damit er nicht brummt (das Mikrofon würde es hören). */
void servoAus(uint8_t kammer) {
  servoPuls(kammer, 0);
}

// ===== Mikrofon =====

/** Misst ab jetzt MIC_FENSTER_MS lang und gibt den lautesten Pegel nach MIC_IGNORIEREN_MS zurück. */
int hinhoeren(bool verlaufZeigen) {
  unsigned long start = millis();
  int lautester = 0;
  if (verlaufZeigen) Serial.print("  Verlauf ms:Pegel (* zaehlt): ");

  for (uint16_t ab = 0; ab < MIC_FENSTER_MS; ab += MIC_STUECK_MS) {
    int tief = 4095, hoch = 0;
    while (millis() - start < (unsigned long)(ab + MIC_STUECK_MS)) {
      int wert = analogRead(PIN_MIKRO);
      if (wert < tief) tief = wert;
      if (wert > hoch) hoch = wert;
    }
    int pegel = hoch - tief;
    bool zaehlt = ab >= MIC_IGNORIEREN_MS;
    if (zaehlt && pegel > lautester) lautester = pegel;
    if (verlaufZeigen) Serial.printf("%u:%d%s ", ab, pegel, zaehlt ? "*" : "");
  }
  if (verlaufZeigen) Serial.println();
  return lautester;
}

/** Zeigt 10 s lang den Pegel im Monitor und als Balken auf dem Display. */
void mikroAnzeigen() {
  Serial.printf("Mikrofon 10 s, Schwelle %d. Jetzt eine Tablette in den Becher fallen lassen.\n", MIC_SCHWELLE);
  lcd.begin(16, 2);
  unsigned long start = millis();
  while (millis() - start < 10000) {
    int tief = 4095, hoch = 0;
    unsigned long stueck = millis();
    while (millis() - stueck < 200) {
      int wert = analogRead(PIN_MIKRO);
      if (wert < tief) tief = wert;
      if (wert > hoch) hoch = wert;
    }
    int pegel = hoch - tief;
    // Rohwerte mit ausgeben: immer 0 = kein Signal am Pin, immer 4095 = Pin hängt an 3.3V
    Serial.printf("Pegel %4d  (roh %4d-%4d) %s\n", pegel, tief, hoch, pegel >= MIC_SCHWELLE ? "<-- KLACK" : "");

    // Balken: 16 Zeichen = doppelte Schwelle, ab Zeichen 8 liegt man über der Schwelle
    char balken[17];
    int laenge = constrain(pegel * 8 / max(MIC_SCHWELLE, 1), 0, 16);
    for (int i = 0; i < 16; i++) balken[i] = i < laenge ? '#' : ' ';
    balken[16] = '\0';
    char zeile1[24];
    snprintf(zeile1, sizeof(zeile1), "Mikro %4d/%4d", pegel, MIC_SCHWELLE);
    zeile1[16] = '\0';  // Display hat 16 Zeichen
    lcd.setCursor(0, 0);
    lcd.print(zeile1);
    lcd.setCursor(0, 1);
    lcd.print(balken);
  }
  bereit();
}

// ===== Ausgabe =====

/** Gibt eine Tablette aus einer Kammer aus und prüft mit dem Mikrofon; true = Tablette gehört.
 *  Der Servo startet immer aus der Ruhelage und steht danach wieder dort, angesteuert.
 *  Loslassen (servoAus) erst, wenn die Kammer fertig ist. */
bool tabletteAusgeben(uint8_t kammer, bool verlaufZeigen) {
  servoWinkel(kammer, WINKEL_RUHE[kammer]);     // sichere Ausgangslage, auch wenn er verschoben wurde
  delay(SERVO_ANFAHREN_MS);
  servoWinkel(kammer, WINKEL_AUSGABE[kammer]);
  int pegel = hinhoeren(verlaufZeigen);  // Servo bleibt solange in Ausgabeposition
  servoWinkel(kammer, WINKEL_RUHE[kammer]);
  delay(SERVO_ZURUECK_MS);

  bool gehoert = pegel >= MIC_SCHWELLE;
  Serial.printf("  Mikrofon Kammer %u: Pegel %d, Schwelle %d -> %s\n",
                kammer + 1, pegel, MIC_SCHWELLE, gehoert ? "Tablette" : "nichts");
  return gehoert;
}

/** Arbeitet einen Auftrag ab: Kammer für Kammer, jede Tablette mit Mikrofon-Prüfung. */
void auftragAusfuehren(const Auftrag& a) {
  melde("OK %d", a.id);
  leds(true, false);

  char zeile1[17], zeile2[17];
  if (a.name && a.name[0]) snprintf(zeile1, sizeof(zeile1), "Hallo %s", a.name);
  else snprintf(zeile1, sizeof(zeile1), "Ihre Medikamente");
  anzeigen(zeile1, "Ausgabe startet");
  delay(1200);

  uint8_t ausgegeben[ANZAHL_KAMMERN] = {0};
  bool allesDa = true;

  for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) {
    for (uint8_t t = 0; t < a.anzahl[k]; t++) {
      snprintf(zeile1, sizeof(zeile1), "Kammer %u", k + 1);
      snprintf(zeile2, sizeof(zeile2), "Tablette %u/%u", t + 1, a.anzahl[k]);
      anzeigen(zeile1, zeile2);

      bool gehoert = false;
      for (uint8_t versuch = 1; versuch <= VERSUCHE && !gehoert; versuch++) {
        if (versuch > 1) anzeigen(zeile1, "Nochmal ...");
        gehoert = tabletteAusgeben(k, false);
      }

      melde("TABLETTE %d K%u %s", a.id, k + 1, gehoert ? "ok" : "fehlt");
      if (gehoert) ausgegeben[k]++;
      else allesDa = false;
    }
    if (a.anzahl[k] > 0) servoAus(k);  // Kammer fertig, Servo steht in Ruhelage: jetzt loslassen
  }

  // Abschlusszeile: was laut Mikrofon wirklich rauskam
  char fertig[64];
  int laenge = snprintf(fertig, sizeof(fertig), "FERTIG %d", a.id);
  for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) {
    if (a.anzahl[k] > 0) laenge += snprintf(fertig + laenge, sizeof(fertig) - laenge, " K%u=%u", k + 1, ausgegeben[k]);
  }
  melde("%s", fertig);

  if (allesDa) {
    leds(true, false);
    anzeigen("Fertig!", "Bitte entnehmen");
  } else {
    // Welche Kammern zu wenig gegeben haben
    int pos = snprintf(zeile1, sizeof(zeile1), "Fehlt:");
    for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) {
      if (ausgegeben[k] < a.anzahl[k]) pos += snprintf(zeile1 + pos, sizeof(zeile1) - pos, " K%u", k + 1);
    }
    leds(false, true);
    anzeigen(zeile1, "Pflege rufen");
  }
  delay(4000);
  bereit();
}

// ===== Befehle =====

/** Liest "AUFTRAG 17 K1=1 K3=2"; false = Zeile ist kein gültiger Auftrag. */
bool auftragLesen(const String& zeile, Auftrag& a) {
  a.id = 0;
  a.name = "";
  for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) a.anzahl[k] = 0;

  char text[96];
  zeile.toCharArray(text, sizeof(text));
  strtok(text, " ");  // das Wort AUFTRAG
  char* teil = strtok(NULL, " ");
  if (!teil || !isDigit(teil[0])) return false;
  a.id = atoi(teil);

  bool etwasDabei = false;
  while ((teil = strtok(NULL, " "))) {
    // Erwartet K<Kammer>=<Anzahl>, z. B. K3=2
    if (strlen(teil) < 4 || toupper(teil[0]) != 'K' || teil[2] != '=') return false;
    int kammer = teil[1] - '1';
    int anzahl = atoi(teil + 3);
    if (kammer < 0 || kammer >= ANZAHL_KAMMERN || anzahl < 0 || anzahl > MAX_PRO_KAMMER) return false;
    a.anzahl[kammer] = anzahl;
    if (anzahl > 0) etwasDabei = true;
  }
  return etwasDabei;
}

/** Zeigt eine Meldung vom Pi an, z. B. "MELDUNG schon_genommen 18:00". */
void meldungAnzeigen(const String& zeile) {
  String rest = zeile.substring(8);  // nach "MELDUNG "
  rest.trim();
  int leer = rest.indexOf(' ');
  String art = leer < 0 ? rest : rest.substring(0, leer);
  String zusatz = leer < 0 ? "" : rest.substring(leer + 1);

  char zeile2[17];
  if (art == "schon_genommen") {
    snprintf(zeile2, sizeof(zeile2), "Wieder um %s", zusatz.c_str());
    leds(false, true);
    anzeigen("Schon genommen", zusatz.length() ? zeile2 : "");
  } else if (art == "unbekannt") {
    leds(false, true);
    anzeigen("Karte unbekannt", "Pflege fragen");
  } else {
    // Unbekannte Art: Text so wie er kommt, max. 16 Zeichen
    leds(false, false);
    anzeigen(rest.substring(0, 16).c_str(), rest.length() > 16 ? rest.substring(16, 32).c_str() : "");
  }
  delay(3000);
  bereit();
}

/** Zeigt die Befehle und die wichtigsten Einstellungen. */
void hilfe() {
  Serial.println();
  Serial.println("=== PillCard Demo ===");
  Serial.println("AUFTRAG 17 K1=1 K3=2 | MELDUNG schon_genommen 18:00");
  Serial.println("mikro | probe 1-3 | schwelle 250 | servo 1 45 | reset | ?");
  Serial.printf("Mikrofon-Schwelle %d, Fenster %u ms, erste %u ms zaehlen nicht, %u Versuche\n",
                MIC_SCHWELLE, MIC_FENSTER_MS, MIC_IGNORIEREN_MS, VERSUCHE);
  for (uint8_t i = 0; i < ANZAHL_NUTZER; i++) {
    Serial.printf("Nutzer %u: %-6s UID %s  K1=%u K2=%u K3=%u%s\n", i + 1, NUTZER[i].name, NUTZER[i].uid,
                  NUTZER[i].anzahl[0], NUTZER[i].anzahl[1], NUTZER[i].anzahl[2],
                  heuteGenommen[i] ? "  (heute schon genommen)" : "");
  }
}

/** Führt eine Zeile aus dem Monitor oder vom Pi aus. */
void befehlAusfuehren(String zeile) {
  zeile.trim();
  if (zeile.length() == 0) return;
  Serial.printf("> %s\n", zeile.c_str());
  String klein = zeile;
  klein.toLowerCase();

  if (klein.startsWith("auftrag")) {
    Auftrag a;
    if (auftragLesen(zeile, a)) auftragAusfuehren(a);
    else melde("FEHLER auftrag_ungueltig");
  } else if (klein.startsWith("meldung")) {
    meldungAnzeigen(zeile);
  } else if (klein == "mikro") {
    mikroAnzeigen();
  } else if (klein.startsWith("probe")) {
    int kammer = klein.substring(5).toInt() - 1;
    if (kammer < 0 || kammer >= ANZAHL_KAMMERN) { Serial.println("probe 1, probe 2 oder probe 3"); return; }
    tabletteAusgeben(kammer, true);
    servoAus(kammer);
  } else if (klein.startsWith("schwelle")) {
    MIC_SCHWELLE = constrain((int)klein.substring(8).toInt(), 1, 4095);
    Serial.printf("Schwelle jetzt %d. Damit sie bleibt: oben bei MIC_SCHWELLE eintragen.\n", MIC_SCHWELLE);
  } else if (klein.startsWith("servo")) {
    int kammer = -1, grad = -1;
    sscanf(klein.c_str(), "servo %d %d", &kammer, &grad);
    if (kammer < 1 || kammer > ANZAHL_KAMMERN || grad < 0 || grad > 180) { Serial.println("z. B. servo 1 45"); return; }
    servoWinkel(kammer - 1, grad);
    Serial.printf("Servo Kammer %d -> %d Grad (bleibt angesteuert bis zur naechsten Ausgabe)\n", kammer, grad);
  } else if (klein == "reset") {
    for (uint8_t i = 0; i < ANZAHL_NUTZER; i++) heuteGenommen[i] = false;
    Serial.println("Alle Karten duerfen wieder.");
  } else {
    hilfe();
  }
}

/** Sammelt Zeichen bis zum Zeilenende und gibt dann die fertige Zeile zurück ("" = noch nicht fertig). */
String zeileLesen(Stream& quelle, String& puffer) {
  while (quelle.available()) {
    char c = quelle.read();
    if (c == '\n' || c == '\r') {
      String fertig = puffer;
      puffer = "";
      if (fertig.length() > 0) return fertig;
    } else if (puffer.length() < 95) {
      puffer += c;
    }
  }
  return "";
}

// ===== RFID (nur bis der Pi das übernimmt) =====

/** Macht aus der gelesenen UID einen Text wie "3D AB 09 01". */
String uidText() {
  String text = "";
  for (uint8_t i = 0; i < rfid.uid.size; i++) {
    char hex[4];
    snprintf(hex, sizeof(hex), i ? " %02X" : "%02X", rfid.uid.uidByte[i]);
    text += hex;
  }
  return text;
}

/** Sucht den Nutzer zur Karte und startet seinen Auftrag (Ersatz für den Pi). */
void karteBearbeiten() {
  String uid = uidText();
  Serial.printf("Karte erkannt, UID: %s\n", uid.c_str());

  int nutzer = -1;
  for (uint8_t i = 0; i < ANZAHL_NUTZER; i++) {
    if (uid.equalsIgnoreCase(NUTZER[i].uid)) nutzer = i;
  }
  if (nutzer < 0) {
    Serial.printf("Unbekannt. Zum Eintragen oben in NUTZER: \"%s\"\n", uid.c_str());
    meldungAnzeigen("MELDUNG unbekannt");
    return;
  }
  if (heuteGenommen[nutzer]) {
    Serial.printf("%s hat heute schon genommen (reset = zuruecksetzen)\n", NUTZER[nutzer].name);
    meldungAnzeigen("MELDUNG schon_genommen");
    return;
  }

  Auftrag a;
  a.id = naechsteId++;
  a.name = NUTZER[nutzer].name;
  for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) a.anzahl[k] = NUTZER[nutzer].anzahl[k];
  heuteGenommen[nutzer] = true;  // auch bei Fehlern, damit nichts doppelt kommt
  auftragAusfuehren(a);
}

// ===== Start und Hauptschleife =====

void setup() {
  Serial.begin(115200);
  if (PI_VERBUNDEN) Serial2.begin(115200, SERIAL_8N1, PIN_PI_RX, PIN_PI_TX);
  delay(300);

  pinMode(PIN_LED_GRUEN, OUTPUT);
  pinMode(PIN_LED_ROT, OUTPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_MIKRO, ADC_11db);  // Messbereich bis ca. 3.3 V

  // Alle Servos in Ruhe fahren, dann loslassen
  for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcAttach(PIN_SERVO[k], 50, 16);
#else
    ledcSetup(k, 50, 16);
    ledcAttachPin(PIN_SERVO[k], k);
#endif
    servoWinkel(k, WINKEL_RUHE[k]);
  }
  delay(600);
  for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) servoAus(k);

  if (RFID_AUF_ESP) {
    SPI.begin();  // ESP32-Standardpins: SCK 18, MISO 19, MOSI 23
    rfid.PCD_Init();
    Serial.print("RFID-Leser: ");
    rfid.PCD_DumpVersionToSerial();  // bei uns 0x18, das ist ok
  }

  hilfe();
  bereit();
  melde("BEREIT");
}

void loop() {
  String zeile = zeileLesen(Serial, pufferMonitor);
  if (zeile != "") befehlAusfuehren(zeile);

  if (PI_VERBUNDEN) {
    zeile = zeileLesen(Serial2, pufferPi);
    if (zeile != "") befehlAusfuehren(zeile);
  }

  if (!RFID_AUF_ESP) return;
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  karteBearbeiten();

  // Karte abmelden: erst nach erneutem Hinhalten passiert wieder etwas
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}
