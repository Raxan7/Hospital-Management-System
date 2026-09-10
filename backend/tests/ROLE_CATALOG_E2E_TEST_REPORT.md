# One HMS — Role Catalogue & Authorization E2E Test Report

- Test cases: **190**
- Passed: **190**
- Failed: **0**
- Built-in role templates: **63**

This suite validates every predefined hospital role, its permission mapping, upgrade-safe template installation, explicit requirement roles, module-disable precedence, and representative department workflows.

## Role catalogue

| Test case | Result | Detail |
|---|---|---|
| Built-in role templates validate with no unknown module/action | PASS |  |
| 63 predefined hospital role templates are published | PASS |  |
| Every explicitly discussed role type is predefined | PASS |  |
| Broader hospital role catalogue is predefined | PASS |  |
| Every template is installed as a selectable hospital role | PASS |  |
| Template categories and descriptions are exposed | PASS |  |
| Every template permission map matches installed default on fresh DB | PASS |  |
| All hospital role categories are represented | PASS |  |

## Upgrade safety

| Test case | Result | Detail |
|---|---|---|
| Installing missing defaults does not overwrite customized existing role | PASS |  |
| Installer reports no missing templates on complete installation | PASS |  |
| Built-in role can be reset to its recommended default permissions | PASS |  |
| Partial existing hospital receives all missing predefined roles | PASS |  |
| Upgrade preserves an existing customized Doctor role | PASS |  |
| Upgrade installs Surgeon and Theatre Staff into existing hospital | PASS |  |

## Explicit role E2E

| Test case | Result | Detail |
|---|---|---|
| Receptionist can read reception queue | PASS |  |
| Receptionist can register patient | PASS |  |
| Receptionist cannot enter laboratory results | PASS |  |
| Nurse can capture triage vitals | PASS |  |
| Nurse cannot edit doctor diagnosis | PASS |  |
| Doctor can document consultation and diagnosis | PASS |  |
| Doctor cannot administer users | PASS |  |
| Lab Technician can print a result | PASS |  |
| Lab Technician cannot verify | PASS |  |
| Lab Technician cannot approve | PASS |  |
| Lab Supervisor can verify result | PASS |  |
| Lab Supervisor can approve verified result | PASS |  |
| Lab Supervisor can export laboratory results | PASS |  |
| Surgeon can create theatre record | PASS |  |
| Surgeon can verify theatre record | PASS |  |
| Surgeon can approve theatre record | PASS |  |
| Surgeon cannot administer users | PASS |  |
| Theatre Staff can create theatre support record | PASS |  |
| Theatre Staff cannot approve surgery | PASS |  |
| Disabled Theatre overrides Surgeon role permissions | PASS |  |

## Representative department E2E

| Test case | Result | Detail |
|---|---|---|
| Radiologist can create record in radiology | PASS |  |
| Radiologist can read radiology workspace | PASS |  |
| Radiologist cannot create staff accounts | PASS |  |
| Midwife can create record in maternity | PASS |  |
| Midwife can read maternity workspace | PASS |  |
| Midwife cannot create staff accounts | PASS |  |
| Insurance Officer can create record in insurance | PASS |  |
| Insurance Officer can read insurance workspace | PASS |  |
| Insurance Officer cannot create staff accounts | PASS |  |
| Procurement Officer can create record in procurement | PASS |  |
| Procurement Officer can read procurement workspace | PASS |  |
| Procurement Officer cannot create staff accounts | PASS |  |
| HR Officer can create record in hr | PASS |  |
| HR Officer can read hr workspace | PASS |  |
| HR Officer cannot create staff accounts | PASS |  |
| Blood Bank Technician can create record in blood_bank | PASS |  |
| Blood Bank Technician can read blood_bank workspace | PASS |  |
| Blood Bank Technician cannot create staff accounts | PASS |  |
| Physiotherapist can create record in physiotherapy | PASS |  |
| Physiotherapist can read physiotherapy workspace | PASS |  |
| Physiotherapist cannot create staff accounts | PASS |  |
| Biomedical Equipment Technician can create record in medical_equipment | PASS |  |
| Biomedical Equipment Technician can read medical_equipment workspace | PASS |  |
| Biomedical Equipment Technician cannot create staff accounts | PASS |  |
| Oncologist can create record in oncology | PASS |  |
| Oncologist can read oncology workspace | PASS |  |
| Oncologist cannot create staff accounts | PASS |  |
| Cardiologist can create record in cardiology | PASS |  |
| Cardiologist can read cardiology workspace | PASS |  |
| Cardiologist cannot create staff accounts | PASS |  |

## Role permission matrix

| Test case | Result | Detail |
|---|---|---|
| Super Administrator: every granted permission is accepted by authorization engine | PASS |  |
| Super Administrator: full administrator template intentionally has all permissions | PASS |  |
| Hospital Administrator: every granted permission is accepted by authorization engine | PASS |  |
| Hospital Administrator: full administrator template intentionally has all permissions | PASS |  |
| Administrator: every granted permission is accepted by authorization engine | PASS |  |
| Administrator: full administrator template intentionally has all permissions | PASS |  |
| Medical Director: every granted permission is accepted by authorization engine | PASS |  |
| Medical Director: an ungranted permission is denied | PASS |  |
| Department Manager: every granted permission is accepted by authorization engine | PASS |  |
| Department Manager: an ungranted permission is denied | PASS |  |
| Receptionist: every granted permission is accepted by authorization engine | PASS |  |
| Receptionist: an ungranted permission is denied | PASS |  |
| Registration Officer: every granted permission is accepted by authorization engine | PASS |  |
| Registration Officer: an ungranted permission is denied | PASS |  |
| Appointment Officer: every granted permission is accepted by authorization engine | PASS |  |
| Appointment Officer: an ungranted permission is denied | PASS |  |
| Medical Records Officer: every granted permission is accepted by authorization engine | PASS |  |
| Medical Records Officer: an ungranted permission is denied | PASS |  |
| Doctor: every granted permission is accepted by authorization engine | PASS |  |
| Doctor: an ungranted permission is denied | PASS |  |
| Medical Officer: every granted permission is accepted by authorization engine | PASS |  |
| Medical Officer: an ungranted permission is denied | PASS |  |
| Clinical Officer: every granted permission is accepted by authorization engine | PASS |  |
| Clinical Officer: an ungranted permission is denied | PASS |  |
| Specialist Doctor: every granted permission is accepted by authorization engine | PASS |  |
| Specialist Doctor: an ungranted permission is denied | PASS |  |
| Nurse: every granted permission is accepted by authorization engine | PASS |  |
| Nurse: an ungranted permission is denied | PASS |  |
| Triage Nurse: every granted permission is accepted by authorization engine | PASS |  |
| Triage Nurse: an ungranted permission is denied | PASS |  |
| Ward Nurse: every granted permission is accepted by authorization engine | PASS |  |
| Ward Nurse: an ungranted permission is denied | PASS |  |
| ICU Nurse: every granted permission is accepted by authorization engine | PASS |  |
| ICU Nurse: an ungranted permission is denied | PASS |  |
| Midwife: every granted permission is accepted by authorization engine | PASS |  |
| Midwife: an ungranted permission is denied | PASS |  |
| Surgeon: every granted permission is accepted by authorization engine | PASS |  |
| Surgeon: an ungranted permission is denied | PASS |  |
| Anaesthetist: every granted permission is accepted by authorization engine | PASS |  |
| Anaesthetist: an ungranted permission is denied | PASS |  |
| Theatre Nurse: every granted permission is accepted by authorization engine | PASS |  |
| Theatre Nurse: an ungranted permission is denied | PASS |  |
| Theatre Technician: every granted permission is accepted by authorization engine | PASS |  |
| Theatre Technician: an ungranted permission is denied | PASS |  |
| Theatre Staff: every granted permission is accepted by authorization engine | PASS |  |
| Theatre Staff: an ungranted permission is denied | PASS |  |
| Lab Technician: every granted permission is accepted by authorization engine | PASS |  |
| Lab Technician: an ungranted permission is denied | PASS |  |
| Lab Scientist: every granted permission is accepted by authorization engine | PASS |  |
| Lab Scientist: an ungranted permission is denied | PASS |  |
| Lab Supervisor: every granted permission is accepted by authorization engine | PASS |  |
| Lab Supervisor: an ungranted permission is denied | PASS |  |
| Pharmacist: every granted permission is accepted by authorization engine | PASS |  |
| Pharmacist: an ungranted permission is denied | PASS |  |
| Pharmacy Technician: every granted permission is accepted by authorization engine | PASS |  |
| Pharmacy Technician: an ungranted permission is denied | PASS |  |
| Pharmacy Supervisor: every granted permission is accepted by authorization engine | PASS |  |
| Pharmacy Supervisor: an ungranted permission is denied | PASS |  |
| Radiologist: every granted permission is accepted by authorization engine | PASS |  |
| Radiologist: an ungranted permission is denied | PASS |  |
| Radiographer: every granted permission is accepted by authorization engine | PASS |  |
| Radiographer: an ungranted permission is denied | PASS |  |
| Sonographer: every granted permission is accepted by authorization engine | PASS |  |
| Sonographer: an ungranted permission is denied | PASS |  |
| Cashier: every granted permission is accepted by authorization engine | PASS |  |
| Cashier: an ungranted permission is denied | PASS |  |
| Billing Officer: every granted permission is accepted by authorization engine | PASS |  |
| Billing Officer: an ungranted permission is denied | PASS |  |
| Insurance Officer: every granted permission is accepted by authorization engine | PASS |  |
| Insurance Officer: an ungranted permission is denied | PASS |  |
| Accountant: every granted permission is accepted by authorization engine | PASS |  |
| Accountant: an ungranted permission is denied | PASS |  |
| Finance Manager: every granted permission is accepted by authorization engine | PASS |  |
| Finance Manager: an ungranted permission is denied | PASS |  |
| Storekeeper: every granted permission is accepted by authorization engine | PASS |  |
| Storekeeper: an ungranted permission is denied | PASS |  |
| Procurement Officer: every granted permission is accepted by authorization engine | PASS |  |
| Procurement Officer: an ungranted permission is denied | PASS |  |
| Inventory Manager: every granted permission is accepted by authorization engine | PASS |  |
| Inventory Manager: an ungranted permission is denied | PASS |  |
| HR Officer: every granted permission is accepted by authorization engine | PASS |  |
| HR Officer: an ungranted permission is denied | PASS |  |
| Payroll Officer: every granted permission is accepted by authorization engine | PASS |  |
| Payroll Officer: an ungranted permission is denied | PASS |  |
| Auditor: every granted permission is accepted by authorization engine | PASS |  |
| Auditor: an ungranted permission is denied | PASS |  |
| Document Officer: every granted permission is accepted by authorization engine | PASS |  |
| Document Officer: an ungranted permission is denied | PASS |  |
| Asset Officer: every granted permission is accepted by authorization engine | PASS |  |
| Asset Officer: an ungranted permission is denied | PASS |  |
| Maintenance Officer: every granted permission is accepted by authorization engine | PASS |  |
| Maintenance Officer: an ungranted permission is denied | PASS |  |
| Blood Bank Technician: every granted permission is accepted by authorization engine | PASS |  |
| Blood Bank Technician: an ungranted permission is denied | PASS |  |
| Mortuary Attendant: every granted permission is accepted by authorization engine | PASS |  |
| Mortuary Attendant: an ungranted permission is denied | PASS |  |
| Nutritionist / Dietitian: every granted permission is accepted by authorization engine | PASS |  |
| Nutritionist / Dietitian: an ungranted permission is denied | PASS |  |
| Physiotherapist: every granted permission is accepted by authorization engine | PASS |  |
| Physiotherapist: an ungranted permission is denied | PASS |  |
| Ambulance / EMS Staff: every granted permission is accepted by authorization engine | PASS |  |
| Ambulance / EMS Staff: an ungranted permission is denied | PASS |  |
| Biomedical Equipment Technician: every granted permission is accepted by authorization engine | PASS |  |
| Biomedical Equipment Technician: an ungranted permission is denied | PASS |  |
| CSSD Technician: every granted permission is accepted by authorization engine | PASS |  |
| CSSD Technician: an ungranted permission is denied | PASS |  |
| Catering / Kitchen Staff: every granted permission is accepted by authorization engine | PASS |  |
| Catering / Kitchen Staff: an ungranted permission is denied | PASS |  |
| Laundry Staff: every granted permission is accepted by authorization engine | PASS |  |
| Laundry Staff: an ungranted permission is denied | PASS |  |
| Dental Clinician: every granted permission is accepted by authorization engine | PASS |  |
| Dental Clinician: an ungranted permission is denied | PASS |  |
| Ophthalmology Clinician: every granted permission is accepted by authorization engine | PASS |  |
| Ophthalmology Clinician: an ungranted permission is denied | PASS |  |
| ENT Clinician: every granted permission is accepted by authorization engine | PASS |  |
| ENT Clinician: an ungranted permission is denied | PASS |  |
| Pediatrician: every granted permission is accepted by authorization engine | PASS |  |
| Pediatrician: an ungranted permission is denied | PASS |  |
| Mental Health Clinician: every granted permission is accepted by authorization engine | PASS |  |
| Mental Health Clinician: an ungranted permission is denied | PASS |  |
| Dialysis Clinician: every granted permission is accepted by authorization engine | PASS |  |
| Dialysis Clinician: an ungranted permission is denied | PASS |  |
| Oncologist: every granted permission is accepted by authorization engine | PASS |  |
| Oncologist: an ungranted permission is denied | PASS |  |
| Cardiologist: every granted permission is accepted by authorization engine | PASS |  |
| Cardiologist: an ungranted permission is denied | PASS |  |
