#!/usr/bin/env bash
# Rebuild REPORT.pdf from REPORT.md (needs pandoc, python3, node + playwright with Chromium).
set -e
cd "$(dirname "$0")/../.."
pandoc REPORT.md -s --metadata title="IT5440 · 5-KH · Báo cáo kết quả chạy mô hình cục bộ" \
  --css analysis/pdf/report.css --embed-resources -o /tmp/it5440_report.html
python3 - <<'PY'
import re
p = "/tmp/it5440_report.html"; s = open(p, encoding="utf-8").read()
s = re.sub(r'<header id="title-block-header">.*?</header>', "", s, flags=re.S)
for sec in ("2.", "3.", "4.", "5."):   # each of these sections starts a new page
    s = re.sub(r'<h2 id="([^"]+)">' + re.escape(sec), lambda m: f'<h2 class="brk" id="{m.group(1)}">' + sec, s, count=1)
open(p, "w", encoding="utf-8").write(s)
PY
node analysis/pdf/print.js /tmp/it5440_report.html "$PWD/REPORT.pdf"
