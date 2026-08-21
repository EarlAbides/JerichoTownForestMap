"""Cut perpendicular transects across a candidate alignment using 0.35 m LiDAR DEM."""
import json, math, pathlib, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEM = ("https://maps.vcgi.vermont.gov/arcgis/rest/services/EGC_services/"
       "IMG_VCGI_LIDARDEM_SP_NOCACHE_v1/ImageServer/getSamples")
LAT0 = 44.5018
MLAT, MLON = 111132.0, 111320.0*math.cos(math.radians(LAT0))

def sample(points):
    vals = []
    for i in range(0, len(points), 100):
        chunk = points[i:i+100]
        body = urllib.parse.urlencode({
            "geometry": json.dumps({"points": chunk,
                                    "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryMultipoint",
            "returnFirstValueOnly": "true", "f": "json"}).encode()
        req = urllib.request.Request(DEM, data=body, headers={"User-Agent":"ForestMap/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.load(r)
        got = {s["locationId"]: float(s["value"]) for s in d.get("samples",[])
               if s.get("value") not in (None,"NoData")}
        vals += [got.get(j) for j in range(len(chunk))]
        time.sleep(0.2)
    return vals

fc = json.loads((ROOT/"data/grade_candidates.geojson").read_text(encoding="utf-8"))
# longest segment in the low (rail-suspect) elevation band
low = [f for f in fc["features"] if f["properties"]["elev_max"] < 190]
seg = max(low, key=lambda f: f["properties"]["length_m"])
co = seg["geometry"]["coordinates"]
print(f"alignment: {seg['properties']['length_m']} m, "
      f"grade {seg['properties']['grade_pct']}%, "
      f"elev {seg['properties']['elev_min']}-{seg['properties']['elev_max']} m\n")

HALF, RES = 14.0, 0.7      # +/-14 m transect at 0.7 m spacing
N = 12                      # transects along the alignment
offs = [(-HALF + k*RES) for k in range(int(2*HALF/RES)+1)]

pts, meta = [], []
for t in range(N):
    i = int(t*(len(co)-2)/(N-1)) if N > 1 else 0
    i = max(1, min(i, len(co)-2))
    ax, ay = co[i-1][0]*MLON, co[i-1][1]*MLAT
    bx, by = co[i+1][0]*MLON, co[i+1][1]*MLAT
    L = math.hypot(bx-ax, by-ay) or 1
    nx, ny = -(by-ay)/L, (bx-ax)/L         # unit normal
    cx, cy = co[i][0]*MLON, co[i][1]*MLAT
    for o in offs:
        pts.append([(cx+nx*o)/MLON, (cy+ny*o)/MLAT])
    meta.append(i)

print(f"sampling {len(pts)} DEM points ({N} transects x {len(offs)})...")
vals = sample(pts)

widths = []
for t in range(N):
    prof = vals[t*len(offs):(t+1)*len(offs)]
    if any(v is None for v in prof): continue
    base = min(prof)
    rel = [v-base for v in prof]
    peak = max(rel)
    # flat crest = contiguous span within 0.35 m of the peak
    thr = peak-0.35
    best, cur = 0, 0
    for r in rel:
        cur = cur+RES if r >= thr else 0
        best = max(best, cur)
    widths.append(best)
    # ascii cross-section, 14 rows
    rows = 13
    grid = [[' ']*len(rel) for _ in range(rows)]
    for x, r in enumerate(rel):
        h = int(round((r/peak)*(rows-1))) if peak > 0 else 0
        grid[rows-1-h][x] = '#'
    print(f"\n--- transect {t+1}  relief {peak:.2f} m   flat crest {best:.1f} m")
    for row in grid[max(0,rows-7):]:
        print('   '+''.join(row))
    print('   '+'-'*len(rel)+f'   (span {2*HALF:.0f} m)')

if widths:
    w = sorted(widths)
    med = w[len(w)//2]
    print(f"\n{'='*58}")
    print(f"flat crest width: median {med:.1f} m, range {min(w):.1f}-{max(w):.1f} m "
          f"across {len(w)} transects")
    spread = max(w)-min(w)
    print(f"consistency (max-min): {spread:.1f} m")
    print("\nINTERPRETATION")
    if 3.0 <= med <= 8.0 and spread <= 4.0:
        print("  Flat crest of consistent width in the single-track railbed range")
        print("  (~4-6 m). Consistent with an ENGINEERED GRADE, not a natural landform.")
    elif med > 8.0:
        print("  Crest wider than a single-track grade - could be double track,")
        print("  a road bed, or a natural ridge.")
    else:
        print("  Narrow or inconsistent crest - more consistent with a natural")
        print("  landform or a footpath worn across one.")
