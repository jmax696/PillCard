"""Ausgewaehlte Anschluss-Abmessungen vergleichen.

Die festgelegten Schnittebenen und Suchbereiche stammen aus der Sichtung
dieser Bauteile. Sie dienen der Auswahl der Merkmale, nicht als Messergebnis.
Es werden keine Bauteile zusammengesetzt und keine Kollisionen simuliert.
"""
from pathlib import Path
import numpy as np,json,hashlib
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
def obj(glob):
    p=find_one(root,glob);return p,read_stl(p)
def loops(mesh,z):
    planar=mesh[np.all(np.isclose(mesh[:,:,2],z,atol=1e-4),axis=1)]
    verts,inv=np.unique(np.round(planar[:,:,:2].reshape(-1,2),5),axis=0,return_inverse=True)
    edge_count=Counter(tuple(sorted((int(face[i]),int(face[(i+1)%3])))) for face in inv.reshape(-1,3) for i in range(3))
    adj=defaultdict(set)
    for (a,b),num in edge_count.items():
        if num==1:adj[a].add(b);adj[b].add(a)
    remaining=set(adj);result=[]
    while remaining:
        seed=remaining.pop();comp={seed};stack=[seed]
        while stack:
            for q in adj[stack.pop()]:
                if q not in comp:comp.add(q);remaining.discard(q);stack.append(q)
        result.append(verts[sorted(comp)])
    return result
def box(points):return [points.min(0),points.max(0)]
def select(loops,lo,hi):
    matches=[x for x in loops if np.all(np.ptp(x,axis=0)>=lo) and np.all(np.ptp(x,axis=0)<=hi)]
    assert len(matches)==1,(lo,hi,[(len(x),np.ptp(x,axis=0).tolist()) for x in loops])
    return matches[0]
def clearance(size_outer,size_inner):return np.round((size_outer-size_inner)/2,3).tolist()
module,base=obj('01_Kassetten*.stl');plate_path,plate=obj('04_Untere*.stl');funnel_path,funnel=obj('07_Trichter*.stl');cup_path,cup=obj('B01*.stl');bed_path,bed=obj('H01*.stl')
base_seat=select(loops(base,13.9),[55,65],[60,70]);plate_tongue=select(loops(plate,0),[55,65],[60,70])
base_size=np.ptp(base_seat,axis=0);plate_size=np.ptp(plate_tongue,axis=0)
assert np.allclose(base_size,[58,68],atol=.001) and np.allclose(plate_size,[57.6,67.6],atol=.001)
plate_opening=select(loops(plate,6),[12,9],[17,13]);funnel_neck=select(loops(funnel,0),[12,9],[16,12])
opening_size=np.ptp(plate_opening,axis=0);neck_size=np.ptp(funnel_neck,axis=0)
assert np.allclose(opening_size,[15.2,11.2],atol=.001) and np.allclose(neck_size,[14.8,10.8],atol=.001)
cup_vertices=cup.reshape(-1,3)
cup_r=round(float(np.ptp(cup_vertices[:,0]))/2,4)
# Boundary points of the circular cup recess on the base plate top; cable channels make the full perimeter one connected loop.
v=bed.reshape(-1,3);center=np.array([95.5,33.]);rad=np.linalg.norm(v[:,:2]-center,axis=1)
top_ring=(np.isclose(v[:,2],6,atol=1e-5))&(rad>=18.49)&(rad<=18.51)
assert top_ring.sum()>20
bed_mouth_radius=float(np.median(rad[top_ring]))
checks={
 'scope':'Nominelle Geometrie der vorhandenen STLs; keine Montage- oder Druckpassung bewiesen',
 'module_base_and_lower_plate':{'recess_xy_mm':base_size.tolist(),'tongue_xy_mm':plate_size.tolist(),'nominal_xy_clearance_per_side_mm':clearance(base_size,plate_size),'condition':'Gleiche XY-Orientierung und zentrierter Einsatz. Tiefe, Rastung und reale Passung nicht geprüft.'},
 'lower_plate_and_upper_funnel':{'opening_xy_mm':opening_size.tolist(),'funnel_end_xy_mm':neck_size.tolist(),'nominal_xy_clearance_per_side_mm':clearance(opening_size,neck_size),'condition':'Zentrierte XY-Ausrichtung vorausgesetzt; vollständige Kontaktgeometrie und Einbaulage nicht geprüft.'},
 'cup_and_base_plate':{'cup_outer_radius_mm':cup_r,'base_plate_top_mouth_radius_mm':round(bed_mouth_radius,3),'nominal_radial_clearance_at_top_mm':round(bed_mouth_radius-cup_r,3),'condition':'Nur Öffnung der Mulde an ihrer Oberkante; tieferer Verlauf und eingesetzte Becherhöhe nicht geprüft.'},
 'unverified_interfaces':['Seitenrahmen zu Bodenplatte und Servoplatte','Motor-Steckhalter zu Servoplatte','Dosierscheibe zu Kassettenboden und Abstreifdeckel in Betriebsstellung','Wellenadapter zu Motor und Dosierscheibe','beide Trichter zur Innenhalterung und zum Becher','vollständige Baugruppe und Drucktoleranzen'],
 'conclusion':'Teilweise passende Nennmasse ermittelt; dass alle 3D-Druckteile zusammenpassen, bleibt unbewiesen.'}
args.ausgabe.write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(checks,ensure_ascii=False,indent=2))
