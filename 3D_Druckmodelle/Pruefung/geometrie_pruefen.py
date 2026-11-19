"""Geometrie der STL-Dateien: Aussenmasse, Volumen und Netzverbindungen.

Entspricht der verwendeten Einzelteilpruefung, ohne die Vorschau-Erzeugung.
Alle Messwerte werden aus den STL-Dateien berechnet.
"""
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from collections import Counter
import hashlib,json

import argparse
from pathlib import Path
from stl_io import read_stl, find_one, validate_output

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--modelle', type=Path, default=Path(__file__).resolve().parent.parent)
parser.add_argument('--ausgabe', type=Path, required=True)
args = parser.parse_args()
root = args.modelle.resolve()
validate_output(args.ausgabe)

dtype=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attribute','<u2')])
results=[]
for p in sorted(root.rglob('*.stl')):
    data=p.read_bytes(); count=int.from_bytes(data[80:84],'little')
    assert len(data)==84+count*50
    t=read_stl(p)
    coords,inv=np.unique(t.reshape(-1,3),axis=0,return_inverse=True)
    # Weld coordinates within 0.00001 mm solely for connectivity inspection.
    parent=np.arange(len(coords))
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]; i=parent[i]
        return int(i)
    for i,j in cKDTree(coords).query_pairs(1e-5):
        parent[find(j)]=find(i)
    mapping=np.array([find(i) for i in range(len(coords))]); faces=mapping[inv].reshape(-1,3)
    # Eine geschlossene Kante muss genau zwei anliegende Dreiecke haben.
    edges=Counter(tuple(sorted((int(f[i]),int(f[(i+1)%3])))) for f in faces for i in range(3))
    directed=Counter((int(f[i]),int(f[(i+1)%3])) for f in faces for i in range(3))
    badwinding=sum(1 for (a1,b),n in edges.items() if n==2 and directed[(a1,b)]!=directed[(b,a1)])
    areas=np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)/2
    # V = Summe(a dot (b cross c)) / 6: orientiertes Modellvolumen.
    volume=np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])).sum()/6
    unique_welded=len(set(mapping.tolist()))
    for a1,b in edges: parent[find(b)]=find(a1)
    comps=len(set(find(int(i)) for i in mapping))
    info={'file':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(data).hexdigest(),
          'size_bytes':len(data),'triangles':count,'dimensions_xyz_mm':np.round(np.ptp(t.reshape(-1,3),axis=0),6).tolist(),
          'bounds_min_mm':t.reshape(-1,3).min(0).tolist(),'bounds_max_mm':t.reshape(-1,3).max(0).tolist(),
          'signed_volume_mm3':round(float(volume),6),'unique_vertices_after_weld':unique_welded,'connected_components':comps,
          'boundary_edges':sum(n==1 for n in edges.values()),'nonmanifold_edges':sum(n>2 for n in edges.values()),
          'inconsistent_winding_edges':badwinding,'degenerate_triangles':int((areas<1e-10).sum()),
          'duplicate_triangles':len(faces)-len(set(tuple(sorted(f)) for f in faces))}
    results.append(info)
    print(p.name,info['dimensions_xyz_mm'],'vol',round(volume,3),'boundary',info['boundary_edges'],'nonmanifold',info['nonmanifold_edges'],'winding',badwinding,'degenerate',info['degenerate_triangles'],'components',comps)
args.ausgabe.write_text(json.dumps(results,indent=2))
