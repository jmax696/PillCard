# Designentscheidungen

Warum PillCard so gebaut ist, wie es ist, und was wir im Rückblick anders machen würden.
Stand: 19.11.2026.

## 1. Ausgabemechanik: Kolben verworfen, Drehrad gebaut

| | Kolben (Schieber) | Drehrad (gebaut) |
|---|---|---|
| Prinzip | Ein Servo schiebt über eine Koppelstange einen Schieber 20 mm nach vorn. Er stößt die unterste Tablette aus dem Magazin über den Fallschacht. | Eine Dosierscheibe mit Tasche sitzt unter dem Einfüllkanal. Der Servo dreht sie um 100° zum Auslass, dort fällt die Tablette. |
| Status | Idee, nicht gebaut. Als 3D-Modell nachträglich modelliert (OpenSCAD, parametrisch). | Drei Module gebaut (je Kammer eins). |

**Warum Drehrad:** Wir gingen davon aus, dass industrielle Prozesse so ein Drehrad nutzen. Für den
MVP wollten wir möglichst nah an einem industriellen Prozess sein und die Entwicklung entsprechend
hoch ansetzen.

**Im Rückblick:** Wahrscheinlich war das nicht die beste Entscheidung.

- **Genauigkeit:** Es sollte immer genau eine Tablette herauskommen, und die Tabletten sollten nicht
  verkanten. Beides war mit dem Drehrad schwierig. Das Verkanten hätten wir mit dem Kolben und
  kantigeren Tabletten wahrscheinlich nicht gehabt.
- **Kalibrierung:** Die Servos mussten pro Kammer genau eingestellt werden. Das war so schwierig,
  dass wir dafür eine eigene Servosteuerung geschrieben haben: die Kalibrierseite `/admin/servos`
  (siehe [Website.md](Website.md#servos-kalibrieren--adminservos)). Beim Kolben wäre auch das
  einfacher gewesen.

## 2. Tabletten zählen: Lichtschranken verworfen, Mikrofon gebaut

Geplant waren drei Lichtschranken, je eine pro Kammer, ursprünglich an einem Arduino Uno. Gebaut
wurde ein ESP32 mit **einem** analogen Mikrofon unter allen Kammern. Es hört, ob und wie viele
Tabletten gefallen sind. Die Sensorlöcher im Auslass sind in der aktuellen Druckversion deshalb
entfallen („Senkrechter Auslass ohne Sensorlöcher“). Der Uno-Aufbau ist in
[Verkabelung.md](Verkabelung.md#arduino-uno-ausweichvariante-uno_-umgebungen) als Ausweichvariante
dokumentiert.

## 3. Becher erkennen: Kupferkontakt

Der Becher steht in einer Mulde der gedruckten Bodenplatte auf zwei Kupferflächen (IO13). Der
Becherboden überbrückt sie. So gibt PillCard nur aus, wenn ein Becher steht, und merkt, wann er
hochgenommen wird (siehe [Datenbank.md](Datenbank.md) und [Verkabelung.md](Verkabelung.md)).

## Quellen

- Gründe und Rückblick zu Abschnitt 1: Aussage des Teams (Max), 19.11.2026.
- Drehrad: STLs in [`3D_Druckmodelle/`](../3D_Druckmodelle/README.md), Entwürfe V01–V08 im
  Modellarchiv `Medikamentenspender_Alle_Versionen_2026-10-31` (nicht im Repo). Tasche und Auslass
  liegen nach der Geometrie um 100° auseinander. Das passt zur Drehprüfung 0°–100° im V08-Entwurf.
- Kolben: `pillendispenser_3d_modelle/` (OpenSCAD + STL, Anastasia, nicht im Repo): Hub 20 mm,
  Servoweg 100°.
- Lichtschranken/Mikrofon: [Verkabelung.md](Verkabelung.md), [Agent-Kontext.md](Agent-Kontext.md).
