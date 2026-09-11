# Configuration Hardening Patch — v1.3.1

This patch verifies and hardens hospital-level enable/disable configuration.

## Fixed

- Module states are persistent and explicit for every registered module, including upgraded installations.
- Every screen transition refreshes effective module configuration, so already logged-in staff receive updated availability without signing out.
- Disabled modules are removed from usable UI choices and remain blocked server-side even if a user's role still has permissions.
- Core modules remain locked ON.
- SMALL, DISTRICT and REFERRAL presets are applied consistently.
- `apply_preset=true` works independently using the hospital's currently saved facility type.
- Dashboard enabled-module totals use the effective registry state.
- Hospital configurations remain isolated between tenants.
- Bed Management depends on Inpatient / Wards: enabling Beds enables Wards; disabling Wards disables Beds.
- Missing module-state rows are installed safely on upgrade without overwriting existing hospital choices.

## Verification

- Specification/API: 436/436 PASS
- Role/authorization: 190/190 PASS
- Configuration/API: 227/227 PASS
- Functional browser: 42/42 PASS
- Responsive browser: 22/22 PASS
- Configuration browser: 22/22 PASS
- Total automated checks: 939/939 PASS
- Smoke test: PASS

See `backend/tests/CONFIGURATION_E2E_TEST_REPORT.md` and `backend/tests/CONFIGURATION_BROWSER_E2E_TEST_REPORT.md`.
