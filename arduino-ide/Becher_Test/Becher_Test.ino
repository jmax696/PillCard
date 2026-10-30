// PillCard Becher-Test für die Arduino IDE (ESP32, ohne Zusatzbibliothek).
// Erkennt, ob der Becher auf der Grundplatte steht: Das Kupferband unter dem Becher verbindet
// zwei getrennte Kupferflächen auf der Platte. Ausgabe im Seriellen Monitor (115200 Baud),
// die grüne LED leuchtet, solange der Becher steht. "r" + Enter zeigt zusätzlich jeden Rohwechsel.
//
// Verkabelung:
//   Bodenfläche A (GND)   -> GND-Schiene
//   Bodenfläche B (Signal) -> 1 kOhm -> IO13      Schutzwiderstand, nah am ESP32
//   IO13 -> 10 kOhm -> 3V3                         Pull-up, stärker als der interne (ca. 45 kOhm)
//   IO13 -> 100 nF -> GND                          filtert Störungen, z. B. von den Servokabeln
//   LED grün -> IO16 über 100 Ohm, - an GND        wie im Demo-Sketch
//   Bodenfläche B nie mit 5V verbinden, der ESP32 verträgt nur 3.3V.
//
// Entprellung: Ein Wechsel zählt erst, wenn der Kontakt lange genug gleich bleibt.
// "Steht" nach 50 ms geschlossen, "entfernt" erst nach 400 ms offen, weil der Becher beim
// Hineinfallen einer Tablette kurz wackeln kann.

const uint8_t PIN_BECHER    = 13;
const uint8_t PIN_LED_GRUEN = 16;

const uint16_t BECHER_DA_MS  = 50;
const uint16_t BECHER_WEG_MS = 400;
const uint8_t  ABTAST_MS     = 5;

bool becherDa = false;            // entprellter Zustand
bool rohLetzter = false;          // zuletzt gelesener Wert, true = Kontakt geschlossen
unsigned long rohSeit = 0;        // seit wann der Rohwert so ist
unsigned long zustandSeit = 0;    // seit wann becherDa so ist
unsigned long letzteAbtastung = 0;
uint16_t unterbrechungen = 0;     // kurze Aussetzer, während der Becher als "steht" gilt
bool rohZeigen = false;

/** true, wenn das Kupfer am Becher die beiden Flächen gerade verbindet. */
bool kontaktGeschlossen() {
  return digitalRead(PIN_BECHER) == LOW;
}

/** Liest den Kontakt einmal. Der Zustand ändert sich erst, wenn der neue Wert lange genug
 *  stabil war. Gibt true zurück, wenn sich becherDa gerade geändert hat. */
bool becherAktualisieren() {
  unsigned long jetzt = millis();
  bool roh = kontaktGeschlossen();

  if (roh != rohLetzter) {
    // Kontakt kommt zurück, obwohl der Becher nie als entfernt galt: das war ein Aussetzer
    if (roh && becherDa) unterbrechungen++;
    rohLetzter = roh;
    rohSeit = jetzt;
    if (rohZeigen) Serial.printf("  roh: %s\n", roh ? "zu" : "offen");
  }

  if (roh == becherDa) return false;
  unsigned long noetig = roh ? BECHER_DA_MS : BECHER_WEG_MS;
  if (jetzt - rohSeit < noetig) return false;

  becherDa = roh;
  return true;
}

void zustandMelden() {
  unsigned long dauer = millis() - zustandSeit;
  if (becherDa) {
    Serial.println("Becher steht");
  } else {
    Serial.printf("Becher entfernt (stand %.1f s, %u kurze Aussetzer)\n", dauer / 1000.0, unterbrechungen);
    if (unterbrechungen > 0) Serial.println("  -> Kontakt wackelt: Flächen, Gewicht oder Führung prüfen");
  }
  digitalWrite(PIN_LED_GRUEN, becherDa ? HIGH : LOW);
  zustandSeit = millis();
  unterbrechungen = 0;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(PIN_BECHER, INPUT_PULLUP);  // bleibt an, auch wenn der externe 10-kOhm-Pull-up drin ist
  pinMode(PIN_LED_GRUEN, OUTPUT);

  // Startzustand direkt übernehmen, sonst meldet er beim Einschalten einen Wechsel
  becherDa = kontaktGeschlossen();
  rohLetzter = becherDa;
  rohSeit = zustandSeit = millis();

  Serial.println("=== PillCard Becher-Test ===");
  Serial.println("r + Enter: Rohwechsel ein/aus");
  zustandMelden();
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'r' || c == 'R') {
      rohZeigen = !rohZeigen;
      Serial.printf("Rohwechsel %s\n", rohZeigen ? "an" : "aus");
    }
  }

  if (millis() - letzteAbtastung < ABTAST_MS) return;
  letzteAbtastung = millis();
  if (becherAktualisieren()) zustandMelden();
}
