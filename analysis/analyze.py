#!/usr/bin/env python3
"""Recompute every number in REPORT.md from the raw result logs (standard library only).

    python3 analysis/analyze.py            # writes analysis/SUMMARY.md and analysis/summary.json

Conventions
  * Position effect D = (start + end)/2 - middle, per item, averaged; 95% CI by percentile
    bootstrap over items (10,000 resamples, fixed seed 0).
  * Paired test middle vs another position: exact two-sided sign test on discordant pairs
    (McNemar exact). b = right elsewhere & wrong in the middle, c = the reverse.
  * D2 (pilot/) is scored on exact answers; D1 on `partial` (share of the answer list right),
    because exact match is near zero there; toolz on exact answers.
"""
import json
import os
import random
from collections import defaultdict
from math import comb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = {}
MD = []


def p(path):
    return os.path.join(ROOT, path)


def load(path):
    return [json.loads(l) for l in open(p(path), encoding="utf-8") if l.strip()]


def sign_test(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, j) for j in range(k + 1)) / 2 ** n)


def boot_ci(vals, n=10000, seed=0):
    rng = random.Random(seed)
    m = len(vals)
    bs = sorted(sum(rng.choice(vals) for _ in range(m)) / m for _ in range(n))
    return bs[int(0.025 * n)], bs[int(0.975 * n) - 1]


def pct(x):
    return f"{100 * x:.0f}%"


# ---------------------------------------------------------------- D2: SemTrace-Dep (pilot.py v5)
D2 = {("4k", 2): "pilot/results/q35_4k_seed2_n20.jsonl", ("16k", 2): "pilot/results/q35_16k_seed2_n20.jsonl",
      ("4k", 3): "pilot/results/q35_4k_seed3_n30.jsonl", ("16k", 3): "pilot/results/q35_16k_seed3_n30.jsonl"}
d2 = {k: {(r["i"], r["cond"], r["pos"]): r for r in load(v)} for k, v in D2.items()}
MD.append("## D2 SemTrace-Dep (qwen3.5:9b, k=5, depth 2, CoT, max 2048 output tokens)\n")
MD.append("| length | seeds | n | C0 | C1 start | C1 middle | C1 end | C2 | C3 | middle vs start (b:c, p) | D [95% CI] | middle answers cut at 2048 |")
MD.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
OUT["d2"] = {}
for L in ("4k", "16k"):
    pool = [(s, i) for s in (2, 3) for i in sorted({k[0] for k in d2[(L, s)]})]
    # same filler at every position (pilot v5 guarantee) and same puzzles at 4k and 16k
    for s, i in pool:
        assert len({d2[(L, s)][(i, "C1", q)]["filler_hash"] for q in (0.0, 0.5, 1.0)}) == 1
        assert d2[("4k", s)][(i, "C0", 0.0)]["target"] == d2[("16k", s)][(i, "C0", 0.0)]["target"]
    g = lambda s, i, c, q=0.0: bool(d2[(L, s)][(i, c, q)]["correct"])
    acc = {c: sum(g(s, i, c) for s, i in pool) / len(pool) for c in ("C0", "C2", "C3")}
    pos = {q: sum(g(s, i, "C1", q) for s, i in pool) / len(pool) for q in (0.0, 0.5, 1.0)}
    b = sum(g(s, i, "C1", 0.0) and not g(s, i, "C1", 0.5) for s, i in pool)
    c = sum(g(s, i, "C1", 0.5) and not g(s, i, "C1", 0.0) for s, i in pool)
    vals = [(g(s, i, "C1", 0.0) + g(s, i, "C1", 1.0)) / 2 - g(s, i, "C1", 0.5) for s, i in pool]
    D, (lo, hi) = sum(vals) / len(vals), boot_ci(vals)
    cut = sum(d2[(L, s)][(i, "C1", 0.5)]["output_tokens"] >= 2048 for s, i in pool)
    toks = [d2[(L, s)][(i, "C1", q)]["prompt_tokens"] for s, i in pool for q in (0.0, 0.5, 1.0)]
    OUT["d2"][L] = dict(n=len(pool), acc=acc, pos=pos, b=b, c=c, p=sign_test(b, c), D=D, ci=[lo, hi],
                        middle_cut=cut, prompt_tokens=[min(toks), max(toks)])
    MD.append(f"| {L} ({min(toks)}–{max(toks)} prompt tokens) | 2+3 | {len(pool)} | {pct(acc['C0'])} | {pct(pos[0.0])} | "
              f"{pct(pos[0.5])} | {pct(pos[1.0])} | {pct(acc['C2'])} | {pct(acc['C3'])} | {b}:{c}, p={sign_test(b, c):.3f} | "
              f"{D:+.2f} [{lo:+.2f}, {hi:+.2f}] | {cut} |")
pool = [(s, i) for s in (2, 3) for i in sorted({k[0] for k in d2[("4k", s)]})]
m4 = lambda s, i: bool(d2[("4k", s)][(i, "C1", 0.5)]["correct"])
m16 = lambda s, i: bool(d2[("16k", s)][(i, "C1", 0.5)]["correct"])
b = sum(m4(s, i) and not m16(s, i) for s, i in pool)
c = sum(m16(s, i) and not m4(s, i) for s, i in pool)
OUT["d2"]["middle_4k_vs_16k"] = dict(b=b, c=c, p=sign_test(b, c))
MD.append(f"\nMiddle position, 4k vs 16k on the same {len(pool)} puzzles: {b} worse at 16k, {c} better, "
          f"p = {sign_test(b, c):.3f}.\n")
# 16k without truncated middle answers
cut_items = [(s, i) for s, i in pool if d2[("16k", s)][(i, "C1", 0.5)]["output_tokens"] >= 2048]
g16 = lambda s, i, q: bool(d2[("16k", s)][(i, "C1", q)]["correct"])
b2 = sum(g16(s, i, 0.0) and not g16(s, i, 0.5) for s, i in pool if (s, i) not in cut_items)
c2 = sum(g16(s, i, 0.5) and not g16(s, i, 0.0) for s, i in pool if (s, i) not in cut_items)
OUT["d2"]["16k_without_cut"] = dict(b=b2, c=c2, p=sign_test(b2, c2))
MD.append(f"16k, leaving out the {len(cut_items)} middle answers cut at 2048 tokens: {b2}:{c2}, p = {sign_test(b2, c2):.3f}.\n")


# ---------------------------------------------------------------- D1: SemTrace (group builder, fixed filler)
D1 = {"qwen2.5-coder:7b": ["d1/experiments/results/d1_q25c_0_4k.jsonl", "d1/experiments/results/d1_q25c_16k.jsonl"],
      "qwen3.5:9b": ["d1/experiments/results/d1_q35n_0.jsonl", "d1/experiments/results/d1_q35n_4k.jsonl",
                     "d1/experiments/results/d1_q35n_16k.jsonl"]}
MD.append("## D1 SemTrace (group builder with layout-independent filler), partial-match score\n")
MD.append("| model | digits | length | n | exact (all positions) | start | middle | end | D [95% CI] |")
MD.append("|---|---|---|---|---|---|---|---|---|")
OUT["d1"] = {}
for model, files in D1.items():
    rs = [r for f in files for r in load(f) if r.get("task") == "semantic" and "error" not in r]
    for dg in (2, 4):
        for L in (0, 4000, 16000):
            sub = [r for r in rs if r["digits"] == dg and r["length"] == L]
            if not sub:
                continue
            ex = sum(bool(r.get("correct")) for r in sub)
            if L == 0:
                part = sum(r.get("partial", 0) for r in sub) / len(sub)
                OUT["d1"][f"{model}|{dg}|oracle"] = dict(n=len(sub), exact=ex, partial=part)
                MD.append(f"| {model} | {dg} | no filler | {len(sub)} | {ex}/{len(sub)} | {part:.2f} (no position) | | | |")
                continue
            by = defaultdict(dict)
            for r in sub:
                by[r["item"]][r["layout"]] = r.get("partial", 0)
            its = [v for v in by.values() if {"start", "middle", "end"} <= set(v)]
            hashes = defaultdict(set)
            for r in sub:
                hashes[r["item"]].add(r["filler_hash"])
            assert all(len(h) == 1 for h in hashes.values()), "filler differs across positions"
            m = {lay: sum(v[lay] for v in its) / len(its) for lay in ("start", "middle", "end")}
            vals = [(v["start"] + v["end"]) / 2 - v["middle"] for v in its]
            D, (lo, hi) = sum(vals) / len(vals), boot_ci(vals)
            OUT["d1"][f"{model}|{dg}|{L}"] = dict(n=len(its), exact=ex, pos=m, D=D, ci=[lo, hi])
            MD.append(f"| {model} | {dg} | {L // 1000}k | {len(its)} | {ex}/{len(sub)} | {m['start']:.2f} | "
                      f"{m['middle']:.2f} | {m['end']:.2f} | {D:+.2f} [{lo:+.2f}, {hi:+.2f}] |")
# the discarded first attempt (thinking leaked through Ollama's /v1 endpoint)
bad = [r for r in load("d1/experiments/results/d1_q35_0.jsonl") if "error" not in r]
OUT["d1"]["discarded_q35_v1"] = dict(n=len(bad), with_thinking=sum(r.get("reasoning_chars", 0) > 0 for r in bad),
                                     empty_answers=sum(not (r.get("output") or "").strip() for r in bad))
MD.append(f"\nDiscarded run `d1_q35_0.jsonl` (qwen3.5 via /v1): {OUT['d1']['discarded_q35_v1']['with_thinking']}/{len(bad)} "
          f"rows contain thinking, {OUT['d1']['discarded_q35_v1']['empty_answers']} empty answers. Not used.\n")


# ---------------------------------------------------------------- toolz (real code, group pipeline)
TZ = {"qwen2.5-coder:7b": ["toolz/experiments/results/local_q25c_0.jsonl", "toolz/experiments/results/local_q25c_4k.jsonl"],
      "qwen3.5:9b": ["toolz/experiments/results/local_q35n_0.jsonl", "toolz/experiments/results/local_q35n_4k.jsonl"]}
MD.append("## toolz real-code benchmark (group pipeline, 40 items per k-group, filler seed 0)\n")
MD.append("| model | no filler k=1 | no filler k=3 | 4k k=1 start / middle / end | middle vs start (b:c, p) | middle vs end (b:c, p) | 4k k=3 cluster start / middle / end / spread |")
MD.append("|---|---|---|---|---|---|---|")
OUT["toolz"] = {}
for model, (f0, f4) in TZ.items():
    r0 = [r for r in load(f0) if "error" not in r]
    o = {k: [bool(r["correct"]) for r in r0 if len(r["requested"]) == k] for k in (1, 3)}
    r4 = [r for r in load(f4) if "error" not in r]
    by = defaultdict(dict)
    for r in r4:
        by[r["item"]][r["layout"]] = bool(r["correct"])
    k1 = [v for v in by.values() if "middle" in v]
    k3 = [v for v in by.values() if "spread" in v]
    a1 = {l: sum(v[l] for v in k1) / len(k1) for l in ("start", "middle", "end")}
    a3 = {l: sum(v[l] for v in k3) / len(k3) for l in ("cluster_start", "cluster_middle", "cluster_end", "spread")}
    tests = {}
    for ref in ("start", "end"):
        b = sum(v[ref] and not v["middle"] for v in k1)
        c = sum(v["middle"] and not v[ref] for v in k1)
        tests[ref] = (b, c, sign_test(b, c))
    OUT["toolz"][model] = dict(oracle={k: sum(v) / len(v) for k, v in o.items()}, k1=a1, k3=a3, tests=tests)
    MD.append(f"| {model} | {pct(sum(o[1]) / len(o[1]))} | {pct(sum(o[3]) / len(o[3]))} | "
              f"{pct(a1['start'])} / {pct(a1['middle'])} / {pct(a1['end'])} | "
              f"{tests['start'][0]}:{tests['start'][1]}, p={tests['start'][2]:.2f} | "
              f"{tests['end'][0]}:{tests['end'][1]}, p={tests['end'][2]:.2f} | "
              + " / ".join(pct(a3[l]) for l in ("cluster_start", "cluster_middle", "cluster_end", "spread")) + " |")

open(p("analysis/SUMMARY.md"), "w", encoding="utf-8").write(
    "# Summary (generated by analysis/analyze.py, do not edit by hand)\n\n" + "\n".join(MD) + "\n")
json.dump(OUT, open(p("analysis/summary.json"), "w"), indent=1, default=str)
print("\n".join(MD))
