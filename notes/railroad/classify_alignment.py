"""Split the snapped alignment into railroad-consistent and inconsistent runs."""
import json, math, pathlib, statistics as st
ROOT=pathlib.Path(__file__).resolve().parent.parent
a=json.loads((ROOT/"data/alignment_analysis.json").read_text())
snap=json.loads((ROOT/"data/snapped_alignment.geojson").read_text())
co=snap["geometry"]["coordinates"]
LAT0=44.5013; MLAT,MLON=111132.0,111320.0*math.cos(math.radians(LAT0))
def xy(c): return (c[0]*MLON,c[1]*MLAT)
S=[xy(c) for c in co]
dist=[0.0]
for i in range(len(S)-1): dist.append(dist[-1]+math.dist(S[i],S[i+1]))

# re-derive elevation by re-reading the snapped sample run is costly; reuse a
# local gradient estimate from the snapped geometry + stored profile instead.
import urllib.request,urllib.parse,time
DEM=("https://maps.vcgi.vermont.gov/arcgis/rest/services/EGC_services/"
     "IMG_VCGI_LIDARDEM_SP_NOCACHE_v1/ImageServer/getSamples")
def sample(points):
    vals=[]
    for i in range(0,len(points),100):
        chunk=points[i:i+100]
        body=urllib.parse.urlencode({
            "geometry":json.dumps({"points":chunk,"spatialReference":{"wkid":4326}}),
            "geometryType":"esriGeometryMultipoint",
            "returnFirstValueOnly":"true","f":"json"}).encode()
        req=urllib.request.Request(DEM,data=body,headers={"User-Agent":"ForestMap/1.0"})
        with urllib.request.urlopen(req,timeout=90) as r: d=json.load(r)
        got={s["locationId"]:float(s["value"]) for s in d.get("samples",[])
             if s.get("value") not in (None,"NoData")}
        vals+=[got.get(j) for j in range(len(chunk))]
        time.sleep(0.15)
    return vals
elev=sample(co)

W=13
cls=[]
for i in range(len(co)):
    lo,hi=max(0,i-W//2),min(len(co)-1,i+W//2)
    if elev[lo] is None or elev[hi] is None or dist[hi]-dist[lo]<20:
        cls.append(None); continue
    g=100*(elev[hi]-elev[lo])/(dist[hi]-dist[lo])
    cls.append(abs(g)<2.6)

runs,cur,curv=[],[],None
for i,c in enumerate(cls):
    if c is None: continue
    if c!=curv:
        if cur: runs.append((curv,cur))
        cur=[i]; curv=c
    else: cur.append(i)
if cur: runs.append((curv,cur))

feats=[]
for good,idx in runs:
    if len(idx)<3: continue
    a_,b_=idx[0],idx[-1]
    L=dist[b_]-dist[a_]
    if L<60: continue
    seg=[e for e in elev[a_:b_+1] if e is not None]
    feats.append({"type":"Feature","properties":{
        "rail_consistent":good,"length_m":round(L),
        "grade_pct":round(100*(elev[b_]-elev[a_])/L,2) if L else None,
        "elev_min":round(min(seg),1),"elev_max":round(max(seg),1)},
        "geometry":{"type":"LineString","coordinates":co[a_:b_+1]}})

gk=sum(f["properties"]["length_m"] for f in feats if f["properties"]["rail_consistent"])
bk=sum(f["properties"]["length_m"] for f in feats if not f["properties"]["rail_consistent"])
print("="*62); print("ALIGNMENT SEGMENTED BY RAILROAD-GRADE CONSISTENCY (|grade|<2.6%)")
print("="*62)
print(f"consistent   {gk:>5} m   ({100*gk/(gk+bk):.0f}%)")
print(f"inconsistent {bk:>5} m   ({100*bk/(gk+bk):.0f}%)\n")
print(f"{'':>3}{'len':>7}{'grade':>9}{'elev range':>16}  verdict")
for i,f in enumerate(sorted(feats,key=lambda f:-f["properties"]["length_m"])):
    p=f["properties"]
    print(f"{i+1:>3}{p['length_m']:>7}{p['grade_pct']:>8}%"
          f"{p['elev_min']:>9}-{p['elev_max']:<6}"
          f"  {'RAIL-LIKE' if p['rail_consistent'] else 'not rail'}")

json.dump({"type":"FeatureCollection","features":feats},
          open(ROOT/"data/alignment_classified.geojson","w"))
print(f"\nwrote data/alignment_classified.geojson ({len(feats)} segments)")
