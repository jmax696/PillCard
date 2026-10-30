// PillCard Demo für die Arduino IDE (ESP32).
// Karte oder Chip hinhalten -> der ESP32 gibt die Tabletten des passenden Nutzers aus.
// Nach jeder Servobewegung hört das Mikrofon unter den Kammern hin, ob wirklich eine Tablette gefallen ist.
// Ausgegeben wird nur, wenn der Becher auf der Grundplatte steht (Kupferband, BECHER_PRUEFEN).
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
//   becher         10 s lang jeden Wechsel am Becherkontakt anzeigen (zum Ausrichten)
//   LEER 0 1 0     LEDs an den Einfüllstutzen: 1 = Kammer leer, LED an (schickt der Pi)
//   WINKEL 170 80 170 80 10 100   Ruhe- und Ausgabewinkel je Kammer (schickt der Pi nach dem Kalibrieren)
//   reset          "heute schon genommen" für alle Karten zurücksetzen
//   ?              Hilfe
//
// Antworten an den Pi (stehen auch im Seriellen Monitor):
//   BEREIT | OK 17 | TABLETTE 17 K1 ok | TABLETTE 17 K3 fehlt | FERTIG 17 K1=1 K3=1 | FEHLER <grund>
//   BECHER 17 genommen 10 | BECHER 17 abgebrochen
//   Kommt der Becher nicht, bevor die erste Tablette fällt: FEHLER kein_becher.
//   Wird er mittendrin weggenommen: Abbruch, BECHER 17 abgebrochen, dann FERTIG mit dem, was bis dahin kam.
//   Nach FERTIG zeigt das Display "Ihre Medikation liegt bereit", bis der Becher genommen wird.
//   Genommen = 10 s lang weg (BECHER_ENTNAHME_MS), dann kommt BECHER 17 genommen 10
//   (Zahl = vor so vielen Sekunden hochgenommen). Wird er vorher zurückgestellt, zählt es nicht.
//   Kommt vorher ein neuer Auftrag, endet die Beobachtung ohne Meldung (Becher blieb stehen).
//
// Verkabelung:
//   RFID:    SDA->IO5  SCK->IO18  MOSI->IO23  MISO->IO19  RST->IO4  3.3V->3V3  GND->GND
//   LCD:     RS->IO22  E->IO21  D4->IO32  D5->IO33  D6->IO14  D7->IO15  R/W->GND
//   Servos:  Signal Kammer 1/2/3 -> IO25/IO26/IO27, rot->5V-Schiene, braun->GND-Schiene
//   LEDs:    grün->IO16, rot->IO17 (je über 100 Ohm)
//   Leer-LEDs an den Einfüllstutzen: Kammer 1/2/3 -> IO18/IO19/IO23 (je über 100 Ohm, - an GND).
//     Die Pins sind nur frei, solange der RFID-Leser am Pi hängt (RFID_AUF_ESP = false).
//   Mikrofon (analoges Modul): S->IO34, V->3V3 (NICHT 5V, sonst bis zu 5V am Pin!), G->GND
//   Becher (Kupferband): Bodenfläche A->GND, Bodenfläche B->1 kOhm->IO13,
//     dazu 10 kOhm IO13->3V3 und 100 nF IO13->GND. Fläche B nie an 5V.
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

// Servowinkel je Kammer. Das sind nur die Startwerte: Kalibriert wird auf der Website (Verwaltung ->
// Servos), der Pi schickt die Werte dann mit "WINKEL Ruhe1 Ausgabe1 Ruhe2 Ausgabe2 Ruhe3 Ausgabe3".
const uint8_t ANZAHL_KAMMERN = 3;
// Nicht 0 oder 180: Dort drückt ein SG90 oft gegen seinen Anschlag, brummt und bleibt mal hier, mal da stehen.
int winkelRuhe[ANZAHL_KAMMERN]    = {170, 170, 10};  // neue 3D-Version: K1/K2 starten von der anderen Seite, K3 (IO27) dreht andersrum
int winkelAusgabe[ANZAHL_KAMMERN] = {80, 80, 100};   // immer genau 90° neben der Ruhelage
// So lange braucht der Servo von der Ruhelage zur Ausgabe und zurück (ms). 0 = volle Geschwindigkeit.
// K3 ist sonst zu ruckartig. Größer = langsamer.
const uint16_t SERVO_FAHRZEIT_MS[ANZAHL_KAMMERN] = {0, 0, 800};
const uint16_t SERVO_SCHRITT_MS = 20;   // ein neuer Winkel pro Servo-Takt (50 Hz)

const uint8_t  MAX_PRO_KAMMER   = 9;    // mehr Tabletten pro Kammer nimmt der ESP32 nicht an (einstellig fürs Display)
const uint8_t  VERSUCHE         = 2;    // so oft fährt der Servo, wenn das Mikrofon nichts hört
const uint16_t SERVO_ANFAHREN_MS = 300; // vor jeder Tablette erst in Ruhelage, falls er verschoben wurde
const uint16_t SERVO_ZURUECK_MS  = 800; // Zeit für den Rückweg; erst danach kommt die nächste Tablette
const uint16_t WECHSEL_MS        = 8000; // Wartebild: so lange "PillCard", dann so lange die leeren Kammern

// Mikrofon: Ab dem Servo-Befehl wird MIC_FENSTER_MS lang gemessen, in Stücken von 50 ms.
// Die ersten MIC_IGNORIEREN_MS zählen nicht, da ist vor allem der Servo laut.
int            MIC_SCHWELLE      = 250;  // Pegel (Spitze-Spitze, 0-4095), ab dem eine Tablette zählt
const uint16_t MIC_FENSTER_MS    = 900;
const uint16_t MIC_IGNORIEREN_MS = 150;
const uint16_t MIC_STUECK_MS     = 50;

// Becher: Das Kupferband unter dem Becher verbindet zwei Flächen auf der Grundplatte.
// false, solange das Kupferband nicht verkabelt ist, sonst gibt das Gerät nie etwas aus.
const bool     BECHER_PRUEFEN   = true;
const uint16_t BECHER_DA_MS     = 50;     // so lange durchgehend Kontakt = Becher steht
const uint16_t BECHER_WEG_MS    = 400;    // so lange durchgehend offen = weg (fallende Tablette lässt ihn wackeln)
const uint16_t BECHER_WARTEN_MS = 15000;  // pro Auftrag höchstens so lange auf den Becher warten.
                                          // Nicht erhöhen: der Pi wartet nur 20 s + 5 s pro Tablette auf FERTIG
const uint32_t BECHER_ENTNAHME_MS = 10000;  // nach der Ausgabe: so lange weg = genommen (kurz anheben zählt nicht)
const uint16_t ABHOL_WECHSEL_MS   = 4000;   // "liegt bereit" und "Fehlt: K1" wechseln sich so ab

// ===== Pins =====

const uint8_t PIN_RFID_SS  = 5;
const uint8_t PIN_RFID_RST = 4;
const uint8_t PIN_LCD_RS = 22, PIN_LCD_E = 21;
const uint8_t PIN_LCD_D4 = 32, PIN_LCD_D5 = 33, PIN_LCD_D6 = 14, PIN_LCD_D7 = 15;
const uint8_t PIN_SERVO[ANZAHL_KAMMERN] = {25, 26, 27};
const uint8_t PIN_LED_GRUEN = 16;
const uint8_t PIN_LED_ROT   = 17;
const uint8_t PIN_LED_LEER[ANZAHL_KAMMERN] = {18, 19, 23};  // am Einfüllstutzen, an = Kammer leer
const uint8_t PIN_MIKRO     = 34;  // ADC1, reiner Eingang
const uint8_t PIN_BECHER    = 13;  // Kupferband Fläche B, LOW = Becher steht
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
bool kammerLeer[ANZAHL_KAMMERN] = {false, false, false};  // meldet der Pi mit LEER
bool zeigtLeerInfo = false;      // Wartebild zeigt gerade die leeren Kammern statt "PillCard"
unsigned long wartebildSeit = 0;
// Nach FERTIG wartet das Gerät, bis der Becher genommen wird (Abholzustand)
int becherAuftrag = -1;          // auf die Entnahme dieses Auftrags warten, -1 = nichts offen
bool becherRohZu = false;        // letzter gelesener Kontakt ...
unsigned long becherRohSeit = 0; // ... und seit wann er so ist
bool becherAbgehoben = false;    // Becher ist weg, die BECHER_ENTNAHME_MS laufen ...
unsigned long becherAbgehobenSeit = 0;  // ... seit dieser Zeit
uint8_t abholAnzahl = 0;         // so viele Tabletten hat das Mikrofon gehört
char fehltText[17] = "";         // z. B. "Fehlt: K1 K3", leer = alles da
bool zeigtFehlt = false;         // Display zeigt gerade "Fehlt: ..." statt "liegt bereit"

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

/** Leer-LED einer Kammer an oder aus. Ohne Wirkung, solange der RFID-Leser diese Pins braucht. */
void leerLed(uint8_t kammer, bool leer) {
  if (!RFID_AUF_ESP) digitalWrite(PIN_LED_LEER[kammer], leer ? HIGH : LOW);
}

/** Normales Wartebild. */
void wartebild() {
  anzeigen("PillCard", "Karte hinhalten");
  zeigtLeerInfo = false;
  wartebildSeit = millis();
}

/** Wartebild mit den leeren Kammern, z. B. "Kammer 3 leer". false = keine Kammer leer. */
bool leerInfo() {
  char zeile1[17] = "";
  uint8_t anzahl = 0, erste = 0, zweite = 0;
  for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) {
    if (!kammerLeer[k]) continue;
    if (anzahl == 0) erste = k + 1; else zweite = k + 1;
    anzahl++;
  }
  if (anzahl == 0) return false;
  if (anzahl == 1) snprintf(zeile1, sizeof(zeile1), "Kammer %u leer", erste);
  else if (anzahl == 2) snprintf(zeile1, sizeof(zeile1), "Kammer %u+%u leer", erste, zweite);
  else snprintf(zeile1, sizeof(zeile1), "Kammer 1-3 leer");
  anzeigen(zeile1, "Bitte auffuellen");
  zeigtLeerInfo = true;
  wartebildSeit = millis();
  return true;
}

/** Abholzustand: "Ihre Medikation liegt bereit", solange der Becher nach der Ausgabe noch steht.
 *  fehltAnzeigen = "Fehlt: K1 / Pflege rufen" zeigen (kommt allein, wenn das Mikrofon gar nichts gehört hat). */
void abholbild(bool fehltAnzeigen) {
  if (!fehltText[0]) fehltAnzeigen = false;
  if (abholAnzahl == 0) fehltAnzeigen = true;
  leds(!fehltText[0], fehltText[0] != '\0');
  if (fehltAnzeigen) anzeigen(fehltText, "Pflege rufen");
  else anzeigen("Ihre Medikation", "liegt bereit");
  zeigtFehlt = fehltAnzeigen;
  zeigtLeerInfo = false;
  wartebildSeit = millis();
}

/** Wechselt im Leerlauf alle WECHSEL_MS zwischen "PillCard" und den leeren Kammern.
 *  Im Abholzustand stattdessen zwischen "liegt bereit" und "Fehlt: ...". */
void wartebildWechseln() {
  if (becherAuftrag >= 0) {
    if (becherAbgehoben || millis() - wartebildSeit < ABHOL_WECHSEL_MS) return;
    if (fehltText[0] && abholAnzahl > 0) abholbild(!zeigtFehlt);
    else wartebildSeit = millis();
    return;
  }
  if (millis() - wartebildSeit < WECHSEL_MS) return;
  if (zeigtLeerInfo) wartebild();
  else if (!leerInfo()) wartebildSeit = millis();  // nichts leer: "PillCard" bleibt einfach stehen
}

/** Wartebildschirm. Beginnt immer mit "PillCard", die Leer-Info kommt nach WECHSEL_MS.
 *  Steht der Becher von der letzten Ausgabe noch da, bleibt "liegt bereit" auf dem Display. */
void bereit() {
  if (becherAuftrag >= 0) {
    abholbild(false);
    Serial.println("Medikation liegt bereit, warte auf Entnahme oder neuen Auftrag ...");
    return;
  }
  leds(false, false);
  wartebild();
  Serial.println("Bereit, warte auf Karte oder Auftrag ...");
}

// ===== Servos =====

/** Schickt einen Pulswert an den Servo einer Kammer. */
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

/** Winkel auf dem Weg von -> nach, wenn seit dem Start "vergangen" ms von "dauer" ms um sind. */
int fahrWinkel(int von, int nach, unsigned long vergangen, uint16_t dauer) {
  if (dauer == 0 || vergangen >= dauer) return nach;
  return von + (long)(nach - von) * (long)vergangen / dauer;
}

/** Fährt den Servo gleichmäßig in "dauer" ms von einem Winkel zum anderen (0 = sofort). */
void servoFahren(uint8_t kammer, int von, int nach, uint16_t dauer) {
  unsigned long start = millis();
  while (millis() - start < dauer) {
    servoWinkel(kammer, fahrWinkel(von, nach, millis() - start, dauer));
    delay(SERVO_SCHRITT_MS);
  }
  servoWinkel(kammer, nach);
}

// ===== Mikrofon =====

/** Fährt den Servo einer Kammer langsam in die Ausgabeposition und hört dabei zu: misst ab jetzt
 *  Fahrzeit + MIC_FENSTER_MS lang und gibt den lautesten Pegel nach MIC_IGNORIEREN_MS zurück.
 *  So zählt auch eine Tablette, die schon während der langsamen Fahrt fällt. */
int hinhoeren(uint8_t kammer, bool verlaufZeigen) {
  unsigned long start = millis();
  uint16_t dauer = SERVO_FAHRZEIT_MS[kammer];
  uint16_t fenster = dauer + MIC_FENSTER_MS;
  int lautester = 0;
  int winkel = dauer ? winkelRuhe[kammer] : winkelAusgabe[kammer];  // ohne Fahrzeit: sofort zur Ausgabe
  servoWinkel(kammer, winkel);
  if (verlaufZeigen) Serial.print("  Verlauf ms:Pegel (* zaehlt): ");

  for (uint16_t ab = 0; ab < fenster; ab += MIC_STUECK_MS) {
    int tief = 4095, hoch = 0;
    while (millis() - start < (unsigned long)(ab + MIC_STUECK_MS)) {
      // Servo nur neu ansteuern, wenn sich der Winkel ändert (sonst stört es Servo und Messung)
      int soll = fahrWinkel(winkelRuhe[kammer], winkelAusgabe[kammer], millis() - start, dauer);
      if (dauer && soll != winkel) { winkel = soll; servoWinkel(kammer, winkel); }
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

// ===== Becher =====

/** true, solange das Kupfer am Becher die beiden Bodenflächen verbindet (ungefiltert). */
bool becherKontakt() {
  return digitalRead(PIN_BECHER) == LOW;
}

/** Prüft entprellt, ob der Becher steht, und braucht dafür höchstens eine Sekunde.
 *  50 ms durchgehend Kontakt = steht, 400 ms durchgehend offen = weg.
 *  Flackert der Kontakt die ganze Zeit, gilt der Becher als nicht da. */
bool becherSteht() {
  if (!BECHER_PRUEFEN) return true;
  unsigned long start = millis();
  unsigned long seit = start;  // seit wann der Kontakt so ist wie jetzt
  bool zu = becherKontakt();
  while (millis() - start < 1000) {
    bool jetztZu = becherKontakt();
    if (jetztZu != zu) {
      zu = jetztZu;
      seit = millis();
    }
    unsigned long stabil = millis() - seit;
    if (zu && stabil >= BECHER_DA_MS) return true;
    if (!zu && stabil >= BECHER_WEG_MS) return false;
    delay(5);
  }
  return false;
}

/** Wartet, bis der Becher steht, und zieht die Wartezeit vom Budget des Auftrags ab.
 *  Solange er fehlt, steht "Becher bitte hinstellen" mit den restlichen Sekunden da.
 *  true = Becher steht, false = Budget aufgebraucht. */
bool aufBecherWarten(unsigned long& budget) {
  if (becherSteht()) return true;

  Serial.println("  Becher fehlt, warte ...");
  leds(false, true);
  unsigned long start = millis();
  long gezeigt = -1;
  while (millis() - start < budget) {
    long rest = (budget - (millis() - start) + 999) / 1000;
    if (rest != gezeigt) {
      char zeile2[17];
      snprintf(zeile2, sizeof(zeile2), "hinstellen  %2ds", (int)constrain(rest, 0L, 99L));
      anzeigen("Becher bitte", zeile2);
      gezeigt = rest;
    }
    if (becherSteht()) {
      budget -= min(budget, millis() - start);
      Serial.println("  Becher steht");
      leds(true, false);
      return true;
    }
  }
  budget = 0;
  return false;
}

/** Zeigt 10 s lang jeden Wechsel am Becherkontakt, zum Ausrichten der Kupferflächen. */
void becherAnzeigen() {
  Serial.println("Becher 10 s: hinstellen, wegnehmen, antippen. Jeder Wechsel wird angezeigt.");
  unsigned long start = millis();
  bool zu = becherKontakt();
  uint16_t wechsel = 0;
  Serial.printf("  Start: %s\n", zu ? "Kontakt (Becher steht)" : "offen");
  anzeigen("Becher-Test", zu ? "steht" : "fehlt");
  while (millis() - start < 10000) {
    bool jetztZu = becherKontakt();
    if (jetztZu != zu) {
      zu = jetztZu;
      wechsel++;
      Serial.printf("  %5lu ms: %s\n", millis() - start, zu ? "Kontakt" : "offen");
      anzeigen("Becher-Test", zu ? "steht" : "fehlt");
    }
    delay(2);
  }
  Serial.printf("%u Wechsel. Wechsel, obwohl der Becher still steht = Kontakt unsicher.\n", wechsel);
  bereit();
}

/** Abholzustand starten: ab jetzt auf die Entnahme des Bechers warten. */
void abholenStarten(int auftragId) {
  becherAuftrag = auftragId;
  becherRohZu = becherKontakt();
  becherRohSeit = millis();
  becherAbgehoben = false;
}

/** Läuft in loop(): Nach einem Auftrag melden, wenn der Becher genommen wurde.
 *  Abgehoben = BECHER_WEG_MS durchgehend offen, dann steht "Bitte einnehmen" da.
 *  Genommen = BECHER_ENTNAHME_MS weg. Wird er vorher zurückgestellt, liegt die Medikation wieder bereit. */
void becherUeberwachen() {
  if (becherAuftrag < 0) return;
  bool zu = becherKontakt();
  if (zu != becherRohZu) {
    becherRohZu = zu;
    becherRohSeit = millis();
  }
  unsigned long stabil = millis() - becherRohSeit;

  if (!becherAbgehoben) {
    if (!zu && stabil >= BECHER_WEG_MS) {
      becherAbgehoben = true;
      becherAbgehobenSeit = becherRohSeit;
      Serial.println("  Becher abgehoben");
      leds(true, false);
      anzeigen("Bitte einnehmen", "");
    }
    return;
  }

  // Zurückgestellt, bevor die Zeit um war: zählt nicht als genommen
  if (zu && stabil >= BECHER_DA_MS) {
    becherAbgehoben = false;
    Serial.println("  Becher wieder hingestellt");
    abholbild(false);
    return;
  }

  unsigned long weg = millis() - becherAbgehobenSeit;
  if (weg >= BECHER_ENTNAHME_MS) {
    melde("BECHER %d genommen %lu", becherAuftrag, weg / 1000);  // Zahl = vor so vielen Sekunden hochgenommen
    becherAuftrag = -1;
    becherAbgehoben = false;
    bereit();
  }
}

// ===== Ausgabe =====

/** Gibt eine Tablette aus einer Kammer aus und prüft mit dem Mikrofon; true = Tablette gehört.
 *  Der Servo startet immer aus der Ruhelage und steht danach wieder dort. Er wird nie losgelassen:
 *  ohne Pulse hat ein SG90 keine Haltekraft, und Reibung oder Tabletten drehen ihn weg. */
bool tabletteAusgeben(uint8_t kammer, bool verlaufZeigen) {
  servoWinkel(kammer, winkelRuhe[kammer]);     // sichere Ausgangslage, auch wenn er verschoben wurde
  delay(SERVO_ANFAHREN_MS);
  int pegel = hinhoeren(kammer, verlaufZeigen);  // fährt zur Ausgabe und bleibt dort, solange gemessen wird
  servoFahren(kammer, winkelAusgabe[kammer], winkelRuhe[kammer], SERVO_FAHRZEIT_MS[kammer]);
  delay(SERVO_FAHRZEIT_MS[kammer] ? SERVO_FAHRZEIT_MS[kammer] / 4 : SERVO_ZURUECK_MS);  // langsam: ist schon fast da

  bool gehoert = pegel >= MIC_SCHWELLE;
  Serial.printf("  Mikrofon Kammer %u: Pegel %d, Schwelle %d -> %s\n",
                kammer + 1, pegel, MIC_SCHWELLE, gehoert ? "Tablette" : "nichts");
  return gehoert;
}

/** Arbeitet einen Auftrag ab: Kammer für Kammer, jede Tablette mit Mikrofon-Prüfung. */
void auftragAusfuehren(const Auftrag& a) {
  becherAuftrag = -1;  // Becher vom letzten Auftrag wurde nicht hochgenommen, die Beobachtung endet hier
  melde("OK %d", a.id);
  leds(true, false);

  char zeile1[17], zeile2[17];
  if (a.name && a.name[0]) snprintf(zeile1, sizeof(zeile1), "Hallo %s", a.name);
  else snprintf(zeile1, sizeof(zeile1), "Ihre Medikamente");
  anzeigen(zeile1, "Ausgabe startet");
  delay(1200);

  uint8_t ausgegeben[ANZAHL_KAMMERN] = {0};
  bool allesDa = true;
  unsigned long becherBudget = BECHER_WARTEN_MS;  // gilt für den ganzen Auftrag
  bool becherFehlt = false;
  uint8_t versucht = 0;                           // Tabletten, für die der Servo schon gefahren ist

  for (uint8_t k = 0; k < ANZAHL_KAMMERN && !becherFehlt; k++) {
    for (uint8_t t = 0; t < a.anzahl[k]; t++) {
      // Vor jeder Tablette: ohne Becher fiele sie auf die Platte
      if (!aufBecherWarten(becherBudget)) {
        becherFehlt = true;
        allesDa = false;
        break;
      }
      versucht++;

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
  }

  // Becher kam gar nicht: nichts ist gefallen, der Pi bekommt einen Fehler statt FERTIG
  if (becherFehlt && versucht == 0) {
    melde("FEHLER kein_becher");
    leds(false, true);
    anzeigen("Kein Becher", "Pflege rufen");
    delay(4000);
    bereit();
    return;
  }
  if (becherFehlt) {
    Serial.println("  Becher weggenommen, Ausgabe abgebrochen");
    melde("BECHER %d abgebrochen", a.id);
  }

  // Abschlusszeile: was laut Mikrofon wirklich rauskam
  char fertig[64];
  int laenge = snprintf(fertig, sizeof(fertig), "FERTIG %d", a.id);
  for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) {
    if (a.anzahl[k] > 0) laenge += snprintf(fertig + laenge, sizeof(fertig) - laenge, " K%u=%u", k + 1, ausgegeben[k]);
  }
  melde("%s", fertig);

  // Welche Kammern zu wenig gegeben haben, z. B. "Fehlt: K1 K3"
  fehltText[0] = '\0';
  if (!allesDa) {
    int pos = snprintf(fehltText, sizeof(fehltText), "Fehlt:");
    for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) {
      if (ausgegeben[k] < a.anzahl[k]) pos += snprintf(fehltText + pos, sizeof(fehltText) - pos, " K%u", k + 1);
    }
  }
  abholAnzahl = 0;
  for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) abholAnzahl += ausgegeben[k];

  // Becher steht mit der Medikation da: "liegt bereit", bis er genommen wird (becherUeberwachen in loop)
  if (BECHER_PRUEFEN && !becherFehlt) {
    abholenStarten(a.id);
    bereit();
    return;
  }

  // Ohne Becherprüfung oder nach Abbruch: Ergebnis 4 s anzeigen
  if (allesDa) {
    leds(true, false);
    anzeigen("Fertig!", "Bitte entnehmen");
  } else {
    leds(false, true);
    anzeigen(fehltText, "Pflege rufen");
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
  Serial.println("mikro | probe 1-3 | schwelle 250 | servo 1 45 | becher | leer 0 1 0 | reset | ?");
  Serial.printf("Mikrofon-Schwelle %d, Fenster %u ms, erste %u ms zaehlen nicht, %u Versuche\n",
                MIC_SCHWELLE, MIC_FENSTER_MS, MIC_IGNORIEREN_MS, VERSUCHE);
  if (BECHER_PRUEFEN) Serial.printf("Becher-Pruefung an (IO%u), gerade: %s\n", PIN_BECHER, becherKontakt() ? "steht" : "fehlt");
  else Serial.println("Becher-Pruefung aus");
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
  } else if (klein == "becher") {
    becherAnzeigen();
  } else if (klein.startsWith("schwelle")) {
    MIC_SCHWELLE = constrain((int)klein.substring(8).toInt(), 1, 4095);
    Serial.printf("Schwelle jetzt %d. Damit sie bleibt: oben bei MIC_SCHWELLE eintragen.\n", MIC_SCHWELLE);
  } else if (klein.startsWith("servo")) {
    int kammer = -1, grad = -1;
    sscanf(klein.c_str(), "servo %d %d", &kammer, &grad);
    if (kammer < 1 || kammer > ANZAHL_KAMMERN || grad < 0 || grad > 180) { Serial.println("z. B. servo 1 45"); return; }
    servoWinkel(kammer - 1, grad);
    Serial.printf("Servo Kammer %d -> %d Grad (bleibt angesteuert bis zur naechsten Ausgabe)\n", kammer, grad);
  } else if (klein.startsWith("winkel")) {
    int w[2 * ANZAHL_KAMMERN];
    if (sscanf(klein.c_str(), "winkel %d %d %d %d %d %d", &w[0], &w[1], &w[2], &w[3], &w[4], &w[5])
        != 2 * ANZAHL_KAMMERN) {
      Serial.println("z. B. winkel 170 80 170 80 10 100");
      return;
    }
    for (uint8_t i = 0; i < 2 * ANZAHL_KAMMERN; i++) {
      if (w[i] < 0 || w[i] > 180) { Serial.println("Winkel nur 0 bis 180"); return; }
    }
    // Der Pi schickt das alle 30 s auch ohne Änderung; nur bei einer neuen Ruhelage fährt der Servo hin
    for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) {
      bool neueRuhe = winkelRuhe[k] != w[2 * k];
      winkelRuhe[k] = w[2 * k];
      winkelAusgabe[k] = w[2 * k + 1];
      if (neueRuhe) {
        servoWinkel(k, winkelRuhe[k]);
        Serial.printf("Kammer %u: neue Ruhelage %d, Ausgabe %d\n", k + 1, winkelRuhe[k], winkelAusgabe[k]);
      }
    }
  } else if (klein.startsWith("leer")) {
    int leer[ANZAHL_KAMMERN] = {0, 0, 0};
    if (sscanf(klein.c_str(), "leer %d %d %d", &leer[0], &leer[1], &leer[2]) != ANZAHL_KAMMERN) {
      Serial.println("z. B. leer 0 1 0");
      return;
    }
    bool geaendert = false;
    for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) {
      leerLed(k, leer[k] != 0);
      if (kammerLeer[k] != (leer[k] != 0)) geaendert = true;
      kammerLeer[k] = leer[k] != 0;
    }
    // Der Pi schickt LEER alle 30 s auch ohne Änderung, dann bleibt die Anzeige, wie sie ist.
    // Wurde gerade nachgefüllt, verschwindet die Leer-Info sofort.
    if (geaendert && zeigtLeerInfo && !leerInfo()) wartebild();
    Serial.printf("Leer-LEDs: K1 %s, K2 %s, K3 %s\n",
                  leer[0] ? "an" : "aus", leer[1] ? "an" : "aus", leer[2] ? "an" : "aus");
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
  // Zuerst die Servos: Bis hier hängen ihre Pins in der Luft und die Servos können zucken.
  // Danach bleiben sie dauerhaft in der Ruhelage angesteuert.
  for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcAttach(PIN_SERVO[k], 50, 16);
#else
    ledcSetup(k, 50, 16);
    ledcAttachPin(PIN_SERVO[k], k);
#endif
    servoWinkel(k, winkelRuhe[k]);
  }

  Serial.begin(115200);
  if (PI_VERBUNDEN) Serial2.begin(115200, SERIAL_8N1, PIN_PI_RX, PIN_PI_TX);
  delay(300);

  pinMode(PIN_LED_GRUEN, OUTPUT);
  pinMode(PIN_LED_ROT, OUTPUT);
  if (!RFID_AUF_ESP) {
    for (uint8_t k = 0; k < ANZAHL_KAMMERN; k++) {
      pinMode(PIN_LED_LEER[k], OUTPUT);
      leerLed(k, false);  // bis der Pi meldet, welche Kammern leer sind
    }
  }
  pinMode(PIN_BECHER, INPUT_PULLUP);  // bleibt an, auch mit externem 10-kOhm-Pull-up
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_MIKRO, ADC_11db);  // Messbereich bis ca. 3.3 V

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

  wartebildWechseln();
  becherUeberwachen();

  if (!RFID_AUF_ESP) return;
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  karteBearbeiten();

  // Karte abmelden: erst nach erneutem Hinhalten passiert wieder etwas
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}
