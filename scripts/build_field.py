import json, pathlib, shutil
ROOT=pathlib.Path(__file__).resolve().parent.parent
DOCS=ROOT/"docs"; DOCS.mkdir(exist_ok=True)

trk=json.loads((ROOT/"data/trails_merged.geojson").read_text(encoding="utf-8"))
aoi=json.loads((ROOT/"data/aoi_traced.geojson").read_text(encoding="utf-8"))

co=aoi["geometry"]["coordinates"]
if co[0]!=co[-1]: co=co+[co[0]]
aoi_poly={"type":"Feature","properties":{},
          "geometry":{"type":"Polygon","coordinates":[co]}}

lats=[c[1] for f in trk["features"] for c in f["geometry"]["coordinates"]]
lons=[c[0] for f in trk["features"] for c in f["geometry"]["coordinates"]]
bounds=[[min(lats),min(lons)],[max(lats),max(lons)]]

tpl=(ROOT/"scripts/field_template.html").read_text(encoding="utf-8")
html=(tpl.replace("/*__TRAILS__*/",json.dumps(trk))
         .replace("/*__AOI__*/",json.dumps(aoi_poly))
         .replace("/*__BOUNDS__*/",json.dumps(bounds)))
(DOCS/"index.html").write_text(html,encoding="utf-8")
for f in ("leaflet.js","leaflet.css","marker-shadow.png"):
    shutil.copy(ROOT/"vendor"/f, DOCS/f)
tiles=sorted(p.relative_to(DOCS).as_posix() for p in (DOCS/"tiles").rglob("*")
             if p.is_file())
(DOCS/"tiles.json").write_text(json.dumps(tiles))
mb=sum((DOCS/t).stat().st_size for t in tiles)/1024/1024
print(f"tiles.json       {len(tiles)} tiles, {mb:.1f} MB")
print(f"docs/index.html  {(DOCS/'index.html').stat().st_size/1024:.0f} KB")
print(f"trail segments: {len(trk['features'])}, "
      f"{sum(f['properties']['length_m'] for f in trk['features'])/1000:.2f} km")
