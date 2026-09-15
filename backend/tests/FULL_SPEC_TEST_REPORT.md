# NEOVAM HMS — Full Specification E2E Test Report

- Total test cases: **436**
- Passed: **436**
- Failed: **0**

The suite tests the exact modular architecture plus end-to-end operational behavior, RBAC, tenant isolation, negative/error paths, and every configurable module workspace.

## Platform

| Test case | Result | Detail |
|---|---|---|
| Health endpoint | PASS |  |
| Web UI root served | PASS |  |
| Browser JavaScript asset is served | PASS |  |
| Browser stylesheet asset is served | PASS |  |

## Authentication

| Test case | Result | Detail |
|---|---|---|
| Admin login succeeds | PASS |  |
| Bad password rejected | PASS |  |
| Protected endpoint rejects missing token | PASS |  |
| Current user returns hospital, role, permissions and modules | PASS |  |

## Specification

| Test case | Result | Detail |
|---|---|---|
| All specified core modules exist | PASS |  |
| All specified optional/configurable modules exist | PASS |  |
| Permission vocabulary is exactly eight required actions | PASS |  |
| All core modules start enabled | PASS |  |
| District seed includes required district modules incl. Nursing | PASS |  |

## Facility presets

| Test case | Result | Detail |
|---|---|---|
| SMALL enables core only | PASS |  |
| Core module cannot be disabled | PASS |  |
| DISTRICT matches specified default set | PASS |  |
| REFERRAL enables every module | PASS |  |
| Invalid facility type rejected | PASS |  |

## Module configuration

| Test case | Result | Detail |
|---|---|---|
| Unknown module toggle rejected | PASS |  |
| Optional module can be disabled then enabled | PASS |  |

## Patients

| Test case | Result | Detail |
|---|---|---|
| Patient registration persists all supplied demographics | PASS |  |
| Patient numbers are unique | PASS |  |
| Search by phone/name/patient number works | PASS |  |
| Patient demographics update works | PASS |  |
| Unknown patient returns 404 | PASS |  |

## Medical records

| Test case | Result | Detail |
|---|---|---|
| Longitudinal patient detail endpoint works | PASS |  |

## Appointments

| Test case | Result | Detail |
|---|---|---|
| Appointment booking works | PASS |  |
| Appointment list includes booking | PASS |  |
| Invalid appointment status rejected | PASS |  |

## Reception

| Test case | Result | Detail |
|---|---|---|
| Reception queue includes booked patient | PASS |  |
| Reception check-in marks appointment ARRIVED | PASS |  |
| Cancelled appointment cannot be checked in | PASS |  |

## OPD

| Test case | Result | Detail |
|---|---|---|
| Encounter starts from matching appointment | PASS |  |
| Encounter automatically keeps linked appointment ARRIVED | PASS |  |
| Mismatched appointment/patient is blocked | PASS |  |

## Triage

| Test case | Result | Detail |
|---|---|---|
| Vital signs save against encounter | PASS |  |
| SpO2 validation rejects >100 | PASS |  |

## Consultation

| Test case | Result | Detail |
|---|---|---|
| Doctor clinical notes persist | PASS |  |
| Invalid encounter status rejected | PASS |  |

## Diagnosis

| Test case | Result | Detail |
|---|---|---|
| Diagnosis persists separately in encounter data | PASS |  |

## Laboratory

| Test case | Result | Detail |
|---|---|---|
| Lab order creation works | PASS |  |
| Cannot verify lab order before result | PASS |  |
| Lab result entry works | PASS |  |
| Lab verification works | PASS |  |

## Inventory

| Test case | Result | Detail |
|---|---|---|
| Inventory item creation with opening stock works | PASS |  |
| Duplicate SKU blocked in same hospital | PASS |  |
| Positive stock adjustment works | PASS |  |
| Negative stock adjustment cannot go below zero | PASS |  |

## Prescriptions

| Test case | Result | Detail |
|---|---|---|
| Prescription creation works | PASS |  |

## Pharmacy

| Test case | Result | Detail |
|---|---|---|
| Dispensing marks prescription dispensed | PASS |  |
| Dispensing deducts exact stock quantity | PASS |  |
| Dispensing creates stock movement | PASS |  |
| Double dispensing is blocked | PASS |  |
| Insufficient stock blocks dispensing | PASS |  |
| Unlinked/non-stock medicine cannot be dispensed | PASS |  |

## Billing

| Test case | Result | Detail |
|---|---|---|
| Partial payment is recorded | PASS |  |
| Invoice moves to PARTIAL after partial payment | PASS |  |
| Over-payment blocked | PASS |  |
| Invalid payment method blocked | PASS |  |
| Full cumulative payment moves invoice to PAID | PASS |  |
| Paid invoice rejects additional payment | PASS |  |
| Invoice payment history returns both payments | PASS |  |

## Wards

| Test case | Result | Detail |
|---|---|---|
| Ward creation works | PASS |  |

## Beds

| Test case | Result | Detail |
|---|---|---|
| Bed creation works | PASS |  |
| Duplicate bed code blocked | PASS |  |
| Occupied bed cannot be reused | PASS |  |
| Discharge releases bed | PASS |  |

## Inpatient

| Test case | Result | Detail |
|---|---|---|
| Patient admission works | PASS |  |
| Admission rejects encounter belonging to another patient | PASS |  |
| Discharge completes admission | PASS |  |
| Repeat discharge is blocked | PASS |  |

## Dashboard

| Test case | Result | Detail |
|---|---|---|
| Dashboard returns all required operating KPIs | PASS |  |

## Reports

| Test case | Result | Detail |
|---|---|---|
| Summary report includes billing, revenue, patients, encounters, labs, stock | PASS |  |

## Audit

| Test case | Result | Detail |
|---|---|---|
| Audit log contains clinical and administrative actions | PASS |  |
| Sensitive workflow actions are audited | PASS |  |

## RBAC

| Test case | Result | Detail |
|---|---|---|
| Unknown modules/actions are sanitized from role permissions | PASS |  |
| VIEW permission allows reading patients | PASS |  |
| Missing CREATE permission blocks patient creation | PASS |  |
| VIEW permission on enabled specialist module allows list | PASS |  |
| Missing CREATE on specialist module blocks create | PASS |  |
| Module disabled overrides user permission | PASS |  |
| Consultation EDIT cannot bypass Diagnosis EDIT permission | PASS |  |

## RBAC example

| Test case | Result | Detail |
|---|---|---|
| Lab Supervisor has VERIFY/APPROVE/PRINT and operational rights | PASS |  |
| Lab Technician cannot VERIFY | PASS |  |
| Lab Technician can PRINT | PASS |  |
| Lab Technician cannot APPROVE | PASS |  |
| Lab Supervisor can VERIFY | PASS |  |
| Lab Supervisor can APPROVE verified result | PASS |  |
| Lab Supervisor can PRINT | PASS |  |
| Lab Supervisor can EXPORT | PASS |  |

## Users

| Test case | Result | Detail |
|---|---|---|
| Admin password reset invalidates old password | PASS |  |
| Admin password reset enables new password | PASS |  |
| Deactivated account cannot use existing token | PASS |  |
| Admin cannot deactivate own account | PASS |  |

## Optional:ambulance

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:assets

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:blood_bank

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:cardiology

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:catering

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:corporate_billing

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:cssd

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:dental

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:dialysis

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:documents

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:emergency

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:ent

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:finance

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:hr

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:icu

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:insurance

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:laundry

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:maintenance

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:maternity

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:medical_equipment

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:mental_health

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:mortuary

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:nursing

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:nutrition

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:oncology

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:ophthalmology

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:payroll

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:pediatrics

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:physiotherapy

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:procurement

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:radiology

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:specialized_clinics

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional:theatre

| Test case | Result | Detail |
|---|---|---|
| Create operational record | PASS |  |
| Read/list operational record | PASS |  |
| Update operational record | PASS |  |
| VERIFY permission/action works | PASS |  |
| APPROVE permission/action works | PASS |  |
| PRINT permission/action works | PASS |  |
| EXPORT permission/action works | PASS |  |
| DELETE permission/action works | PASS |  |
| Deleted record disappears from list | PASS |  |

## Optional modules

| Test case | Result | Detail |
|---|---|---|
| Generic operations reject core modules | PASS |  |
| Wards use dedicated workflow instead of generic records | PASS |  |
| Beds use dedicated workflow instead of generic records | PASS |  |

## Disabled:ambulance

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:assets

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:blood_bank

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:cardiology

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:catering

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:corporate_billing

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:cssd

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:dental

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:dialysis

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:documents

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:emergency

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:ent

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:finance

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:hr

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:icu

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:insurance

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:laundry

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:maintenance

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:maternity

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:medical_equipment

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:mental_health

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:mortuary

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:nursing

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:nutrition

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:oncology

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:ophthalmology

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:payroll

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:pediatrics

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:physiotherapy

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:procurement

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:radiology

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:specialized_clinics

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:theatre

| Test case | Result | Detail |
|---|---|---|
| Disabled module is blocked at API | PASS |  |

## Disabled:wards

| Test case | Result | Detail |
|---|---|---|
| Disabled wards endpoint blocked | PASS |  |

## Disabled:beds

| Test case | Result | Detail |
|---|---|---|
| Disabled beds endpoint blocked | PASS |  |

## Multi-hospital

| Test case | Result | Detail |
|---|---|---|
| Second hospital user can operate same platform independently | PASS |  |
| Hospital A cannot read Hospital B patient | PASS |  |
| Hospital B cannot read Hospital A patient | PASS |  |
| Patient lists are tenant-isolated | PASS |  |
| Module configuration is independent per hospital | PASS |  |

## Roles

| Test case | Result | Detail |
|---|---|---|
| Duplicate role rename returns conflict instead of server error | PASS |  |
| Role permission edits persist | PASS |  |
