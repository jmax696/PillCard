"""Becher, Dosiertasche und mittig ausgerichteten Dummy vermessen.

Konturvergleich in 2D, keine Simulation eines drehenden oder montierten Modells.
Die Taschenkontur wird als konvex vorausgesetzt.
"""
from pathlib import Path
import numpy as np,json
from scipy.spatial import ConvexHull
from collections import Counter,defaultdict
import argparse
from pathlib import Path
from stl_io import read_stl, find_one, validate_output

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--modelle', type=Path, default=Path(__file__).resolve().parent.parent)
parser.add_argument('--ausgabe', type=Path, required=True)
args = parser.parse_args()
root = args.modelle.resolve()
validate_output(args.ausgabe)

dt=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('a','<u2')])
def mesh(p): return read_stl(p)
t=mesh(find_one(root,'03_Dosier*.stl'))
top=t[np.all(np.isclose(t[:,:,2],t[:,:,2].max(),atol=1e-5),axis=1)]
v,inv=np.unique(np.round(top[:,:,:2].reshape(-1,2),5),axis=0,return_inverse=True)
edges=Counter(tuple(sorted((int(f[i]),int(f[(i+1)%3])))) for f in inv.reshape(-1,3) for i in range(3))
adj=defaultdict(set)
for (a,b),n in edges.items():
    if n==1: adj[a].add(b);adj[b].add(a)
remaining=set(adj); loops=[]
while remaining:
    seed=remaining.pop(); component={seed}; stack=[seed]
    while stack:
        for b in adj[stack.pop()]:
            if b not in component: component.add(b);remaining.discard(b);stack.append(b)
    loops.append(v[sorted(component)])
sizes=[np.ptp(loop,axis=0).tolist() for loop in loops]
pocket=next(loop for loop in loops if 8<np.ptp(loop,axis=0)[0]<15)
pocket_center=(pocket.max(0)+pocket.min(0))/2
eq=ConvexHull(pocket-pocket_center).equations
dummy=mesh(find_one(root,'Pillen_Dummy*.stl')).reshape(-1,3)
xy=dummy[:,:2]-(dummy[:,:2].max(0)+dummy[:,:2].min(0))/2
# Abstand zu den Kanten der konvexen Taschenkontur; positive Werte bedeuten innen.
clearance=float(-(xy@eq[:,:2].T+eq[:,2]).max())
cup_tri=mesh(find_one(root,'B01*.stl'))
cup=cup_tri.reshape(-1,3)
cup_height=float(np.ptp(cup[:,2]))
dummy_height=float(np.ptp(dummy[:,2]))
center=(cup[:,:2].max(0)+cup[:,:2].min(0))/2
topxy=cup[np.isclose(cup[:,2],cup[:,2].max())][:,:2]
radii=np.linalg.norm(topxy-center,axis=1)
inner=float(radii.min()); outer=float(radii.max())
# Der flache Innenboden zeigt nach oben und liegt unterhalb des Becherrands.
normals=np.cross(cup_tri[:,1]-cup_tri[:,0],cup_tri[:,2]-cup_tri[:,0])
flat=np.ptp(cup_tri[:,:,2],axis=1)<1e-5
inside=np.linalg.norm(cup_tri.mean(axis=1)[:,:2]-center,axis=1)<inner*.95
floor=cup_tri[flat & inside & (normals[:,2]>1e-8)]
if len(floor)==0:
    raise ValueError('Innenboden des Bechers nicht eindeutig gefunden')
bottom=float(floor[:,:,2].min()-cup[:,2].min())
features={'cup':{'outer_diameter_mm':round(2*outer,4),'inner_diameter_mm':round(2*inner,4),'wall_mm':round(outer-inner,4),'bottom_mm':round(bottom,4),'height_mm':round(cup_height,4),'z_planes_mm':np.unique(np.round(cup[:,2],4)).tolist()},
          'disc_top_boundary_sizes_mm':sizes,'pocket_size_xy_mm':np.ptp(pocket,axis=0).tolist(),'pocket_center_xy_mm':pocket_center.tolist(),
          'disc_thickness_mm':float(np.ptp(t[:,:,2])),'dummy_height_mm':dummy_height,'nominal_thickness_margin_mm':round(float(np.ptp(t[:,:,2]))-dummy_height,5),
          'centered_aligned_dummy_min_profile_clearance_mm':round(clearance,5),
          'profile_fit_scope':'2D convex pocket profile, centered and parallel XY axes, nominal STL geometry only; not full assembly or dispensing validation'}
assert clearance>0
args.ausgabe.write_text(json.dumps(features,indent=2))
print(json.dumps(features,indent=2))
