# One HMS — Enterprise Modular HMS MVP

This project is a runnable, end-to-end Hospital Management System foundation based on one configurable HMS platform. The browser UI and API are served by the same FastAPI application, so there is no Node/npm frontend build required. The current UI is an enterprise-polished responsive interface designed for desktop, tablet and mobile use.

## Functional scope

### Platform and security
- JWT login and active-user checks
- Hospital profile and facility type: SMALL / DISTRICT / REFERRAL
- Facility presets for module configuration
- Core and optional module registry
- Hospital-level enable / disable enforcement with persistent state and live session refresh
- Role-based permissions: VIEW, CREATE, EDIT, DELETE, APPROVE, VERIFY, PRINT, EXPORT
- 63 predefined hospital role templates across management, front office, clinical, nursing, theatre, laboratory, pharmacy, radiology, finance, procurement, administration and specialty services
- Upgrade-safe role-template installation: missing defaults are added without overwriting hospital customizations
- User creation, grouped role assignment, activation/deactivation and password reset API
- Granular role-permission editor, role descriptions/categories and reset-to-default controls in the browser UI
- Audit logging
- Multi-hospital ownership checks in protected records

### Clinical workflow
- Patient registration and separately permissioned patient medical-record history
- Appointment booking and status changes
- OPD / follow-up / emergency encounters
- Triage and vital signs
- Consultation notes and diagnosis
- Laboratory orders, results and verification
- Prescriptions
- Pharmacy dispensing
- Dispensing automatically reduces inventory stock
- Double dispensing and insufficient stock are blocked

### Billing and inventory
- Invoice creation
- Partial and full payments
- Cash, card, mobile-money, bank and insurance payment methods
- Over-payment and repeat payment of a paid invoice are blocked
- Inventory catalog
- Opening stock
- Positive / negative stock adjustments
- Stock movement history API
- Negative stock is blocked
- Low-stock reporting

### Inpatient
- Ward creation
- Bed creation and availability state
- Patient admission
- Occupied-bed reuse is blocked
- Patient discharge automatically releases the bed

### Optional / configurable modules
Every optional module in the architecture can be enabled at hospital level. Nursing is also included because it is explicitly present in the District Hospital example. Enabled optional modules receive a working operational-record workspace with patient linkage, status and structured details. This covers Radiology, Maternity, Theatre, ICU, Emergency, Ambulance, Dental, Physiotherapy, Ophthalmology, ENT, Pediatrics, Mental Health, Dialysis, Oncology, Cardiology, specialized clinics, Insurance, Corporate Billing, Finance, Procurement, HR, Payroll, Assets, Maintenance, Documents, Mortuary, Blood Bank, Nutrition, Laundry, Catering, CSSD and Medical Equipment.

Wards and Bed Management additionally have dedicated admission/occupancy workflows. Bed Management requires Wards: enabling Beds automatically enables Wards, and disabling Wards automatically disables Beds.

## Run with Docker

From the project root:

```bash

docker compose up --build
```

Then open:

- HMS: http://localhost:8082
- API docs: http://localhost:8082/docs
- Health: http://localhost:8082/api/health

Docker runs PostgreSQL 16 automatically.

## Run locally with SQLite

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8082
```

Open http://localhost:8082.

## Demo accounts

Administrator:
- Email: `admin@onehms.com`
- Password: `Admin123!`

Other seeded workflow accounts use password `Demo123!`:
- `doctor@onehms.com`
- `nurse@onehms.com`
- `reception@onehms.com`
- `lab@onehms.com`
- `pharmacy@onehms.com`
- `cashier@onehms.com`
- `surgeon@onehms.com`
- `theatre.nurse@onehms.com`

Change demo passwords and JWT secret before any real deployment.

## Repeatable smoke test

After installing backend dependencies:

```bash
cd backend
PYTHONPATH=. python tests/smoke_test.py
```

It tests the full main workflow plus critical guards: patient, appointment, encounter, vitals, consultation, lab verification, inventory, prescription/dispensing, partial/full payment, ward/bed admission/discharge, module blocking/enabling and RBAC denial.


## Deep verification

This build includes a specification-driven end-to-end test suite. Current verified result:

- 436 / 436 specification/API E2E cases passed
- 190 / 190 role-catalogue & authorization E2E cases passed
- 42 / 42 Chromium functional browser E2E cases passed
- 22 / 22 responsive UI/browser E2E checks passed
- 227 / 227 configuration/API E2E cases passed
- 22 / 22 configuration browser E2E checks passed
- 939 distinct automated verification cases passed, 0 failed

Read `docs/TESTING_AND_COVERAGE.md`, `docs/UI_REDESIGN.md`, plus the full spec, role, configuration, functional browser and responsive UI reports under `backend/tests/` for the requirement-by-requirement evidence. Run all locally with:

```bash
./run-tests.sh
```

## Architecture rule

Access is granted only when both are true:

1. The hospital has enabled the module.
2. The user's role has the required permission.

A doctor can therefore have `THEATRE: CREATE`, but Theatre still returns `403 MODULE_DISABLED` until that hospital enables Theatre.

## Important production boundary

This is a fully working end-to-end HMS MVP and demonstration platform. Before treating it as a production clinical system for real hospitals, add your country's required regulatory/compliance controls, database migrations, encrypted backups, disaster recovery, TLS/domain configuration, monitoring, attachment/document storage, clinical coding/catalog integrations, insurer/payment integrations and specialty-specific validation rules required by the facilities you deploy to.
