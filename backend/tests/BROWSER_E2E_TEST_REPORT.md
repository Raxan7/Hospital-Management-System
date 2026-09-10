# One HMS — Browser End-to-End Test Report

- Browser test cases: **42**
- Passed: **42**
- Failed: **0**

These tests use a real headless Chromium browser against a live Uvicorn server and interact with the actual HMS forms, navigation and buttons.

| Test case | Result | Detail |
|---|---|---|
| Login screen renders | PASS |  |
| Admin can log in through browser UI | PASS |  |
| Core navigation includes Reception | PASS |  |
| Core navigation includes Patients, Appointments, OPD, Lab, Pharmacy, Billing, Inventory, Users, Reports, Audit and Configuration | PASS |  |
| Patient can be registered through UI | PASS |  |
| Patient medical record/history modal opens | PASS |  |
| Inventory medicine can be created through UI | PASS |  |
| Appointment can be booked through UI | PASS |  |
| Reception queue shows booked patient | PASS |  |
| Reception can check patient in | PASS |  |
| OPD encounter can be opened through UI | PASS |  |
| Triage vital signs can be saved through UI | PASS |  |
| Lab order can be created from encounter UI | PASS |  |
| Prescription can be added from encounter UI | PASS |  |
| Consultation and diagnosis can be completed through UI | PASS |  |
| Laboratory result can be entered and verified through UI | PASS |  |
| Pharmacy can dispense prescription through UI | PASS |  |
| Dispensing visibly reduces inventory quantity | PASS |  |
| Invoice can be created through UI | PASS |  |
| Payment can be collected and invoice becomes PAID through UI | PASS |  |
| Ward can be created through UI | PASS |  |
| Patient can be admitted into an available bed through UI | PASS |  |
| Patient can be discharged and admission changes to DISCHARGED | PASS |  |
| Predefined hospital role catalogue is visible in UI | PASS |  |
| Role catalogue reports all built-in templates | PASS |  |
| Staff role selector includes grouped Surgeon template | PASS |  |
| Role can be created through UI | PASS |  |
| Staff user can be created and assigned a role through UI | PASS |  |
| Disabled Theatre is hidden from specialist operational dropdown | PASS |  |
| Facility type can be changed to REFERRAL with preset from UI | PASS |  |
| Nursing module is present in configuration UI | PASS |  |
| Theatre module is enabled by referral preset in UI | PASS |  |
| Enabled specialist module can create operational record through UI | PASS |  |
| Reports screen loads in browser | PASS |  |
| Audit screen loads in browser and shows actions | PASS |  |
| Dashboard still loads after complete workflow | PASS |  |
| No uncaught JavaScript page errors occurred | PASS |  |
| Limited staff user can log in | PASS |  |
| Limited user does not see Configuration navigation | PASS |  |
| Limited user does not see Users & Roles navigation | PASS |  |
| Limited user does not see Reception without permission | PASS |  |
| Medical record Open action is hidden without medical_records VIEW | PASS |  |