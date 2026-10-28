// Datenformat der PillCard-Karten und Funktionen zum Lesen und Schreiben.
// Wird vom Codierer, vom Decodierer und vom Hauptprogramm gemeinsam benutzt.
#pragma once
#include <Arduino.h>
#include "RfidLeser.h"

const uint8_t PC_KAMMERN       = 3;
const uint8_t PC_MAX_EINNAHMEN = 4;
const uint8_t PC_NAME_LAENGE   = 12;  // inkl. abschliessender 0, also 11 Zeichen
const uint8_t PC_VERSION       = 1;

// Ein Einnahmezeitpunkt: ab wann er fällig ist und wie viele Tabletten aus jeder Kammer.
struct __attribute__((packed)) Einnahme {
  uint8_t stunde;
  uint8_t minute;
  uint8_t anzahl[PC_KAMMERN];
};

// Alles, was auf der Karte steht. Belegt genau die Blöcke 4, 5 und 6 (Sektor 1)
// einer MIFARE-Classic-Karte und wird Byte für Byte so geschrieben.
struct __attribute__((packed)) KartenDaten {
  char     magic[2];                          // immer 'P','C'
  uint8_t  version;
  uint16_t personId;
  char     name[PC_NAME_LAENGE];
  uint8_t  anzahlEinnahmen;
  Einnahme einnahmen[PC_MAX_EINNAHMEN];       // nach Uhrzeit sortiert
  uint16_t verschrieben[PC_KAMMERN];          // verschriebene Packungsmenge je Kammer
  uint8_t  reserviert[3];
  uint8_t  pruefsumme;                        // CRC-8 über alle Bytes davor
};
static_assert(sizeof(KartenDaten) == 48, "KartenDaten muss genau 3 Blöcke à 16 Byte belegen");

enum class KartenStatus : uint8_t {
  OK,
  KEIN_MIFARE_CLASSIC,
  AUTH_FEHLER,
  LESEFEHLER,
  SCHREIBFEHLER,
  LEER,
  FREMDE_DATEN,
  FALSCHE_VERSION,
  PRUEFSUMME_FALSCH,
  UNGUELTIGER_PLAN
};

/** Gibt eine kurze deutsche Beschreibung zum Status zurück. */
const __FlashStringHelper* pcStatusText(KartenStatus s);

/** Setzt die Daten auf eine leere Karte mit Person, aber ohne Einnahmen. */
void pcInit(KartenDaten& d, uint16_t personId, const char* name);

/** Hängt einen Einnahmezeitpunkt an. Gibt false zurück, wenn kein Platz mehr ist oder die Zeit nicht später als die vorige ist. */
bool pcEinnahmeHinzufuegen(KartenDaten& d, uint8_t stunde, uint8_t minute,
                           uint8_t kammer1, uint8_t kammer2, uint8_t kammer3);

/** Startet den Bus (I2C oder SPI) und initialisiert den Leser. */
void pcLeserStarten(RfidLeser& rfid);

/** Liest und prüft die Daten der Karte, die gerade per PICC_ReadCardSerial ausgewählt wurde. */
KartenStatus pcLesen(RfidLeser& rfid, KartenDaten& d);

/** Schreibt die Daten auf die Karte und liest sie zur Kontrolle wieder zurück. */
KartenStatus pcSchreiben(RfidLeser& rfid, KartenDaten& d);

/** Überschreibt die drei PillCard-Blöcke mit Nullen. */
KartenStatus pcLoeschen(RfidLeser& rfid);

/** Beendet die Verbindung zur Karte, damit sie erst nach erneutem Hinhalten wieder erkannt wird. */
void pcKarteFreigeben(RfidLeser& rfid);

/** Gibt den Karteninhalt lesbar aus, z. B. auf Serial. */
void pcAusgeben(Print& out, const KartenDaten& d);

/** Gibt die UID der Karte als Hex aus, z. B. "A3 1F 0C 7E". */
void pcUidAusgeben(Print& out, const RfidLeser::Uid& uid);
