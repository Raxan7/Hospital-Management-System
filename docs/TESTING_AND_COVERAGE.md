# One HMS — Requirements Traceability and Test Coverage

## Verification result

The current build has been verified against the HMS specification supplied for this project.

- Specification/API E2E cases: **436 / 436 passed**
- Role-catalogue & authorization E2E cases: **190 / 190 passed**
- Real-browser UI E2E cases: **42 / 42 passed**
- Total distinct automated verification cases: **668 passed, 0 failed**
- Original smoke workflow: **PASS**
- Python backend compile check: **PASS**
- Browser JavaScript syntax check: **PASS**
- PostgreSQL DDL compilation: **PASS for all 19 tables**
- API route inventory: **65 application API routes**
- Docker Compose structural validation: **PASS**

A live Docker/PostgreSQL container could not be started in the verification sandbox because the Docker runtime is not installed there. Runtime E2E tests therefore use the project's supported SQLite mode. The SQLAlchemy schema has separately been compiled against the PostgreSQL dialect and the Compose PostgreSQL configuration has been validated.


## Predefined hospital user/role coverage

The build now ships with **63 predefined hospital role templates**. These are installed for fresh hospitals and missing templates are also added to existing hospitals without overwriting any role that the hospital has customized. Administrators can edit permissions, create custom roles, reinstall missing defaults and deliberately reset a built-in role to its recommended permission map.

The catalogue covers: system/hospital administrators and medical leadership; reception, registration, appointments and medical records; doctors, medical/clinical officers and specialist doctors; general, triage, ward, ICU and maternity nursing; surgeons, anaesthesia and theatre staff; laboratory; pharmacy; radiology; cashier/billing/insurance/accounting/finance; stores/procurement/inventory; HR/payroll/audit/documents/assets/maintenance; blood bank, mortuary, nutrition, physiotherapy, ambulance/EMS, biomedical equipment, CSSD, catering and laundry; and named specialty clinicians for Dental, Ophthalmology, ENT, Pediatrics, Mental Health, Dialysis, Oncology and Cardiology.

The role suite explicitly proves the originally discussed **Doctor, Nurse, Receptionist, Lab Technician, Lab Supervisor, Surgeon and Theatre Staff** behaviors, including the rule that a disabled Theatre module blocks a Surgeon even when the role contains Theatre permissions.

## Requirement traceability

| Specification requirement | Implementation | Verification |
|---|---|---|
| One HMS platform for Small, District and Referral facilities | Single application and data model with hospital `facility_type` | PASS |
| Hospital setup and facility selection | Hospital configuration API + UI | PASS |
| Core modules remain enabled | Core flag + disable guard | PASS |
| Optional modules can be enabled/disabled | HospitalModule configuration | PASS |
| Disabled module is hidden and blocked | UI filtering + API `MODULE_DISABLED` enforcement | PASS |
| Module status is separate from user permission | `ensure_access()` checks module state before RBAC | PASS |
| VIEW | Role matrix + enforced endpoints/actions | PASS |
| CREATE | Role matrix + enforced endpoints/actions | PASS |
| EDIT | Role matrix + enforced endpoints/actions | PASS |
| DELETE | Role matrix + specialist record delete action | PASS |
| APPROVE | Role matrix + lab/specialist approval actions | PASS |
| VERIFY | Role matrix + lab/specialist verification actions | PASS |
| PRINT | Role matrix + lab/specialist printable output | PASS |
| EXPORT | Role matrix + lab/specialist CSV export | PASS |
| Patient Registration | Dedicated core module + create/search/update UI/API | PASS |
| Patient Management / Medical Records | Dedicated core permission + longitudinal record view | PASS |
| Reception | Dedicated queue and patient check-in workflow | PASS |
| Appointment Management | Book/list/status workflow | PASS |
| OPD / Outpatient | Encounter workflow | PASS |
| Triage / Vital Signs | Vitals capture | PASS |
| Doctor Consultation | Consultation notes/status | PASS |
| Diagnosis & Clinical Notes | Separate diagnosis permission enforced | PASS |
| Prescription Management | Prescription creation | PASS |
| Pharmacy | Dispensing + inventory deduction | PASS |
| Laboratory | Order/result/verify/approve/print/export | PASS |
| Billing & Payments | Invoice + partial/full payment | PASS |
| Inventory / Stock | Items, movements, adjustments, low stock | PASS |
| Reports & Dashboard | Operational/financial summary + dashboard | PASS |
| User & Role Management | Users, activation, passwords, roles, granular permissions | PASS |
| Audit Logs | Clinical/admin/security-relevant actions recorded | PASS |
| System Configuration | Facility profile, presets, module switches | PASS |
| Small preset | Core only | PASS |
| District preset | Core + Radiology, Nursing, Wards, Beds, Maternity, Emergency, Insurance | PASS |
| Referral preset | Core + all configurable modules | PASS |
| Multi-hospital same-platform operation | Tenant ownership and independent module configuration | PASS |

## Configurable module coverage

All configurable modules named by the specification are present and tested for hospital-level enable/disable behavior. Wards and Beds have dedicated operational workflows. Every other configurable module uses the common specialist operational workspace, with patient linkage, status/details, create/read/update/delete, approval, verification, printable output and CSV export.

### Clinical / specialized

Radiology / Imaging; Nursing; Inpatient / Wards; Bed Management; Maternity; Theatre / Surgery; ICU; Emergency Department; Ambulance Management; Dental; Physiotherapy; Ophthalmology; ENT; Pediatrics; Mental Health; Dialysis; Oncology; Cardiology; Other Specialized Clinics.

### Administrative / financial

Insurance Management; Corporate Billing; Advanced Accounting / Finance; Procurement; Human Resources; Payroll; Asset Management; Maintenance; Document Management.

### Other hospital services

Mortuary; Blood Bank; Nutrition / Dietetics; Laundry; Catering / Kitchen; Central Sterile Supply; Medical Equipment Management.

## Main end-to-end clinical test

The automated workflow exercises this chain using persisted records:

`Login -> Patient registration -> Appointment -> Reception check-in -> OPD encounter -> Triage -> Consultation -> Diagnosis -> Lab order -> Result -> Verification -> Prescription -> Pharmacy dispense -> Stock movement -> Invoice -> Partial/full payment -> Ward/bed admission -> Discharge -> Reports -> Audit`

The browser suite independently executes the same major user journey through the real forms and buttons.

## Negative/integrity tests

The suite also verifies that the system rejects or protects against:

- bad credentials and unauthenticated access
- inactive accounts
- missing role permissions
- role permission attempts to bypass a disabled hospital module
- disabling a core module
- invalid facility types
- invalid appointment/encounter statuses
- appointment-to-wrong-patient encounter linkage
- admission-to-wrong-patient encounter linkage
- invalid SpO2 values
- lab verification before a result exists
- lab technician verification/approval without permission
- duplicate inventory SKU
- stock adjustment below zero
- double pharmacy dispensing
- dispensing with insufficient stock
- dispensing an unlinked medicine that does not exist in stock
- invoice over-payment
- payment after invoice is already paid
- unsupported payment methods
- duplicate bed codes
- admission into an occupied bed
- repeated discharge
- cross-hospital record access
- cross-hospital module-configuration leakage
- duplicate role rename conflicts
- unauthorized medical-record UI access
- disabled specialist modules appearing in the operational selector

## Scope boundary

The supplied specification defines the modular architecture, the module catalogue, facility presets, enable/disable behavior and RBAC model. It does **not** define detailed specialty-domain workflows such as DICOM/PACS protocols for Radiology, a maternity partograph, anaesthesia charts for Theatre, ICU ventilator charting, insurer claim adjudication rules, statutory payroll calculation, or blood-component compatibility workflows.

Accordingly, this build is fully verified against the supplied specification. For named specialist modules whose detailed domain workflow was not specified, the implementation is a complete generic operational-record workspace rather than an invented specialty-specific clinical protocol.
