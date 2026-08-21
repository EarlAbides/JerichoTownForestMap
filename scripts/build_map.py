"""Build map.html -- the desktop review map, opened straight off disk.

Reads only the merged trail network.  Individual walks, OSM paths and the
railroad alignment are deliberately not carried through: the map shows one line
per trail, weighted by how many visits crossed it.
"""
import json, pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent

trails = json.loads((ROOT/"data/trails_merged.geojson").read_text(encoding="utf-8"))

lats = [p[1] for f in trails["features"] for p in f["geometry"]["coordinates"]]
lons = [p[0] for f in trails["features"] for p in f["geometry"]["coordinates"]]
bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]

tpl = (ROOT/"scripts/map_template.html").read_text(encoding="utf-8")
html = (tpl.replace("/*__TRAILS__*/", json.dumps(trails))
           .replace("/*__BOUNDS__*/", json.dumps(bounds)))
(ROOT/"map.html").write_text(html, encoding="utf-8")

by = defaultdict(float)
for f in trails["features"]:
    by[f["properties"]["passes"]] += f["properties"]["length_m"]
print(f"wrote map.html  {(ROOT/'map.html').stat().st_size/1024:.0f} KB")
print(f"{len(trails['features'])} segments, "
      f"{sum(by.values())/1000:.2f} km, up to {max(by)} visits")
