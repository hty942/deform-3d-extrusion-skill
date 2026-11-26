#!/usr/bin/env python3
"""Determine which unit system a DEFORM case (or material library folder) uses.

DEFORM .KEY files carry a `UNIT n` line, but NOT on the first line and not in
every file, so the only reliable approach is to scan for the keyword and tally
the values found. UNIT 1 = SI (mm/N/MPa/C/s), UNIT 2 = English (inch/lbf/ksi/F/s).

Also decodes the material-library naming convention: the `_s` variant is SI,
the `_e` variant is English.

Console output is ASCII-only on purpose (cp936 console). Stdlib only. Usage:
    python read_key_unit.py <dir-or-file> [more...] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Not anchored to line 1 by design - see module docstring.
UNIT_RE = re.compile(r"^\s*UNIT\s+(\d+)\s*$")
YOUNG_RE = re.compile(r"^\s*YOUNG\s+\d+\s+\d+\s+([-+0-9.Ee]+)\s*$")
MASDEN_RE = re.compile(r"^\s*MASDEN\s+\d+\s+\d+\s+([-+0-9.Ee]+)\s*$")

UNIT_NAME = {
    1: "SI  (mm / N / MPa / C / s)",
    2: "English (inch / lbf / ksi / F / s)",
}


def variant_from_name(path: str) -> str | None:
    """Material files: <name>_s00000N.KEY is SI, <name>_e00000N.KEY is English."""
    base = os.path.basename(path)
    if re.search(r"_s\d{6}\.KEY$", base, re.IGNORECASE):
        return "s (SI variant)"
    if re.search(r"_e\d{6}\.KEY$", base, re.IGNORECASE):
        return "e (English variant)"
    return None


def scan(path: str) -> dict:
    unit = None
    unit_line = None
    young = None
    masden = None
    try:
        with open(path, "r", errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                if unit is None:
                    m = UNIT_RE.match(line)
                    if m:
                        unit = int(m.group(1))
                        unit_line = lineno
                if young is None:
                    m = YOUNG_RE.match(line)
                    if m:
                        young = float(m.group(1))
                if masden is None:
                    m = MASDEN_RE.match(line)
                    if m:
                        masden = float(m.group(1))
                if unit is not None and young is not None and masden is not None:
                    break
    except OSError as exc:
        return {"file": path, "error": str(exc)}
    return {
        "file": path,
        "unit": unit,
        "unit_line": unit_line,
        "young": young,
        "masden": masden,
        "name_variant": variant_from_name(path),
    }


def collect(targets):
    """Split targets into existing .KEY files and paths that do not exist.

    Silently treating a bad path as "a file with no UNIT line" would turn a typo
    into a confident wrong answer about the unit system, so missing paths are
    reported separately and make the run fail.
    """
    files, missing = [], []
    for t in targets:
        if os.path.isdir(t):
            for root, _dirs, names in os.walk(t):
                for n in sorted(names):
                    if n.lower().endswith(".key"):
                        files.append(os.path.join(root, n))
        elif os.path.isfile(t):
            files.append(t)
        else:
            missing.append(t)
    return files, missing


def shorten(path: str, limit: int = 51) -> str:
    """Shorten for display without os.path.relpath.

    relpath raises ValueError when the target sits on a different drive than the
    current directory (D: vs C: here), which is the normal situation for this
    install.
    """
    p = os.path.abspath(path).replace("\\", "/")
    return p if len(p) <= limit else "..." + p[-(limit - 3):]


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect DEFORM unit system from .KEY files.")
    ap.add_argument("targets", nargs="+", help=".KEY files and/or directories")
    ap.add_argument("--json", metavar="PATH", help="also write machine-readable results")
    ap.add_argument("--quiet", action="store_true", help="summary only")
    args = ap.parse_args()

    files, missing = collect(args.targets)
    if missing:
        print("ERROR: path does not exist (check quoting and that the drive is mounted):")
        for m in missing:
            print(f"  {m}")
        print()
    if not files:
        print("No .KEY files found.")
        return 1

    results = [scan(p) for p in files]

    tally: dict[int, int] = {}
    by_unit: dict[int, list] = {}
    no_unit = 0
    for r in results:
        if r.get("unit") is None:
            no_unit += 1
        else:
            tally[r["unit"]] = tally.get(r["unit"], 0) + 1
            by_unit.setdefault(r["unit"], []).append(r["file"])

    if not args.quiet:
        print(f"{'FILE':<52} {'UNIT':>5} {'LINE':>5}  {'YOUNG':>12}  VARIANT")
        print("-" * 100)
        for r in results:
            name = shorten(r["file"])
            if r.get("unit") is None:
                print(f"{name:<52} {'-':>5} {'-':>5}  {'-':>12}  {r.get('name_variant') or ''}")
                continue
            young = f"{r['young']:.6g}" if r.get("young") is not None else "-"
            print(f"{name:<52} {r['unit']:>5} {r['unit_line']:>5}  {young:>12}  "
                  f"{r.get('name_variant') or ''}")
        print()

    print(f"Scanned {len(files)} .KEY file(s); {no_unit} contain no UNIT line.")
    if not tally:
        print("RESULT: no UNIT line found anywhere - cannot determine unit system from .KEY files.")
        print("Fall back to geometry magnitude or ask which units the CAD used.")
    else:
        total = sum(tally.values())
        for u in sorted(tally, key=lambda k: -tally[k]):
            label = UNIT_NAME.get(u, "unknown")
            print(f"  UNIT {u}: {tally[u]} file(s)  ->  {label}")

        dominant, dom_count = max(tally.items(), key=lambda kv: kv[1])
        share = dom_count / total
        if len(tally) == 1:
            print(f"RESULT: {UNIT_NAME.get(dominant, 'unknown')}")
        elif share >= 0.8:
            # Vendor example trees are not perfectly homogeneous: material files
            # travel with both unit variants, so a handful of outliers in the
            # other system is normal and not a sign of a corrupt case.
            print(f"RESULT: predominantly UNIT {dominant} "
                  f"({UNIT_NAME.get(dominant, 'unknown')}) - {share:.0%} of the "
                  f"{total} tagged file(s).")
            for u, paths in sorted(by_unit.items()):
                if u == dominant:
                    continue
                print(f"  Outliers in UNIT {u} ({len(paths)}) - inspect these, "
                      "they are often copied material files rather than the case itself:")
                for p in paths[:8]:
                    print(f"    {shorten(p, 80)}")
                if len(paths) > 8:
                    print(f"    ... and {len(paths) - 8} more")
        else:
            print(f"RESULT: MIXED unit systems ({share:.0%} majority). The tagged files do not")
            print("describe one consistent case. Separate them before trusting either reading.")

        if dominant in UNIT_NAME:
            print("Cross-check with YOUNG (~6.9e4 = MPa/SI, ~1e4 = ksi/English) "
                  "and MASDEN (~2.7e-9 = t/mm^3).")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"files": results, "tally": tally, "without_unit": no_unit},
                      fh, indent=2, ensure_ascii=False)
        print(f"\nJSON written to {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
