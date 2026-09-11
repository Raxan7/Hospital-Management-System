# One HMS — Configuration Browser E2E Test Report

- Checks: **22**
- Passed: **22**
- Failed: **0**

This suite uses two real Chromium sessions to verify that hospital configuration switches affect navigation and module availability for currently logged-in staff.

| Check | Result | Detail |
|---|---|---|
| Configuration page loads for administrator | PASS |  |
| Core Patient Registration switch is locked | PASS |  |
| District preset starts with Theatre disabled | PASS |  |
| Theatre can be enabled through the real UI | PASS |  |
| Surgeon sees Specialist Modules when Theatre is enabled | PASS |  |
| Admin UI immediately shows Theatre disabled | PASS |  |
| Existing Surgeon session refreshes configuration on next navigation | PASS |  |
| Disabled Theatre does not produce an error screen for current staff session | PASS |  |
| Admin can re-enable Theatre | PASS |  |
| Existing Surgeon session sees re-enabled Theatre without re-login | PASS |  |
| Wards are enabled before dependency test | PASS |  |
| Beds are enabled before dependency test | PASS |  |
| Disabling Wards switches Wards off | PASS |  |
| Disabling Wards automatically switches Beds off | PASS |  |
| Enabling Beds switches Beds on | PASS |  |
| Enabling Beds automatically switches required Wards on | PASS |  |
| SMALL preset applied through UI changes facility label | PASS |  |
| SMALL preset disables every optional switch in UI | PASS |  |
| REFERRAL preset enables every optional switch in UI | PASS |  |
| REFERRAL preset keeps every core switch enabled | PASS |  |
| Configuration survives normal screen transitions | PASS |  |
| Facility type remains REFERRAL after screen transitions | PASS |  |