"""Binaere STL-Dateien nur lesen; keine Aenderung der Quelldateien."""
import struct
from pathlib import Path
import numpy as np

DTYPE = np.dtype([('normal', '<f4', (3,)), ('vertices', '<f4', (3, 3)), ('attribute', '<u2')])

def validate_output(path):
    path = Path(path).resolve()
    if path.suffix.lower() != '.json' or path.exists():
        raise ValueError('Ausgabe muss eine neue JSON-Datei sein; vorhandene Dateien werden nicht ersetzt')
    path.parent.mkdir(parents=True, exist_ok=True)

def find_one(root, pattern):
    matches = sorted(Path(root).rglob(pattern))
    if len(matches) != 1:
        raise ValueError(f'Erwartet genau eine Datei fuer {pattern}, gefunden: {len(matches)}')
    return matches[0]

def read_stl(path):
    data = Path(path).read_bytes()
    if len(data) < 84:
        raise ValueError(f'Keine vollstaendige binaere STL: {path}')
    count = struct.unpack_from('<I', data, 80)[0]
    if count == 0 or len(data) != 84 + count * 50:
        raise ValueError(f'Ungueltige binaere STL oder nicht unterstuetzte ASCII-STL: {path}')
    triangles = np.frombuffer(data, dtype=DTYPE, offset=84)['vertices'].astype(float)
    if not np.isfinite(triangles).all():
        raise ValueError(f'Ungueltige Koordinaten: {path}')
    return triangles
