"""Validate the traced area of interest and count tiles needed to cache it."""
import json, math, pathlib
ROOT=pathlib.Path(__file__).resolve().parent.parent
co=json.loads((ROOT/"data/aoi_traced.geojson").read_text())["geometry"]["coordinates"]
if co[0]!=co[-1]: co=co+[co[0]]
LAT0=44.498; MLAT,MLON=111132.0,111320.0*math.cos(math.radians(LAT0))
def xy(c): return (c[0]*MLON,c[1]*MLAT)
P=[xy(c) for c in co]

area=abs(sum(P[i][0]*P[i+1][1]-P[i+1][0]*P[i][1] for i in range(len(P)-1)))/2
print(f"ring: {len(co)-1} vertices, closed automatically" if co[0]==co[-1] else "")
print(f"area: {area/1e6:.2f} km2  ({area/4046.86:.0f} acres)")

def inter(a,b,c,d):
    def ccw(p,q,r): return (r[1]-p[1])*(q[0]-p[0])>(q[1]-p[1])*(r[0]-p[0])
    return ccw(a,c,d)!=ccw(b,c,d) and ccw(a,b,c)!=ccw(a,b,d)
bad=0
for i in range(len(P)-1):
    for j in range(i+2,len(P)-1):
        if i==0 and j==len(P)-2: continue
        if inter(P[i],P[i+1],P[j],P[j+1]): bad+=1
print(f"self-intersections: {bad}" + ("  <-- ring is not simple" if bad else "  (simple ring)"))

lats=[c[1] for c in co]; lons=[c[0] for c in co]
print(f"bbox  S={min(lats):.6f} W={min(lons):.6f} N={max(lats):.6f} E={max(lons):.6f}")
print(f"      {(max(lats)-min(lats))*MLAT/1000:.2f} km N-S x {(max(lons)-min(lons))*MLON/1000:.2f} km E-W")
bboxa=(max(lats)-min(lats))*MLAT*(max(lons)-min(lons))*MLON
print(f"polygon covers {100*area/bboxa:.0f}% of its bounding box")

def t(lat,lon,z):
    n=2**z
    return (int((lon+180)/360*n),
            int((1-math.log(math.tan(math.radians(lat))+1/math.cos(math.radians(lat)))/math.pi)/2*n))
def inside(px,py):
    c=False; n=len(P)-1
    for i in range(n):
        x1,y1=P[i]; x2,y2=P[i+1]
        if (y1>py)!=(y2>py) and px<(x2-x1)*(py-y1)/(y2-y1)+x1: c=not c
    return c

print(f"\n{'zoom':>5}{'bbox tiles':>12}{'in polygon':>12}{'m/px':>8}{'~MB (1 layer)':>15}")
tot_bbox=tot_poly=0
for z in range(13,20):
    x0,y1_=t(max(lats),min(lons),z); x1,y0_=t(min(lats),max(lons),z)
    nb=(x1-x0+1)*(y0_-y1_+1)
    np_=0
    for X in range(x0,x1+1):
        for Y in range(y1_,y0_+1):
            n=2**z
            lon=(X+0.5)/n*360-180
            lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*(Y+0.5)/n))))
            if inside(lon*MLON,lat*MLAT): np_+=1
    mpp=156543.03*math.cos(math.radians(44.5))/(2**z)
    tot_bbox+=nb; tot_poly+=np_
    print(f"{z:>5}{nb:>12}{np_:>12}{mpp:>8.2f}{np_*12/1024:>15.1f}")
print(f"{'TOTAL':>5}{tot_bbox:>12}{tot_poly:>12}{'':>8}{tot_poly*12/1024:>15.1f}")
print(f"\nthree layers (imagery + hillshade + contours): "
      f"{3*tot_poly} tiles, ~{3*tot_poly*12/1024:.0f} MB")
