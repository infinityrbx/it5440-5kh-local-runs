"""toolz exact score recomputed from the logged prediction.

run_eval.semantic_pred keeps everything after the last "ANSWER:" match, so an output written as
"ANSWER: ANSWER: [1, 0, 4, 3]" is logged with pred "ANSWER: [1, 0, 4, 3]" and scored wrong
(one qwen3.5 row, toolz-0536 at 4k middle). This rescoring drops repeated "ANSWER:" prefixes and
otherwise uses the group's same_value() unchanged.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "toolz", "experiments"))
from run_eval import same_value  # noqa: E402

_ITEMS = {}


def _gold(item_id):
    if not _ITEMS:
        with open(os.path.join(ROOT, "toolz/experiments/data/toolz_final_clean_items.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                it = json.loads(line)
                _ITEMS[it["id"]] = it["answer"]
    return _ITEMS[item_id]


def toolz_correct(r):
    pred = re.sub(r"^(?:ANSWER:\s*)+", "", (r.get("pred") or "").strip())
    return bool(r.get("correct")) or same_value(pred, _gold(r["item"]))
