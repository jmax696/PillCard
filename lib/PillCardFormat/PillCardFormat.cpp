#include "PillCardFormat.h"

static const uint8_t ERSTER_BLOCK  = 4;
static const uint8_t TRAILER_BLOCK = 7;  // Sektor-Trailer mit den Schlüsseln, nie beschreiben!
static const uint8_t ANZAHL_BLOCKS = 3;

/** Prüft, ob die ausgewählte Karte eine MIFARE Classic ist (nur die hat Sektoren mit Schlüsseln). */
static bool istMifareClassic(RfidLeser& rfid) {
  uint8_t typ = rfid.PICC_GetType(rfid.uid.sak);
  return typ == RfidLeser::PICC_TYPE_MIFARE_MINI ||
         typ == RfidLeser::PICC_TYPE_MIFARE_1K ||
         typ == RfidLeser::PICC_TYPE_MIFARE_4K;
}

/** Meldet sich mit dem Werksschlüssel FF FF FF FF FF FF an Sektor 1 an. */
static bool anmelden(RfidLeser& rfid) {
  RfidLeser::MIFARE_Key key;
  for (uint8_t i = 0; i < 6; i++) key.keyByte[i] = 0xFF;
  return rfid.PCD_Authenticate(RfidLeser::PICC_CMD_MF_AUTH_KEY_A, TRAILER_BLOCK, &key, &rfid.uid)
         == RfidLeser::STATUS_OK;
}

/** Berechnet die CRC-8 (Polynom 0x07) über alle Bytes ausser der Prüfsumme selbst. */
static uint8_t berechnePruefsumme(const KartenDaten& d) {
  const uint8_t* p = reinterpret_cast<const uint8_t*>(&d);
  uint8_t crc = 0;
  for (size_t i = 0; i < sizeof(KartenDaten) - 1; i++) {
    crc ^= p[i];
    for (uint8_t b = 0; b < 8; b++) {
      crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x07) : (uint8_t)(crc << 1);
    }
  }
  return crc;
}

/** Liest die drei Blöcke roh in den Puffer (48 Byte). */
static KartenStatus rohLesen(RfidLeser& rfid, uint8_t* ziel) {
  for (uint8_t i = 0; i < ANZAHL_BLOCKS; i++) {
    uint8_t puffer[18];  // MIFARE_Read braucht 16 Daten + 2 CRC-Bytes
    uint8_t groesse = sizeof(puffer);
    if (rfid.MIFARE_Read(ERSTER_BLOCK + i, puffer, &groesse) != RfidLeser::STATUS_OK) {
      return KartenStatus::LESEFEHLER;
    }
    memcpy(ziel + i * 16, puffer, 16);
  }
  return KartenStatus::OK;
}

/** Schreibt 48 Byte roh in die drei Blöcke. */
static KartenStatus rohSchreiben(RfidLeser& rfid, const uint8_t* quelle) {
  for (uint8_t i = 0; i < ANZAHL_BLOCKS; i++) {
    uint8_t puffer[16];
    memcpy(puffer, quelle + i * 16, 16);
    if (rfid.MIFARE_Write(ERSTER_BLOCK + i, puffer, 16) != RfidLeser::STATUS_OK) {
      return KartenStatus::SCHREIBFEHLER;
    }
  }
  return KartenStatus::OK;
}

/** Prüft Kennung, Version, Prüfsumme und ob der Plan plausibel ist. */
static KartenStatus pruefen(const KartenDaten& d) {
  const uint8_t* p = reinterpret_cast<const uint8_t*>(&d);
  bool alleNull = true;
  for (size_t i = 0; i < sizeof(KartenDaten); i++) {
    if (p[i] != 0) { alleNull = false; break; }
  }
  if (alleNull) return KartenStatus::LEER;
  if (d.magic[0] != 'P' || d.magic[1] != 'C') return KartenStatus::FREMDE_DATEN;
  if (d.version != PC_VERSION) return KartenStatus::FALSCHE_VERSION;
  if (d.pruefsumme != berechnePruefsumme(d)) return KartenStatus::PRUEFSUMME_FALSCH;

  if (d.name[PC_NAME_LAENGE - 1] != '\0') return KartenStatus::UNGUELTIGER_PLAN;
  if (d.anzahlEinnahmen > PC_MAX_EINNAHMEN) return KartenStatus::UNGUELTIGER_PLAN;
  int vorher = -1;
  for (uint8_t i = 0; i < d.anzahlEinnahmen; i++) {
    const Einnahme& e = d.einnahmen[i];
    if (e.stunde > 23 || e.minute > 59) return KartenStatus::UNGUELTIGER_PLAN;
    int jetzt = e.stunde * 60 + e.minute;
    if (jetzt <= vorher) return KartenStatus::UNGUELTIGER_PLAN;
    vorher = jetzt;
  }
  return KartenStatus::OK;
}

const __FlashStringHelper* pcStatusText(KartenStatus s) {
  switch (s) {
    case KartenStatus::OK:                  return F("OK");
    case KartenStatus::KEIN_MIFARE_CLASSIC: return F("Kartentyp nicht unterstuetzt (nur MIFARE Classic)");
    case KartenStatus::AUTH_FEHLER:         return F("Anmeldung an Sektor 1 fehlgeschlagen (anderer Schluessel?)");
    case KartenStatus::LESEFEHLER:          return F("Lesefehler - Karte ruhig halten");
    case KartenStatus::SCHREIBFEHLER:       return F("Schreibfehler - Karte ruhig halten");
    case KartenStatus::LEER:                return F("Karte ist leer (noch nicht codiert)");
    case KartenStatus::FREMDE_DATEN:        return F("Keine PillCard-Daten auf der Karte");
    case KartenStatus::FALSCHE_VERSION:     return F("Kartenformat hat eine andere Version");
    case KartenStatus::PRUEFSUMME_FALSCH:   return F("Pruefsumme falsch - Daten beschaedigt");
    case KartenStatus::UNGUELTIGER_PLAN:    return F("Plan auf der Karte ist ungueltig");
  }
  return F("?");
}

void pcLeserStarten(RfidLeser& rfid) {
#ifdef PILLCARD_RFID_I2C
  Wire.begin();
#ifdef WIRE_HAS_TIMEOUT
  Wire.setWireTimeout(25000, true);  // ohne Timeout hängt der Uno bei Wackelkontakt fest
#endif
#else
  SPI.begin();
#endif
  rfid.PCD_Init();
}

void pcInit(KartenDaten& d, uint16_t personId, const char* name) {
  memset(&d, 0, sizeof(d));
  d.magic[0] = 'P';
  d.magic[1] = 'C';
  d.version = PC_VERSION;
  d.personId = personId;
  strncpy(d.name, name, PC_NAME_LAENGE - 1);
}

bool pcEinnahmeHinzufuegen(KartenDaten& d, uint8_t stunde, uint8_t minute,
                           uint8_t kammer1, uint8_t kammer2, uint8_t kammer3) {
  if (d.anzahlEinnahmen >= PC_MAX_EINNAHMEN || stunde > 23 || minute > 59) return false;
  if (d.anzahlEinnahmen > 0) {
    const Einnahme& letzte = d.einnahmen[d.anzahlEinnahmen - 1];
    if (stunde * 60 + minute <= letzte.stunde * 60 + letzte.minute) return false;
  }
  Einnahme& e = d.einnahmen[d.anzahlEinnahmen++];
  e.stunde = stunde;
  e.minute = minute;
  e.anzahl[0] = kammer1;
  e.anzahl[1] = kammer2;
  e.anzahl[2] = kammer3;
  return true;
}

KartenStatus pcLesen(RfidLeser& rfid, KartenDaten& d) {
  if (!istMifareClassic(rfid)) return KartenStatus::KEIN_MIFARE_CLASSIC;
  if (!anmelden(rfid)) return KartenStatus::AUTH_FEHLER;
  KartenStatus s = rohLesen(rfid, reinterpret_cast<uint8_t*>(&d));
  if (s != KartenStatus::OK) return s;
  return pruefen(d);
}

KartenStatus pcSchreiben(RfidLeser& rfid, KartenDaten& d) {
  if (!istMifareClassic(rfid)) return KartenStatus::KEIN_MIFARE_CLASSIC;
  if (!anmelden(rfid)) return KartenStatus::AUTH_FEHLER;

  d.magic[0] = 'P';
  d.magic[1] = 'C';
  d.version = PC_VERSION;
  d.name[PC_NAME_LAENGE - 1] = '\0';
  d.pruefsumme = berechnePruefsumme(d);

  KartenStatus s = rohSchreiben(rfid, reinterpret_cast<const uint8_t*>(&d));
  if (s != KartenStatus::OK) return s;

  // Zur Kontrolle zurücklesen und Byte für Byte vergleichen
  KartenDaten kontrolle;
  s = rohLesen(rfid, reinterpret_cast<uint8_t*>(&kontrolle));
  if (s != KartenStatus::OK) return s;
  if (memcmp(&kontrolle, &d, sizeof(KartenDaten)) != 0) return KartenStatus::SCHREIBFEHLER;
  return pruefen(kontrolle);
}

KartenStatus pcLoeschen(RfidLeser& rfid) {
  if (!istMifareClassic(rfid)) return KartenStatus::KEIN_MIFARE_CLASSIC;
  if (!anmelden(rfid)) return KartenStatus::AUTH_FEHLER;
  uint8_t nullen[sizeof(KartenDaten)] = {0};
  return rohSchreiben(rfid, nullen);
}

void pcKarteFreigeben(RfidLeser& rfid) {
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}

void pcAusgeben(Print& out, const KartenDaten& d) {
  char zeile[80];

  out.print(F("Person:      "));
  out.print(d.name);
  out.print(F("  (ID "));
  out.print(d.personId);
  out.println(F(")"));

  out.print(F("Einnahmen:   "));
  out.println(d.anzahlEinnahmen);
  for (uint8_t i = 0; i < d.anzahlEinnahmen && i < PC_MAX_EINNAHMEN; i++) {
    const Einnahme& e = d.einnahmen[i];
    snprintf(zeile, sizeof(zeile), "  ab %02u:%02u   Kammer 1: %u   Kammer 2: %u   Kammer 3: %u",
             e.stunde, e.minute, e.anzahl[0], e.anzahl[1], e.anzahl[2]);
    out.println(zeile);
  }

  snprintf(zeile, sizeof(zeile), "Verschrieben: Kammer 1: %u   Kammer 2: %u   Kammer 3: %u",
           d.verschrieben[0], d.verschrieben[1], d.verschrieben[2]);
  out.println(zeile);
}

void pcUidAusgeben(Print& out, const RfidLeser::Uid& uid) {
  for (uint8_t i = 0; i < uid.size; i++) {
    if (i > 0) out.print(' ');
    if (uid.uidByte[i] < 0x10) out.print('0');
    out.print(uid.uidByte[i], HEX);
  }
}
