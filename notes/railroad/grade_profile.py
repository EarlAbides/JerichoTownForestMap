"""Sample VCGI QL1 LiDAR bare-earth DEM along each track; find engineered grades.

A railroad grade holds a near-constant, very low gradient and a large, steady
curve radius. An esker undulates and meanders. This separates them.
"""
import json, math, pathlib, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEM = ("https://maps.vcgi.vermont.gov/arcgis/rest/services/EGC_services/"
       "IMG_VCGI_LIDARDEM_SP_NOCACHE_v1/ImageServer/getSamples")
LAT0 = 44.5018
MLAT, MLON = 111132.0, 111320.0 * math.cos(math.radians(LAT0))
STEP = 12.0          # metres between samples
BATCH = 100

def xy(c): return (c[0]*MLON, c[1]*MLAT)

def resample(coords, step=STEP):
    """Walk the polyline emitting a point every `step` metres."""
    pts = [xy(c) for c in coords]
    out, acc = [coords[0]], 0.0
    for i in range(len(pts)-1):
        seg = math.dist(pts[i], pts[i+1])
        if seg == 0: continue
        t = step - acc
        while t <= seg:
            f = t/seg
            out.append([coords[i][0]+(coords[i+1][0]-coords[i][0])*f,
                        coords[i][1]+(coords[i+1][1]-coords[i][1])*f])
            t += step
        acc = (acc + seg) % step
    return out

def sample_dem(points):
    vals = []
    for i in range(0, len(points), BATCH):
        chunk = points[i:i+BATCH]
        body = urllib.parse.urlencode({
            "geometry": json.dumps({"points": [[p[0], p[1]] for p in chunk],
                                    "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryMultipoint",
            "returnFirstValueOnly": "true", "f": "json"}).encode()
        req = urllib.request.Request(DEM, data=body,
                                     headers={"User-Agent": "ForestMap/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.load(r)
        got = {s["locationId"]: float(s["value"]) for s in d.get("samples", [])
               if s.get("value") not in (None, "NoData")}
        vals += [got.get(j) for j in range(len(chunk))]
        time.sleep(0.25)
    return vals

def curve_radius(pts, i, span):
    """Circumradius through three points spaced `span` indices apart."""
    if i-span < 0 or i+span >= len(pts): return None
    a, b, c = xy(pts[i-span]), xy(pts[i]), xy(pts[i+span])
    ax,ay=a; bx,by=b; cx,cy=c
    d = 2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
    if abs(d) < 1e-9: return float('inf')
    ux = ((ax**2+ay**2)*(by-cy)+(bx**2+by**2)*(cy-ay)+(cx**2+cy**2)*(ay-by))/d
    uy = ((ax**2+ay**2)*(cx-bx)+(bx**2+by**2)*(ax-cx)+(cx**2+cy**2)*(bx-ax))/d
    return math.hypot(ax-ux, ay-uy)

tracks = json.loads((ROOT/"data/forest_tracks.geojson").read_text(encoding="utf-8"))
report, out_feats = [], []

for f in tracks["features"]:
    name = f["properties"]["name"][:10]
    pts = resample(f["geometry"]["coordinates"])
    if len(pts) < 20: continue
    elev = sample_dem(pts)
    # cumulative distance
    dist = [0.0]
    for i in range(len(pts)-1):
        dist.append(dist[-1] + math.dist(xy(pts[i]), xy(pts[i+1])))

    WIN = 10   # 10 samples * 12 m = 120 m rolling window
    best = []
    for i in range(len(pts)-WIN):
        seg_e = elev[i:i+WIN+1]
        if any(e is None for e in seg_e): continue
        run = dist[i+WIN]-dist[i]
        if run < 1: continue
        rise = seg_e[-1]-seg_e[0]
        grade = 100*rise/run
        # linearity: max deviation from the straight chord in elevation
        dev = max(abs(seg_e[k] - (seg_e[0] + (seg_e[-1]-seg_e[0])*(dist[i+k]-dist[i])/run))
                  for k in range(len(seg_e)))
        r = curve_radius(pts, i+WIN//2, 4)
        best.append((i, grade, dev, r))

    rail = [b for b in best if abs(b[1]) < 2.0 and b[2] < 0.6
            and b[3] is not None and b[3] > 120]
    tot = len([b for b in best if b[2] is not None])
    report.append((name, len(pts), tot, len(rail),
                   min((b[2] for b in rail), default=None),
                   sum(abs(b[1]) for b in rail)/len(rail) if rail else None))

    # emit contiguous rail-like runs >= 150 m
    idxs = sorted({b[0] for b in rail})
    runs, cur = [], []
    for i in idxs:
        if cur and i - cur[-1] <= 2: cur.append(i)
        else:
            if cur: runs.append(cur)
            cur = [i]
    if cur: runs.append(cur)
    for run in runs:
        a, b = run[0], min(run[-1]+WIN, len(pts)-1)
        if dist[b]-dist[a] < 150: continue
        seg_e = [e for e in elev[a:b+1] if e is not None]
        out_feats.append({"type":"Feature","properties":{
            "track":name,"length_m":round(dist[b]-dist[a]),
            "grade_pct":round(100*(elev[b]-elev[a])/(dist[b]-dist[a]),2)
                        if elev[a] and elev[b] else None,
            "elev_min":round(min(seg_e),1),"elev_max":round(max(seg_e),1)},
            "geometry":{"type":"LineString","coordinates":pts[a:b+1]}})

print(f"{'track':12}{'samples':>9}{'windows':>9}{'rail-like':>11}{'mean|grade|':>13}")
for r in report:
    print(f"{r[0]:12}{r[1]:>9}{r[2]:>9}{r[3]:>11}"
          f"{(f'{r[5]:.2f}%' if r[5] is not None else '-'):>13}")

out_feats.sort(key=lambda f: -f["properties"]["length_m"])
print(f"\nEngineered-grade candidates (>=150 m, |grade|<2%, elev dev<0.6 m, radius>120 m):")
for f in out_feats:
    p = f["properties"]
    print(f"   {p['length_m']:>4} m  grade {p['grade_pct']:>6}%  "
          f"elev {p['elev_min']}-{p['elev_max']} m   [{p['track']}]")

(ROOT/"data/grade_candidates.geojson").write_text(
    json.dumps({"type":"FeatureCollection","features":out_feats}))
print(f"\nwrote data/grade_candidates.geojson ({len(out_feats)} segments)")
