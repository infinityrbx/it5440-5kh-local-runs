#!/usr/bin/env python3
"""
Pilot for IT5440 topic 5-KH: SemTrace-Dep (small) + context conditions C0-C3.

Pure standard library. Talks to a local Ollama server (http://localhost:11434).

  python3 pilot.py --dry-run --n 5           # build items, check answers, show one prompt
  python3 pilot.py --model qwen2.5-coder:7b --n 20
  python3 pilot.py --model qwen2.5-coder:7b --n 20 --tokens 8000 --conds C0,C1,C2,C3

Output: results/<model>_<time>.jsonl (one line per query) and an accuracy table.

v5 (12/11/2026) fixes three problems of v3/v4 (keep pilot_v4.py to reproduce old runs):
  1. Filler confound: v4 drew NEW distractors for every position, so start/middle/end
     differed in filler as well as in position. v5 builds the filler pool and the
     insertion offsets ONCE per item (own RNG stream), reuses them at every position,
     and logs filler_hash; only the position of the needed functions changes.
  2. Name collisions: every generated name (target, helpers, distractors and the fake
     callees inside distractors) is unique within an item, so C3 cannot pick up a
     distractor by accident.
  3. Length: --tokens now means real tokens (chars / CHARS_PER_TOKEN = 2.2, measured on
     the v3 run: --tokens 2000 gave ~3,700 real tokens with len/4), and num_ctx is sized
     from it (override with --num-ctx). A warning is printed if a prompt reaches num_ctx.
     Defaults follow the draft's D2: m = 3 (k in {3,5}, depth in {1,2} via flags).

Differences from the draft's Appendix A (on purpose):
  * Each helper mixes +c, -c, *k and an if-branch, so it does NOT collapse to
    "x + constant" (the shortcut the draft itself flags).
  * Distractors come in two kinds: "similar" (same template, other constants,
    never called) and "generic" (small utility functions written here, so no
    licence question).
"""
import argparse, ast, hashlib, json, os, random, re, string, sys, time, urllib.request
from collections import defaultdict

CHARS_PER_TOKEN = 2.2  # measured: qwen2.5-coder tokenizer on this generated code

# ---------------------------------------------------------------- generator
def rand_name(rng, used=None):
    """Random fn_xxxx name; if `used` is given, never repeat a name already in it."""
    while True:
        n = "fn_" + "".join(rng.choice("0123456789abcdef") for _ in range(4))
        if used is None:
            return n
        if n not in used:
            used.add(n)
            return n

def arith_body(rng, call=None, m=2, mul=False):
    """Lines computing from x; optional call to helper `call`. Returns list of lines."""
    lines, cur = [], "x"
    if call:
        lines.append(f"    a = {call}(x {rng.choice('+-')} {rng.randint(10, 99)})")
        cur = "a"
    for i in range(m):
        v = "bcdefg"[i]
        op = rng.choice(["+", "-", "*"] if mul else ["+", "-"])
        c = rng.randint(2, 3) if op == "*" else rng.randint(100, 999)
        lines.append(f"    {v} = {cur} {op} {c}")
        cur = v
    t = rng.randint(100, 999)
    c1, c2 = rng.randint(10, 99), rng.randint(10, 99)
    lines.append(f"    if {cur} > {t}:")
    lines.append(f"        {cur} = {cur} - {c1}")
    lines.append(f"    else:")
    lines.append(f"        {cur} = {cur} + {c2}")
    lines.append(f"    return {cur}")
    return lines

def make_func(name, body):
    return f"def {name}(x):\n" + "\n".join(body) + "\n"

GENERIC = [
    "def {n}(s):\n    words = [w for w in s.split() if w]\n    return ' '.join(reversed(words))\n",
    "def {n}(xs):\n    seen = set()\n    out = []\n    for v in xs:\n        if v not in seen:\n            seen.add(v)\n            out.append(v)\n    return out\n",
    "def {n}(d, key, default=None):\n    if key in d:\n        return d[key]\n    return default\n",
    "def {n}(path):\n    parts = path.strip('/').split('/')\n    return parts[-1] if parts else ''\n",
    "def {n}(xs, k):\n    return [xs[i:i + k] for i in range(0, len(xs), k)]\n",
    "def {n}(s):\n    return sum(1 for ch in s if ch in 'aeiou')\n",
    "def {n}(a, b):\n    while b:\n        a, b = b, a % b\n    return a\n",
    "def {n}(xs):\n    if not xs:\n        return 0\n    return sum(xs) / len(xs)\n",
]

def make_item(rng, k=3, depth=2, m=3, mul=False):
    """Target f -> h1 -> h2 (chain of `depth`) plus extra direct helpers up to k."""
    assert 1 <= depth <= k, "--depth must be between 1 and --k"
    used = set()
    names = [rand_name(rng, used) for _ in range(k + 1)]
    target, helpers = names[0], names[1:]
    funcs = {}
    # chain: helpers[0] calls helpers[1] ... up to depth
    chain = helpers[:depth]
    for i in range(len(chain) - 1, -1, -1):
        callee = chain[i + 1] if i + 1 < len(chain) else None
        funcs[chain[i]] = make_func(chain[i], arith_body(rng, call=callee, m=m, mul=mul))
    extra = helpers[depth:]
    for h in extra:
        funcs[h] = make_func(h, arith_body(rng, m=m, mul=mul))
    # target: calls chain head and each extra helper, returns a list
    body = [f"    r = {chain[0]}(x + {rng.randint(10, 99)})"]
    outs = ["r"]
    for j, h in enumerate(extra):
        v = f"s{j}"
        body.append(f"    {v} = {h}(r {rng.choice('+-')} {rng.randint(10, 99)})")
        outs.append(v)
    body.append(f"    return [{', '.join(outs)}]")
    funcs[target] = make_func(target, body)
    order = list(reversed(chain)) + extra + [target]          # callee before caller
    needed = [funcs[n] for n in order]
    x = rng.randint(10, 99)
    ns = {}
    exec("\n".join(needed), ns)
    y = ns[target](x)
    # independent check: re-evaluate with a fresh namespace in reverse definition order
    ns2 = {}
    for src in reversed(needed):
        exec(src, ns2)
    assert ns2[target](x) == y, "answer cross-check failed"
    return {"target": target, "x": x, "y": y, "needed": needed, "needed_names": order,
            "used_names": used, "m": m, "mul": mul}

def distractors(rng, count, used, m=3, mul=False, frac_similar=0.5):
    """`used` = names already taken in this item; new names are added to it."""
    out = []
    for _ in range(count):
        n = rand_name(rng, used)
        if rng.random() < frac_similar:
            callee = rand_name(rng, used) if rng.random() < .5 else None  # undefined, never a real name
            out.append(make_func(n, arith_body(rng, call=callee, m=m, mul=mul)))
        else:
            out.append(rng.choice(GENERIC).format(n=n))
    return out

def approx_tokens(s):
    return int(len(s) / CHARS_PER_TOKEN)

# ---------------------------------------------------------------- contexts
def callgraph_closure(source, target):
    """C3: static call graph by name (ast), closure from target, callee first."""
    tree = ast.parse(source)
    defs = {f.name: f for f in tree.body if isinstance(f, ast.FunctionDef)}
    calls = {n: {c.func.id for c in ast.walk(f) if isinstance(c, ast.Call)
                 and isinstance(c.func, ast.Name) and c.func.id in defs}
             for n, f in defs.items()}
    seen, order = set(), []
    def visit(n):
        if n in seen:
            return
        seen.add(n)
        for m in sorted(calls[n]):
            visit(m)
        order.append(n)
    visit(target)
    return "\n".join(ast.unparse(defs[n]) + "\n" for n in order), order

def make_filler(item, frng, tokens):
    """Filler pool + scatter offsets, built ONCE per item and reused at every position."""
    pool, total = [], approx_tokens("\n".join(item["needed"]))
    while total < tokens:
        d = distractors(frng, 1, item["used_names"], item["m"], item["mul"])[0]
        pool.append(d)
        total += approx_tokens(d)
    spread = max(1, len(pool) // 10)
    offsets = [frng.randint(-spread, spread) for _ in item["needed"]]
    item["pool"], item["offsets"] = pool, offsets
    item["filler_hash"] = hashlib.md5("".join(pool).encode()).hexdigest()[:10]

def build_contexts(item, pos):
    needed, pool = item["needed"], item["pool"]
    ctx = {"C0": "\n".join(needed)}
    # C1: needed functions scattered around relative position pos (same filler, same offsets)
    c1 = list(pool)
    centre = int(pos * len(c1))
    for f, off in zip(needed, item["offsets"]):
        at = min(len(c1), max(0, centre + off))
        c1.insert(at, f)
    ctx["C1"] = "\n".join(c1)
    # C2: same content, needed block contiguous at the end (dependency order)
    ctx["C2"] = "\n".join(pool + needed)
    # C3: static closure computed from C1 (not from generator ground truth)
    ctx["C3"], c3_names = callgraph_closure(ctx["C1"], item["target"])
    item["c3_exact"] = set(c3_names) == set(item["needed_names"])
    return ctx

PROMPT = ("You are given Python source code. Read it carefully and answer the question.\n"
          "Question: What does {f}({x}) return? Answer with the Python literal only.\n"
          "<code>\n{code}\n</code>\n"
          "Question (repeated): What does {f}({x}) return? Answer with the Python literal only.\n")

PROMPT_COT = ("You are given Python source code. Read it carefully and answer the question.\n"
              "Question: What does {f}({x}) return?\n"
              "<code>\n{code}\n</code>\n"
              "Question (repeated): What does {f}({x}) return? Trace the execution step by step, "
              "then give the final answer as a Python literal on the last line.\n")

# ---------------------------------------------------------------- model
def ask_ollama(model, prompt, host, num_ctx, max_out=1024):
    body = json.dumps({"model": model, "prompt": prompt, "stream": False, "think": False,
                       "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": max_out}}).encode()
    req = urllib.request.Request(host + "/api/generate", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    return d.get("response", ""), d.get("prompt_eval_count"), d.get("eval_count")

def parse_answer(text):
    text = re.sub(r"```(?:python)?", "", text).strip()
    found = re.findall(r"\[[^\[\]]*\]", text)   # last list = final answer (works with step-by-step)
    cand = found[-1] if found else text.splitlines()[-1] if text else ""
    try:
        return ast.literal_eval(cand)
    except Exception:
        return None

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5-coder:7b")
    ap.add_argument("--n", type=int, default=20, help="items per cell")
    ap.add_argument("--tokens", type=int, default=4000, help="target context length for C1/C2 (real tokens, approx.)")
    ap.add_argument("--num-ctx", type=int, default=0, help="Ollama context window (0 = sized from --tokens)")
    ap.add_argument("--positions", default="0,0.5,1")
    ap.add_argument("--conds", default="C0,C1,C2,C3")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--m", type=int, default=3, help="arithmetic lines per helper (draft D2: 3)")
    ap.add_argument("--mul", action="store_true", help="allow *2/*3 steps (harder)")
    ap.add_argument("--cot", action="store_true", help="let the model reason step by step")
    ap.add_argument("--max-out", type=int, default=1024, help="max output tokens (num_predict)")
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rng = random.Random(a.seed)
    conds = a.conds.split(",")
    positions = [float(p) for p in a.positions.split(",")]
    num_ctx = a.num_ctx or max(8192, int(a.tokens * 1.3) + a.max_out + 512)
    os.makedirs("results", exist_ok=True)
    out = f"results/{a.model.replace(':', '_').replace('/', '_')}_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    acc = defaultdict(lambda: [0, 0])
    c3_ok = 0
    t0 = time.time()
    with open(out, "w") as fh:
        for i in range(a.n):
            item = make_item(rng, a.k, a.depth, a.m, a.mul)
            make_filler(item, random.Random(f"filler|{a.seed}|{i}"), a.tokens)
            hashes = set()
            for pos in positions:
                ctx = build_contexts(item, pos)
                hashes.add(item["filler_hash"])
                c3_ok += item["c3_exact"]
                for c in conds:
                    if c in ("C0", "C2", "C3") and pos != positions[0]:
                        continue  # position only matters for C1
                    prompt = (PROMPT_COT if a.cot else PROMPT).format(f=item["target"], x=item["x"], code=ctx[c])
                    if a.dry_run:
                        if i == 0 and c == "C0":
                            print(prompt)
                            print("expected:", item["y"])
                        continue
                    resp, pin, pout = ask_ollama(a.model, prompt, a.host, num_ctx, a.max_out)
                    if pin and pin >= num_ctx - 16:
                        print(f"WARNING item {i} {c}: prompt {pin} tokens reached num_ctx {num_ctx} "
                              f"(probably truncated) - raise --num-ctx", file=sys.stderr)
                    pred = parse_answer(resp)
                    ok = pred == item["y"]
                    key = f"{c}@p={pos}" if c == "C1" else c
                    acc[key][0] += ok
                    acc[key][1] += 1
                    fh.write(json.dumps({"i": i, "cond": c, "pos": pos, "target": item["target"],
                                         "x": item["x"], "expected": item["y"], "raw": resp,
                                         "pred": repr(pred), "correct": ok,
                                         "prompt_tokens": pin, "output_tokens": pout,
                                         "est_tokens": approx_tokens(prompt), "num_ctx": num_ctx,
                                         "filler_hash": item["filler_hash"],
                                         "c3_exact": item["c3_exact"]}) + "\n")
                    fh.flush()
            assert len(hashes) == 1, "filler differs between positions"
            print(f"item {i + 1}/{a.n} done ({time.time() - t0:.0f}s)", file=sys.stderr)
    cells = a.n * len(positions)
    print(f"\nC3 closure exact on {c3_ok}/{cells} contexts")
    if a.dry_run:
        print("dry run OK: items generated, answers cross-checked, contexts built")
        return
    print(f"\nModel {a.model}, ~{a.tokens} tokens, n={a.n}\n{'condition':<12}{'acc':>8}{'n':>6}")
    for key in sorted(acc):
        c, t = acc[key]
        print(f"{key:<12}{c / t:>8.2%}{t:>6}")
    print(f"\nlog: {out}")

if __name__ == "__main__":
    main()
