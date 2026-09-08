"""Unpack any new walks sitting in Exports/, then run the whole pipeline.

Adding walks is: drop the HealthFit .zip (or the loose .fit files) into
Exports/ and run this.  Every stage is a pure function of its input, so the
map is re-derived from scratch every time -- about three seconds end to end,
and getting relatively cheaper as the trail network saturates.  See "Why every
walk reprocesses everything" in STATE.md before reaching for anything clever.

Unpacking is deliberately dumb: a .fit whose name is already in Exports/ is
skipped, never overwritten.  HealthFit names its exports by timestamp, so the
name identifies the walk, and leaving old zips lying around costs nothing --
re-running an already-unpacked zip extracts nothing.  A newer zip carrying
newer walks contributes exactly those walks.

fetch_tiles.py is not run here.  The offline tiles only need refetching if the
AOI widens; check with aoi_tiles.py when walks start pushing past its edge.
"""
import pathlib
import subprocess
import sys
import time
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "Exports"

STAGES = ["parse_fit.py", "clip_tracks.py", "merge_passes.py", "gap_audit.py",
          "build_field.py", "build_map.py", "privacy_audit.py"]


def unpack():
    """Extract .fit members that are not already in Exports/.  Never overwrite."""
    zips = sorted(EXPORTS.glob("*.zip"))
    if not zips:
        return 0
    new = 0
    for z in zips:
        added, had = [], 0
        with zipfile.ZipFile(z) as zf:
            for info in zf.infolist():
                name = pathlib.PurePosixPath(info.filename).name
                if info.is_dir() or not name.lower().endswith(".fit"):
                    continue
                if info.filename.startswith("__MACOSX"):
                    continue
                target = EXPORTS / name
                if target.exists():
                    had += 1
                    continue
                target.write_bytes(zf.read(info))
                added.append(name)
        note = f"{len(added)} new" if added else "nothing new"
        print(f"  {z.name:<28} {note}, {had} already unpacked")
        for name in added:
            print(f"      + {name}")
        new += len(added)
    return new


def main():
    print(f"unpack   {EXPORTS}")
    new = unpack()
    fits = sorted(EXPORTS.glob("*.fit"))
    if not fits:
        sys.exit(f"No .fit files in {EXPORTS}")
    print(f"  {len(fits)} .fit files total, {new} added this run\n")

    for stage in STAGES:
        print(f"===== {stage} " + "=" * (40 - len(stage)))
        t = time.time()
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / stage)],
                            cwd=ROOT).returncode
        if rc:
            sys.exit(f"\n{stage} failed (exit {rc}) -- pipeline stopped, "
                     f"nothing downstream was rebuilt.")
        print(f"[{stage} ok, {time.time() - t:.2f}s]\n")

    print("Pipeline clean. Review map.html, then commit docs/ and map.html.")


if __name__ == "__main__":
    main()
