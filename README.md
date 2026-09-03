# Jericho Town Forest — trail map

A trail map of the Jericho Town Forest in Jericho, Vermont, built from Apple Watch
GPS tracks and Vermont's open LiDAR and orthoimagery.

The trails here are informal — no blazes, no signs, no names — and the forest has
no crisp edge. The town's line is one thing; past it is wild land threaded with
herd paths and neighbourhood connectors that appear on no map at all. Working out
where they actually go, by walking them, is the point of this repository.

**Live map:** https://earlabides.github.io/JerichoTownForestMap/
(GitHub Pages, served from `main` / `docs`)

## What's here

`docs/` is a self-contained progressive web app and the published site. It
installs to a phone home screen, shows your position over aerial imagery or
bare-earth LiDAR terrain, and works with no cell signal once you tap **Download
map for offline use** — the 1,599 tiles it needs ship in the repo.

`map.html` is the same map as a desktop review tool, with LiDAR contours and a
hillshade blend for spotting trail you have not walked yet. Open it from disk.

Both draw one line per trail, weighted by how many separate visits crossed it.
The visual scale saturates at **8 visits** and deliberately does not track the
data maximum: anything walked 8 times or more reads the same. Tying the scale to
the actual maximum would restretch the whole map every time a walk was added, so
a trail nobody had touched would change colour and weight on its own and no two
versions would be comparable.

## Pipeline

Each script is independent and re-runnable in this order:

| Script | Does |
|---|---|
| `parse_fit.py` | Apple Watch `.fit` exports → `raw_tracks.geojson` |
| `clip_tracks.py` | Clips to the forest gateways, strips timestamps → `forest_tracks.geojson` |
| `merge_passes.py` | Collapses repeat visits into one centreline per trail → `trails_merged.geojson` |
| `aoi_tiles.py` | Validates the area polygon, counts tiles |
| `fetch_tiles.py` | Pre-fetches VCGI tiles for offline use |
| `build_field.py` | Builds `docs/` |
| `build_map.py` | Builds `map.html` |
| `privacy_audit.py` | Gate — exits non-zero on any leak. Run before every push |

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install fitdecode
.venv/Scripts/python.exe scripts/parse_fit.py
```

`fitdecode` is the only dependency. Adding new walks means dropping the `.fit`
files into `Exports/` and running the pipeline again from the top — every stage is
a pure function of its input, so nothing drifts out of sync.

## How the merge works

Nineteen walks over one path are nineteen parallel lines with GPS scatter between
them. `merge_passes.py` turns them into one line down the middle carrying a count
of how often it has been walked:

1. stamp a 4 m disc around every fix — half the 8 m match tolerance, so two passes
   of the same trail fuse into a solid corridor while genuinely separate trails
   stay apart
2. fill the pinholes GPS braiding leaves inside the corridor, keeping real loops
3. thin to a one-cell skeleton for the network topology
4. trace it into chains, junction to junction
5. slide each vertex sideways onto the centre of the local fixes, recovering the
   sub-metre precision the grid threw away

## Findings

**50.48 km walked across 19 outings**, median GPS accuracy 2 m under summer canopy.
That merges down to **6.33 km of distinct trail** — 8.0× redundancy — of which
about a fifth has been walked only once and is worth a second visit to confirm.
The merged centrelines sit a median of 0.88 m from the nearest real GPS fix.

A section of the **Burlington & Lamoille Railroad** also runs through the forest —
a 2.36 km abandoned grade traced off the LiDAR hillshade. It is not part of the
trail map; the evidence and the scripts are archived in
[`notes/railroad/`](notes/railroad/).

## Privacy

Every recorded walk begins and ends at a private residence; the 26 raw track
endpoints cluster within a median of 8 m, which pinpoints a front door and shows
when it is routinely empty. `.gitignore` therefore excludes `Exports/` and
`data/raw_tracks.geojson`.

Only clipped data is committed — cut at the forest gateways, held at least 100 m
from the convergence point, and stripped of all timestamps. The `.fit` filenames
themselves encode a personal name and the exact minute of each walk, so track
properties are rebuilt from scratch rather than carried over.

`privacy_audit.py` scans every committable file for coordinates inside the
exclusion radius and for name, timestamp and filename patterns. It exits non-zero
on a leak and works as a pre-commit hook. Three separate leaks have been caught
this way; assume more are possible.

## Data sources and licensing

Imagery, LiDAR DEM, hillshade and contours are © [VCGI](https://vcgi.vermont.gov/),
Vermont Center for Geographic Information, used as open state data.
`docs/tiles/` redistributes 1,599 VCGI tiles for offline use, with attribution
shown in the map.

Trail data from Trailforks and AllTrails was **deliberately not used**. Both are
proprietary databases. Everything here derives from personal GPS recordings and
openly licensed government data.

## Still to do

- Walk the once-only trail and the spurs that run off the edge of the tracks
- Widen the area-of-interest polygon as walks push past it, and refetch tiles
- Keep merging: the map improves on its own with every walk added
