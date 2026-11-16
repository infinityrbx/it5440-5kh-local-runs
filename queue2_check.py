"""Guard for run_queue2.sh: is a results file usable (no thinking leak, answers in the asked format)?
Exit 0 = OK, 1 = not usable. Usage: python3 queue2_check.py <results.jsonl>"""
import json
import sys

rs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
ok = [r for r in rs if "error" not in r]
sem = [r for r in ok if r.get("task") == "semantic"]
leak = sum(r.get("reasoning_chars", 0) > 0 or "<think>" in (r.get("output") or "") for r in ok)
fmt = sum("ANSWER:" in (r.get("output") or "") for r in sem)
print(f"records {len(rs)}, errors {len(rs) - len(ok)}, thinking leaked {leak}, "
      f"ANSWER: format {fmt}/{len(sem)}, correct {sum(bool(r.get('correct')) for r in sem)}/{len(sem)}")
good = rs and len(ok) >= 0.9 * len(rs) and leak == 0 and sem and fmt >= 0.8 * len(sem)
sys.exit(0 if good else 1)
