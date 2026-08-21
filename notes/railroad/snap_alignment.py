"""Snap a hand-traced line onto the true bench centreline using the LiDAR DEM,
then re-test gradient and curvature without hand-tracing error."""
import json, math, pathlib, statistics as st, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEM = ("https://maps.vcgi.vermont.gov/arcgis/rest/services/EGC_services/"
       "IMG_VCGI_LIDARDEM_SP_NOCACHE_v1/ImageServer/getSamples")
LAT0=44.5013; MLAT,MLON=111132.0,111320.0*math.cos(math.radians(LAT0))
def xy(c): return (c[0]*MLON, c[1]*MLAT)
def ll(p): return [p[0]/MLON, p[1]/MLAT]

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

co=json.loads((ROOT/"data/traced_alignment.geojson").read_text())["geometry"]["coordinates"]
P=[xy(c) for c in co]
STEP=8.0
pts=[co[0]]; acc=0.0
for i in range(len(P)-1):
    seg=math.dist(P[i],P[i+1])
    if seg==0: continue
    t=STEP-acc
    while t<=seg:
        f=t/seg
        pts.append([co[i][0]+(co[i+1][0]-co[i][0])*f, co[i][1]+(co[i+1][1]-co[i][1])*f])
        t+=STEP
    acc=(acc+seg)%STEP
Q=[xy(p) for p in pts]
print(f"{len(pts)} points at {STEP:.0f} m spacing")

HALF,RES=12.0,0.6
offs=[-HALF+k*RES for k in range(int(2*HALF/RES)+1)]
tp=[]
for i in range(len(Q)):
    a=Q[max(0,i-1)]; b=Q[min(len(Q)-1,i+1)]
    L=math.hypot(b[0]-a[0],b[1]-a[1]) or 1
    nx,ny=-(b[1]-a[1])/L,(b[0]-a[0])/L
    cx,cy=Q[i]
    for o in offs: tp.append(ll((cx+nx*o, cy+ny*o)))
print(f"sampling {len(tp)} DEM points for snapping...")
tv=sample(tp)

snapped, shifts = [], []
for i in range(len(Q)):
    prof=tv[i*len(offs):(i+1)*len(offs)]
    xs=[o for o,v in zip(offs,prof) if v is not None]
    ys=[v for v in prof if v is not None]
    if len(xs)<20: snapped.append(pts[i]); shifts.append(0.0); continue
    ox=[x for x in xs if abs(x)>8]; oy=[y for x,y in zip(xs,ys) if abs(x)>8]
    if len(ox)>=6:
        mx,my=st.mean(ox),st.mean(oy)
        den=sum((x-mx)**2 for x in ox) or 1
        sl=sum((x-mx)*(y-my) for x,y in zip(ox,oy))/den
        res=[y-(my+sl*(x-mx)) for x,y in zip(xs,ys)]
    else:
        res=list(ys)
    # widest gentle-slope run = the bench; take its midpoint
    best,cur,start=0,0,None; bs=be=0
    for k in range(1,len(xs)):
        s=abs((res[k]-res[k-1])/(xs[k]-xs[k-1]))
        if s<0.09:
            if cur==0: start=xs[k-1]
            cur+=xs[k]-xs[k-1]
            if cur>best: best,bs,be=cur,start,xs[k]
        else: cur=0
    off=(bs+be)/2 if best>=2.5 else 0.0
    off=max(-8,min(8,off))
    a=Q[max(0,i-1)]; b=Q[min(len(Q)-1,i+1)]
    L=math.hypot(b[0]-a[0],b[1]-a[1]) or 1
    nx,ny=-(b[1]-a[1])/L,(b[0]-a[0])/L
    snapped.append(ll((Q[i][0]+nx*off, Q[i][1]+ny*off)))
    shifts.append(off)

# light smoothing of the snapped line
S=[xy(p) for p in snapped]
for _ in range(3):
    S=[S[0]]+[((S[i-1][0]+2*S[i][0]+S[i+1][0])/4,(S[i-1][1]+2*S[i][1]+S[i+1][1])/4)
              for i in range(1,len(S)-1)]+[S[-1]]
snapped=[ll(p) for p in S]

print(f"lateral shift: median {st.median([abs(s) for s in shifts]):.1f} m, "
      f"max {max(abs(s) for s in shifts):.1f} m")

elev=sample(snapped)
dist=[0.0]
for i in range(len(S)-1): dist.append(dist[-1]+math.dist(S[i],S[i+1]))
ok=[(d,e) for d,e in zip(dist,elev) if e is not None]
W=13  # ~100 m
gr=[100*(ok[i+W][1]-ok[i][1])/(ok[i+W][0]-ok[i][0])
    for i in range(len(ok)-W) if ok[i+W][0]-ok[i][0]>1]

def radius(i,span):
    if i-span<0 or i+span>=len(S): return None
    (ax,ay),(bx,by),(cx,cy)=S[i-span],S[i],S[i+span]
    d=2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
    if abs(d)<1e-9: return float('inf')
    ux=((ax*ax+ay*ay)*(by-cy)+(bx*bx+by*by)*(cy-ay)+(cx*cx+cy*cy)*(ay-by))/d
    uy=((ax*ax+ay*ay)*(cx-bx)+(bx*bx+by*by)*(ax-cx)+(cx*cx+cy*cy)*(bx-ax))/d
    return math.hypot(ax-ux,ay-uy)
R=[radius(i,6) for i in range(len(S))]
fin=[r for r in R if r and r!=float('inf') and r<5000]

print("\n"+"="*60); print("SNAPPED ALIGNMENT"); print("="*60)
print(f"length {dist[-1]:.0f} m   elevation {min(e for _,e in ok):.1f}-{max(e for _,e in ok):.1f} m")
print(f"end to end {ok[-1][1]-ok[0][1]:+.1f} m = {100*(ok[-1][1]-ok[0][1])/(ok[-1][0]-ok[0][0]):+.2f}%")
print(f"\n100 m gradient: median {st.median(gr):+.2f}%  stdev {st.pstdev(gr):.2f}%  "
      f"range {min(gr):+.2f}% to {max(gr):+.2f}%")
print(f"   under 2%: {100*sum(1 for g in gr if abs(g)<2)/len(gr):.0f}%"
      f"   under 3%: {100*sum(1 for g in gr if abs(g)<3)/len(gr):.0f}%")
print(f"\nradius: median {st.median(fin):.0f} m  min {min(fin):.0f} m")
print(f"   under 150 m: {sum(1 for r in fin if r<150)} of {len(fin)}")

json.dump({"type":"Feature","properties":{"snapped":True,"length_m":round(dist[-1])},
           "geometry":{"type":"LineString",
           "coordinates":[[round(p[0],6),round(p[1],6)] for p in snapped]}},
          open(ROOT/"data/snapped_alignment.geojson","w"))
print("\nwrote data/snapped_alignment.geojson")
