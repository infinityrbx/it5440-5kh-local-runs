#!/usr/bin/env python3
"""Draw the report figures from the raw logs (needs matplotlib).

    python3 analysis/figures.py      # writes analysis/figures/fig1_d2.png, fig2_d1.png, fig3_effect.png
"""
import json
import os
import random
from collections import defaultdict
from math import sqrt

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "analysis", "figures")
os.makedirs(OUT, exist_ok=True)

INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
C4K, C16K = "#2a78d6", "#eb6834"          # categorical slots 1 and 2 (validated pair)
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "savefig.dpi": 220, "savefig.bbox": "tight", "figure.facecolor": "white"})
POS = ["Đầu", "Giữa", "Cuối"]


def load(path):
    return [json.loads(l) for l in open(os.path.join(ROOT, path), encoding="utf-8") if l.strip()]


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def boot_ci(vals, n=10000, seed=0):
    rng = random.Random(seed)
    m = len(vals)
    bs = sorted(sum(rng.choice(vals) for _ in range(m)) / m for _ in range(n))
    return bs[int(0.025 * n)], bs[int(0.975 * n) - 1]


def mean_ci(vals, seed=0):
    return sum(vals) / len(vals), *boot_ci(vals, seed=seed)


effects = []   # (label, group, D, lo, hi)

# ---------------------------------------------------------------- Fig 1: D2 profile
D2 = {("4k", 2): "pilot/results/q35_4k_seed2_n20.jsonl", ("16k", 2): "pilot/results/q35_16k_seed2_n20.jsonl",
      ("4k", 3): "pilot/results/q35_4k_seed3_n30.jsonl", ("16k", 3): "pilot/results/q35_16k_seed3_n30.jsonl"}
d2 = {k: {(r["i"], r["cond"], r["pos"]): r for r in load(v)} for k, v in D2.items()}
fig, ax = plt.subplots(figsize=(5.6, 3.3))
for L, col, dx in (("4k", C4K, -0.06), ("16k", C16K, 0.06)):
    pool = [(s, i) for s in (2, 3) for i in sorted({k[0] for k in d2[(L, s)]})]
    ks = [sum(bool(d2[(L, s)][(i, "C1", q)]["correct"]) for s, i in pool) for q in (0.0, 0.5, 1.0)]
    n = len(pool)
    ys = [100 * k / n for k in ks]
    cis = [wilson(k, n) for k in ks]
    xs = [j + dx for j in range(3)]
    ax.errorbar(xs, ys, yerr=[[y - 100 * lo for y, (lo, hi) in zip(ys, cis)], [100 * hi - y for y, (lo, hi) in zip(ys, cis)]],
                fmt="none", ecolor=col, elinewidth=1.4, capsize=3, alpha=0.75)
    ax.plot(xs, ys, color=col, lw=2, marker="o", ms=7, mec="white", mew=1.5, zorder=3)
    ax.annotate(f"{L} ({ys[1]:.0f}% ở giữa)", (xs[1], ys[1]), xytext=(0, -18 if L == "16k" else 14),
                textcoords="offset points", ha="center", fontsize=8.5, color=INK)
    vals = [(d2[(L, s)][(i, "C1", 0.0)]["correct"] + d2[(L, s)][(i, "C1", 1.0)]["correct"]) / 2
            - d2[(L, s)][(i, "C1", 0.5)]["correct"] for s, i in pool]
    effects.append((f"D2 · qwen3.5:9b · {L}", "D2 (chính xác)", *mean_ci(vals)))
ax.set_xticks(range(3), POS)
ax.set_xlim(-0.4, 2.4)
ax.set_ylim(50, 102)
ax.set_ylabel("Độ chính xác C1 (%)")
ax.set_title("D2 SemTrace-Dep, qwen3.5:9b, n = 50: chỉ sụt ở giữa khi dài 16k", loc="left", fontsize=10, color=INK)
ax.legend(handles=[plt.Line2D([], [], color=C4K, lw=2, marker="o", label="4k token"),
                   plt.Line2D([], [], color=C16K, lw=2, marker="o", label="16k token")],
          frameon=False, loc="lower left", fontsize=8.5)
fig.savefig(os.path.join(OUT, "fig1_d2.png"))
plt.close(fig)

# ---------------------------------------------------------------- Fig 2: D1 small multiples
D1 = {"qwen2.5-coder:7b": ["d1/experiments/results/d1_q25c_0_4k.jsonl", "d1/experiments/results/d1_q25c_16k.jsonl"],
      "qwen3.5:9b": ["d1/experiments/results/d1_q35n_0.jsonl", "d1/experiments/results/d1_q35n_4k.jsonl",
                     "d1/experiments/results/d1_q35n_16k.jsonl"]}
fig, axes = plt.subplots(2, 2, figsize=(6.6, 4.6), sharex=True, sharey=True)
for r_i, (model, files) in enumerate(D1.items()):
    rs = [r for f in files for r in load(f) if r.get("task") == "semantic" and "error" not in r]
    for c_i, dg in enumerate((2, 4)):
        ax = axes[r_i][c_i]
        orc = [r.get("partial", 0) for r in rs if r["digits"] == dg and r["length"] == 0]
        ax.axhline(sum(orc) / len(orc), color=MUTED, lw=1, ls=(0, (4, 3)))
        for L, col, dx in ((4000, C4K, -0.06), (16000, C16K, 0.06)):
            by = defaultdict(dict)
            for r in rs:
                if r["digits"] == dg and r["length"] == L:
                    by[r["item"]][r["layout"]] = r.get("partial", 0)
            its = [v for v in by.values() if {"start", "middle", "end"} <= set(v)]
            stats = [mean_ci([v[l] for v in its], seed=j) for j, l in enumerate(("start", "middle", "end"))]
            xs = [j + dx for j in range(3)]
            ys = [s[0] for s in stats]
            ax.errorbar(xs, ys, yerr=[[s[0] - s[1] for s in stats], [s[2] - s[0] for s in stats]],
                        fmt="none", ecolor=col, elinewidth=1.2, capsize=2.5, alpha=0.75)
            ax.plot(xs, ys, color=col, lw=2, marker="o", ms=6, mec="white", mew=1.2, zorder=3)
            vals = [(v["start"] + v["end"]) / 2 - v["middle"] for v in its]
            effects.append((f"D1 · {model.split(':')[0]} · {dg} chữ số · {L // 1000}k", "D1 (khớp một phần)", *mean_ci(vals)))
        ax.set_title(f"{model} · {dg} chữ số", fontsize=9, color=INK, loc="left")
        ax.set_xticks(range(3), POS)
        ax.set_xlim(-0.4, 2.4)
        ax.set_ylim(0, 0.62)
for ax in axes[:, 0]:
    ax.set_ylabel("Điểm khớp một phần")
fig.legend(handles=[plt.Line2D([], [], color=C4K, lw=2, marker="o", label="4k token"),
                    plt.Line2D([], [], color=C16K, lw=2, marker="o", label="16k token"),
                    plt.Line2D([], [], color=MUTED, lw=1, ls=(0, (4, 3)), label="không filler")],
           frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.04), fontsize=8.5)
fig.suptitle("D1 SemTrace, n = 30 mỗi ô: vị trí giữa thấp nhất, rõ nhất ở qwen2.5-coder", x=0.01, ha="left",
             y=1.1, fontsize=10, color=INK)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig2_d1.png"))
plt.close(fig)

# ---------------------------------------------------------------- toolz effects
for model, f in (("qwen2.5-coder", "toolz/experiments/results/local_q25c_4k.jsonl"),
                 ("qwen3.5", "toolz/experiments/results/local_q35n_4k.jsonl")):
    by = defaultdict(dict)
    for r in load(f):
        if "error" not in r:
            by[r["item"]][r["layout"]] = bool(r["correct"])
    its = [v for v in by.values() if {"start", "middle", "end"} <= set(v)]
    vals = [(v["start"] + v["end"]) / 2 - v["middle"] for v in its]
    effects.append((f"toolz · {model} · k=1 · 4k", "toolz (chính xác)", *mean_ci(vals)))

# ---------------------------------------------------------------- Fig 3: forest plot of D
order = ["D2 (chính xác)", "D1 (khớp một phần)", "toolz (chính xác)"]
effects.sort(key=lambda e: (order.index(e[1]), e[0]))
fig, ax = plt.subplots(figsize=(6.6, 4.4))
y = 0
ticks, labels = [], []
for g in order:
    rows = [e for e in effects if e[1] == g]
    ax.text(-0.21, y - 0.15, g, fontsize=8.5, color=INK, fontweight="bold", va="bottom")
    y -= 0.8
    for lab, _, d, lo, hi in rows:
        sig = lo > 0
        col = INK if sig else MUTED
        ax.plot([lo, hi], [y, y], color=col, lw=2, solid_capstyle="round")
        ax.plot([d], [y], marker="o", ms=6.5, color=col, mec="white", mew=1.2, zorder=3)
        ax.text(1.01, y, f"{d:+.2f}  [{lo:+.2f}; {hi:+.2f}]", fontsize=7.5, color=INK2, va="center", ha="left",
                transform=ax.get_yaxis_transform())
        ticks.append(y)
        labels.append(lab.split(" · ", 1)[1])
        y -= 1
    y -= 0.3
ax.axvline(0, color=INK2, lw=1)
ax.set_yticks(ticks, labels, fontsize=7.8)
ax.set_xlim(-0.21, 0.40)
ax.set_ylim(y + 0.3, 0.4)
ax.grid(axis="y", visible=False)
ax.set_xlabel("D = (đầu + cuối)/2 − giữa   (> 0: giữa thấp hơn hai đầu)")
ax.set_title("Hiệu ứng vị trí D và khoảng tin cậy 95% (bootstrap) ở mọi lần chạy cục bộ",
             loc="left", fontsize=10, color=INK)
ax.legend(handles=[plt.Line2D([], [], color=INK, lw=2, marker="o", label="CI nằm hẳn trên 0"),
                   plt.Line2D([], [], color=MUTED, lw=2, marker="o", label="CI chứa 0")],
          frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, fontsize=8)
fig.savefig(os.path.join(OUT, "fig3_effect.png"))
plt.close(fig)
for e in effects:
    print(f"{e[0]:45s} {e[2]:+.3f} [{e[3]:+.3f}, {e[4]:+.3f}]")
