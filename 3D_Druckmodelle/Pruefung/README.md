# Geometriepruefung der Druckmodelle

Hier liegen die Python-Skripte zu den Ergebnissen in [PRUEFUNGSERGEBNIS.json](../PRUEFUNGSERGEBNIS.json).
Sie berechnen Abmessungen, Volumen, Netzfehler und ausgewaehlte Abstaende direkt aus den STL-Dateien.
Die verwendeten Pruefskripte wurden fuer die Abgabe mit relativen Pfaden und einem gemeinsamen Startskript aufbereitet.

## Starten

Im Ordner `3D_Druckmodelle` ein Terminal oeffnen. Mit Python 3.12 ausfuehren:

```powershell
python -m pip install -r Pruefung/requirements.txt
python Pruefung/pruefung_ausfuehren.py
```

Die angegebenen Versionen von NumPy und SciPy wurden fuer den Kontrolllauf verwendet.
Der zweite Befehl berechnet die Werte neu und vergleicht sie mit dem vorhandenen Bericht.
STLs und Bericht werden dabei nicht veraendert. Zwischenergebnisse liegen nur in einem temporaeren Ordner.

Optional die neuen Ergebnisse in eine eigene, noch nicht vorhandene Datei schreiben:

```powershell
python Pruefung/pruefung_ausfuehren.py --ausgabe ergebnisse_neu.json
```

Ein anderer Modellordner kann mit `--modelle PFAD_ZUM_MODELLORDNER` angegeben werden.
Die Einheit wird als Millimeter angenommen; STL-Dateien selbst speichern keine Einheit.

## Dateien

| Datei | Aufgabe |
|---|---|
| `pruefung_ausfuehren.py` | Startet die drei Berechnungen und vergleicht ihre Ergebnisse mit dem Bericht. |
| `geometrie_pruefen.py` | Misst jede STL und untersucht ihre Dreiecksverbindungen. |
| `merkmale_pruefen.py` | Misst Becher und Dosiertasche und vergleicht die Tasche mit dem Dummy. |
| `anschluesse_pruefen.py` | Vergleicht ausgewaehlte Anschluss-Abmessungen. |
| `stl_io.py` | Liest binaere STL-Dateien und kontrolliert Dateilaenge und Koordinaten. |
| `requirements.txt` | Benoetigte Python-Bibliotheken. |

Die Berechnungsskripte lesen keine Ergebniswerte aus `PRUEFUNGSERGEBNIS.json`. Erst das Startskript liest diese Datei zum Vergleich.
Jedes Berechnungsskript kann auch einzeln mit `--modelle ORDNER --ausgabe NEUE_DATEI.json` gestartet werden.
Vorhandene Ausgabedateien werden nicht ueberschrieben.

## Rechenwege

### Abmessungen und Volumen

Jedes Dreieck hat drei Punkte `a`, `b` und `c`.

- Breite, Tiefe und Hoehe: jeweils groesster minus kleinster Koordinatenwert.
- Dreiecksflaeche: `0.5 * Laenge((b - a) Kreuzprodukt (c - a))`.
- Orientiertes Volumen: `Summe(a Skalarprodukt (b Kreuzprodukt c)) / 6`.

Das Volumen ist das geometrische Materialvolumen des geschlossenen Modells, ohne Slicer-Infill oder Druckstuetzen.
Die Abmessungen beziehen sich auf die Exportlage, nicht automatisch auf die Einbaulage.

### Netzverbindungen

Punkte mit hoechstens `0.00001 mm` Abstand werden nur fuer die Auswertung zusammengefasst.
Die Originaldatei wird dabei nicht bearbeitet.

- Eine Kante mit nur einem Dreieck ist offen.
- Mehr als zwei Dreiecke an derselben Kante gelten als Netzfehler.
- Zwei Nachbardreiecke muessen ihre gemeinsame Kante in entgegengesetzter Richtung durchlaufen.
- Es werden zusammenhaengende Teile, doppelte Dreiecke und Dreiecke mit einer Flaeche unter `1e-10 mm2` gezaehlt.
- SHA-256-Pruefsummen erkennen, ob sich eine STL seit dem gespeicherten Bericht geaendert hat.

Damit werden die genannten Netzmerkmale geprueft. Selbstueberschneidungen und alle moeglichen Sonderfaelle an einzelnen Eckpunkten werden nicht untersucht.

### Becher, Tasche und Dummy

Am oberen Becherrand werden innerer und aeusserer Radius bestimmt. Die Wandstaerke ist deren Differenz.
Die Hoehe ergibt sich aus den Z-Grenzen. Die Bodendicke wird aus der Hoehe der flachen inneren Bodenflaeche bestimmt.

Bei der Dosierscheibe werden die Raender der oberen ebenen Flaeche gesucht.
Die Tasche wird anhand ihrer Breite zwischen 8 und 15 mm ausgewaehlt.
Ihr Rand wird als konvex vorausgesetzt. Dummy und Taschenkontur werden rechnerisch zentriert, mit parallelen Laengsachsen.
Der kleinste Abstand zur polygonalen Kontur ergibt rund `0.58951 mm`.
Die Scheibendicke minus Dummy-Hoehe ergibt rund `0.4 mm`; das ist keine Messung des Freiraums unter dem Deckel.

### Anschluss-Abmessungen

Die Schnittebenen und Suchbereiche im Skript stammen aus der Sichtung dieser Bauteile.
Sie legen fest, welche Flaechen verglichen werden. Es findet keine automatische Montage statt.

| Vergleich | Rechnung | Aussage |
|---|---|---|
| Kassettenboden / untere Platte | `(58 - 57.6) / 2` und `(68 - 67.6) / 2` | 0.2 mm je Seite bei gleicher Orientierung und zentriertem Einsatz. |
| Untere Platte / oberer Trichter | `(15.2 - 14.8) / 2` und `(11.2 - 10.8) / 2` | 0.2 mm je Seite bei zentrierter Lage. |
| Becher / obere Muldenoeffnung | ausgewaehlter Radius minus Becherradius | Rund 0.7 mm an der betrachteten Oberkante; keine Aussage ueber die Einsetztiefe. |

Fuer die Muldenoeffnung verwendet das Skript die angenommene Mitte `(95.5, 33)` und Punkte bei `Z = 6 mm`
mit einem Radius zwischen `18.49` und `18.51 mm`. Der Median dieser Auswahl ist eine eingeschraenkte Schaetzung.
Der Wert von rund `0.702 mm` ist deshalb kein unabhaengiger Nachweis der gesamten Becherpassung.
Diese Auswahl ist offen im Skript angegeben und wird bei geaenderten Bauteilen nicht automatisch neu bestimmt.

Die beiden anderen Anschlussvergleiche verwenden die Breite und Tiefe der Flaechen.
Ecken, Rastnasen, Einstecktiefen und alle Kontaktflaechen werden damit nicht vollstaendig verglichen.

## Ergebnis des Programmlaufs

- Rueckgabecode `0`: Die neu berechneten Felder stimmen mit dem Bericht ueberein; die Einzelteil-Netzpruefungen sind unauffaellig.
- Rueckgabecode `1`: Messwerte, Dateipruefsummen oder Netzmerkmale weichen ab.
- Rueckgabecode `2`: Eine Datei fehlt, ist ungueltig oder eine Berechnung konnte nicht ausgefuehrt werden.

Zahlen werden mit einer absoluten Toleranz von `0.00001` und einer relativen Toleranz von `1e-9` verglichen.
Zusaetzliche Angaben im Bericht, etwa Druckmengen, Entwurfsradien, fruehere Volumenvergleiche und der physische Teststatus,
sind dokumentierte Angaben und werden durch diesen Lauf nicht erneut ermittelt.

**Ein erfolgreicher Programmlauf bestaetigt keine vollstaendige Passung des Dispensers.**
Nicht enthalten sind eine Kollisionspruefung aller montierten Teile, eine Bewegungspruefung,
die Passung zum realen Motor und eine Passprobe der gedruckten Teile.
