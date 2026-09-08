# Project state — resume here

Working notes for picking this up in a fresh session. Last updated 2026-09-07.

**Shipped and live.** Public repo, several commits past the initial one, GitHub
Pages serving the field app. Working tree clean, privacy audit passing. Nothing
is half-finished — pick up from *Wanted next*, not from a broken state.

Quickest orientation: read *What this is*, then *Wanted next*. Everything between
is reference for when you need it.

---

## What this is

A trail map of the **Jericho Town Forest**, Jericho, Vermont (Chittenden County),
built from Apple Watch GPS tracks plus Vermont's open LiDAR and orthoimagery.

Decisions already made, so they don't get relitigated:

| Question | Answer |
|---|---|
| Audience | Me first; shareable to locals if it comes together |
| Offline | Was "online is fine", later upgraded to full offline caching |
| Working split | I build; the user walks, reviews, and provides ground truth |
| Source of truth | Personal GPS + open government data **only** |
| Delivery | GitHub Pages. Everything ships as static files in `docs/` |
| OSM | **Not uploading.** OSM paths are ignored entirely — bad coordinates |
| Map scale | Visit weight/colour saturate at **8**, fixed, not data-driven |
| Adding walks | Drop the `.fit` in `Exports/`, **reprocess everything**. No incremental base map |

**Trailforks and AllTrails are off limits.** Trailforks lists 53 trails for this
forest; both are proprietary databases and copying from them into OSM is a licence
violation. Nothing here derives from them, and nothing should.

---

## Key facts and coordinates

```
Home convergence point   44.503533, -72.973008   (100 m hard exclusion radius)
Forest main entrance     44.504441, -72.974760
Road popout to home      44.503235, -72.974428
Area of interest         data/aoi_traced.geojson — 1.16 km2 / 287 acres, simple ring
```

- **20 walks**, Aug 8 – Sep 7 2026, exported from HealthFit as `.fit` (not GPX — HealthFit
  does not offer GPX; FIT parses fine with `fitdecode`).
- **55.50 km** of forest walking after clipping, from 64.41 km raw.
- **6.78 km of distinct trail** after merging repeat visits — 8.2x redundancy,
  184 segments in a **single connected component**.
  About a fifth of it (1.45 km) has been walked only once; both maps flag that on
  request. Saturation is real but not finished: the 9.3 km walked in the Aug 27 –
  Sep 2 batch added only 120 m of new trail, and then the single Sep 7 walk added
  **400 m** — the biggest jump in a while, and it pushed the walked-once figure
  *up* rather than down. There is still new ground to find.
- Line weight and colour saturate at `CAP = 8` in both templates, **on purpose**.
  The user confirmed 8 is as bold as it should ever get, and pass counts will
  climb well past that as walks accumulate. Do not wire the scale back to the
  data maximum — that would restretch the map on every new walk and make
  versions incomparable. `MAXP` is still used, but only for the filter slider's
  upper bound, which should track the real data. As of the 2026-09-07 walk the
  busiest trail is at **20 passes**, so the cap is well past clamping — which is
  the intended behaviour, not a bug.
- **Median GPS accuracy 2 m** even under summer canopy. Merged centrelines sit a
  median 0.84 m from the nearest real fix (p95 3.12 m — tighter than at 13 walks,
  because every extra pass sharpens a centreline it crosses).

### What OSM has here
Nothing usable. 16 unnamed foot-usable ways with coordinates wonky enough not to
be worth reconciling, and no boundary polygon. Vermont's E911 trails layer returns
**zero features** for this bbox. **Decision 2026-08-20: ignore OSM entirely** —
not displayed, not compared against, not uploaded to. `export_osm_paths.py`,
`gap_analysis.py` and `osm_paths.geojson` were deleted, not archived.

### Ground truth from the user
- **No trail markers, no blazes, no names.** These are informal forest/streamside
  paths. Correct tagging is `highway=path` + `informal=yes`, with **no** `name` tag.
  Inventing names would be wrong.
- The dashed "unwalked OSM paths" near the entrance are **elementary school paths**,
  not forest trails. Not a to-do item.
- Coverage is subjectively good; a few unwalked spurs remain, and the user can now
  reason about where they lead from the map.

### The railroad
A 2.36 km alignment traced from LiDAR hillshade is a section of the **Burlington &
Lamoille Railroad** (chartered 1877, Burlington → Essex → Jericho → Cambridge
Junction, abandoned 1938). Evidence: 91% of its length holds railroad-consistent
gradient, including a continuous **729 m run at 0.65%**, with curve radii 90–336 m.
The user independently spotted the constant-radius curves and that it connects to
the known rail alignment. Originally suspected to be an esker; it is not.

This was a detour, not the main thread. **Archived to `notes/railroad/`** on
2026-08-20 with a write-up of the evidence — out of both maps, out of the
pipeline, outside `docs/` so it never publishes. The scripts resolve paths as if
they still live in `scripts/`; copy one back there to re-run it.

---

## Data sources (all verified working)

```
VCGI ArcGIS REST root
  https://maps.vcgi.vermont.gov/arcgis/rest/services/

  EGC_services/IMG_VCGI_CLR2024_WM_CACHE/ImageServer/tile/{z}/{y}/{x}
      2024 colour orthoimagery, cached, Web Mercator
  EGC_services/IMG_VCGI_LIDARHILLSHD_WM_CACHE_v1/ImageServer/tile/{z}/{y}/{x}
      bare-earth LiDAR hillshade — this is what reveals trails under canopy
  MAP_VCGI_LIDARCONTOURS_WM_CACHE_v1/MapServer/tile/{z}/{y}/{x}
      20 ft LiDAR contours
  EGC_services/IMG_VCGI_LIDARDEM_SP_NOCACHE_v1/ImageServer/getSamples
      0.35 m QL1 bare-earth DEM, spring 2023 — POST points, returns elevations
```

Note the ArcGIS tile path is `/{z}/{y}/{x}` — row before column, not the usual
`/{z}/{x}/{y}`. Getting this backwards returns 400s.

OSM data via Overpass: `https://overpass-api.de/api/interpreter`.

---

## Layout

```
Exports/          raw .fit files            GITIGNORED — personal
data/             derived geojson           committed except raw_tracks
docs/             the field PWA + 1599 tiles (12.9 MB) — THE PUBLISHED SITE
notes/railroad/   archived B&L detour, out of the pipeline, never published
scripts/          pipeline + html templates
vendor/           Leaflet 1.9.4, vendored
map.html          desktop review tool, open from disk
```

**Delivery is GitHub Pages, `main` / `docs`.** `docs/index.html` is the site root,
so a shared link opens the trail map directly. `survey.html` and its whole
OSM-gap narrative were retired on 2026-08-20 — that story is dead, and a second
published surface was not worth keeping in sync. The old Claude artifact is
therefore stale and superseded; do not republish it.

### Pipeline order

```
run_pipeline.py      Exports/*.zip          -> unpacks, then runs the chain below
parse_fit.py         Exports/*.fit          -> data/raw_tracks.geojson  [PRIVATE]
clip_tracks.py       raw_tracks             -> data/forest_tracks.geojson
merge_passes.py      forest_tracks          -> data/trails_merged.geojson
gap_audit.py         merged + forest_tracks -> data/gap_candidates.geojson
aoi_tiles.py         aoi polygon            -> tile counts
fetch_tiles.py       VCGI                   -> docs/tiles/
build_field.py       trails_merged + aoi    -> docs/index.html + tiles.json
build_map.py         trails_merged + gaps   -> map.html
privacy_audit.py     GATE — exits non-zero on any leak
```

Both maps read `trails_merged.geojson` and nothing else — `map.html` also reads
`gap_candidates.geojson`, but only to draw the review overlay, never as trail.
`build_map.py` tolerates that file being absent so it still runs standalone. **Never point anything at
`raw_tracks.geojson`** — that is exactly the bug that leaked the user's home into
`map.html` and `grade_candidates.geojson`.

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install fitdecode
```

The venv was rebuilt in place on 2026-08-20 after the folder move and the full
pipeline was re-run clean, so **nothing is pending here**. Kept as a note only
because it will bite again: `.venv/Scripts/` bakes the absolute path into
`activate` and the `pip` / `fitjson` / `fittxt` shims, so *any* future move means
deleting and rebuilding rather than patching. It is gitignored and there is one
dependency, so that costs ten seconds.

`fitdecode` remains the only dependency. `merge_passes.py` is deliberately pure
Python — no numpy, no shapely — so setup stays one line and there are no wheels
to build on Windows.

### Why every walk reprocesses everything

`run_pipeline.py` (added 2026-09-02) is the one command for all of this: it
unpacks every zip in `Exports/`, skipping any `.fit` whose name is already there
so stale zips can sit around without overwriting anything, then runs the chain
and halts on the first non-zero exit — a tripped privacy gate means nothing
downstream gets rebuilt. It does not run `fetch_tiles.py`; tiles only need a
refetch when the AOI widens.

Asked and settled 2026-09-02: should new walks be merged into a saved base map
instead of re-deriving the whole thing? **No.** Full reprocess is both the
cheaper and the more accurate option, which is unusual enough to write down.

*It is not slow.* Measured on the 19-walk set: parse 1.4 s, clip 0.2 s, merge
1.3 s, both builds 0.3 s — **about 3 seconds end to end**. Going 13 → 19 walks
moved the merge from 1.00 s to 1.25 s. The expensive stages (corridor, fill,
thin) scale with the *area* the trails cover, not with the number of walks, and
that area has stopped growing — so merge time is going flat while the data keeps
accumulating. Only `parse_fit.py` is truly linear, at ~0.11 s per file.

*Incremental would be worse, not just equal.* Every stage is global:

- A centreline is the average of **all** fixes near it. Freezing it means the
  first walk's GPS scatter permanently decides where a trail is drawn and no
  later pass can correct it. The opposite is happening now — p95 offset went
  from 3.43 m at 13 walks to 3.15 m at 19.
- Topology comes from thinning the *union* corridor. A walk that links two
  previously separate stubs turns them into a real junction and re-splits the
  chains either side. Bolting a new line onto a frozen network cannot discover
  that; it staples a T-joint onto a line instead.
- `passes` is `len({distinct walks within MATCH_R})` **per vertex**, not a
  counter. Move the vertex and the answer legitimately changes. Incrementing a
  stored count on old geometry produces a different number, not the same one.
- The pipeline is a pure function today: delete `data/` and it regenerates
  identically. With saved state the map would depend on the *order* walks were
  added, and a constant tuned later (`MATCH_R`, `CELL`, `SPUR`) could not be
  applied retroactively without a full reprocess anyway.

*If it ever does get slow*, the fix is to cache `parse_fit.py` per file, keyed on
content hash — it is the one stage that is a genuine per-file map. That is worth
doing somewhere north of a few hundred walks. **Never** freeze the merge.

### The disconnection bugs, fixed 2026-09-07

The user reported, twice, that trails which should join were drawn broken — and
specifically **in high-traffic areas**, which ruled out thin data. Three separate
faults, all in `merge_passes.py`, all now fixed. Ground truth came from a review
pass in the new gap-audit overlay; the user's verdicts are what calibrated the
thresholds, so do not retune these from intuition.

1. **Short connectors were deleted.** `raw = [c for c in chains(skel) if plen >= SPUR]`
   dropped every chain under 12 m — including chains welded to a junction at
   *both* ends, which are connectors, not whiskers. Five were being deleted every
   run, two of them carrying **11 and 12 walks**. The prune loop directly above
   had always had the rule right (`plen < SPUR and not (h and tl)`); the final
   filter simply disagreed with it. `SPUR` is a whisker rule, never a minimum
   trail length.

2. **The hole-fill invented trail.** Stage 2 fills braiding pinholes, which is
   what stops thinning turning every hole into a mesh — but it pays by inventing
   corridor, and the skeleton then runs down ground nobody walked. One blob near
   the entrance produced a segment **10 m from the nearest fix carrying 0 passes**,
   drawing as a hole punched through a 9-pass trail. Now: skeleton cells further
   than `FILL_MAX` from any fix are pruned and the skeleton re-thinned.
   **`FILL_MAX = DILATE + CELL` and the window is narrow** — the corridor reaches
   `DILATE` from a fix and the grid quantises by one cell, so that is the ceiling
   on a legitimately derived cell; real skeleton runs p99 = 4.5 m from a fix.
   Both sides were tested the hard way. At **5 m** the cut severed a stretch two
   walks had crossed and invented four false gaps. At **`MATCH_R`** it left the
   two stubs from the user's screenshot, 7.0 and 7.8 m from any fix, drawn as
   *9-pass trail* — because pass count is sampled at `MATCH_R`, so a stub lying
   within 8 m of a busy trail **inherits that trail's walk count whether or not
   anyone walked the stub**. That inheritance is why phantom geometry does not
   look phantom on the map, and it is the single most useful test in this file:
   compare walks within 3 m of a segment against the count it is drawn with.
   Real trail here sits 0.3–0.4 m from a fix; the stubs had nothing within 7 m.

3. **Thinning left T-junctions hanging.** Thinning is a local rule, so a stem
   meeting a crossbar at a shallow angle can stop metres short, and the cells are
   genuinely not adjacent — re-thinning cannot fix it. `weld()` now rejoins
   dangling ends, **gated on evidence**: at least `WELD_W = 2` distinct walks must
   have a fix near *every* quarter point of the gap. A gap nobody has walked
   stays open, so this does not undo `MATCH_R`. Bridges are laid straight and
   then refined onto the fixes they cross, so a weld across a curve follows the
   curve instead of cutting the corner — which is what the user asked for at the
   rail-bed terminus. Whether an end is dangling is decided **geometrically**, by
   whether anything is actually joined there; the `head`/`tail` flags cannot
   answer it, because they only say "hangs off a junction group" and stay true
   for a stub left alone after the phantom prune removed what it used to meet.

4. **`refine()` ran after `weld()`, so welding judged the wrong gap.** Thinning
   leaves a chain end metres off the line people walked. At the entrance two ends
   sat **11.7 m apart across the void** unrefined and **7.5 m apart** once slid
   onto the trail — so the evidence test sampled ground nobody had walked and
   declined a join **8 walks had made**. Refining first fixed it. General lesson:
   any test about how a map *looks* has to run on the geometry that gets drawn,
   not on an earlier draft of it.

Result: **184 segments in a single connected component**, up from a network that
broke into pieces, and `gap_audit.py` now reports **zero** candidates. The fixes
are worth about 0.05 km of recovered trail, but the point was never the length —
it was that a walked trail is drawn as one trail, and that nothing is drawn where
nobody walked.

### The gap-audit overlay

`gap_audit.py` → `data/gap_candidates.geojson` → numbered rings in `map.html`
under **Review ▸ Gap audit**. It exists because this class of bug is invisible in
aggregate statistics and obvious to someone who has walked the ground.

Detection is deliberately conservative — a gap is reported only if walks actually
cross it, since two trails passing close is what `MATCH_R` exists to preserve.
The workflow: the user marks each candidate real/not/unsure, **shift-clicks the
map** to pin anything the scan missed, and copies a plain-text report back. The
pins carried more information than the verdicts did — one "appendage that is a
mis-step" turned out to be fault 1, a 10 m connector with 12 walks on it.

Keep the overlay. When new walks land, an empty audit is the signal that the
merge is behaving, and a non-empty one is a question worth asking the user.

---

## Privacy model

Every walk starts and ends at the user's condo. The 26 raw endpoints cluster
within a median of **8 m** — the raw data pinpoints their front door, and the
timestamps show when they are routinely out.

Three separate leaks were found and fixed; assume more are possible:

1. **Geometry** — unclipped tracks reaching 0.3 m from the door.
2. **Derived artifacts** — `map.html` and `grade_candidates.geojson` regenerated
   from the raw file after the clip was already written.
3. **Metadata** — the `.fit` filename encodes the user's personal name *and* the
   exact minute of each walk, and survived into the "clean" file via the `name`
   and `source_file` properties. Properties are now rebuilt from scratch as
   `walk-01`…`walk-13`.

`scripts/privacy_audit.py` scans every committable file for coordinates inside the
exclusion radius and for name / timestamp / filename patterns. **Run it before any
push.** It exits non-zero on a leak and works as a pre-commit hook.

---

## Decisions and closed issues

None of these are open. They are here so they do not get relitigated.

1. ~~**Tails on the clipped paths**~~ — **fixed 2026-08-20.** The cut was being
   made at the first point *inside* the 30 m gateway radius, i.e. on the outer
   edge of the circle on the approach side, leaving a stub of driveway on every
   end — 16 of them fanning out of the entrance. `clip_tracks.py` now clusters
   the gateway touches, cuts at the point of closest approach within the first
   and last cluster, and interpolates the terminal vertex onto the exact
   perpendicular foot. On the 13 walks of the day that removed 950 m of stub
   (longest 42.5 m); every endpoint lands 0.0–2.7 m from a gateway node
   instead of ~29.5 m from it.
2. **No forest boundary — and that is the point, not a defect.** The town's
   line is one thing; beyond it is wild land threaded with herd paths and
   neighbourhood connectors. Finding those extents *is* the project, so there is
   no denominator to chase and no "coverage %" worth quoting. `aoi_traced.geojson`
   stays as a tile-fetch envelope only. Expect it to need widening as walks push
   past its edge.
3. ~~**Repeated passes not merged**~~ — **fixed 2026-08-20.** `merge_passes.py`
   collapses every visit into one centreline per trail carrying a `passes` count,
   and both maps draw line weight from it. **6.78 km of distinct trail** out of
   55.50 km walked — 8.2x redundancy. The merged centreline sits a median 0.84 m
   from the nearest real fix (p95 3.12 m). Re-runnable: it is a pure function of
   `forest_tracks.geojson`, so adding a walk means re-running the pipeline, with
   no incremental state to drift.
4. ~~**Nothing uploaded to OSM**~~ — **not a goal.** Not uploading. This also
   retires the tagging question: no `name`, no `informal=yes`, no upload at all.
5. ~~`docs/tiles/` size~~ — **keep them, settled.** GitHub Pages serves straight
   out of the repo, so the 12.9 MB of tiles *is* the offline map. Excluding them
   would mean refetching from VCGI at view time, which breaks offline use in the
   forest and makes the site depend on VCGI being up and CORS-friendly. 12.9 MB
   is nothing against the 1 GB Pages soft limit.

## Wanted next

Nothing here is started. In rough priority order.

### 1. Named routes with distances

The user's idea, raised 2026-08-20, explicitly *not* to be acted on yet.

The shape they described: **select sections of the network, assemble them into a
route, name it, and get total mileage for that route.** So "the long loop" or
"the river out-and-back" becomes a thing with a name and a number, rather than a
shape you have to trace with your eye every time.

Design notes worth having before starting, because one of them is a trap:

- **The rendered features are the wrong selection unit.** `merge_passes.py` splits
  each traced chain into runs of *equal pass count*, so one continuous trail
  between two junctions can be several features, and a feature can end in the
  middle of nowhere where the visit count happened to change. For routes the unit
  wants to be junction-to-junction, with pass count carried along the segment
  rather than used to split it. Cleanest fix is a second output —
  `trails_topology.geojson`, one feature per junction-to-junction edge with node
  ids at each end — leaving `trails_merged.geojson` alone for rendering.
- Node ids fall straight out of the existing tracer: `chains()` already clusters
  junction cells into groups and welds every chain end onto a shared centroid.
  Those group indices *are* the node ids; they are simply not emitted today.
- Distance is free — `length_m` is already per segment, so a route total is a sum.
  Report miles, since that is how the user thinks about it.
- **Where routes live matters.** The site is static on GitHub Pages, so either
  routes are committed as `data/routes.json` and rebuilt into the page, or they
  are per-viewer in `localStorage`. Committed is right for anything shareable to
  locals; `localStorage` alone would strand a route on one phone.
- Assembling by clicking segments needs a click-to-select interaction and a
  copy-to-clipboard, much like the trace tool that was removed. That tool is gone
  from `map_template.html` but recoverable from git history if the pattern helps.
- Once edges carry node ids, "shortest route between these two points" is a
  Dijkstra away. Probably not wanted, but the data would support it.

### 2. Walk more

The map improves on its own with every walk. About a fifth of the network has
been crossed exactly once; both maps flag it on request.

- Once-only trail and the spurs running off the ends of the tracks
- Widen `aoi_traced.geojson` as walks push past it, then refetch tiles. Checked
  on 2026-09-07: the 20 walks still sit inside the AOI *bounding box*, so the
  fetched tiles still cover them and no refetch is due. Two merged vertices do
  fall outside the traced *ring*, up to 83.0 m, all of them the entrance stub —
  that is pre-existing (the 8- and 13-walk maps had the same two) and is the ring
  clipping the gateway, not a walk escaping the envelope.
- Watch for genuinely parallel paths closer than `MATCH_R = 8.0` m getting fused
  into one line. More data will not split them — it only makes the fused line
  more confident. That constant is the fix, and only the user can spot the case
  from the ground.

## Shipped

Pushed 2026-08-20 as **[EarlAbides/JerichoTownForestMap](https://github.com/EarlAbides/JerichoTownForestMap)**,
public, branch `main`. First commit `024f60c`, 1641 files. `gh` is authenticated
as EarlAbides over ssh.

**Local checkout lives at `C:\Users\jeffr\Projects\GitHub\EarlAbides\JerichoTownForestMap`.**
Moved there from `GitHub\ForestMap` on 2026-08-20 to match the repo name and to
sit under an owner directory. Git itself is unaffected by the move — no absolute
paths in `.git/config`, and every script resolves its own root from `__file__` —
but the venv is, see above.

**GitHub Pages is enabled**, legacy build from `main` / `docs`, HTTPS enforced:
https://earlabides.github.io/JerichoTownForestMap/

Geolocation needs HTTPS, so the field PWA cannot locate you from `file://` —
only from the Pages URL. That is expected, not a bug to chase.
