#!/usr/bin/env python3
"""Preflight STL geometry before importing into DEFORM-3D.

Reports, per file: encoding (ASCII/binary), triangle and node counts, bounding
box, watertightness (every edge shared by exactly 2 faces), signed volume and
degenerate faces.

Console output is deliberately ASCII-only: Windows consoles here are cp936 and
mangle non-ASCII output, which makes a geometry report worse than useless.

Stdlib only. Usage:
    python preflight_stl.py <file-or-dir> [more...] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys

# Vertices coming out of the same CAD export normally agree exactly, but meshes
# that went through a converter can differ in the last bits. Rounding to 1e-4 mm
# (0.1 micron) merges those without merging genuinely distinct vertices.
ROUND_ND = 4


def detect_encoding(path: str) -> str:
    """Return 'ascii' or 'binary'.

    Size is the reliable test: a binary STL is exactly 84 + 50*n bytes. The
    leading keyword cannot be trusted, because binary STL exporters often write
    'solid' into the 80-byte header anyway.
    """
    size = os.path.getsize(path)
    if size < 84:
        return "ascii"
    with open(path, "rb") as fh:
        head = fh.read(84)
    (count,) = struct.unpack("<I", head[80:84])
    return "binary" if 84 + 50 * count == size else "ascii"


def read_ascii(path: str):
    """Yield (v0, v1, v2) triangles from an ASCII STL.

    Keyword matching is case-insensitive on purpose: DEFORM and several
    exporters write the uppercase variant (SOLID / FACET NORMAL / VERTEX),
    while the STL convention is lowercase. Both occur in the wild.
    """
    tri = []
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            parts = line.split()
            if not parts or parts[0].lower() != "vertex":
                continue
            tri.append((float(parts[1]), float(parts[2]), float(parts[3])))
            if len(tri) == 3:
                yield tri[0], tri[1], tri[2]
                tri = []


def read_binary(path: str):
    """Yield (v0, v1, v2) triangles from a binary STL."""
    with open(path, "rb") as fh:
        fh.seek(84)
        while True:
            rec = fh.read(50)
            if len(rec) < 50:
                return
            vals = struct.unpack("<12fH", rec)
            yield ((vals[3], vals[4], vals[5]),
                   (vals[6], vals[7], vals[8]),
                   (vals[9], vals[10], vals[11]))


def analyse(path: str) -> dict:
    enc = detect_encoding(path)
    reader = read_binary(path) if enc == "binary" else read_ascii(path)

    with open(path, "rb") as fh:
        starts_with_solid = fh.read(5).lower() == b"solid"

    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    edges: dict[tuple, int] = {}
    nodes: set = set()
    ntris = 0
    degenerate = 0
    volume = 0.0

    for v0, v1, v2 in reader:
        ntris += 1
        for v in (v0, v1, v2):
            nodes.add((round(v[0], ROUND_ND), round(v[1], ROUND_ND), round(v[2], ROUND_ND)))
            for i in range(3):
                if v[i] < lo[i]:
                    lo[i] = v[i]
                if v[i] > hi[i]:
                    hi[i] = v[i]

        ax, ay, az = v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]
        bx, by, bz = v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]
        cx = ay * bz - az * by
        cy = az * bx - ax * bz
        cz = ax * by - ay * bx
        if math.sqrt(cx * cx + cy * cy + cz * cz) < 1e-10:
            degenerate += 1

        volume += (v0[0] * (v1[1] * v2[2] - v1[2] * v2[1])
                   - v0[1] * (v1[0] * v2[2] - v1[2] * v2[0])
                   + v0[2] * (v1[0] * v2[1] - v1[1] * v2[0])) / 6.0

        for a, b in ((v0, v1), (v1, v2), (v2, v0)):
            ka = (round(a[0], ROUND_ND), round(a[1], ROUND_ND), round(a[2], ROUND_ND))
            kb = (round(b[0], ROUND_ND), round(b[1], ROUND_ND), round(b[2], ROUND_ND))
            key = (ka, kb) if ka <= kb else (kb, ka)
            edges[key] = edges.get(key, 0) + 1

    boundary = sum(1 for c in edges.values() if c == 1)
    nonmanifold = sum(1 for c in edges.values() if c > 2)

    if ntris == 0:
        return {
            "file": path, "encoding": enc, "triangles": 0, "nodes": 0,
            "bbox": None, "watertight": None, "boundary_edges": None,
            "nonmanifold_edges": None, "volume": None, "degenerate": 0,
            "error": "no triangles parsed",
        }

    dims = [hi[i] - lo[i] for i in range(3)]
    return {
        "file": path,
        "encoding": enc,
        "starts_with_solid": starts_with_solid,
        "triangles": ntris,
        "nodes": len(nodes),
        "bbox": {"min": lo, "max": hi, "dims": dims},
        "watertight": boundary == 0 and nonmanifold == 0,
        "boundary_edges": boundary,
        "nonmanifold_edges": nonmanifold,
        "volume": volume,
        "volume_abs": abs(volume),
        "normals_outward": volume > 0,
        "degenerate": degenerate,
    }


def fmt_dims(d):
    return " x ".join(f"{x:.2f}" for x in d)


def collect(targets) -> list:
    files = []
    for t in targets:
        if os.path.isdir(t):
            for root, _dirs, names in os.walk(t):
                for n in sorted(names):
                    if n.lower().endswith(".stl"):
                        files.append(os.path.join(root, n))
        else:
            files.append(t)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description="Preflight STL files for DEFORM-3D.")
    ap.add_argument("targets", nargs="+", help="STL files and/or directories")
    ap.add_argument("--json", metavar="PATH", help="also write machine-readable results")
    args = ap.parse_args()

    files = collect(args.targets)
    if not files:
        print("No .stl files found.")
        return 1

    results = []
    print(f"{'FILE':<32} {'ENC':<7} {'TRIS':>7} {'NODES':>7}  "
          f"{'BBOX (file units)':<26} {'VOLUME':>12} {'WATERTIGHT':<11} {'DEGEN':>5}")
    print("-" * 118)

    warn = []
    for path in files:
        try:
            r = analyse(path)
        except Exception as exc:  # keep going: one bad file must not stop the batch
            r = {"file": path, "error": f"{type(exc).__name__}: {exc}",
                 "encoding": "?", "triangles": 0, "nodes": 0, "bbox": None,
                 "watertight": None, "degenerate": 0}
        results.append(r)

        name = os.path.basename(path)
        if r.get("bbox") is None:
            print(f"{name[:31]:<32} {r.get('encoding','?'):<7} {'-':>7} {'-':>7}  "
                  f"{r.get('error','unreadable'):<26} {'-':>12} {'-':<11} {'-':>5}")
            warn.append(f"{name}: {r.get('error')}")
            continue

        dims = fmt_dims(r["bbox"]["dims"])
        wt = "yes" if r["watertight"] else f"NO({r['boundary_edges']})"
        print(f"{name[:31]:<32} {r['encoding']:<7} {r['triangles']:>7} {r['nodes']:>7}  "
              f"{dims:<26} {r['volume_abs']:>12.4g} {wt:<11} {r['degenerate']:>5}")

        if not r["watertight"]:
            warn.append(f"{name}: not watertight - {r['boundary_edges']} boundary edge(s), "
                        f"{r['nonmanifold_edges']} non-manifold edge(s). Fatal for a plastic "
                        "workpiece or a die that must mesh as a solid; acceptable for a rigid "
                        "planar pusher (a flat sheet is expected to have boundary edges).")
        if r["degenerate"]:
            warn.append(f"{name}: {r['degenerate']} degenerate (zero-area) face(s).")
        if r["volume"] < 0:
            warn.append(f"{name}: signed volume is negative - face normals point inward.")

    print()
    print("Interpretation: the numbers above are in the file's own units.")
    print("DEFORM reads them as the case's length unit: mm for SI, inch for English.")
    for r in results:
        if r.get("bbox"):
            mm = r["bbox"]["dims"]
            print(f"  {os.path.basename(r['file'])[:31]:<32} as SI: {fmt_dims(mm)} mm"
                  f"   |   as English: {fmt_dims([x*25.4 for x in mm])} mm")

    misleading = [r for r in results
                  if r.get("starts_with_solid") and r.get("encoding") == "binary"]
    if misleading:
        print()
        print(f"NOTE: {len(misleading)} file(s) start with 'solid' yet are binary STL "
              f"(e.g. {os.path.basename(misleading[0]['file'])}).")
        print("      The header keyword does not indicate encoding - DEFORM itself writes binary")
        print("      STL with a 'SOLID ...' header. Judge by size (84 + 50*n), not by the keyword.")

    if warn:
        print()
        print("WARNINGS")
        for w in warn:
            print(f"  - {w}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False)
        print(f"\nJSON written to {args.json}")

    return 0 if not warn else 2


if __name__ == "__main__":
    sys.exit(main())
