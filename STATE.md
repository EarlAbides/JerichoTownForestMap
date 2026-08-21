# Project state — resume here

Working notes for picking this up in a fresh session. Last updated 2026-08-20.

**Nothing is committed.** The repo is initialized, everything is staged, the privacy
audit passes. Holding at the gate deliberately — see Open issues.

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

- **8 walks**, Aug 8–19 2026, exported from HealthFit as `.fit` (not GPX — HealthFit
  does not offer GPX; FIT parses fine with `fitdecode`).
- **21.41 km** of forest walking after clipping, from 25.15 km raw.
- **5.45 km of distinct trail** after merging repeat visits — 3.9x redundancy.
  About a third of it has been walked only once; both maps flag that on request.
- **Median GPS accuracy 2 m** even under summer canopy. Merged centrelines sit a
  median 0.82 m from the nearest real fix (p95 2.78 m).

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
parse_fit.py         Exports/*.fit          -> data/raw_tracks.geojson  [PRIVATE]
clip_tracks.py       raw_tracks             -> data/forest_tracks.geojson
merge_passes.py      forest_tracks          -> data/trails_merged.geojson
aoi_tiles.py         aoi polygon            -> tile counts
fetch_tiles.py       VCGI                   -> docs/tiles/
build_field.py       trails_merged + aoi    -> docs/index.html + tiles.json
build_map.py         trails_merged          -> map.html
privacy_audit.py     GATE — exits non-zero on any leak
```

Both maps read `trails_merged.geojson` and nothing else. **Never point anything at
`raw_tracks.geojson`** — that is exactly the bug that leaked the user's home into
`map.html` and `grade_candidates.geojson`.

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install fitdecode
```

**The venv is not portable and the project has just been moved.** `.venv/Scripts/`
bakes the absolute path into `activate` and into the `pip` / `fitjson` / `fittxt`
shims, so a moved venv breaks in confusing ways. It is gitignored and there is
exactly one dependency, so delete and rebuild rather than patching:

```
rm -rf .venv && python -m venv .venv
.venv/Scripts/python.exe -m pip install fitdecode
```

Then re-run the pipeline once to confirm, ending with `privacy_audit.py`.

`fitdecode` remains the only dependency. `merge_passes.py` is deliberately pure
Python — no numpy, no shapely — so setup stays one line and there are no wheels
to build on Windows.

---

## Privacy model

Every walk starts and ends at the user's condo. The 16 raw endpoints cluster
within a median of **8 m** — the raw data pinpoints their front door, and the
timestamps show when they are routinely out.

Three separate leaks were found and fixed; assume more are possible:

1. **Geometry** — unclipped tracks reaching 0.3 m from the door.
2. **Derived artifacts** — `map.html` and `grade_candidates.geojson` regenerated
   from the raw file after the clip was already written.
3. **Metadata** — the `.fit` filename encodes the user's personal name *and* the
   exact minute of each walk, and survived into the "clean" file via the `name`
   and `source_file` properties. Properties are now rebuilt from scratch as
   `walk-01`…`walk-08`.

`scripts/privacy_audit.py` scans every committable file for coordinates inside the
exclusion radius and for name / timestamp / filename patterns. **Run it before any
push.** It exits non-zero on a leak and works as a pre-commit hook.

---

## Open issues

1. ~~**Tails on the clipped paths**~~ — **fixed 2026-08-20.** The cut was being
   made at the first point *inside* the 30 m gateway radius, i.e. on the outer
   edge of the circle on the approach side, leaving a stub of driveway on every
   end — 16 of them fanning out of the entrance. `clip_tracks.py` now clusters
   the gateway touches, cuts at the point of closest approach within the first
   and last cluster, and interpolates the terminal vertex onto the exact
   perpendicular foot. 579 m of stub removed (longest 40.9 m); every endpoint
   now lands 0.0–2.5 m from a gateway node instead of ~29.5 m from it.
2. **No forest boundary — and that is the point, not a defect.** The town's
   line is one thing; beyond it is wild land threaded with herd paths and
   neighbourhood connectors. Finding those extents *is* the project, so there is
   no denominator to chase and no "coverage %" worth quoting. `aoi_traced.geojson`
   stays as a tile-fetch envelope only. Expect it to need widening as walks push
   past its edge.
3. ~~**Repeated passes not merged**~~ — **fixed 2026-08-20.** `merge_passes.py`
   collapses every visit into one centreline per trail carrying a `passes` count,
   and both maps draw line weight from it. **5.45 km of distinct trail** out of
   21.41 km walked — 3.9x redundancy. The merged centreline sits a median 0.82 m
   from the nearest real fix (p95 2.78 m). Re-runnable: it is a pure function of
   `forest_tracks.geojson`, so adding a walk means re-running the pipeline, with
   no incremental state to drift.
4. ~~**Nothing uploaded to OSM**~~ — **not a goal.** Not uploading. This also
   retires the tagging question: no `name`, no `informal=yes`, no upload at all.
5. ~~`docs/tiles/` size~~ — **keep them, settled.** GitHub Pages serves straight
   out of the repo, so the 12.9 MB of tiles *is* the offline map. Excluding them
   would mean refetching from VCGI at view time, which breaks offline use in the
   forest and makes the site depend on VCGI being up and CORS-friendly. 12.9 MB
   is nothing against the 1 GB Pages soft limit.

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
