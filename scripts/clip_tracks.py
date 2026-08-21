"""Clip each track to the forest side of the two known gateways.

Gateway 1: main forest entrance.  Gateway 2: road popout shortcut to home.
Everything before the first gateway crossing and after the last is the walk
to and from the condo -- removed for privacy and for honest coverage stats.

The cut is made at the point of *closest approach* to the gateway, not at the
first point inside the proximity radius.  Cutting on the radius left a ~30 m
stub of approach road hanging off every clipped end -- sixteen of them fanning
out of the entrance.  Within the touch cluster the nearest vertex is the
crossing itself; the endpoint is then interpolated onto the exact perpendicular
foot so all eight walks terminate on the same node.
"""
import json, math, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATES = [(-72.974760, 44.504441), (-72.974428, 44.503235)]
NEAR = 30.0     # metres, gateway proximity -- defines a touch, not the cut
GAP = 5         # points, max break within a single gateway touch
HOME = (-72.973008, 44.503533)   # convergence point of all track endpoints
HOME_R = 100.0  # metres, hard exclusion radius around it

LAT0 = 44.5018
MLAT, MLON = 111132.0, 111320.0*math.cos(math.radians(LAT0))
def xy(c): return (c[0]*MLON, c[1]*MLAT)
G = [xy(g) for g in GATES]
H = xy(HOME)

def split_home(pts):
    """Drop any run of points inside HOME_R; return the surviving runs."""
    runs, cur = [], []
    for c in pts:
        if math.dist(xy(c), H) >= HOME_R:
            cur.append(c)
        else:
            if len(cur) > 9: runs.append(cur)
            cur = []
    if len(cur) > 9: runs.append(cur)
    return runs

def clusters(idxs):
    """Group contiguous hit indices into separate gateway touches."""
    cl = []
    for i in idxs:
        if cl and i - cl[-1][-1] <= GAP: cl[-1].append(i)
        else: cl.append([i])
    return cl

def foot(co, i, g):
    """Point on the polyline nearest gateway `g`, on a segment adjoining vertex i.

    The vertices sit ~0.8 m apart, so this is a sub-metre correction -- but it
    puts the terminal node on the gateway rather than beside it.
    """
    best = (math.dist(xy(co[i]), g), co[i])
    for j in (i-1, i):
        if j < 0 or j+1 >= len(co): continue
        p, q = xy(co[j]), xy(co[j+1])
        vx, vy = q[0]-p[0], q[1]-p[1]
        L2 = vx*vx + vy*vy
        if L2 == 0: continue
        t = max(0.0, min(1.0, ((g[0]-p[0])*vx + (g[1]-p[1])*vy) / L2))
        c = [co[j][0] + t*(co[j+1][0]-co[j][0]),
             co[j][1] + t*(co[j+1][1]-co[j][1])]
        d = math.dist(xy(c), g)
        if d < best[0]: best = (d, c)
    return best[1]

def length(pts):
    q = [xy(c) for c in pts]
    return sum(math.dist(q[i], q[i+1]) for i in range(len(q)-1))

tracks = json.loads((ROOT/"data/raw_tracks.geojson").read_text(encoding="utf-8"))
out, rows, tails = [], [], []

for f in tracks["features"]:
    co = f["geometry"]["coordinates"]
    P = [xy(c) for c in co]
    near = [min(range(len(G)), key=lambda j: math.dist(p, G[j])) for p in P]
    d = [math.dist(P[i], G[near[i]]) for i in range(len(P))]
    hits = [i for i, v in enumerate(d) if v <= NEAR]
    name = f["properties"]["name"][:10]
    full = length(co)

    if not hits:
        rows.append((name, full/1000, 0.0, 0, "NO GATEWAY TOUCH - dropped"))
        continue
    cl = clusters(hits)
    if len(cl) < 2:
        rows.append((name, full/1000, 0.0, 0, "only one gateway touch - dropped"))
        continue

    # Cut at closest approach within the first and last touch, not on the radius.
    a = min(cl[0], key=lambda i: d[i])
    b = min(cl[-1], key=lambda i: d[i])
    if b - a < 10:
        rows.append((name, full/1000, 0.0, 0, "too short after clip - dropped"))
        continue

    # How much stub the old radius-edge cut would have left dangling.
    tails.append((name, length(co[cl[0][0]:a+1]), length(co[b:cl[-1][-1]+1])))

    kept = [foot(co, a, G[near[a]])] + co[a+1:b] + [foot(co, b, G[near[b]])]
    runs = split_home(kept)
    if not runs:
        rows.append((name, full/1000, 0.0, 0, "nothing outside home radius - dropped"))
        continue
    kl = sum(length(r) for r in runs)
    rows.append((name, full/1000, kl/1000, sum(len(r) for r in runs),
                 f"clipped {full-kl:.0f} m ({100*(full-kl)/full:.0f}%)"
                 + (f", {len(runs)} parts" if len(runs) > 1 else "")))
    for n, r in enumerate(runs):
        # Rebuild properties from scratch. The source filename encodes a personal
        # name and the exact minute of the walk, so nothing is carried over.
        label = f"walk-{len(out)+1:02d}"
        p = {"name": label,
             "distance_km": round(length(r)/1000, 3),
             "points": len(r),
             "clipped": True}
        if len(runs) > 1: p["part"] = n+1
        out.append({"type": "Feature", "properties": p,
                    "geometry": {"type": "LineString", "coordinates": r}})

print(f"{'track':12}{'raw km':>9}{'kept km':>9}{'pts':>7}  note")
for r in rows:
    print(f"{r[0]:12}{r[1]:>9.2f}{r[2]:>9.2f}{r[3]:>7}  {r[4]}")

rk = sum(r[1] for r in rows); kk = sum(r[2] for r in rows)
print(f"\n{'TOTAL':12}{rk:>9.2f}{kk:>9.2f}")
print(f"removed {rk-kk:.2f} km of approach walking ({100*(rk-kk)/rk:.0f}%)")
print(f"{len(out)} segments retained from {len(tracks['features'])} tracks")

ts = sum(t[1]+t[2] for t in tails)
print(f"\ntails removed: {2*len(tails)} stubs, {ts:.0f} m total, "
      f"longest {max(max(t[1],t[2]) for t in tails):.1f} m")

# Every endpoint should now sit on a gateway node, not on the proximity circle.
print(f"\n{'segment':12}{'end A -> gate':>16}{'end B -> gate':>16}{'min home':>11}")
for f in out:
    c = f["geometry"]["coordinates"]
    ea = min(math.dist(xy(c[0]), g) for g in G)
    eb = min(math.dist(xy(c[-1]), g) for g in G)
    mh = min(math.dist(xy(p), H) for p in c)
    print(f"{f['properties']['name']:12}{ea:>15.1f}m{eb:>15.1f}m{mh:>10.1f}m")

lats = [c[1] for f in out for c in f["geometry"]["coordinates"]]
lons = [c[0] for f in out for c in f["geometry"]["coordinates"]]
print(f"\nforest-only bbox  S={min(lats):.6f} W={min(lons):.6f} "
      f"N={max(lats):.6f} E={max(lons):.6f}")
ns = (max(lats)-min(lats))*MLAT/1000
ew = (max(lons)-min(lons))*MLON/1000
print(f"extent {ns:.2f} km N-S x {ew:.2f} km E-W")

(ROOT/"data/forest_tracks.geojson").write_text(
    json.dumps({"type":"FeatureCollection","features":out}))
print("\nwrote data/forest_tracks.geojson (timestamps stripped)")
