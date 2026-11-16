"""D1 partial-match score recomputed from the logged prediction.

The `partial` field written by older versions of d1/experiments/compare_pilot.py did not strip
Markdown backticks, so an answer such as `[57, 136, -10]` (in backticks) scored 0 although
`correct` (run_eval.same_value) strips them. 26 of qwen2.5-coder's 60 no-filler answers were
affected. The analysis therefore rescores every D1 row from `pred` with the fixed partial(),
against the gold answer rebuilt from the same deterministic generator (seed 11).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "d1", "experiments"))
from compare_pilot import partial, semtrace_item  # noqa: E402  (partial() fixed: strips backticks)

_GOLD = {}


def gold(item_id, digits, seed=11):
    key = (item_id, digits)
    if key not in _GOLD:
        i = int(re.search(r"-(\d+)$", item_id).group(1))
        it, unit = semtrace_item(i, digits, seed)
        _GOLD[key] = (it["answer"], unit["name"])
    return _GOLD[key]


def d1_partial(r):
    answer, name = gold(r["item"], r["digits"])
    assert name in r["requested"][0], f"gold mismatch for {r['item']}"
    return partial(r.get("pred", ""), answer)
