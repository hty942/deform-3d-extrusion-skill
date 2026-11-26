#!/usr/bin/env python3
"""Extract engineering metrics from a DEFORM-3D exported .KEY file.

Blocks understood (as written by DEF_PRE_64 "Keyword Values Save"):
    RZ      id x y z
    URZ     id vx vy vz
    NDTMP   id T
    ELMCON  id n1 n2 n3 n4
    STRAIN  id eff_strain
    STRESS  id sxx syy szz sxy syz szx      (may wrap over two lines)

Outputs a JSON summary (and optional CSV): global min/max/mean of temperature,
effective strain, von Mises stress; and, for a z-plane, velocity statistics,
per-quadrant means and the spread between quadrants ("hole spread").

Usage:
    python key_metrics.py out.KEY --z-exit -10 --tol 0.5 -o metrics.json
"""
import argparse
import array
import json
import math
import os
import statistics
import sys
import time

BLOCK_VALS = {"RZ": 3, "URZ": 3, "NDTMP": 1, "ELMCON": 4, "STRAIN": 1, "STRESS": 6}


class Reader:
    def __init__(self, fh):
        self.fh = fh
        self.pending = None

    def next_line(self):
        if self.pending is not None:
            line, self.pending = self.pending, None
            return line
        for line in self.fh:
            if line.strip():
                return line
        return None

    def push(self, line):
        self.pending = line

    def record(self, nvals):
        line = self.next_line()
        if line is None:
            return None
        toks = line.split()
        rid = int(float(toks[0]))
        vals = [float(x) for x in toks[1:]]
        while len(vals) < nvals:
            line = self.next_line()
            if line is None:
                break
            vals.extend(float(x) for x in line.split())
        return rid, vals[:nvals]


def stats(values):
    if not values:
        return None
    vals = sorted(values)
    n = len(vals)
    mean = sum(vals) / n
    p95 = vals[min(n - 1, int(round(0.95 * (n - 1))))]
    return {
        "count": n,
        "min": vals[0],
        "max": vals[-1],
        "mean": mean,
        "p95": p95,
        "std": statistics.pstdev(vals) if n > 1 else 0.0,
    }


def von_mises(s):
    sxx, syy, szz, sxy, syz, szx = s
    return math.sqrt(
        0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
        + 3.0 * (sxy * sxy + syz * syz + szx * szx)
    )


def parse(path, want_stress=True, progress=True):
    nodes = {}
    vel = {}
    temp = {}
    elems = array.array("i")
    eff = array.array("f")
    mises = array.array("f")
    counts = {}
    t0 = time.time()
    total = os.path.getsize(path)
    with open(path, "r", errors="ignore") as fh:
        rd = Reader(fh)
        line = rd.next_line()
        while line is not None:
            toks = line.split()
            if len(toks) >= 3 and toks[0] in BLOCK_VALS:
                name = toks[0]
                try:
                    cnt = int(toks[2])
                except ValueError:
                    line = rd.next_line()
                    continue
                counts[name] = counts.get(name, 0) + cnt
                if name == "RZ":
                    for _ in range(cnt):
                        rec = rd.record(3)
                        if rec is None:
                            break
                        nodes[rec[0]] = (rec[1][0], rec[1][1], rec[1][2])
                elif name == "URZ":
                    for _ in range(cnt):
                        rec = rd.record(3)
                        if rec is None:
                            break
                        vel[rec[0]] = (rec[1][0], rec[1][1], rec[1][2])
                elif name == "NDTMP":
                    for _ in range(cnt):
                        rec = rd.record(1)
                        if rec is None:
                            break
                        temp[rec[0]] = rec[1][0]
                elif name == "ELMCON":
                    for _ in range(cnt):
                        rec = rd.record(4)
                        if rec is None:
                            break
                        elems.extend(int(v) for v in rec[1])
                elif name == "STRAIN":
                    for _ in range(cnt):
                        rec = rd.record(1)
                        if rec is None:
                            break
                        eff.append(rec[1][0])
                elif name == "STRESS" and want_stress:
                    for _ in range(cnt):
                        rec = rd.record(6)
                        if rec is None:
                            break
                        mises.append(von_mises(rec[1]))
                line = rd.next_line()
            else:
                line = rd.next_line()
            if progress and time.time() - t0 > 30 and int(time.time() - t0) % 30 < 2:
                pass
    return {
        "nodes": nodes, "vel": vel, "temp": temp,
        "elems": elems, "eff": eff, "mises": mises, "counts": counts,
    }


def vector_stats(vecs):
    if not vecs:
        return None
    speeds = [math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) for v in vecs]
    vzs = [v[2] for v in vecs]
    out = stats(speeds)
    out["vz"] = stats(vzs)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("key", help="exported .KEY file")
    ap.add_argument("--z-exit", type=float, default=None,
                    help="z coordinate of the exit section (mm)")
    ap.add_argument("--tol", type=float, default=0.5,
                    help="half-thickness of the section band (mm)")
    ap.add_argument("--no-stress", action="store_true", help="skip STRESS block (faster)")
    ap.add_argument("--csv", default=None, help="write a flat CSV summary")
    ap.add_argument("-o", "--out", default=None, help="write JSON here (default stdout)")
    args = ap.parse_args()

    t0 = time.time()
    data = parse(args.key, want_stress=not args.no_stress)
    nodes, vel, temp = data["nodes"], data["vel"], data["temp"]
    empty_mesh = len(nodes) == 0
    if empty_mesh:
        print("WARNING: no RZ block found in %s" % args.key, file=sys.stderr)
        print("         This is usually an export of a non-existent step "
              "(DEF_PRE writes a ~2 KB skeleton KEY).", file=sys.stderr)

    result = {
        "file": os.path.abspath(args.key),
        "size_mb": round(os.path.getsize(args.key) / 1048576, 1),
        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(args.key))),
        "counts": {
            "nodes": len(nodes),
            "nodes_with_velocity": len(vel),
            "nodes_with_temperature": len(temp),
            "elements": len(data["elems"]) // 4,
        },
        "temperature": stats(list(temp.values())),
        "eff_strain": stats(list(data["eff"])),
    }
    if data["mises"]:
        result["von_mises"] = stats(list(data["mises"]))

    if args.z_exit is not None:
        band = args.z_exit - args.tol, args.z_exit + args.tol
        sel_nodes = [nid for nid, xyz in nodes.items() if band[0] <= xyz[2] <= band[1]]
        sec_vel = [vel[nid] for nid in sel_nodes if nid in vel]
        sec = {
            "z": args.z_exit,
            "tol": args.tol,
            "nodes": len(sel_nodes),
            "speed": vector_stats(sec_vel),
        }
        if sec_vel:
            quads = {"++": [], "+-": [], "-+": [], "--": []}
            for nid in sel_nodes:
                if nid not in vel:
                    continue
                x, y, _ = nodes[nid]
                key = ("+" if x >= 0 else "-") + ("+" if y >= 0 else "-")
                v = vel[nid]
                quads[key].append(math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2))
            qmeans = {k: (sum(v) / len(v) if v else None) for k, v in quads.items()}
            sec["quadrant_mean_speed"] = qmeans
            present = [m for m in qmeans.values() if m]
            if len(present) >= 2:
                mean_all = sum(present) / len(present)
                sec["hole_spread_pct"] = (max(present) - min(present)) / mean_all * 100.0
        temps = [temp[nid] for nid in sel_nodes if nid in temp]
        sec["temperature"] = stats(temps)

        # element-based values near the section (centroid inside the band)
        if nodes and len(data["elems"]) >= 4:
            band_eff = []
            band_mis = []
            ne = len(data["elems"]) // 4
            for i in range(ne):
                n1, n2, n3, n4 = data["elems"][4 * i:4 * i + 4]
                p1 = nodes.get(n1)
                if p1 is None:
                    continue
                zc = (p1[2] + nodes.get(n2, p1)[2] + nodes.get(n3, p1)[2] + nodes.get(n4, p1)[2]) / 4.0
                if band[0] <= zc <= band[1]:
                    if i < len(data["eff"]):
                        band_eff.append(data["eff"][i])
                    if i < len(data["mises"]):
                        band_mis.append(data["mises"][i])
            if band_eff:
                sec["eff_strain"] = stats(band_eff)
            if band_mis:
                sec["von_mises"] = stats(band_mis)
        result["section"] = sec

    result["elapsed_s"] = round(time.time() - t0, 1)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("written", args.out)
    else:
        print(text)

    if args.csv:
        rows = []
        for k in ("temperature", "eff_strain", "von_mises"):
            s = result.get(k)
            if s:
                rows.append([k, s["min"], s["max"], s["mean"], s.get("p95")])
        sec = result.get("section") or {}
        for k in ("speed", "temperature", "eff_strain", "von_mises"):
            s = sec.get(k)
            if s and isinstance(s, dict) and "mean" in s:
                rows.append(["section_" + k, s["min"], s["max"], s["mean"], s.get("p95")])
        if "hole_spread_pct" in sec:
            rows.append(["hole_spread_pct", "", "", sec["hole_spread_pct"], ""])
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
            f.write("metric,min,max,mean,p95\n")
            for r in rows:
                f.write(",".join(str(x) for x in r) + "\n")
        print("written", args.csv)

    return 2 if empty_mesh else 0


if __name__ == "__main__":
    sys.exit(main())
