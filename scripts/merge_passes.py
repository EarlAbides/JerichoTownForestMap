"""Merge repeated passes over the same trail into one centreline per trail.

Eight walks over the same path are eight parallel lines with GPS scatter between
them.  What we want is one line down the middle carrying a count of how many
times it has been walked, so the map can draw a well-worn trail thicker than a
route taken once.

The whole thing is a pure function of data/forest_tracks.geojson.  Adding new
.fit files means re-running the pipeline from parse_fit; there is no incremental
state to drift out of sync, and the same input always gives the same output.

    1. corridor    stamp a DILATE-radius disc around every fix
    2. fill        close pinholes left by GPS braiding, keep real loops
    3. thin        Zhang-Suen to a one-cell skeleton -> network topology
    4. trace       split the skeleton into chains at junctions and dead ends
    5. refine      slide each vertex sideways onto the centre of the local fixes
    6. attribute   count distinct walks near each vertex, split on changes

Two details that are easy to get wrong:

DILATE is half MATCH_R, so two passes within the match tolerance fuse into one
solid corridor with no gap between them, while passes further apart than that
stay separate trails.  Without it the corridor is porous and thinning preserves
every pinhole as a loop -- you get a mesh, not a trail.

A junction is a cell whose CROSSING NUMBER is 3 or more, not one with three or
more neighbours.  In an 8-connected skeleton a plain diagonal staircase makes
cells with three neighbours all the time; using raw degree shatters straight
trail into hundreds of fragments.
"""
import json, math, pathlib
from collections import defaultdict, deque

ROOT = pathlib.Path(__file__).resolve().parent.parent

CELL     = 2.0    # m, grid resolution
MATCH_R  = 8.0    # m, how far apart two passes can be and still be one trail
DILATE   = MATCH_R/2
HOLE_M2  = 400.0  # m2, enclosed gaps smaller than this are GPS braiding
REFINE_R = 7.0    # m, window for pulling a vertex onto the centre of the fixes
SPUR     = 12.0   # m, dead-end branches shorter than this are thinning artefacts
DP_TOL   = 0.75   # m, final simplify tolerance
SMOOTH   = 5      # vertices, median window on the pass count
FILL_MAX = DILATE + CELL  # m, skeleton further than this from any fix is fill
WELD_R   = 25.0   # m, furthest a dangling end will reach to rejoin the network
WELD_W   = 2      # distinct walks that must cross a gap before it is welded shut

LAT0 = 44.5018
MLAT, MLON = 111132.0, 111320.0*math.cos(math.radians(LAT0))
def xy(c): return (c[0]*MLON, c[1]*MLAT)
def ll(p): return [round(p[0]/MLON, 7), round(p[1]/MLAT, 7)]

N8 = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]
N4 = [(0, 1), (1, 0), (0, -1), (-1, 0)]

# ---------------------------------------------------------------- load
src = json.loads((ROOT/"data/forest_tracks.geojson").read_text(encoding="utf-8"))
walks = [(f["properties"]["name"],
          [xy(c) for c in f["geometry"]["coordinates"]]) for f in src["features"]]
allpts = [(p, w) for w, (_, pts) in enumerate(walks) for p in pts]
walked = sum(math.dist(p[i], p[i+1]) for _, p in walks for i in range(len(p)-1))
print(f"{len(walks)} walks, {len(allpts)} fixes, {walked/1000:.2f} km walked")

X0 = min(p[0] for p, _ in allpts) - 30
Y0 = min(p[1] for p, _ in allpts) - 30
def cell(p):   return (int((p[0]-X0)//CELL), int((p[1]-Y0)//CELL))
def uncell(c): return (X0 + (c[0]+0.5)*CELL, Y0 + (c[1]+0.5)*CELL)

# spatial hash of the raw fixes, for stages 5 and 6
HB = 10.0
hashed = defaultdict(list)
for p, w in allpts:
    hashed[(int(p[0]//HB), int(p[1]//HB))].append((p, w))

def near(p, r):
    """Every fix within r of p, as (point, walk index)."""
    bx, by = int(p[0]//HB), int(p[1]//HB)
    n = int(r//HB) + 1
    out = []
    for i in range(bx-n, bx+n+1):
        for j in range(by-n, by+n+1):
            for q, w in hashed.get((i, j), ()):
                if math.dist(p, q) <= r: out.append((q, w))
    return out

# ----------------------------------------------------- 1. corridor
R = int(DILATE//CELL) + 1
occ = set()
for p, _ in allpts:
    cx, cy = cell(p)
    for i in range(cx-R, cx+R+1):
        for j in range(cy-R, cy+R+1):
            if math.dist(p, uncell((i, j))) <= DILATE: occ.add((i, j))
print(f"corridor {len(occ)} cells ({DILATE:.0f} m around every fix)")

# --------------------------------------------------------- 2. fill
xs = [c[0] for c in occ]; ys = [c[1] for c in occ]
lo = (min(xs)-2, min(ys)-2); hi = (max(xs)+2, max(ys)+2)

def flood(start, blocked, seen):
    comp, q = [], deque([start]); seen.add(start)
    while q:
        c = q.popleft(); comp.append(c)
        for d in N4:
            n = (c[0]+d[0], c[1]+d[1])
            if (lo[0] <= n[0] <= hi[0] and lo[1] <= n[1] <= hi[1]
                    and n not in blocked and n not in seen):
                seen.add(n); q.append(n)
    return comp

outside = set()
flood(lo, occ, outside)
seen, pin, loops = set(outside), 0, []
for i in range(lo[0], hi[0]+1):
    for j in range(lo[1], hi[1]+1):
        if (i, j) in occ or (i, j) in seen: continue
        comp = flood((i, j), occ, seen)
        area = len(comp)*CELL*CELL
        if area < HOLE_M2: occ |= set(comp); pin += 1
        else: loops.append(area)
print(f"filled   {pin} braiding pinholes, kept {len(loops)} real loops "
      f"({min(loops):.0f}-{max(loops):.0f} m2)" if loops else f"filled {pin} pinholes")

# ------------------------------------------------------- 3. thinning
def thin(S):
    """Zhang-Suen: erode to a one-cell skeleton without breaking connectivity."""
    S = set(S)
    while True:
        removed = 0
        for step in (0, 1):
            drop = []
            for c in S:
                P = [1 if (c[0]+d[0], c[1]+d[1]) in S else 0 for d in N8]
                if not 2 <= sum(P) <= 6: continue
                if sum(1 for i in range(8)
                       if P[i] == 0 and P[(i+1) % 8] == 1) != 1: continue
                if step == 0:
                    if P[0]*P[2]*P[4] or P[2]*P[4]*P[6]: continue
                else:
                    if P[0]*P[2]*P[6] or P[0]*P[4]*P[6]: continue
                drop.append(c)
            S -= set(drop); removed += len(drop)
        if not removed: return S

skel = thin(occ)

# The fill in stage 2 closes braiding pinholes, which is what keeps thinning
# from turning every hole into a loop -- but it pays for that by inventing
# corridor.  Where it closes a hole of any size, the skeleton runs down the
# middle of ground nobody walked, and the result is trail drawn from no evidence
# at all: one such blob near the entrance produced a segment 10 m from the
# nearest fix, carrying 0 passes, drawing as a hole punched through a 9-pass
# trail.  DILATE + CELL is the ceiling on how far a legitimately derived cell
# can sit from the fix that put it there: the corridor reaches DILATE, and the
# grid quantises position by one cell.  Real skeleton runs p99 = 4.5 m from a
# fix, so this cuts well clear of it, and the window is not as wide as it looks
# -- at 5 m the cut severed a stretch two walks had crossed, and at MATCH_R it
# left two stubs 7.0 and 7.8 m from any fix drawn as 9-pass trail, because a
# stub within MATCH_R of a real trail inherits that trail's walk count whether
# or not anyone walked the stub.  Drop these cells and re-thin.  The fill still
# does its job; this only declines to draw its interior.
phantom = {c for c in skel if not near(uncell(c), FILL_MAX)}
if phantom:
    skel = thin(skel - phantom)
print(f"pruned   {len(phantom)} phantom cells further than {FILL_MAX:.0f} m from any fix")

def cross(S, c):
    """Crossing number: 1 = dead end, 2 = along a trail, 3+ = junction."""
    P = [1 if (c[0]+d[0], c[1]+d[1]) in S else 0 for d in N8]
    return sum(1 for i in range(8) if P[i] == 0 and P[(i+1) % 8] == 1)

# ------------------------------------------------ 4. trace to chains
def chains(S):
    """Split the skeleton into polylines running junction to junction.

    Junction cells AND their 8-neighbours are blocked out before tracing.  It is
    not enough to drop the junction cell itself: the branch cells around it are
    8-adjacent to each other, so the branches stay connected and a trace runs
    straight through the junction and off into the next branch.  Blocking the
    neighbourhood cuts the branches genuinely apart; each stub is then rejoined
    to the junction centroid, so the network stays welded.
    """
    jcells = {c for c in S if cross(S, c) >= 3}

    groups, gseen = [], set()           # adjacent junction cells are one node
    for c in sorted(jcells):
        if c in gseen: continue
        g, q = [], [c]; gseen.add(c)
        while q:
            x = q.pop(); g.append(x)
            for d in N8:
                n = (x[0]+d[0], x[1]+d[1])
                if n in jcells and n not in gseen: gseen.add(n); q.append(n)
        groups.append(g)
    gpos = [(sum(uncell(c)[0] for c in g)/len(g),
             sum(uncell(c)[1] for c in g)/len(g)) for g in groups]

    blocked = {}
    for i, g in enumerate(groups):
        for c in g:
            blocked.setdefault(c, i)
            for d in N8:
                n = (c[0]+d[0], c[1]+d[1])
                if n in S: blocked.setdefault(n, i)

    interior = S - set(blocked)
    out, seen = [], set()
    for c0 in sorted(interior):
        if c0 in seen: continue
        comp, q = [], [c0]; seen.add(c0)
        while q:
            x = q.pop(); comp.append(x)
            for d in N8:
                n = (x[0]+d[0], x[1]+d[1])
                if n in interior and n not in seen: seen.add(n); q.append(n)
        cset = set(comp)

        touch = {}                      # which junction each end cell hangs off
        for x in comp:
            for d in N8:
                n = (x[0]+d[0], x[1]+d[1])
                if n in blocked: touch.setdefault(x, set()).add(blocked[n])

        if touch:
            # order along the path by hop count from one end; with the junctions
            # blocked out each component is a simple path, so this is unambiguous
            start = min(touch)
            dist, dq = {start: 0}, deque([start])
            while dq:
                x = dq.popleft()
                for d in N8:
                    n = (x[0]+d[0], x[1]+d[1])
                    if n in cset and n not in dist:
                        dist[n] = dist[x]+1; dq.append(n)
            path = sorted(comp, key=lambda c: (dist.get(c, 1 << 30), c))
        else:
            path, vis, cur = [c0], {c0}, c0      # closed loop, no junction on it
            while True:
                cand = [n for n in ((cur[0]+d[0], cur[1]+d[1]) for d in N8)
                        if n in cset and n not in vis]
                if not cand: break
                cur = min(cand, key=lambda n: (abs(n[0]-cur[0])+abs(n[1]-cur[1]), n))
                path.append(cur); vis.add(cur)

        pts = [uncell(c) for c in path]
        head = touch.get(path[0]); tail = touch.get(path[-1])
        if head: pts.insert(0, gpos[min(head)])
        if tail: pts.append(gpos[min(tail)])
        if not touch: pts.append(pts[0])          # close the ring
        out.append((pts, bool(head) or not touch, bool(tail) or not touch))

    # junctions close enough that their blocked zones meet, with no trail between
    linked = set()
    for c, i in blocked.items():
        for d in N8:
            j = blocked.get((c[0]+d[0], c[1]+d[1]))
            if j is not None and j != i and (min(i, j), max(i, j)) not in linked:
                linked.add((min(i, j), max(i, j)))
                out.append(([gpos[i], gpos[j]], True, True))
    return out

def plen(pts):
    return sum(math.dist(pts[i], pts[i+1]) for i in range(len(pts)-1))

for _ in range(4):                      # drop thinning whiskers, then re-thin
    junk = set()
    for pts, h, tl in chains(skel):
        if plen(pts) < SPUR and not (h and tl):
            for x, y in pts:
                junk.add((int((x-X0)//CELL), int((y-Y0)//CELL)))
    if not junk: break
    skel = thin(skel - junk)

# SPUR is a whisker rule, not a minimum trail length: a chain welded to a
# junction at BOTH ends is a connector, however short, and dropping it punches a
# hole through a trail that is otherwise continuous.  The prune loop above has
# always had this right; this filter used to disagree with it and deleted five
# real connectors, two of them carrying 11 and 12 walks.
raw = [c for c in chains(skel) if plen(c[0]) >= SPUR or (c[1] and c[2])]

# ------------------------------------------------- 4b. weld dangling ends
def crossing_walks(a, b):
    """Distinct walks with a fix near EVERY quarter point of the line a->b.

    Requiring all three points rules out a walk that merely brushes one end;
    only something that actually traversed the gap counts.
    """
    return set.intersection(*[
        {w for _, w in near((a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t), DILATE+CELL)}
        for t in (0.25, 0.5, 0.75)])


def weld(ch):
    """Rejoin chain ends that thinning left hanging, where the GPS proves it.

    Thinning is a local rule, so at a T whose stem meets the crossbar at a
    shallow angle it can stop a few metres short: the cells are genuinely not
    adjacent and no amount of re-thinning brings them together.  The evidence
    for the join is not in the skeleton at all, it is in the fixes lying in the
    gap -- so that is what gets tested, and a gap nobody has walked through
    stays open.  Two trails passing close by is exactly the case MATCH_R exists
    to keep apart, and this must not undo that.

    The bridge is laid down straight and left for refine() to pull sideways onto
    the fixes underneath it, so a weld across a curve comes out following the
    curve rather than cutting the corner.
    """
    ch = [[list(pts), h, t] for pts, h, t in ch]
    welds = []
    for _ in range(64):
        # An end is dangling if nothing is actually joined to it.  The head/tail
        # flags cannot answer that: they say "hangs off a junction group", which
        # stays true for a stub left alone at a junction after the phantom prune
        # took away everything it used to meet.  Ask the geometry instead.
        held = defaultdict(int)
        for P, _, _ in ch:
            for q in P: held[(round(q[0], 1), round(q[1], 1))] += 1

        best = None
        for i, (P, h, t) in enumerate(ch):
            for end in (0, -1):
                p = P[end]
                if held[(round(p[0], 1), round(p[1], 1))] > 1: continue
                near_ch = []
                for j, (Q, _, _) in enumerate(ch):
                    if j == i: continue
                    k, d = min(((k, math.dist(p, q)) for k, q in enumerate(Q)),
                               key=lambda kd: kd[1])
                    if 1e-9 < d <= WELD_R: near_ch.append((d, j, k))
                for d, j, k in sorted(near_ch):
                    if best and d >= best[0]: break
                    w = crossing_walks(p, ch[j][0][k])
                    if len(w) >= WELD_W:
                        best = (d, i, end, j, k, len(w)); break
        if not best: break

        d, i, end, j, k, nw = best
        p, q = ch[i][0][end], ch[j][0][k]
        n = max(1, round(d/CELL))
        bridge = [(p[0]+(q[0]-p[0])*s/n, p[1]+(q[1]-p[1])*s/n) for s in range(n+1)]
        bridge = refine(bridge)          # let it settle onto the fixes it crosses
        bridge[0], bridge[-1] = p, q     # but keep it attached to what it joins

        if end == 0: ch[i][1] = True
        else:        ch[i][2] = True
        Q, hj, tj = ch[j]
        if k == 0:            ch[j][1] = True      # welded onto an existing end
        elif k == len(Q)-1:   ch[j][2] = True
        else:                                      # T into the middle: split it
            ch[j] = [Q[:k+1], hj, True]
            ch.append([Q[k:], True, tj])
        ch.append([bridge, True, True])
        welds.append((d, nw))

    if welds:
        print(f"welded   {len(welds)} gaps thinning left open "
              f"({min(w[0] for w in welds):.1f}-{max(w[0] for w in welds):.1f} m, "
              f"{min(w[1] for w in welds)}-{max(w[1] for w in welds)} walks crossing)")
    return [(P, h, t) for P, h, t in ch]

ends = sum(1 for c in skel if cross(skel, c) == 1)
jns  = sum(1 for c in skel if cross(skel, c) >= 3)
print(f"skeleton {len(skel)} cells, {ends} dead ends, {jns} junction cells")
print(f"traced   {len(raw)} chains, {sum(plen(c[0]) for c in raw)/1000:.2f} km")

# --------------------------------------------------------- 5. refine
def refine(P):
    """Slide each vertex along its normal onto the centre of the nearby fixes."""
    out = []
    for i, p in enumerate(P):
        a, b = P[max(0, i-2)], P[min(len(P)-1, i+2)]
        tx, ty = b[0]-a[0], b[1]-a[1]
        L = math.hypot(tx, ty)
        loc = near(p, REFINE_R)
        if L == 0 or not loc: out.append(p); continue
        nx, ny = -ty/L, tx/L                       # unit normal
        off = sum((q[0]-p[0])*nx + (q[1]-p[1])*ny for q, _ in loc)/len(loc)
        out.append((p[0] + off*nx, p[1] + off*ny))
    return out

def chaikin(P, it=2):
    for _ in range(it):
        if len(P) < 3: break
        Q = [P[0]]
        for i in range(len(P)-1):
            a, b = P[i], P[i+1]
            Q.append((0.75*a[0]+0.25*b[0], 0.75*a[1]+0.25*b[1]))
            Q.append((0.25*a[0]+0.75*b[0], 0.25*a[1]+0.75*b[1]))
        Q.append(P[-1]); P = Q
    return P

def dp(P, tol):
    if len(P) < 3: return P
    a, b = P[0], P[-1]
    dx, dy = b[0]-a[0], b[1]-a[1]
    L2 = dx*dx + dy*dy
    best, bi = -1.0, 0
    for i in range(1, len(P)-1):
        q = P[i]
        if L2 == 0:
            d = math.dist(q, a)
        else:
            t = max(0.0, min(1.0, ((q[0]-a[0])*dx + (q[1]-a[1])*dy)/L2))
            d = math.dist(q, (a[0]+t*dx, a[1]+t*dy))
        if d > best: best, bi = d, i
    if best <= tol: return [a, b]
    return dp(P[:bi+1], tol)[:-1] + dp(P[bi:], tol)

# Refine BEFORE welding, not after.  Thinning leaves a chain end a few metres
# off the line people actually walked, and a gap measured between two unrefined
# ends runs through different ground than the gap that finally gets drawn: at
# the entrance the ends sat 11.7 m apart across the void here and 7.5 m apart
# once refined onto the trail, so the evidence test looked in the wrong place
# and declined a join that 8 walks had made.  Refine first and weld() sees the
# gap the reader will see.
ref = []
for pts, head, tail in raw:
    P = refine(pts)
    if head: P[0]  = pts[0]        # junction positions are shared, so leave
    if tail: P[-1] = pts[-1]       # them exactly where chains() put them
    ref.append((P, head, tail))
raw = weld(ref)

# ------------------------------------------------------ 6. attribute
feats, tot = [], defaultdict(float)
for pts, head, tail in raw:
    P = dp(chaikin(list(pts)), DP_TOL)
    if len(P) < 2: continue

    cnt = [len({w for _, w in near(p, MATCH_R)}) for p in P]
    med = []                                    # median filter, kill the flicker
    for i in range(len(cnt)):
        w = sorted(cnt[max(0, i-SMOOTH//2):i+SMOOTH//2+1])
        med.append(w[len(w)//2])

    i = 0                     # split into runs of equal count so width can vary
    while i < len(P)-1:
        j = i
        while j < len(P)-1 and med[j+1] == med[i]: j += 1
        if j == i: j = i+1
        seg = P[i:j+1]
        L = sum(math.dist(seg[k], seg[k+1]) for k in range(len(seg)-1))
        if L > 0:
            tot[med[i]] += L
            feats.append({"type": "Feature",
                          "properties": {"passes": med[i], "length_m": round(L, 1)},
                          "geometry": {"type": "LineString",
                                       "coordinates": [ll(p) for p in seg]}})
        i = j

total = sum(tot.values())
print(f"\nmerged   {len(feats)} segments, {total/1000:.2f} km of distinct trail")
print(f"         {walked/total:.1f}x redundancy from {len(walks)} visits")
print(f"\n{'passes':>7}{'km':>9}{'share':>8}")
for k in sorted(tot):
    print(f"{k:>7}{tot[k]/1000:>9.2f}{100*tot[k]/total:>7.0f}%")

(ROOT/"data/trails_merged.geojson").write_text(
    json.dumps({"type": "FeatureCollection", "features": feats}))
print(f"\nwrote data/trails_merged.geojson")
