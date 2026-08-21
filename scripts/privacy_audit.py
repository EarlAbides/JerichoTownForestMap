"""Scan every committable file for coordinates near the home convergence point."""
import json, math, pathlib, re, sys

ROOT=pathlib.Path(__file__).resolve().parent.parent
HOME=(-72.973008, 44.503533)
R=100.0
LAT0=44.5018; MLAT,MLON=111132.0,111320.0*math.cos(math.radians(LAT0))
H=(HOME[0]*MLON, HOME[1]*MLAT)
def d(lon,lat): return math.dist((lon*MLON,lat*MLAT),H)

IGNORED={"Exports","raw_tracks.geojson",".venv",".git","cache","__pycache__"}
PAIR=re.compile(r'\[\s*(-7[23]\.\d{3,})\s*,\s*(4[45]\.\d{3,})\s*\]')
NAME=re.compile(r'Jeffrey', re.I)
STAMP=re.compile(r'20\d\d-\d\d-\d\d-\d{6}')
FITF=re.compile(r'\.fit')

rows=[]
for p in sorted(ROOT.rglob("*")):
    if not p.is_file(): continue
    rel=p.relative_to(ROOT).as_posix()
    if any(part in IGNORED for part in p.parts): continue
    if p.suffix.lower() not in (".geojson",".json",".html",".js"): continue
    if rel.startswith("docs/tiles"): continue
    try: txt=p.read_text(encoding="utf-8")
    except Exception: continue
    # identifying strings, not just coordinates
    ident=[]
    for pat,label in ((NAME,"personal name"),(STAMP,"walk timestamp"),
                      (FITF,"source filename")):
        n=len(pat.findall(txt))
        if n: ident.append(f"{label} x{n}")
    hits=[(float(a),float(b)) for a,b in PAIR.findall(txt)]
    if not hits and not ident: continue
    if not hits:
        rows.append((rel,0,float("inf"),0,"; ".join(ident))); continue
    dists=[d(lon,lat) for lon,lat in hits]
    near=sum(1 for x in dists if x<R)
    rows.append((rel,len(hits),min(dists),near,"; ".join(ident)))

print(f"home = {HOME[1]:.6f}, {HOME[0]:.6f}   exclusion radius {R:.0f} m\n")
print(f"{'file':40}{'coords':>7}{'closest':>10}{'in':>5}  status")
worst=0
for rel,n,mn,near,ident in rows:
    bad = (mn < R) or bool(ident)
    worst = max(worst, near + (1 if ident else 0))
    cl = "  n/a" if mn==float("inf") else f"{mn:>8.1f}m"
    note = ("LEAK: "+ident) if ident else ("LEAK" if mn<R else "ok")
    print(f"{rel:40}{n:>7}{cl}{near:>5}  {note}")
print()
sys.exit(1 if worst else 0)
