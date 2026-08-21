"""Parse Apple Watch FIT exports into per-track GeoJSON + a summary report.

WARNING: the output raw_tracks.geojson contains home location, personal name
and exact timestamps. It is gitignored. Run clip_tracks.py before anything
downstream consumes it.
"""
import json
import math
import pathlib
import sys

import fitdecode

SEMI = 180.0 / (2**31)
ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "Exports"
OUT = ROOT / "data"


def to_deg(v):
    """FIT stores lat/lon in semicircles; some writers emit degrees already."""
    if v is None:
        return None
    return v * SEMI if abs(v) > 180 else float(v)


def haversine(a, b):
    r = 6371008.8
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp = p2 - p1
    dl = math.radians(b[0] - a[0])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def read_track(path):
    pts, times, alts, hacc = [], [], [], []
    with fitdecode.FitReader(str(path)) as fr:
        for frame in fr:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA or frame.name != "record":
                continue
            lat = to_deg(frame.get_value("position_lat", fallback=None))
            lon = to_deg(frame.get_value("position_long", fallback=None))
            if lat is None or lon is None:
                continue
            pts.append((lon, lat))
            times.append(frame.get_value("timestamp", fallback=None))
            alts.append(frame.get_value("enhanced_altitude", fallback=None)
                        or frame.get_value("altitude", fallback=None))
            hacc.append(frame.get_value("gps_accuracy", fallback=None))
    return pts, times, alts, hacc


def main():
    files = sorted(EXPORTS.glob("*.fit"))
    if not files:
        sys.exit(f"No .fit files in {EXPORTS}")

    OUT.mkdir(exist_ok=True)
    features, rows = [], []
    all_lon, all_lat = [], []

    for f in files:
        pts, times, alts, hacc = read_track(f)
        if len(pts) < 2:
            rows.append((f.name, 0, 0.0, None, None, "NO GPS DATA"))
            continue

        dist = sum(haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        lons = [p[0] for p in pts]
        lats = [p[1] for p in pts]
        all_lon += lons
        all_lat += lats

        good_alt = [a for a in alts if a is not None]
        good_acc = [a for a in hacc if a is not None]
        dur = None
        if times[0] and times[-1]:
            dur = (times[-1] - times[0]).total_seconds() / 60.0

        name = f.stem
        features.append({
            "type": "Feature",
            "properties": {
                "source_file": f.name,
                "name": name,
                "points": len(pts),
                "distance_km": round(dist / 1000, 3),
                "duration_min": round(dur, 1) if dur else None,
                "start_time": times[0].isoformat() if times[0] else None,
                "median_gps_accuracy_m": (
                    round(sorted(good_acc)[len(good_acc) // 2], 1) if good_acc else None
                ),
            },
            "geometry": {"type": "LineString", "coordinates": [list(p) for p in pts]},
        })
        rows.append((
            f.name[:26], len(pts), round(dist / 1000, 2),
            round(dur, 1) if dur else None,
            round(sorted(good_acc)[len(good_acc) // 2], 1) if good_acc else None,
            f"{min(lats):.5f},{min(lons):.5f} .. {max(lats):.5f},{max(lons):.5f}",
        ))

    fc = {"type": "FeatureCollection", "features": features}
    (OUT / "raw_tracks.geojson").write_text(json.dumps(fc), encoding="utf-8")

    print(f"{'file':28} {'pts':>6} {'km':>7} {'min':>7} {'acc_m':>6}  bbox")
    for r in rows:
        print(f"{r[0]:28} {r[1]:>6} {r[2]:>7} {str(r[3]):>7} {str(r[4]):>6}  {r[5]}")

    if all_lat:
        print(f"\nCOMBINED BBOX  S={min(all_lat):.6f} W={min(all_lon):.6f} "
              f"N={max(all_lat):.6f} E={max(all_lon):.6f}")
        print(f"center: {(min(all_lat)+max(all_lat))/2:.6f}, "
              f"{(min(all_lon)+max(all_lon))/2:.6f}")
        span_km_ns = haversine((0, min(all_lat)), (0, max(all_lat))) / 1000
        span_km_ew = haversine((min(all_lon), sum(all_lat)/len(all_lat)),
                               (max(all_lon), sum(all_lat)/len(all_lat))) / 1000
        print(f"extent: {span_km_ns:.2f} km N-S x {span_km_ew:.2f} km E-W")
        print(f"total distance walked: {sum(f['properties']['distance_km'] for f in features):.2f} km")
    print(f"\nwrote {OUT/'raw_tracks.geojson'}")


if __name__ == "__main__":
    main()
