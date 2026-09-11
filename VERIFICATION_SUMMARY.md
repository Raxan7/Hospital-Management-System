# One HMS v1.3.0 — Enterprise UI Verification Summary

- Runtime port: **8082**
- Predefined hospital role templates: **63**
- Specification/API E2E: **436/436 PASS**
- Role catalogue & authorization E2E: **190/190 PASS**
- Real-browser functional Chromium E2E: **42/42 PASS**
- Responsive UI Chromium E2E: **22/22 PASS**
- Distinct automated verification cases: **690 PASS, 0 FAIL**
- Original main-workflow smoke test: **PASS**
- Python compile / browser JavaScript syntax: **PASS**
- PostgreSQL DDL compilation: **19/19 tables PASS**
- API route inventory: **65**
- Docker Compose: **PASS** (`8082:8082`, PostgreSQL 16, DB health dependency)
- Live Uvicorn health/UI check on port 8082: **PASS**

Detailed evidence is under `backend/tests/`, `docs/TESTING_AND_COVERAGE.md`, and `docs/UI_REDESIGN.md`.
