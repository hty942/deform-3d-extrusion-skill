#!/usr/bin/env python3
"""Build a self-contained HTML report from key_metrics.py JSON outputs.

    python make_report.py -i baseline.json opt1.json opt2.json -o report.html
    python make_report.py -i m.json -o report.html --images figs --title "423002 优化对比"

The first input is treated as the baseline; every other case is compared to it.
Images in --images (png/jpg) are embedded as base64, sorted by filename.
"""
import argparse
import base64
import datetime
import json
import os
import pathlib
import sys

ROW_SPEC = [
    ("temperature", "温度 T (°C)"),
    ("eff_strain", "等效应变 ε"),
    ("von_mises", "等效应力 σ (MPa)"),
    ("section.speed", "出口截面速度 (mm/s)"),
    ("section.temperature", "出口截面温度 (°C)"),
    ("section.eff_strain", "出口截面应变"),
    ("section.von_mises", "出口截面应力 (MPa)"),
]

EXTRA_ROWS = [("section.hole_spread_pct", "孔间差 (%)")]


def dig(obj, path):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        if abs(v) >= 1000:
            return f"{v:,.1f}"
        if abs(v) >= 1:
            return f"{v:.3f}"
        return f"{v:.4g}"
    return str(v)


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    data["_name"] = os.path.splitext(os.path.basename(path))[0]
    return data


def case_value(data, key):
    if key == "section.hole_spread_pct":
        return dig(data, key)
    s = dig(data, key)
    if isinstance(s, dict):
        return s.get("mean")
    return None


def build(cases, images, title, notes):
    base = cases[0]
    parts = []
    parts.append(f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<title>{title}</title><style>
body{{margin:0;padding:30px 36px;background:#f3f6fa;color:#1d2733;font-family:"Microsoft YaHei","PingFang SC",sans-serif;line-height:1.75;font-size:14px}}
.wrap{{max-width:1100px;margin:0 auto;background:#fff;padding:34px 40px 44px;border-radius:10px;box-shadow:0 2px 14px rgba(0,0,0,.08)}}
h1{{font-size:23px;color:#12365e;margin:0 0 4px}}
.sub{{color:#6b7a8c;font-size:12.5px;margin-bottom:22px}}
h2{{font-size:17px;color:#12365e;margin:28px 0 8px;padding-left:9px;border-left:4px solid #2a6dbb}}
table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}}
th,td{{border:1px solid #d8e0e9;padding:6px 9px;text-align:right}}
th:first-child,td:first-child{{text-align:left}}
th{{background:#eef3f9;color:#12365e}}
tr.base td{{background:#f6fbff}}
.good{{color:#1c7c3c;font-weight:600}}
.bad{{color:#b0322a;font-weight:600}}
.flat{{color:#8a97a6}}
.fig{{margin:16px 0;text-align:center}}
.fig img{{max-width:100%;border:1px solid #ccd6e0;border-radius:6px}}
.cap{{color:#6b7a8c;font-size:12px;margin-top:4px}}
.note{{background:#fff7e8;border:1px solid #f0d8ae;border-radius:8px;padding:12px 16px;margin:14px 0;font-size:13px}}
.foot{{color:#8a97a6;font-size:12px;margin-top:26px}}
</style></head><body><div class="wrap">
<h1>{title}</h1>
<div class="sub">生成时间 {datetime.datetime.now():%Y-%m-%d %H:%M}　│　基线：{base['_name']}　│　算例数 {len(cases)}</div>""")

    parts.append("<h2>一、算例指标总表</h2><table><tr><th>指标</th>")
    for c in cases:
        parts.append(f"<th>{c['_name']}</th>")
    parts.append("</tr>")
    for key, label in ROW_SPEC + EXTRA_ROWS:
        parts.append(f"<tr><td>{label}</td>")
        for c in cases:
            v = case_value(c, key)
            parts.append(f"<td>{fmt(v)}</td>")
        parts.append("</tr>")
    parts.append("</table>")
    parts.append("<div class='cap'>表格取各指标的均值（应力/应变/温度取全域或截面均值，孔间差为百分比）。完整 min/max/p95 见 JSON。</div>")

    if len(cases) > 1:
        parts.append("<h2>二、相对基线的变化</h2><table><tr><th>指标</th>")
        for c in cases[1:]:
            parts.append(f"<th>{c['_name']}</th>")
        parts.append("</tr>")
        for key, label in ROW_SPEC + EXTRA_ROWS:
            b = case_value(base, key)
            if b in (None, 0):
                continue
            parts.append(f"<tr><td>{label}</td>")
            for c in cases[1:]:
                v = case_value(c, key)
                if v is None:
                    parts.append("<td>—</td>")
                    continue
                d = (v - b) / b * 100.0
                # Only metrics with an unambiguous better direction get red/green.
                # (Lower force/temperature is not automatically "good".)
                if key in ("section.hole_spread_pct",) and abs(d) >= 0.005:
                    cls = "good" if d < 0 else "bad"
                else:
                    cls = "flat"
                parts.append(f"<td class='{cls}'>{d:+.2f}%</td>")
            parts.append("</tr>")
        parts.append("</table>")
        parts.append("<div class='cap'>只有孔间差按“越低越好”着色（绿＝改善，红＝变差）；其余指标只给变化百分比——温度、力、速度的升降是否有利要结合工艺判断。</div>")

    if images:
        parts.append("<h2>三、结果图</h2>")
        for img in images:
            b64 = base64.b64encode(pathlib.Path(img).read_bytes()).decode("ascii")
            ext = "jpeg" if img.lower().endswith((".jpg", ".jpeg")) else "png"
            parts.append(f"<div class='fig'><img src='data:image/{ext};base64,{b64}'>"
                         f"<div class='cap'>{pathlib.Path(img).stem}</div></div>")

    if notes:
        parts.append("<h2>四、说明</h2><div class='note'>" + notes.replace("\n", "<br>") + "</div>")

    parts.append("<h2>五、数据来源</h2><table><tr><th>算例</th><th>KEY 文件</th><th>大小 (MB)</th><th>修改时间</th></tr>")
    for c in cases:
        parts.append(f"<tr><td>{c['_name']}</td><td>{c.get('file','—')}</td>"
                     f"<td>{fmt(c.get('size_mb'))}</td><td>{c.get('modified','—')}</td></tr>")
    parts.append("</table>")
    parts.append("<div class='foot'>由 deform-3d-extrusion-workflow / make_report.py 生成。结论段需人工撰写。</div>")
    parts.append("</div></body></html>")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-i", "--inputs", nargs="+", required=True, help="metrics JSON files; first = baseline")
    ap.add_argument("-o", "--out", default="report.html")
    ap.add_argument("--images", default=None, help="folder with png/jpg to embed")
    ap.add_argument("--title", default="DEFORM 挤压仿真结果报告")
    ap.add_argument("--notes", default="", help="free text shown in section 4")
    args = ap.parse_args()

    cases = [load(p) for p in args.inputs]
    images = []
    if args.images and os.path.isdir(args.images):
        for name in sorted(os.listdir(args.images)):
            if name.lower().endswith((".png", ".jpg", ".jpeg")):
                images.append(os.path.join(args.images, name))
    html = build(cases, images, args.title, args.notes)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("written", args.out, len(html), "chars")


if __name__ == "__main__":
    sys.exit(main())
