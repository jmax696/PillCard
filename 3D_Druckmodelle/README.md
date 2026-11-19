# Medikamentenspender – aktuelle Druckdateien

Diese Anleitung beschreibt die tatsächlich vorhandenen Dateien.
Die STLs enthalten eine gemeinsame Bauteilausführung für die drei Dosierpositionen.
Die Datei `PRUEFUNGSERGEBNIS.json` enthält Messwerte und SHA-256-Prüfsummen für alle 14 STLs.

## Ordner und Druckmengen

- `01_Dispenser_Innen_Bauteile/STL`: sieben Teile je Dosierposition. Für drei Positionen jedes Teil dreimal drucken.
- `02_Innenhalterung/STL_GESAMTES_GESTELL_UND_BECHER`: vier Gestellteile und ein Becher, jeweils einmal.
- `02_Innenhalterung/STL_GEMEINSAMER_TRICHTER`: ein gemeinsamer Sammeltrichter, einmal.
- `04_Pillen_Dummys`: ein Testkörper nach Bedarf.

**Gesamt: 7 × 3 + 4 + 1 + 1 = 27 Druckteile**, ohne Testkörper, Elektronik, Motoren und Gehäuse.
Die drei Motor-Steckhalter sind in den 21 Modulbauteilen enthalten. Nicht zusätzlich für die Innenhalterung zählen.
Die Servoplatte enthält bereits sechs feste Stützen; dafür sind keine separaten Stützdateien erforderlich.

## Bauteile und gemessene Masse

Alle Masse in Millimetern. Die Tabelle zeigt X × Y × Z der jeweiligen STL in ihrer Exportlage,
auf 0,01 mm gerundet. Bei liegend exportierten Seitenrahmen ist die dritte Zahl nicht die Montagehöhe.

| STL-Bauteil | Anzahl für drei Positionen | Aussenmasse X × Y × Z (mm) |
|---|---:|---|
| [Kassettenboden mit Stufensitz](01_Dispenser_Innen_Bauteile/STL/01_Kassettenboden_Stufensitz.stl) | 3 | 62 × 72 × 13,9 |
| [Senkrechter Auslass ohne Sensorlöcher](01_Dispenser_Innen_Bauteile/STL/02_Senkrechter_Auslass_ohne_Sensorloecher.stl) | 3 | 16,7 × 16,7 × 33 |
| [Dosierscheibe mit Formtasche](01_Dispenser_Innen_Bauteile/STL/03_Dosierscheibe_Formtasche.stl) | 3 | 56 × 56 × 4,4 |
| [Untere Platte / Abstreifdeckel](01_Dispenser_Innen_Bauteile/STL/04_Untere_Platte_Abstreifdeckel.stl) | 3 | 62 × 72 × 6 |
| [Verstärkter Motor-Steckhalter](01_Dispenser_Innen_Bauteile/STL/05_Motor_Steckhalter_verstaerkt.stl) | 3 | 60 × 18,3 × 41,35 |
| [Wellenadapter](01_Dispenser_Innen_Bauteile/STL/06_Wellenadapter_D9_Hplus1.stl) | 3 | 19,6 × 18,19 × 14,95 |
| [Oberer Trichter mit Rohr und festem Auflagerand](01_Dispenser_Innen_Bauteile/STL/07_Trichter_Rohr_Fester_Auflagerand.stl) | 3 | 60 × 93 × 88,3 |
| [Gemeinsamer Sammeltrichter](02_Innenhalterung/STL_GEMEINSAMER_TRICHTER/G14_Gemeinsamer_Trichter.stl) | 1 | 160 × 46 × 70 |
| [Becher](02_Innenhalterung/STL_GESAMTES_GESTELL_UND_BECHER/B01_Becher_D35_6_H50_Wand2.stl) | 1 | 35,6 × 35,6 × 50 |
| [Bodenplatte mit Bechermulde und Kabelwegen](02_Innenhalterung/STL_GESAMTES_GESTELL_UND_BECHER/H01_Bodenplatte_mit_Bechermulde_und_Kabelwegen.stl) | 1 | 191 × 122 × 6 |
| [Linker Seitenrahmen mit Trichterauflage](02_Innenhalterung/STL_GESAMTES_GESTELL_UND_BECHER/H02_Seitenrahmen_mit_Trichterauflage_Links.stl) | 1 | 147 × 113 × 14,5 |
| [Rechter Seitenrahmen mit Trichterauflage](02_Innenhalterung/STL_GESAMTES_GESTELL_UND_BECHER/H03_Seitenrahmen_mit_Trichterauflage_Rechts.stl) | 1 | 147 × 113 × 16,5 |
| [Servoplatte mit sechs festen Stützen](02_Innenhalterung/STL_GESAMTES_GESTELL_UND_BECHER/H04_Servoplatte_mit_sechs_festen_Stuetzen.stl) | 1 | 191 × 115 × 42 |
| [Pillen-Dummy, leicht ovaleres Rechteck](04_Pillen_Dummys/Pillen_Dummy_rechteckig_9x5x4mm.stl) | nach Bedarf | 9 × 5 × 4 |

STL speichert keine verbindliche Einheit. Beim Import Millimeter und 100 % Skalierung wählen.
Alle Dateien beginnen bei Z = 0. Daraus folgt keine allgemeine Aussage über nötige Druckstützen,
Schichthöhe oder die Eignung der Ausrichtung für jeden Drucker.
Die Materialvolumina im Prüfbericht sind Volumina der geschlossenen Modelle; Infill und Slicer-Stützmaterial sind darin nicht berücksichtigt.

## Prüfung

Python-Skripte und Anleitung zum Nachrechnen: [Prüfungsanleitung](Pruefung/README.md).
Die gespeicherten Ergebnisse stehen in [PRUEFUNGSERGEBNIS.json](PRUEFUNGSERGEBNIS.json).
