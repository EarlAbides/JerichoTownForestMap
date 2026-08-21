"""Pre-fetch VCGI tiles covering the traced area of interest.

Polite: single-threaded, rate limited, identifies itself, skips existing files.
"""
import json, math, pathlib, sys, time, urllib.error, urllib.request

ROOT=pathlib.Path(__file__).resolve().parent.parent
OUT=ROOT/"docs/tiles"
co=json.loads((ROOT/"data/aoi_traced.geojson").read_text())["geometry"]["coordinates"]
if co[0]!=co[-1]: co=co+[co[0]]

LAYERS={
 "img":  ("EGC_services/IMG_VCGI_CLR2024_WM_CACHE/ImageServer","jpg",19),
 "hill": ("EGC_services/IMG_VCGI_LIDARHILLSHD_WM_CACHE_v1/ImageServer","jpg",19),
 "cont": ("EGC_services/MAP_VCGI_LIDARCONTOURS_WM_CACHE_v1/MapServer","png",18),
}
BASE="https://maps.vcgi.vermont.gov/arcgis/rest/services/"
ZMIN=13

def inside(lon,lat):
    c=False; n=len(co)-1
    for i in range(n):
        x1,y1=co[i]; x2,y2=co[i+1]
        if (y1>lat)!=(y2>lat) and lon<(x2-x1)*(lat-y1)/(y2-y1)+x1: c=not c
    return c
def t(lat,lon,z):
    n=2**z
    return (int((lon+180)/360*n),
            int((1-math.log(math.tan(math.radians(lat))+1/math.cos(math.radians(lat)))/math.pi)/2*n))
def bounds(X,Y,z):
    n=2**z
    def lat_(Yy): return math.degrees(math.atan(math.sinh(math.pi*(1-2*Yy/n))))
    return (X/n*360-180,(X+1)/n*360-180, lat_(Y+1), lat_(Y))

lats=[c[1] for c in co]; lons=[c[0] for c in co]

def tiles_for(zmax):
    want=[]
    for z in range(ZMIN,zmax+1):
        x0,y1_=t(max(lats),min(lons),z); x1,y0_=t(min(lats),max(lons),z)
        for X in range(x0,x1+1):
            for Y in range(y1_,y0_+1):
                w,e,s,nn=bounds(X,Y,z)
                # keep the tile if it overlaps the ring at all
                hit=any(inside(lo,la) for lo,la in
                        ((w,s),(w,nn),(e,s),(e,nn),((w+e)/2,(s+nn)/2)))
                if not hit:
                    hit=any(w<=c[0]<=e and s<=c[1]<=nn for c in co)
                if hit: want.append((z,X,Y))
    return want

total_done=total_skip=total_fail=0
for key,(path,ext,zmax) in LAYERS.items():
    want=tiles_for(zmax)
    print(f"[{key}] {len(want)} tiles z{ZMIN}-{zmax}", flush=True)
    for i,(z,X,Y) in enumerate(want):
        dest=OUT/key/str(z)/str(X)/f"{Y}.{ext}"
        if dest.exists() and dest.stat().st_size>0:
            total_skip+=1; continue
        dest.parent.mkdir(parents=True,exist_ok=True)
        url=f"{BASE}{path}/tile/{z}/{Y}/{X}"
        try:
            req=urllib.request.Request(url,headers={
                "User-Agent":"ForestMap/1.0 (personal trail mapping; jericho VT)"})
            with urllib.request.urlopen(req,timeout=45) as r:
                data=r.read()
            if len(data)<100: raise ValueError("empty tile")
            dest.write_bytes(data); total_done+=1
        except Exception as e:
            total_fail+=1
            if total_fail<6: print(f"   miss {z}/{X}/{Y}: {e}", flush=True)
        time.sleep(0.12)
        if (i+1)%150==0: print(f"   {i+1}/{len(want)}", flush=True)

mb=sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())/1024/1024
print(f"\nfetched {total_done}, skipped {total_skip}, failed {total_fail}")
print(f"cache size: {mb:.1f} MB at {OUT}")
