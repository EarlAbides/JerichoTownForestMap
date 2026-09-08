"""Find places where the merged network is probably broken, for human review.

Three different faults make a trail look disconnected on the map, and they need
different fixes, so they are detected and labelled separately:

  weld  a chain ends within GAP_MAX of another trail and the raw GPS shows
        walks running straight through the gap.  The corridor failed to fuse.
        A gap with no walks crossing it is NOT reported -- that is two real
        trails that happen to pass close, which is exactly what MATCH_R exists
        to keep apart.
  zero  a segment carrying passes == 0.  Draws as nothing, so a busy trail gets
        a hole punched in it.  Always a bug: the segment exists because fixes
        made it exist.
  dip   a short segment whose pass count sits far below BOTH its neighbours.
        Same visual symptom as zero, same suspected cause -- the count is
        sampled at a junction centroid that sits too far from any real fix.

Output is data/gap_candidates.geojson, one Point per candidate, ranked so the
most confident bugs come first.  build_map.py draws them as numbered rings in
the audit overlay; nothing here changes the trail network itself.  Reviewing
them is a human job -- this script only narrows 173 segments down to a handful.
"""
import json, math, pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent

GAP_MAX   = 30.0   # m, furthest dangling end we bother testing
BRIDGE_R  = 6.0    # m, a fix this close to the gap line counts as crossing it
MIN_WALKS = 2      # distinct walks through a gap before it is called a bug
DIP_LEN   = 12.0   # m, only short segments can be a junction artefact.
                   # Matches SPUR in merge_passes -- the same "shorter than
                   # this is a thinning artefact" line.  Calibrated against
                   # ground truth: the user called a 3.4 m dip a real break
                   # and a 20.4 m one normal variation between busy trails.
DIP_DROP  = 3      # passes below both neighbours to count as a dip

LAT0 = 44.5018
MLAT, MLON = 111132.0, 111320.0*math.cos(math.radians(LAT0))
def xy(c): return (c[0]*MLON, c[1]*MLAT)
def ll(p): return [round(p[0]/MLON, 7), round(p[1]/MLAT, 7)]
def plen(P): return sum(math.dist(P[i], P[i+1]) for i in range(len(P)-1))

merged = json.loads((ROOT/"data/trails_merged.geojson").read_text(encoding="utf-8"))
tracks = json.loads((ROOT/"data/forest_tracks.geojson").read_text(encoding="utf-8"))

segs = []
for i, f in enumerate(merged["features"]):
    P = [xy(c) for c in f["geometry"]["coordinates"]]
    segs.append({"i": i, "P": P, "passes": f["properties"]["passes"], "len": plen(P)})

# ------------------------------------------------------------ raw fixes
fixes = []
for f in tracks["features"]:
    g = f["geometry"]
    parts = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
    name = f["properties"]["name"]
    for line in parts:
        for c in line: fixes.append((xy(c), name))

HB = 15.0
hashed = defaultdict(list)
for p, w in fixes: hashed[(int(p[0]//HB), int(p[1]//HB))].append((p, w))

def walks_near(p, r):
    """Names of the walks with a fix within r of p."""
    bx, by = int(p[0]//HB), int(p[1]//HB)
    n = int(r//HB) + 1
    out = set()
    for i in range(bx-n, bx+n+1):
        for j in range(by-n, by+n+1):
            for q, w in hashed.get((i, j), ()):
                if math.dist(p, q) <= r: out.add(w)
    return out

def crossing_walks(a, b):
    """Walks with a fix near EVERY quarter point of the gap, so they really
    traversed it rather than just brushing one end."""
    sets = []
    for t in (0.25, 0.5, 0.75):
        sets.append(walks_near((a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t), BRIDGE_R))
    return set.intersection(*sets)

# ------------------------------------------------------- node bookkeeping
def key(p): return (round(p[0], 1), round(p[1], 1))
node = defaultdict(set)
for s in segs:
    node[key(s["P"][0])].add(s["i"]); node[key(s["P"][-1])].add(s["i"])

def pt_seg(p, a, b):
    px, py = p[0]-a[0], p[1]-a[1]
    vx, vy = b[0]-a[0], b[1]-a[1]
    L2 = vx*vx + vy*vy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, (px*vx+py*vy)/L2))
    return math.hypot(px-t*vx, py-t*vy), (a[0]+t*vx, a[1]+t*vy)

cands = []

# ------------------------------------------------------------ weld faults
for s in segs:
    for p in (s["P"][0], s["P"][-1]):
        if len(node[key(p)]) != 1:          # already joined to something
            continue
        best = (math.inf, None, None)
        for o in segs:
            if o["i"] == s["i"]: continue
            for k in range(len(o["P"])-1):
                d, q = pt_seg(p, o["P"][k], o["P"][k+1])
                if d < best[0]: best = (d, o, q)
        d, o, q = best
        if d > GAP_MAX: continue
        w = crossing_walks(p, q)
        if len(w) < MIN_WALKS: continue
        cands.append({
            "kind": "weld", "at": p, "bridge": [ll(p), ll(q)],
            "gap_m": round(d, 1), "passes": [s["passes"], o["passes"]],
            "walks": len(w), "segs": [s["i"], o["i"]],
            "why": f"{len(w)} walks cross a {d:.1f} m gap between "
                   f"{s['passes']}- and {o['passes']}-pass trail",
            "score": (2, min(s["passes"], o["passes"]), len(w)),
        })

# -------------------------------------------------------- zero / dip faults
for s in segs:
    nb = []
    for p in (s["P"][0], s["P"][-1]):
        other = [segs[j]["passes"] for j in node[key(p)] if j != s["i"]]
        if other: nb.append(max(other))
    mid = s["P"][len(s["P"])//2]
    if s["passes"] == 0:
        cands.append({
            "kind": "zero", "at": mid, "bridge": None,
            "gap_m": 0.0, "passes": nb, "walks": len(walks_near(mid, 8.0)),
            "segs": [s["i"]],
            "why": f"{s['len']:.1f} m segment counts 0 passes beside "
                   f"{nb or '?'}-pass trail -- draws as nothing",
            "score": (3, max(nb or [0]), 0),
        })
    elif len(nb) == 2 and s["len"] < DIP_LEN and min(nb) - s["passes"] >= DIP_DROP:
        cands.append({
            "kind": "dip", "at": mid, "bridge": None,
            "gap_m": 0.0, "passes": nb, "walks": len(walks_near(mid, 8.0)),
            "segs": [s["i"]],
            "why": f"{s['len']:.1f} m segment drops to {s['passes']} passes "
                   f"between {nb[0]}- and {nb[1]}-pass trail",
            "score": (1, min(nb), 0),
        })

cands.sort(key=lambda c: c["score"], reverse=True)

feats = []
for n, c in enumerate(cands, 1):
    feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": ll(c["at"])},
                  "properties": {"id": n, "kind": c["kind"], "gap_m": c["gap_m"],
                                 "passes": c["passes"], "walks": c["walks"],
                                 "segs": c["segs"], "why": c["why"],
                                 "bridge": c["bridge"]}})

out = {"type": "FeatureCollection", "features": feats}
(ROOT/"data/gap_candidates.geojson").write_text(json.dumps(out), encoding="utf-8")

by = defaultdict(int)
for c in cands: by[c["kind"]] += 1
print(f"gap candidates: {len(cands)}  " +
      "  ".join(f"{k}={by[k]}" for k in ("weld", "zero", "dip") if by[k]))
for n, c in enumerate(cands, 1):
    print(f"  {n:2}. [{c['kind']:4}] {c['why']}")
print("wrote data/gap_candidates.geojson")
