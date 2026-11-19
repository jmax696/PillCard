"""Berechnungen wiederholen und mit der vorhandenen PRUEFUNGSERGEBNIS.json vergleichen."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent

def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*.stl'))}

def differences(actual, expected, path=''):
    """Nur neu berechnete Felder vergleichen; alte Metadaten sind keine Rechnung."""
    problems = []
    if isinstance(actual, dict):
        if not isinstance(expected, dict):
            return [path + ': falscher Datentyp']
        for key, value in actual.items():
            if key not in expected:
                problems.append(path + '/' + key + ': fehlt im Bericht')
            else:
                problems.extend(differences(value, expected[key], path + '/' + key))
    elif isinstance(actual, list):
        if not isinstance(expected, list) or len(actual) != len(expected):
            return [path + ': unterschiedliche Listenlaenge']
        if path.endswith('disc_top_boundary_sizes_mm'):
            actual, expected = sorted(actual), sorted(expected)
        for i, (a, b) in enumerate(zip(actual, expected)):
            problems.extend(differences(a, b, path + f'/{i}'))
    elif isinstance(actual, (int, float)) and not isinstance(actual, bool):
        if not isinstance(expected, (int, float)) or not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-5):
            problems.append(f'{path}: berechnet {actual}, Bericht {expected}')
    elif actual != expected:
        problems.append(f'{path}: abweichender Wert')
    return problems

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modelle', type=Path, default=HERE.parent, help='Ordner mit STLs und PRUEFUNGSERGEBNIS.json')
    parser.add_argument('--ausgabe', type=Path, help='Optional: neu berechnete Ergebnisse separat speichern')
    args = parser.parse_args()
    root = args.modelle.resolve()
    before = hashes(root)
    if not before:
        raise ValueError('Keine STL-Dateien gefunden')
    output = args.ausgabe.resolve() if args.ausgabe else None
    if output and (output == (root/'PRUEFUNGSERGEBNIS.json').resolve() or output.suffix.lower() == '.stl' or output.exists()):
        raise ValueError('Ausgabe muss eine neue Datei sein und darf weder PRUEFUNGSERGEBNIS.json noch eine STL ersetzen')
    reference = json.loads((root/'PRUEFUNGSERGEBNIS.json').read_text(encoding='utf-8'))
    actual = {}
    with tempfile.TemporaryDirectory(prefix='stl_pruefung_') as temp:
        for script, key in [('geometrie_pruefen.py', 'parts'), ('merkmale_pruefen.py', 'measured_features'),
                            ('anschluesse_pruefen.py', 'nominal_interface_checks')]:
            target = Path(temp)/(key+'.json')
            process = subprocess.run([sys.executable, '-B', str(HERE/script), '--modelle', str(root), '--ausgabe', str(target)], capture_output=True, text=True, encoding='utf-8', errors='replace')
            if process.returncode:
                raise RuntimeError(f'{script} fehlgeschlagen:\n{process.stderr or process.stdout}')
            actual[key] = json.loads(target.read_text(encoding='utf-8'))
            print(script + ': berechnet')
    if hashes(root) != before:
        raise RuntimeError('STL-Pruefsummen haben sich waehrend des Laufs geaendert')
    actual['parts'].sort(key=lambda x: x['file'])
    reference['parts'].sort(key=lambda x: x['file'])
    problems = differences(actual, reference)
    for part in actual['parts']:
        if part['connected_components'] != 1 or part['signed_volume_mm3'] <= 0 or any(part[k] for k in ('boundary_edges','nonmanifold_edges','inconsistent_winding_edges','degenerate_triangles','duplicate_triangles')):
            problems.append(part['file'] + ': auffaelliges STL-Netz')
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({'calculated':actual, 'differences':problems},ensure_ascii=False,indent=2).replace('ss','ss')+'\n',encoding='utf-8')
    if problems:
        print('\n'.join(problems))
        return 1
    print(f'{len(actual["parts"])} STL-Dateien: Berechnungen stimmen mit PRUEFUNGSERGEBNIS.json ueberein.')
    print('STL-Dateien unveraendert. Keine Bestaetigung der Passung des gesamten Zusammenbaus.')
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
