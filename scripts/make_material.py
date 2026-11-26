#!/usr/bin/env python3
"""Build a DEFORM-3D material keyfile from published flow-stress data.

DEFORM needs the flow stress as a three-dimensional table: sigma( strain,
strain rate, temperature ). Papers almost never publish it in that form --
they give constitutive equation parameters or plotted curves. This script is
the bridge: give it parameters (or an explicit table) plus the grid you want,
and it writes a material .KEY file DEFORM can load.

Supported model forms:

  hensel_spittel   sigma = A * exp(m1*T) * T^m9 * eps^m2 * exp(m4/eps)
                         * (1+eps)^(m5*T) * exp(m7*eps)
                         * edot^m3 * edot^(m8*T)
                   This is the form used by extrusion codes (QForm, Simufact).
                   Many variants exist -- CHECK the paper's own formula and
                   parameter count before trusting the numbers.

  arrhenius        Z = edot * exp( Q / (R*T_K) )        (Zener-Hollomon)
                   sigma = (1/alpha) * asinh( (Z/A)^(1/n) )
                   Optionally strain-compensated: alpha, n, Q, ln(A) given as
                   polynomials in strain (coefficients highest power first).

  johnson_cook     sigma = (A + B*eps^n) * (1 + C*ln(edot/edot_ref))
                           * (1 - Tstar^m)
                   Tstar = (T - T_room)/(T_melt - T_room).  Usually poor above
                   ~0.5 Tm for aluminium -- use with care for hot extrusion.

  table            explicit sigma values, layout = temperature-major then
                   strain rate then strain (the order DEFORM itself uses).

Usage:
    python make_material.py --config 6060.json --out 6060_s000001.KEY
    python make_material.py --from-key <existing.KEY> --out copy_s000001.KEY

Console output is ASCII-only (Windows console here is cp936).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

R_GAS = 8.314462618  # J/(mol*K)


# --------------------------------------------------------------------------
# constitutive models
# --------------------------------------------------------------------------

def hensel_spittel(eps, edot, T, p, temp_unit="C"):
    """Hensel-Spittel 9-parameter form (see module docstring)."""
    T = T + 273.15 if temp_unit == "C" else T
    # exp(m1*T) wants the temperature in the unit the parameters were fitted
    # in; most published sets use degrees Celsius, so keep that convention.
    Tfit = T - 273.15 if temp_unit == "C" else T
    eps_s = max(eps, 1e-6)
    edot_s = max(edot, 1e-9)
    s = (p["A"]
         * math.exp(p["m1"] * Tfit)
         * (Tfit ** p.get("m9", 0.0))
         * (eps_s ** p["m2"])
         * math.exp(p.get("m4", 0.0) / eps_s)
         * ((1.0 + eps_s) ** (p.get("m5", 0.0) * Tfit))
         * math.exp(p.get("m7", 0.0) * eps_s)
         * (edot_s ** p["m3"])
         * (edot_s ** (p.get("m8", 0.0) * Tfit)))
    return s


def arrhenius(eps, edot, T, p, temp_unit="C"):
    """Sellars-McTegart / Garofalo hyperbolic-sine, optional strain compensation."""
    TK = T + 273.15 if temp_unit == "C" else T
    eps_s = max(eps, 1e-6)
    edot_s = max(edot, 1e-9)

    def poly(coeffs, x):
        # highest power first, e.g. [a4, a3, a2, a1, a0]
        v = 0.0
        for c in coeffs:
            v = v * x + c
        return v

    alpha = poly(p["alpha"], eps_s) if isinstance(p["alpha"], list) else p["alpha"]
    n = poly(p["n"], eps_s) if isinstance(p["n"], list) else p["n"]
    Q = poly(p["Q"], eps_s) if isinstance(p["Q"], list) else p["Q"]
    A = p["A"]
    if isinstance(A, list):
        A = math.exp(poly(A, eps_s))       # published as ln A polynomials
    elif p.get("A_is_ln"):
        A = math.exp(A)

    Z = edot_s * math.exp(Q / (R_GAS * TK))
    return math.asinh((Z / A) ** (1.0 / n)) / alpha


def johnson_cook(eps, edot, T, p, temp_unit="C"):
    Tc = T if temp_unit == "C" else T - 273.15
    Tr = p.get("T_room", 20.0)
    Tm = p["T_melt"]
    edot_ref = p.get("edot_ref", 1.0)
    tstar = (Tc - Tr) / (Tm - Tr)
    tstar = min(max(tstar, 0.0), 1.0)
    edot_s = max(edot, 1e-9)
    return ((p["A"] + p["B"] * max(eps, 0.0) ** p["n"])
            * (1.0 + p["C"] * math.log(edot_s / edot_ref))
            * (1.0 - tstar ** p["m"]))


MODELS = {
    "hensel_spittel": hensel_spittel,
    "arrhenius": arrhenius,
    "johnson_cook": johnson_cook,
}


# --------------------------------------------------------------------------
# keyfile writer
# --------------------------------------------------------------------------

DEFAULT_PROPS = {
    # SI: MPa, degC, W/(m*K), N/(mm^2*degC) for heat capacity, t/mm^3 density
    "young": 69000.0,
    "poisson": 0.30,
    "expand": 2.2e-5,
    "expand_ref_temp": 20.0,
    "thrcnd": 180.0,
    "heatcp": 2.43,
    "masden": 2.7e-9,
}

STRAIN_WIDTH = 9      # values per physical line in the strain/rate/temp rows
STRESS_WIDTH = 7      # values per physical line in the stress rows


def wrap(values, per_line):
    """Wrap numbers across lines the way DEFORM's own files do.

    DEFORM writes 7 digits after the point (e.g. 3.7111111E+002); using fewer
    loses precision on grid coordinates that came from an F-to-C conversion.
    """
    rows, cur = [], []
    for v in values:
        cur.append("%.7E" % v)
        if len(cur) == per_line:
            rows.append(cur)
            cur = []
    if cur:
        rows.append(cur)
    return ["  ".join(r) for r in rows]


def write_key(path, name, props, grid, table):
    """table[iT][iRate] -> list of stress values (one per strain)."""
    ns = len(grid["strains"])
    nr = len(grid["rates"])
    nt = len(grid["temps"])

    L = []
    L.append("*")
    L.append("")
    L.append("UNIT         1")
    L.append("*")
    L.append("*  Property Data of Material     1")
    L.append("*")
    L.append("MTNAME       1")
    L.append(name)
    L.append("FRAE2H       1  9.0000000E-001")
    L.append("FPERV        1  0.0000000E+000       0  0.0000000E+000       0")
    L.append("FRCMOD       1       0  0.0000000E+000  0.0000000E+000 "
             "0.0000000E+000  0.0000000E+000  0.0000000E+000")
    L.append("FSTRES       1       2")
    L.append("   %7d %7d %7d" % (ns, nr, nt))
    L.extend(wrap(grid["strains"], STRAIN_WIDTH))
    L.extend(wrap(grid["rates"], STRAIN_WIDTH))
    L.extend(wrap(grid["temps"], STRAIN_WIDTH))
    for iT in range(nt):
        for iR in range(nr):
            L.extend(wrap(table[iT][iR], STRESS_WIDTH))
    L.append("YOUNG        1       0  %.7E" % props["young"])
    L.append("POISON       1       0  %.7E" % props["poisson"])
    L.append("EXPAND       1       0  %.7E  %.7E" % (props["expand"], props["expand_ref_temp"]))
    L.append("THRCND       1       0  %.7E" % props["thrcnd"])
    L.append("HEATCP       1       0  %.7E" % props["heatcp"])
    L.append("EMSVTY       1       0  7.0000000E-001")
    L.append("MASDEN       1       0  %.7E" % props["masden"])
    for kw in ("HDNPHA", "MSTMTR", "CREEP", "DIFCOE", "ELRST", "UTSDAT", "HDNRUL",
               "PMEAB", "PMITT", "BURGRS", "ALPHA", "NDISFM", "RECVRY"):
        L.append("%-12s 1       0  0.0000000E+000" % kw)
    L.append("MATDEN       1  0.0000000E+000")
    L.append("")
    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("\n".join(L))


def write_std(path, name, equivalents):
    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(name + "\n")
        for e in equivalents:
            fh.write(e + "\n")


# --------------------------------------------------------------------------
# reading an existing keyfile (for --from-key)
# --------------------------------------------------------------------------

NUM = re.compile(r"[-+]?\d+\.?\d*(?:[Ee][-+]?\d+)?")


def read_text(p):
    raw = open(p, "rb").read()
    for enc in ("utf-8", "cp936", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def parse_key(path):
    lines = read_text(path).splitlines()
    d = {"props": dict(DEFAULT_PROPS)}
    for i, l in enumerate(lines):
        s = l.strip()
        for kw, key in (("YOUNG", "young"), ("POISON", "poisson"), ("THRCND", "thrcnd"),
                        ("HEATCP", "heatcp"), ("MASDEN", "masden")):
            m = re.match(r"^%s\s+\d+\s+\d+\s+([-+0-9.Ee]+)" % kw, s)
            if m:
                d["props"][key] = float(m.group(1))
        m = re.match(r"^EXPAND\s+\d+\s+\d+\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)", s)
        if m:
            d["props"]["expand"] = float(m.group(1))
            d["props"]["expand_ref_temp"] = float(m.group(2))
        if s.startswith("MTNAME"):
            d["name"] = lines[i + 1].strip()
        if s.startswith("FSTRES"):
            # The block is: 3 header numbers, then nstrain strains, nrates rates,
            # ntemps temperatures, then nstrain*nrates*ntemps stresses. Count them
            # all -- an off-by-N here silently truncates the last stress block.
            nums = []
            for l2 in lines[i + 1:]:
                nums.extend(float(x) for x in NUM.findall(l2))
                ns, nr, nt = int(nums[0]), int(nums[1]), int(nums[2])
                if len(nums) >= 3 + ns + nr + nt + ns * nr * nt:
                    break
            ns, nr, nt = int(nums[0]), int(nums[1]), int(nums[2])
            p = 3
            strains = nums[p:p + ns]; p += ns
            rates = nums[p:p + nr]; p += nr
            temps = nums[p:p + nt]; p += nt
            blocks = nums[p:p + ns * nr * nt]
            table = []
            for iT in range(nt):
                row = []
                for iR in range(nr):
                    k = (iT * nr + iR) * ns
                    row.append(blocks[k:k + ns])
                table.append(row)
            d["grid"] = {"strains": strains, "rates": rates, "temps": temps}
            d["table"] = table
            break
    return d


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def build_table(model, params, grid, temp_unit):
    fn = MODELS[model]
    table = []
    for T in grid["temps"]:
        row = []
        for edot in grid["rates"]:
            row.append([fn(e, edot, T, params, temp_unit) for e in grid["strains"]])
        table.append(row)
    return table


def sanity_check(grid, table):
    warns = []
    for iT in range(len(grid["temps"])):
        vals = [v for r in table[iT] for v in r]
        if any((not math.isfinite(v)) or v <= 0 for v in vals):
            warns.append("temperature %.1f: non-positive or non-finite stress"
                         % grid["temps"][iT])
    # stress should fall as temperature rises (compare lowest rate, mid strain)
    m = len(grid["strains"]) // 2
    trend = [table[iT][0][m] for iT in range(len(grid["temps"]))]
    if len(trend) > 1 and trend[-1] >= trend[0]:
        warns.append("stress does NOT decrease with temperature (%s) - check the model "
                     "or the temperature unit" % ", ".join("%.1f" % t for t in trend))
    # stress should rise with strain rate
    for iT in range(len(grid["temps"])):
        col = [table[iT][iR][m] for iR in range(len(grid["rates"]))]
        if len(col) > 1 and col[-1] <= col[0]:
            warns.append("temperature %.1f: stress does NOT increase with strain rate (%s)"
                         % (grid["temps"][iT], ", ".join("%.1f" % c for c in col)))
    return warns


def main():
    ap = argparse.ArgumentParser(description="Build a DEFORM material keyfile.")
    ap.add_argument("--config", help="JSON config (see docstring)")
    ap.add_argument("--from-key", help="copy an existing DEFORM material keyfile")
    ap.add_argument("--out", required=True, help="output .KEY path")
    ap.add_argument("--name", help="override the material name (MTNAME)")
    ap.add_argument("--props", help="JSON file with property overrides")
    ap.add_argument("--std", action="store_true",
                    help="also write the companion .std index file")
    ap.add_argument("--alias", action="append",
                    help="extra library-search alias for the .std file (repeatable)")
    args = ap.parse_args()

    aliases_extra = args.alias or []

    if not args.config and not args.from_key:
        ap.error("give either --config or --from-key")

    if args.from_key:
        d = parse_key(args.from_key)
        if "table" not in d:
            print("ERROR: could not parse FSTRES from %s" % args.from_key)
            return 1
        name, props, grid, table = d["name"], d["props"], d["grid"], d["table"]
        print("read %s: %d strains x %d rates x %d temps"
              % (os.path.basename(args.from_key), len(grid["strains"]),
                 len(grid["rates"]), len(grid["temps"])))
    else:
        cfg = json.load(open(args.config, encoding="utf-8"))
        name = cfg["name"]
        model = cfg["model"]
        if model not in MODELS:
            print("ERROR: unknown model %r; choose from %s" % (model, list(MODELS)))
            return 1
        grid = cfg["grid"]
        props = dict(DEFAULT_PROPS)
        props.update(cfg.get("props", {}))
        temp_unit = cfg.get("temperature_unit", "C")
        table = build_table(model, cfg["params"], grid, temp_unit)
        print("model: %s (temperature in deg%s)" % (model, temp_unit))

    if args.name:
        print("material name: %s -> %s" % (name, args.name))
        name = args.name
    if args.props:
        ov = json.load(open(args.props, encoding="utf-8"))
        applied = {k: v for k, v in ov.items()
                   if k in props and not k.startswith("_")}
        props.update(applied)
        print("properties overridden: %s" % ", ".join("%s=%g" % (k, v)
                                                      for k, v in applied.items()))

    warns = sanity_check(grid, table)
    print("\nflow stress grid (MPa):")
    print("  T(degC) " + "".join("%10s" % ("edot=%g" % r) for r in grid["rates"]))
    m = len(grid["strains"]) // 2
    for iT, T in enumerate(grid["temps"]):
        print("  %7.1f " % T + "".join("%10.1f" % table[iT][iR][m]
                                       for iR in range(len(grid["rates"]))))

    write_key(args.out, name, props, grid, table)
    print("\nwrote %s" % args.out)
    if args.std:
        # The library pairs <name>.std with <name>_s00000N.KEY, i.e. the .std
        # carries the bare name and the keyfile carries the unit suffix. Naming
        # the .std after the full keyfile makes the material invisible to the
        # library browser.
        base = re.sub(r"_[se]\d{6}$", "", os.path.splitext(args.out)[0])
        stdp = base + ".std"
        # write_std already emits the material name as the first line; only the
        # extra search aliases need passing.
        write_std(stdp, name, [a.strip() for a in aliases_extra if a.strip()])
        print("wrote %s" % stdp)

    if warns:
        print("\nWARNINGS")
        for w in warns:
            print("  - " + w)
        return 2
    print("\nSanity checks passed (stress falls with T, rises with strain rate).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
