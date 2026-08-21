"""Test a traced alignment against the railroad-grade signature.

Three independent tests, each of which an esker should fail:
  1. Gradient    - sustained, near-constant, under ~2%
  2. Curve radii - large and locally constant (surveyed curves)
  3. Cross-section - a flat bench of consistent width, cut into uphill
     side and filled on downhill side (half-bench construction)
"""
import json, math, pathlib, statistics as st, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEM = ("https://maps.vcgi.vermont.gov/arcgis/rest/services/EGC_services/"
       "IMG_VCGI_LIDARDEM_SP_NOCACHE_v1/ImageServer/getSamples")
LAT0 = 44.5013
MLAT, MLON = 111132.0, 111320.0*math.cos(math.radians(LAT0))
def xy(c): return (c[0]*MLON, c[1]*MLAT)
def ll(p): return [p[0]/MLON, p[1]/MLAT]

def sample(points, tag=""):
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
        time.sleep(0.2)
    return vals

co = json.loads((ROOT/"data/traced_alignment.geojson").read_text())["geometry"]["coordinates"]
P = [xy(c) for c in co]

STEP=10.0
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
dist=[0.0]
for i in range(len(Q)-1): dist.append(dist[-1]+math.dist(Q[i],Q[i+1]))
print(f"alignment resampled: {len(pts)} points at {STEP:.0f} m, total {dist[-1]:.0f} m\n")

# ---------- 1. GRADIENT ----------
elev = sample(pts)
ok=[(d,e) for d,e in zip(dist,elev) if e is not None]
print("="*66); print("TEST 1  GRADIENT"); print("="*66)
print(f"DEM returned {len(ok)}/{len(pts)} elevations")
if len(ok)>10:
    e0,e1=ok[0][1],ok[-1][1]
    print(f"elevation {min(e for _,e in ok):.1f} - {max(e for _,e in ok):.1f} m "
          f"(end to end {e1-e0:+.1f} m over {ok[-1][0]-ok[0][0]:.0f} m "
          f"= {100*(e1-e0)/(ok[-1][0]-ok[0][0]):+.2f}%)")
    W=10  # 100 m windows
    gr=[]
    for i in range(len(ok)-W):
        run=ok[i+W][0]-ok[i][0]
        if run>1: gr.append(100*(ok[i+W][1]-ok[i][1])/run)
    if gr:
        print(f"\n100 m rolling gradient over {len(gr)} windows:")
        print(f"   median {st.median(gr):+.2f}%   mean {st.mean(gr):+.2f}%   "
              f"stdev {st.pstdev(gr):.2f}%")
        print(f"   range  {min(gr):+.2f}% to {max(gr):+.2f}%")
        u2=100*sum(1 for g in gr if abs(g)<2.0)/len(gr)
        u3=100*sum(1 for g in gr if abs(g)<3.0)/len(gr)
        print(f"   under 2%: {u2:.0f}% of windows    under 3%: {u3:.0f}%")
        # profile sparkline
        lo,hi=min(e for _,e in ok),max(e for _,e in ok)
        rows=9
        cols=min(100,len(ok))
        grid=[[' ']*cols for _ in range(rows)]
        for c in range(cols):
            e=ok[int(c*(len(ok)-1)/(cols-1))][1]
            h=int(round((e-lo)/(hi-lo)*(rows-1))) if hi>lo else 0
            grid[rows-1-h][c]='*'
        print(f"\n   elevation profile ({lo:.0f}-{hi:.0f} m over {dist[-1]:.0f} m):")
        for r in grid: print("   |"+"".join(r))
        print("   +"+"-"*cols)

# ---------- 2. CURVE RADII ----------
print("\n"+"="*66); print("TEST 2  CURVE RADIUS"); print("="*66)
def radius(i,span):
    if i-span<0 or i+span>=len(Q): return None
    (ax,ay),(bx,by),(cx,cy)=Q[i-span],Q[i],Q[i+span]
    d=2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
    if abs(d)<1e-9: return float('inf')
    ux=((ax*ax+ay*ay)*(by-cy)+(bx*bx+by*by)*(cy-ay)+(cx*cx+cy*cy)*(ay-by))/d
    uy=((ax*ax+ay*ay)*(cx-bx)+(bx*bx+by*by)*(ax-cx)+(cx*cx+cy*cy)*(bx-ax))/d
    return math.hypot(ax-ux,ay-uy)
R=[radius(i,5) for i in range(len(Q))]
fin=[r for r in R if r and r!=float('inf') and r<3000]
if fin:
    print(f"radius over 100 m chords: median {st.median(fin):.0f} m, "
          f"range {min(fin):.0f}-{max(fin):.0f} m")
    tight=[r for r in fin if r<150]
    print(f"   curves tighter than 150 m: {len(tight)} of {len(fin)} samples "
          f"({100*len(tight)/len(fin):.0f}%)")
    print(f"   min radius {min(fin):.0f} m"
          f"   ({'within' if min(fin)>90 else 'below'} typical branch-line practice ~90 m+)")

# ---------- 3. CROSS-SECTION ----------
print("\n"+"="*66); print("TEST 3  CROSS-SECTION"); print("="*66)
HALF,RES=18.0,0.6
offs=[-HALF+k*RES for k in range(int(2*HALF/RES)+1)]
N=14
tp,ti=[],[]
for t in range(N):
    i=max(1,min(int(t*(len(Q)-2)/(N-1)),len(Q)-2))
    ax,ay=Q[i-1]; bx,by=Q[i+1]
    L=math.hypot(bx-ax,by-ay) or 1
    nx,ny=-(by-ay)/L,(bx-ax)/L
    cx,cy=Q[i]
    for o in offs: tp.append(ll((cx+nx*o, cy+ny*o)))
    ti.append(i)
print(f"cutting {N} transects x {len(offs)} samples ({len(tp)} DEM points)...\n")
tv=sample(tp)

benches=[]
for t in range(N):
    prof=tv[t*len(offs):(t+1)*len(offs)]
    if sum(1 for v in prof if v is None)>3: continue
    xs=[o for o,v in zip(offs,prof) if v is not None]
    ys=[v for v in prof if v is not None]
    # detrend on the OUTER thirds only = the natural hillside
    ox=[x for x in xs if abs(x)>10]; oy=[y for x,y in zip(xs,ys) if abs(x)>10]
    if len(ox)<6: continue
    mx,my=st.mean(ox),st.mean(oy)
    den=sum((x-mx)**2 for x in ox) or 1
    slope=sum((x-mx)*(y-my) for x,y in zip(ox,oy))/den
    res=[y-(my+slope*(x-mx)) for x,y in zip(xs,ys)]
    # flat bench: contiguous run near centre where local slope is gentle
    best,cur,start=0,0,None; bs=be=0
    for k in range(1,len(xs)):
        s=abs((res[k]-res[k-1])/(xs[k]-xs[k-1]))
        if s<0.10:
            if cur==0: start=xs[k-1]
            cur+=xs[k]-xs[k-1]
            if cur>best: best,bs,be=cur,start,xs[k]
        else: cur=0
    ctr=[r for x,r in zip(xs,res) if abs(x)<3]
    cut=max((r for x,r in zip(xs,res) if 4<x<HALF), default=0)
    fill=min((r for x,r in zip(xs,res) if -HALF<x<-4), default=0)
    benches.append((best,(bs+be)/2,st.mean(ctr) if ctr else 0,cut,fill,abs(slope)*100))

print(f"{'#':>3}{'bench m':>9}{'centre':>8}{'hillside%':>11}{'cut m':>8}{'fill m':>8}")
for i,b in enumerate(benches):
    print(f"{i+1:>3}{b[0]:>9.1f}{b[1]:>8.1f}{b[5]:>11.1f}{b[3]:>8.2f}{b[4]:>8.2f}")

if benches:
    w=[b[0] for b in benches]
    print(f"\nbench width: median {st.median(w):.1f} m  "
          f"IQR {sorted(w)[len(w)//4]:.1f}-{sorted(w)[3*len(w)//4]:.1f} m  "
          f"stdev {st.pstdev(w):.1f} m")
    sidehill=[b for b in benches if b[5]>5]
    halfbench=[b for b in sidehill if b[3]>0.3 and b[4]<-0.3]
    print(f"transects on notable sidehill (>5%): {len(sidehill)} of {len(benches)}")
    print(f"   showing cut-uphill AND fill-downhill (half-bench): {len(halfbench)}")

json.dump({"elev":elev,"dist":dist,"radii":R,"benches":benches},
          open(ROOT/"data/alignment_analysis.json","w"))
print("\nwrote data/alignment_analysis.json")
