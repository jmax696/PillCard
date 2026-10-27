# PillCard

Ein Tablettenspender für Senioren, der über RFID-Karten programmiert wird.

Projekt im Kurs **Hands-on HCI** (HSG, Herbst 2026), Themenbereich 1: *Augmenting Humans in Everyday Life*.

## Idee

Viele ältere Menschen nehmen mehrere Medikamente zu unterschiedlichen Zeiten ein. Elektronische Spender gibt es bereits, aber sie müssen am Gerät eingestellt werden. Das ist für viele Senioren schwierig.

Bei PillCard ist der Medikamentenplan auf einer persönlichen RFID-Karte gespeichert. Pflegepersonal oder Angehörige richten die Karte einmal ein. Die Senioren halten danach nur noch ihre Karte an das Lesefeld.

## Was PillCard besonders macht

1. **Keine Programmierung durch Senioren.** Die Einstellungen kommen über die RFID-Karte und nicht über das Gerät.
2. **Mehrere Bewohner nutzen einen Spender.** Jede Person hat eine eigene Karte, alle nutzen dasselbe Gerät.
3. **Immer die verschriebene Kombination.** Wurden die Tabletten schon ausgegeben, gibt es keine weitere Ausgabe.

## Ablauf einer Ausgabe

1. Die Person hält ihre RFID-Karte an das Lesefeld.
2. Der Spender liest den Plan und prüft, ob die Dosis schon ausgegeben wurde.
3. Falls nicht: Die Servos geben die verschriebenen Tabletten aus den Kammern in den Becher aus, die Lichtschranken zählen mit, die grüne LED leuchtet.
4. Falls doch: Es gibt keine Ausgabe. Die rote LED leuchtet und das LCD-Display zeigt an, dass die Dosis schon genommen wurde.
5. Ein Kontaktsensor in der Schale erkennt, ob der Becher entnommen wurde.

## Aufbau

| Bauteil | Aufgabe |
|---|---|
| Arduino (Elegoo Uno R3) | Steuerung, Ausgaben speichern, Bestand zählen |
| RFID-RC522 und Karten | Person, Plan und verschriebene Menge lesen |
| 3 Servomotoren | je Kammer eine Ausgabe |
| 3 Lichtschranken (eine pro Kammer) | ausgegebene Tabletten zählen |
| Kontaktsensor aus Kupferband | erkennt, ob der Becher in der Schale steht |
| LCD-Display | Hinweise für den Nutzer |
| Grüne und rote LED | Statusanzeige |
| Gehäuse aus dem 3D-Drucker | 3 Kammern, Lesefeld, Ausgabeschale mit Becher |

Plan B für das Zählen: ein Mikrofon unter dem Becher, das die fallenden Tabletten erkennt.

Details zu Anforderungen, Sensoren und offenen Punkten: [REQUIREMENTS.md](REQUIREMENTS.md)

## Stand

- [x] Idee und Idea Pitch (27.10.2026)
- [x] 3D-Modell des Gehäuses
- [ ] Gehäuse drucken
- [ ] Elektronik aufbauen und einzeln testen
- [ ] Arduino-Code für den gesamten Ablauf
- [ ] Prototype Demo (29.10.2026)
- [ ] Video Showcase (30.10.2026)
- [ ] Portfolio-Abgabe: Bericht, Video, Code, Schaltpläne (20.11.2026)

## Repo-Struktur

Noch leer. Geplant sind zum Beispiel Ordner für den Arduino-Code, die Schaltpläne und die 3D-Dateien.
