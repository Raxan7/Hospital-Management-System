# One HMS — Configuration End-to-End Test Report

- Checks: **227**
- Passed: **227**
- Failed: **0**

This suite validates hospital-level module configuration at database, API, permission, preset, dependency, tenant-isolation and persistence layers.

| Check | Result | Detail |
|---|---|---|
| Registry: every declared module is returned exactly once | PASS |  |
| Database: every registry module has an explicit hospital state row | PASS |  |
| Core:patients: disable request is rejected | PASS |  |
| Core:patients: remains enabled in /api/modules and /api/me | PASS |  |
| Core:medical_records: disable request is rejected | PASS |  |
| Core:medical_records: remains enabled in /api/modules and /api/me | PASS |  |
| Core:reception: disable request is rejected | PASS |  |
| Core:reception: remains enabled in /api/modules and /api/me | PASS |  |
| Core:appointments: disable request is rejected | PASS |  |
| Core:appointments: remains enabled in /api/modules and /api/me | PASS |  |
| Core:opd: disable request is rejected | PASS |  |
| Core:opd: remains enabled in /api/modules and /api/me | PASS |  |
| Core:triage: disable request is rejected | PASS |  |
| Core:triage: remains enabled in /api/modules and /api/me | PASS |  |
| Core:consultation: disable request is rejected | PASS |  |
| Core:consultation: remains enabled in /api/modules and /api/me | PASS |  |
| Core:diagnosis: disable request is rejected | PASS |  |
| Core:diagnosis: remains enabled in /api/modules and /api/me | PASS |  |
| Core:prescriptions: disable request is rejected | PASS |  |
| Core:prescriptions: remains enabled in /api/modules and /api/me | PASS |  |
| Core:pharmacy: disable request is rejected | PASS |  |
| Core:pharmacy: remains enabled in /api/modules and /api/me | PASS |  |
| Core:laboratory: disable request is rejected | PASS |  |
| Core:laboratory: remains enabled in /api/modules and /api/me | PASS |  |
| Core:billing: disable request is rejected | PASS |  |
| Core:billing: remains enabled in /api/modules and /api/me | PASS |  |
| Core:inventory: disable request is rejected | PASS |  |
| Core:inventory: remains enabled in /api/modules and /api/me | PASS |  |
| Core:reports: disable request is rejected | PASS |  |
| Core:reports: remains enabled in /api/modules and /api/me | PASS |  |
| Core:users: disable request is rejected | PASS |  |
| Core:users: remains enabled in /api/modules and /api/me | PASS |  |
| Core:audit: disable request is rejected | PASS |  |
| Core:audit: remains enabled in /api/modules and /api/me | PASS |  |
| Core:configuration: disable request is rejected | PASS |  |
| Core:configuration: remains enabled in /api/modules and /api/me | PASS |  |
| Preset SMALL: all optional modules disabled | PASS |  |
| Preset SMALL: all core modules enabled | PASS |  |
| Toggle:radiology: enable persists to modules/me | PASS |  |
| Toggle:radiology: enabled endpoint is usable | PASS |  |
| Toggle:radiology: enabled state survives a fresh login token | PASS |  |
| Toggle:radiology: disable persists to modules/me | PASS |  |
| Toggle:radiology: disabled endpoint is blocked | PASS |  |
| Toggle:nursing: enable persists to modules/me | PASS |  |
| Toggle:nursing: enabled endpoint is usable | PASS |  |
| Toggle:nursing: enabled state survives a fresh login token | PASS |  |
| Toggle:nursing: disable persists to modules/me | PASS |  |
| Toggle:nursing: disabled endpoint is blocked | PASS |  |
| Toggle:wards: enable persists to modules/me | PASS |  |
| Toggle:wards: enabled endpoint is usable | PASS |  |
| Toggle:wards: enabled state survives a fresh login token | PASS |  |
| Toggle:wards: disable persists to modules/me | PASS |  |
| Toggle:wards: disabled endpoint is blocked | PASS |  |
| Toggle:maternity: enable persists to modules/me | PASS |  |
| Toggle:maternity: enabled endpoint is usable | PASS |  |
| Toggle:maternity: enabled state survives a fresh login token | PASS |  |
| Toggle:maternity: disable persists to modules/me | PASS |  |
| Toggle:maternity: disabled endpoint is blocked | PASS |  |
| Toggle:theatre: enable persists to modules/me | PASS |  |
| Toggle:theatre: enabled endpoint is usable | PASS |  |
| Toggle:theatre: enabled state survives a fresh login token | PASS |  |
| Toggle:theatre: disable persists to modules/me | PASS |  |
| Toggle:theatre: disabled endpoint is blocked | PASS |  |
| Toggle:icu: enable persists to modules/me | PASS |  |
| Toggle:icu: enabled endpoint is usable | PASS |  |
| Toggle:icu: enabled state survives a fresh login token | PASS |  |
| Toggle:icu: disable persists to modules/me | PASS |  |
| Toggle:icu: disabled endpoint is blocked | PASS |  |
| Toggle:emergency: enable persists to modules/me | PASS |  |
| Toggle:emergency: enabled endpoint is usable | PASS |  |
| Toggle:emergency: enabled state survives a fresh login token | PASS |  |
| Toggle:emergency: disable persists to modules/me | PASS |  |
| Toggle:emergency: disabled endpoint is blocked | PASS |  |
| Toggle:ambulance: enable persists to modules/me | PASS |  |
| Toggle:ambulance: enabled endpoint is usable | PASS |  |
| Toggle:ambulance: enabled state survives a fresh login token | PASS |  |
| Toggle:ambulance: disable persists to modules/me | PASS |  |
| Toggle:ambulance: disabled endpoint is blocked | PASS |  |
| Toggle:dental: enable persists to modules/me | PASS |  |
| Toggle:dental: enabled endpoint is usable | PASS |  |
| Toggle:dental: enabled state survives a fresh login token | PASS |  |
| Toggle:dental: disable persists to modules/me | PASS |  |
| Toggle:dental: disabled endpoint is blocked | PASS |  |
| Toggle:physiotherapy: enable persists to modules/me | PASS |  |
| Toggle:physiotherapy: enabled endpoint is usable | PASS |  |
| Toggle:physiotherapy: enabled state survives a fresh login token | PASS |  |
| Toggle:physiotherapy: disable persists to modules/me | PASS |  |
| Toggle:physiotherapy: disabled endpoint is blocked | PASS |  |
| Toggle:ophthalmology: enable persists to modules/me | PASS |  |
| Toggle:ophthalmology: enabled endpoint is usable | PASS |  |
| Toggle:ophthalmology: enabled state survives a fresh login token | PASS |  |
| Toggle:ophthalmology: disable persists to modules/me | PASS |  |
| Toggle:ophthalmology: disabled endpoint is blocked | PASS |  |
| Toggle:ent: enable persists to modules/me | PASS |  |
| Toggle:ent: enabled endpoint is usable | PASS |  |
| Toggle:ent: enabled state survives a fresh login token | PASS |  |
| Toggle:ent: disable persists to modules/me | PASS |  |
| Toggle:ent: disabled endpoint is blocked | PASS |  |
| Toggle:pediatrics: enable persists to modules/me | PASS |  |
| Toggle:pediatrics: enabled endpoint is usable | PASS |  |
| Toggle:pediatrics: enabled state survives a fresh login token | PASS |  |
| Toggle:pediatrics: disable persists to modules/me | PASS |  |
| Toggle:pediatrics: disabled endpoint is blocked | PASS |  |
| Toggle:mental_health: enable persists to modules/me | PASS |  |
| Toggle:mental_health: enabled endpoint is usable | PASS |  |
| Toggle:mental_health: enabled state survives a fresh login token | PASS |  |
| Toggle:mental_health: disable persists to modules/me | PASS |  |
| Toggle:mental_health: disabled endpoint is blocked | PASS |  |
| Toggle:dialysis: enable persists to modules/me | PASS |  |
| Toggle:dialysis: enabled endpoint is usable | PASS |  |
| Toggle:dialysis: enabled state survives a fresh login token | PASS |  |
| Toggle:dialysis: disable persists to modules/me | PASS |  |
| Toggle:dialysis: disabled endpoint is blocked | PASS |  |
| Toggle:oncology: enable persists to modules/me | PASS |  |
| Toggle:oncology: enabled endpoint is usable | PASS |  |
| Toggle:oncology: enabled state survives a fresh login token | PASS |  |
| Toggle:oncology: disable persists to modules/me | PASS |  |
| Toggle:oncology: disabled endpoint is blocked | PASS |  |
| Toggle:cardiology: enable persists to modules/me | PASS |  |
| Toggle:cardiology: enabled endpoint is usable | PASS |  |
| Toggle:cardiology: enabled state survives a fresh login token | PASS |  |
| Toggle:cardiology: disable persists to modules/me | PASS |  |
| Toggle:cardiology: disabled endpoint is blocked | PASS |  |
| Toggle:specialized_clinics: enable persists to modules/me | PASS |  |
| Toggle:specialized_clinics: enabled endpoint is usable | PASS |  |
| Toggle:specialized_clinics: enabled state survives a fresh login token | PASS |  |
| Toggle:specialized_clinics: disable persists to modules/me | PASS |  |
| Toggle:specialized_clinics: disabled endpoint is blocked | PASS |  |
| Toggle:insurance: enable persists to modules/me | PASS |  |
| Toggle:insurance: enabled endpoint is usable | PASS |  |
| Toggle:insurance: enabled state survives a fresh login token | PASS |  |
| Toggle:insurance: disable persists to modules/me | PASS |  |
| Toggle:insurance: disabled endpoint is blocked | PASS |  |
| Toggle:corporate_billing: enable persists to modules/me | PASS |  |
| Toggle:corporate_billing: enabled endpoint is usable | PASS |  |
| Toggle:corporate_billing: enabled state survives a fresh login token | PASS |  |
| Toggle:corporate_billing: disable persists to modules/me | PASS |  |
| Toggle:corporate_billing: disabled endpoint is blocked | PASS |  |
| Toggle:finance: enable persists to modules/me | PASS |  |
| Toggle:finance: enabled endpoint is usable | PASS |  |
| Toggle:finance: enabled state survives a fresh login token | PASS |  |
| Toggle:finance: disable persists to modules/me | PASS |  |
| Toggle:finance: disabled endpoint is blocked | PASS |  |
| Toggle:procurement: enable persists to modules/me | PASS |  |
| Toggle:procurement: enabled endpoint is usable | PASS |  |
| Toggle:procurement: enabled state survives a fresh login token | PASS |  |
| Toggle:procurement: disable persists to modules/me | PASS |  |
| Toggle:procurement: disabled endpoint is blocked | PASS |  |
| Toggle:hr: enable persists to modules/me | PASS |  |
| Toggle:hr: enabled endpoint is usable | PASS |  |
| Toggle:hr: enabled state survives a fresh login token | PASS |  |
| Toggle:hr: disable persists to modules/me | PASS |  |
| Toggle:hr: disabled endpoint is blocked | PASS |  |
| Toggle:payroll: enable persists to modules/me | PASS |  |
| Toggle:payroll: enabled endpoint is usable | PASS |  |
| Toggle:payroll: enabled state survives a fresh login token | PASS |  |
| Toggle:payroll: disable persists to modules/me | PASS |  |
| Toggle:payroll: disabled endpoint is blocked | PASS |  |
| Toggle:assets: enable persists to modules/me | PASS |  |
| Toggle:assets: enabled endpoint is usable | PASS |  |
| Toggle:assets: enabled state survives a fresh login token | PASS |  |
| Toggle:assets: disable persists to modules/me | PASS |  |
| Toggle:assets: disabled endpoint is blocked | PASS |  |
| Toggle:maintenance: enable persists to modules/me | PASS |  |
| Toggle:maintenance: enabled endpoint is usable | PASS |  |
| Toggle:maintenance: enabled state survives a fresh login token | PASS |  |
| Toggle:maintenance: disable persists to modules/me | PASS |  |
| Toggle:maintenance: disabled endpoint is blocked | PASS |  |
| Toggle:documents: enable persists to modules/me | PASS |  |
| Toggle:documents: enabled endpoint is usable | PASS |  |
| Toggle:documents: enabled state survives a fresh login token | PASS |  |
| Toggle:documents: disable persists to modules/me | PASS |  |
| Toggle:documents: disabled endpoint is blocked | PASS |  |
| Toggle:mortuary: enable persists to modules/me | PASS |  |
| Toggle:mortuary: enabled endpoint is usable | PASS |  |
| Toggle:mortuary: enabled state survives a fresh login token | PASS |  |
| Toggle:mortuary: disable persists to modules/me | PASS |  |
| Toggle:mortuary: disabled endpoint is blocked | PASS |  |
| Toggle:blood_bank: enable persists to modules/me | PASS |  |
| Toggle:blood_bank: enabled endpoint is usable | PASS |  |
| Toggle:blood_bank: enabled state survives a fresh login token | PASS |  |
| Toggle:blood_bank: disable persists to modules/me | PASS |  |
| Toggle:blood_bank: disabled endpoint is blocked | PASS |  |
| Toggle:nutrition: enable persists to modules/me | PASS |  |
| Toggle:nutrition: enabled endpoint is usable | PASS |  |
| Toggle:nutrition: enabled state survives a fresh login token | PASS |  |
| Toggle:nutrition: disable persists to modules/me | PASS |  |
| Toggle:nutrition: disabled endpoint is blocked | PASS |  |
| Toggle:laundry: enable persists to modules/me | PASS |  |
| Toggle:laundry: enabled endpoint is usable | PASS |  |
| Toggle:laundry: enabled state survives a fresh login token | PASS |  |
| Toggle:laundry: disable persists to modules/me | PASS |  |
| Toggle:laundry: disabled endpoint is blocked | PASS |  |
| Toggle:catering: enable persists to modules/me | PASS |  |
| Toggle:catering: enabled endpoint is usable | PASS |  |
| Toggle:catering: enabled state survives a fresh login token | PASS |  |
| Toggle:catering: disable persists to modules/me | PASS |  |
| Toggle:catering: disabled endpoint is blocked | PASS |  |
| Toggle:cssd: enable persists to modules/me | PASS |  |
| Toggle:cssd: enabled endpoint is usable | PASS |  |
| Toggle:cssd: enabled state survives a fresh login token | PASS |  |
| Toggle:cssd: disable persists to modules/me | PASS |  |
| Toggle:cssd: disabled endpoint is blocked | PASS |  |
| Toggle:medical_equipment: enable persists to modules/me | PASS |  |
| Toggle:medical_equipment: enabled endpoint is usable | PASS |  |
| Toggle:medical_equipment: enabled state survives a fresh login token | PASS |  |
| Toggle:medical_equipment: disable persists to modules/me | PASS |  |
| Toggle:medical_equipment: disabled endpoint is blocked | PASS |  |
| Dependency: disabling Wards also disables Beds | PASS |  |
| Dependency: enabling Beds atomically enables Wards | PASS |  |
| Dependency: Beds endpoint usable when both are enabled | PASS |  |
| Dependency: Beds endpoint blocked after Wards is disabled | PASS |  |
| Preset DISTRICT: optional set exactly matches configured district defaults | PASS |  |
| Facility type change without Apply Preset preserves manual module choices | PASS |  |
| Apply Preset works even when facility_type is omitted from API request | PASS |  |
| Preset REFERRAL: every module enabled | PASS |  |
| Dashboard enabled_modules KPI matches effective module registry | PASS |  |
| RBAC: Surgeon has Theatre permission in role | PASS |  |
| Configuration overrides RBAC: disabled Theatre blocks Surgeon | PASS |  |
| Configuration activation takes effect for existing Surgeon token | PASS |  |
| Audit: module configuration changes are recorded | PASS |  |
| Tenant isolation: Hospital A Theatre can be disabled independently | PASS |  |
| Tenant isolation: Hospital B Theatre remains enabled | PASS |  |
| Tenant isolation: Hospital B can use enabled Theatre | PASS |  |
| Tenant isolation: Hospital A remains blocked | PASS |  |
| Persistence: module state survives application restart/lifespan re-entry | PASS |  |
| Persistence: complete module-state rows still exist after restart | PASS |  |