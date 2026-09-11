# One HMS v1.3.1 — Configuration-Hardened Verification Summary

- Runtime port: **8082**
- Predefined hospital role templates: **63**
- Specification/API E2E: **436/436 PASS**
- Role catalogue & authorization E2E: **190/190 PASS**
- Configuration/API E2E: **227/227 PASS**
- Real-browser functional Chromium E2E: **42/42 PASS**
- Responsive UI Chromium E2E: **22/22 PASS**
- Configuration browser E2E: **22/22 PASS**
- Distinct automated verification cases: **939 PASS, 0 FAIL**
- Original main-workflow smoke test: **PASS**
- Python compile / browser JavaScript syntax: **PASS**
- Runtime port: **8082**

## Configuration fixes in v1.3.1

- Every registry module now receives an explicit persistent hospital-state row, including upgrade scenarios.
- Enable/disable state is enforced by API authorization, reflected by `/api/me`, and refreshed by the UI on every screen transition.
- Staff with an already-open session see updated module availability without logging out and back in.
- SMALL, DISTRICT and REFERRAL presets are verified end-to-end.
- `apply_preset=true` works even when an API client does not resend `facility_type`.
- Core modules cannot be disabled.
- Optional module state is tenant-isolated between hospitals.
- Module states survive new login tokens and application restart/lifespan re-entry.
- Bed Management now has a structural dependency on Inpatient / Wards: enabling Beds enables Wards; disabling Wards disables Beds.
- Dashboard enabled-module count is calculated from the effective module registry.
- Configuration changes remain audit logged.

Detailed evidence is under `backend/tests/CONFIGURATION_E2E_TEST_REPORT.md` and `backend/tests/CONFIGURATION_BROWSER_E2E_TEST_REPORT.md`.
