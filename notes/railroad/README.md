# The Burlington & Lamoille grade — archived

Not part of the trail map. Parked here because it is a real finding and the
evidence took work to assemble, not because anything downstream needs it.

## What it is

A 2.36 km alignment running through the forest, first traced by eye off the VCGI
bare-earth LiDAR hillshade. The initial guess was an esker. It is not — it is a
section of the **Burlington & Lamoille Railroad**, chartered 1877, running
Burlington → Essex → Jericho → Cambridge Junction, abandoned 1938.

## The evidence

Sampled against Vermont's 0.35 m QL1 bare-earth DEM (spring 2023):

- **91%** of its length holds railroad-consistent gradient
- a continuous **729 m run at 0.65%**
- curve radii between **90 m and 336 m** — constant-radius, not meandering

No natural landform holds two thirds of a percent for three quarters of a
kilometre, and eskers do not turn on fixed radii. The constant-radius curves and
the connection to the known rail alignment were spotted independently on the map
before the DEM analysis confirmed them.

## The scripts

| Script | Does |
|---|---|
| `grade_profile.py` | Samples the LiDAR DEM along tracks, finds low-gradient runs |
| `snap_alignment.py` | Snaps a hand-traced line onto the true bench centreline |
| `classify_alignment.py` | Splits an alignment by railroad-grade consistency |
| `analyze_alignment.py` | Gradient and curve-radius statistics |
| `cross_section.py` | Cuts perpendicular DEM transects across an alignment |

They resolve paths as `Path(__file__).parent.parent`, which assumed they lived in
`scripts/` at the repo root. To re-run any of them, copy it back there first.

They hit the VCGI DEM sampling endpoint:

```
https://maps.vcgi.vermont.gov/arcgis/rest/services/EGC_services/
  IMG_VCGI_LIDARDEM_SP_NOCACHE_v1/ImageServer/getSamples
```

POST points, get elevations back.

## The data

`traced_alignment.geojson` is the hand trace, `snapped_alignment.geojson` the
DEM-snapped centreline, `alignment_classified.geojson` the same line split by
grade consistency, and `alignment_analysis.json` the summary statistics.
`grade_candidates.geojson` is the wider sweep for low-gradient runs along the
walked tracks — how the alignment turned up in the first place.
