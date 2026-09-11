#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m compileall -q backend/app
if command -v node >/dev/null 2>&1; then node --check backend/web/app.js; fi
PYTHONPATH=backend python backend/tests/smoke_test.py
PYTHONPATH=backend python backend/tests/full_spec_e2e.py
PYTHONPATH=backend python backend/tests/role_catalog_e2e.py
if command -v chromium >/dev/null 2>&1 || command -v chromium-browser >/dev/null 2>&1 || command -v google-chrome >/dev/null 2>&1; then
  PYTHONPATH=backend python backend/tests/browser_e2e.py
  PYTHONPATH=backend python backend/tests/responsive_ui_e2e.py
else
  echo "Browser E2E skipped: Chromium/Chrome not installed."
fi
