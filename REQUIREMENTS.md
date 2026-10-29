# PillCard: Anforderungen

Stand: 27.10.2026. Noch ist nichts implementiert, alle Punkte sind offen.

## Funktionale Anforderungen

### Karte und Nutzer

- [ ] **FR-01** Der Spender liest RFID-Karten mit dem RC522.
- [ ] **FR-02** Auf der Karte stehen die Person, der Medikamentenplan und die verschriebene Menge.
- [ ] **FR-03** Am Gerät selbst muss nichts eingestellt werden.
- [ ] **FR-04** Mehrere Personen nutzen denselben Spender, jede mit ihrer eigenen Karte.

### Ausgabe

- [ ] **FR-05** Nach dem Lesen der Karte gibt der Spender genau die verschriebene Kombination aus den 3 Kammern aus.
- [ ] **FR-06** Jede Kammer hat einen eigenen Servo.
- [ ] **FR-07** Wurde die Dosis einer Person schon ausgegeben, gibt es keine weitere Ausgabe.
- [ ] **FR-08** Der Spender speichert pro Person, was schon ausgegeben wurde.

### Kontrolle

- [ ] **FR-09** Pro Kammer zählt eine Lichtschranke die herausfallenden Tabletten.
- [ ] **FR-10** Stimmt die gezählte Anzahl nicht mit dem Plan überein, reagiert der Spender. *(Wie genau, ist noch offen.)*
- [ ] **FR-11** Ein Kontaktsensor aus Kupferband in der Schale erkennt, ob der Becher entnommen wurde.

### Bestand

- [ ] **FR-12** Die Karte überträgt, wie viele Tabletten verschrieben sind.
- [ ] **FR-13** Der Spender zieht jede Ausgabe vom Bestand ab und weiss so, wie viele Tabletten noch im System sind.

### Rückmeldung

- [ ] **FR-14** Ein LCD-Display zeigt Hinweise an, z. B. dass die Tagesdosis schon genommen wurde, wenn jemand sie ein zweites Mal abholen will.
- [ ] **FR-15** Eine grüne und eine rote LED zeigen den Status an.

> Annahme: Grün heisst „Ausgabe läuft“, Rot heisst „keine Ausgabe, Dosis schon abgeholt“. Noch nicht festgelegt.

### Neues Medikament per E-Rezept (QR-Code)

- [x] **FR-16** Der QR-Code eines Schweizer E-Rezepts bzw. eMediplans wird gelesen. Umgesetzt mit der
  Handykamera im Webinterface (Foto) statt einer Kamera am Spender, plus Textfeld für einen USB-QR-Scanner.
- [x] **FR-17** Wird eine Kammer leer (Vorrat 0), leuchtet oben am Einfüllstutzen ihre LED, und die
  Website bietet „E-Rezept scannen“ an. Geht auch für einen Medikamentenwechsel.
- [x] **FR-18** Aus dem QR-Code wird die Kammer neu belegt: Medikament, Tabletten pro Tag (Summe der
  Tageszeiten), eingefüllte Menge, Nutzer. Siehe [docs/Website.md](docs/Website.md).

> Hintergrund: Der QR-Code des E-Rezepts enthält einen Link zur Info-Seite, die Rezeptdaten im
> Format CHMED16A und eine Signatur
> ([HIN-Funktionsdokumentation](https://hin.ch/files/pdf1/e-rezept-schweiz-funktionsdokumentation-de.pdf)).

## Sensoren und Aktoren

| ID | Bauteil | Ort | Aufgabe | Status |
|---|---|---|---|---|
| S1 | Lichtschranke (3×) | je eine pro Kammer | zählt ausgegebene Tabletten | geplant |
| S1-B | Mikrofon | unter dem Becher | Plan B für S1: erkennt fallende Tabletten | Plan B |
| S2 | Kontaktsensor aus Kupferband | Ausgabeschale | erkennt, ob der Becher steht oder entnommen wurde | geplant |
| | RFID-RC522 | seitliches Lesefeld | liest die Karte | geplant |
| | Servomotor (3×) | je eine pro Kammer | gibt Tabletten aus | geplant |
| S3 | Kamera | Position offen | liest den QR-Code vom E-Rezept (FR-16) | geplant |
| | LCD-Display | Position offen | Hinweise anzeigen | geplant |
| | LED grün, LED rot | Position offen | Status anzeigen | geplant |
| | Arduino (Elegoo Uno R3) | im Gehäuse | Steuerung | geplant |

## Gehäuse

- [x] 3D-Modell mit 3 nummerierten Kammern, RFID-Lesefeld und Ausgabeschale
- [ ] Display und LEDs ins Modell einbauen
- [ ] Gehäuse drucken
- [ ] Kupferband in der Schale anbringen

## Offene Punkte

- **Zeitfenster:** Gilt eine Tagesdosis, oder gibt es mehrere Zeitpunkte pro Tag? Für Zeitfenster braucht der Arduino wahrscheinlich ein Uhrmodul (RTC).
- **Vereinzelung:** Wie kommen die Tabletten einzeln aus der Kammer, damit die Lichtschranke sauber zählt?
- **Mikrofon als Plan B:** Ein Mikrofon unter dem Becher hört nicht, aus welcher Kammer eine Tablette kommt. Das funktioniert nur, wenn die Kammern nacheinander ausgeben.
- **Daten auf der Karte:** Wie wird der Plan auf die Karte geschrieben, und mit welchem Gerät?
- **Fehlerfall:** Was passiert, wenn zu wenig oder zu viele Tabletten gezählt werden, oder eine Kammer leer ist?
- **Pins:** Reichen die Pins des Uno für RC522, 3 Servos, 3 Lichtschranken, LCD, 2 LEDs und den Kupferband-Kontakt? Eventuell ein LCD mit I²C-Modul verwenden.
- **Strom:** Wie werden 3 Servos versorgt? Direkt am Arduino wird es knapp.
- **Kamera und QR-Code (FR-16 bis FR-18):**
  - Welche Kamera, und hängt sie am Raspberry Pi (dort liegt die Datenbank mit den Kammern) oder am ESP32?
  - Wer stösst den Scan an: automatisch, wenn der Vorrat einer Kammer leer ist, oder per Knopf auf der Website?
  - Woher weiss der Spender, in welche Kammer das neue Medikament kommt, wenn das Rezept mehrere Medikamente enthält?
  - Wie wird die Dosierung aus dem Rezept auf den Plan übertragen (Anzahl pro Einnahme und Uhrzeit)?
  - Format geklärt (IG eMediplan, ChTransmissionFormat): `CHMED16A0` + JSON oder `CHMED16A1` +
    Base64(gzip(JSON)). Der Code enthält keinen Medikamentennamen, nur GTIN/Pharmacode; den Namen
    trägt die Verwaltung ein. Eine Namenssuche bräuchte die (kostenpflichtige) INDEX-Datenbank.
  - Offen: Signatur prüfen. Der Prototyp liest nur aus.
  - Offen: Einnahmezeiten. Der Spender kennt eine Tagesdosis, morgens/abends werden zusammengezählt.
