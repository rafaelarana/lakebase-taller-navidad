#!/usr/bin/env bash
# Builds dist/navidad-workshop.zip: ONLY what a partner needs to share and import.
#   workshop/deck/            the presentation (self-contained HTML, opens offline)
#   workshop/notebooks/       00–08 + 99 (Workspace → Import → File, keep the folder structure)
#   workshop/sql/             SQL for the Lakebase SQL editor
#   workshop/README.md        how to import and run
#   navidad-hack-infra/       scripts, SQL, app templates, road graphs (imported by the notebooks)
#   navidad-hack-build-assistant/  Genie Code skill (installed by 02_instalar_skills)
# Excluded: tests, tools, CLI installers/packagers, DAB config, dist, repo-level docs.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=dist/navidad-workshop
rm -rf "$OUT" dist/navidad-workshop.zip && mkdir -p "$OUT"
{ git ls-files; git ls-files --others --exclude-standard; } | sort -u \
  | grep -E '^(LICENSE$|NOTICE$|workshop/(deck|notebooks|sql)/|workshop/README\.md$|navidad-hack-infra/|navidad-hack-build-assistant/)' \
  | grep -v -E '/(tests|tools|__pycache__|\.pytest_cache)/' \
  | while read -r f; do [ -f "$f" ] && mkdir -p "$OUT/$(dirname "$f")" && cp "$f" "$OUT/$f"; done
(cd dist && zip -qr navidad-workshop.zip navidad-workshop -x '*.DS_Store')
echo "dist/navidad-workshop.zip ($(du -h dist/navidad-workshop.zip | cut -f1), $(find "$OUT" -type f | wc -l | tr -d ' ') files)"
