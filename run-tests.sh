#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m compileall -q backend/app
if command -v node >/dev/null 2>&1; then
  node --check backend/web/app.js
  node --check backend/web/notifications.js
  node --check backend/web/patient_journey.js
  node --check backend/web/care_pathways.js
fi
PYTHONPATH=backend python backend/tests/smoke_test.py
PYTHONPATH=backend python backend/tests/database_portability_e2e.py
PYTHONPATH=backend python backend/tests/sms_gateway_client_e2e.py
PYTHONPATH=backend python backend/tests/notifications_pharmacy_bill_e2e.py
PYTHONPATH=backend python backend/tests/prescription_pharmacy_e2e.py
PYTHONPATH=backend python backend/tests/full_spec_e2e.py
PYTHONPATH=backend python backend/tests/role_catalog_e2e.py
PYTHONPATH=backend python backend/tests/configuration_e2e.py
PYTHONPATH=backend python backend/tests/patient_journey_e2e.py
PYTHONPATH=backend python backend/tests/care_pathways_e2e.py
PYTHONPATH=backend python backend/tests/care_service_matrix_e2e.py
if command -v chromium >/dev/null 2>&1 || command -v chromium-browser >/dev/null 2>&1 || command -v google-chrome >/dev/null 2>&1; then
  PYTHONPATH=backend python backend/tests/browser_e2e.py
  PYTHONPATH=backend python backend/tests/responsive_ui_e2e.py
  PYTHONPATH=backend python backend/tests/configuration_browser_e2e.py
  PYTHONPATH=backend python backend/tests/patient_journey_browser_e2e.py
  PYTHONPATH=backend python backend/tests/patient_journey_role_switch_browser_e2e.py
  PYTHONPATH=backend python backend/tests/care_pathways_browser_e2e.py
  PYTHONPATH=backend python backend/tests/prescription_pharmacy_browser_e2e.py
  PYTHONPATH=backend python backend/tests/notifications_pharmacy_browser_e2e.py
else
  echo "Browser E2E skipped: Chromium/Chrome not installed."
fi
