from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleDefinition:
    key: str
    name: str
    group: str
    core: bool = False


MODULES = [
    ModuleDefinition("patients", "Patient Registration", "Core", True),
    ModuleDefinition("medical_records", "Patient Management / Medical Records", "Core", True),
    ModuleDefinition("reception", "Reception", "Core", True),
    ModuleDefinition("appointments", "Appointment Management", "Core", True),
    ModuleDefinition("opd", "OPD / Outpatient", "Core", True),
    ModuleDefinition("triage", "Triage / Vital Signs", "Core", True),
    ModuleDefinition("consultation", "Doctor Consultation", "Core", True),
    ModuleDefinition("diagnosis", "Diagnosis & Clinical Notes", "Core", True),
    ModuleDefinition("prescriptions", "Prescription Management", "Core", True),
    ModuleDefinition("pharmacy", "Pharmacy", "Core", True),
    ModuleDefinition("laboratory", "Laboratory", "Core", True),
    ModuleDefinition("billing", "Billing & Payments", "Core", True),
    ModuleDefinition("inventory", "Inventory / Stock", "Core", True),
    ModuleDefinition("reports", "Reports & Dashboard", "Core", True),
    ModuleDefinition("users", "User & Role Management", "Core", True),
    ModuleDefinition("audit", "Audit Logs", "Core", True),
    ModuleDefinition("configuration", "System Configuration", "Core", True),
    ModuleDefinition("radiology", "Radiology / Imaging", "Clinical"),
    ModuleDefinition("nursing", "Nursing", "Clinical"),
    ModuleDefinition("wards", "Inpatient / Wards", "Clinical"),
    ModuleDefinition("beds", "Bed Management", "Clinical"),
    ModuleDefinition("maternity", "Maternity", "Clinical"),
    ModuleDefinition("theatre", "Theatre / Surgery", "Clinical"),
    ModuleDefinition("icu", "ICU", "Clinical"),
    ModuleDefinition("emergency", "Emergency Department", "Clinical"),
    ModuleDefinition("ambulance", "Ambulance Management", "Clinical"),
    ModuleDefinition("dental", "Dental", "Clinical"),
    ModuleDefinition("physiotherapy", "Physiotherapy", "Clinical"),
    ModuleDefinition("ophthalmology", "Ophthalmology", "Clinical"),
    ModuleDefinition("ent", "ENT", "Clinical"),
    ModuleDefinition("pediatrics", "Pediatrics", "Clinical"),
    ModuleDefinition("mental_health", "Mental Health", "Clinical"),
    ModuleDefinition("dialysis", "Dialysis", "Clinical"),
    ModuleDefinition("oncology", "Oncology", "Clinical"),
    ModuleDefinition("cardiology", "Cardiology", "Clinical"),
    ModuleDefinition("specialized_clinics", "Other Specialized Clinics", "Clinical"),
    ModuleDefinition("insurance", "Insurance Management", "Administrative"),
    ModuleDefinition("corporate_billing", "Corporate Billing", "Administrative"),
    ModuleDefinition("finance", "Advanced Accounting / Finance", "Administrative"),
    ModuleDefinition("procurement", "Procurement", "Administrative"),
    ModuleDefinition("hr", "Human Resources", "Administrative"),
    ModuleDefinition("payroll", "Payroll", "Administrative"),
    ModuleDefinition("assets", "Asset Management", "Administrative"),
    ModuleDefinition("maintenance", "Maintenance", "Administrative"),
    ModuleDefinition("documents", "Document Management", "Administrative"),
    ModuleDefinition("mortuary", "Mortuary", "Hospital Services"),
    ModuleDefinition("blood_bank", "Blood Bank", "Hospital Services"),
    ModuleDefinition("nutrition", "Nutrition / Dietetics", "Hospital Services"),
    ModuleDefinition("laundry", "Laundry", "Hospital Services"),
    ModuleDefinition("catering", "Catering / Kitchen", "Hospital Services"),
    ModuleDefinition("cssd", "Central Sterile Supply", "Hospital Services"),
    ModuleDefinition("medical_equipment", "Medical Equipment Management", "Hospital Services"),
]

MODULE_BY_KEY = {m.key: m for m in MODULES}
PERMISSIONS = ["VIEW", "CREATE", "EDIT", "DELETE", "APPROVE", "VERIFY", "PRINT", "EXPORT"]

# Actions with a live enforcement point in the API, per module. Any action not listed
# here has no endpoint behind it, so the role editor renders it as unavailable.
SUPPORTED_ACTIONS: dict[str, list[str]] = {
    'patients': ['VIEW', 'CREATE', 'EDIT'],
    'medical_records': ['VIEW'],
    'reception': ['VIEW', 'CREATE', 'EDIT'],
    'appointments': ['VIEW', 'CREATE', 'EDIT'],
    'opd': ['VIEW', 'CREATE'],
    'triage': ['CREATE'],
    'consultation': ['EDIT'],
    'diagnosis': ['EDIT'],
    'prescriptions': ['VIEW', 'CREATE'],
    'pharmacy': ['EDIT'],
    'laboratory': ['VIEW', 'CREATE', 'EDIT', 'VERIFY', 'APPROVE', 'PRINT', 'EXPORT'],
    'billing': ['VIEW', 'CREATE', 'EDIT', 'PRINT'],
    'inventory': ['VIEW', 'CREATE', 'EDIT'],
    'reports': ['VIEW', 'EXPORT'],
    'users': ['VIEW', 'CREATE', 'EDIT'],
    'audit': ['VIEW'],
    'configuration': ['VIEW', 'EDIT'],
    'wards': ['VIEW', 'CREATE', 'EDIT'],
    'beds': ['VIEW', 'CREATE', 'EDIT'],
}


def module_supported(module_key: str) -> list[str]:
    return SUPPORTED_ACTIONS.get(module_key, PERMISSIONS.copy())

DISTRICT_DEFAULTS = {
    "radiology", "nursing", "wards", "beds", "maternity", "emergency", "insurance"
}
REFERRAL_DEFAULTS = {m.key for m in MODULES if not m.core}


def preset_enabled(facility_type: str, module: ModuleDefinition) -> bool:
    if module.core:
        return True
    facility_type = facility_type.upper()
    if facility_type == "REFERRAL":
        return module.key in REFERRAL_DEFAULTS
    if facility_type == "DISTRICT":
        return module.key in DISTRICT_DEFAULTS
    return False
