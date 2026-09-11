"""Built-in hospital role catalogue.

Templates provide safe starting permissions. Hospitals may edit installed Role rows
without modifying this catalogue. Startup only installs a template when a role with
that name does not already exist, so local customisations are preserved.
"""
from dataclasses import dataclass
from .modules import MODULES, PERMISSIONS


@dataclass(frozen=True)
class RoleTemplate:
    name: str
    category: str
    description: str
    permissions: dict[str, list[str]]


def p(*actions: str) -> list[str]:
    return list(actions)


def full(*module_keys: str) -> dict[str, list[str]]:
    return {key: PERMISSIONS.copy() for key in module_keys}


def view(*module_keys: str) -> dict[str, list[str]]:
    return {key: p('VIEW') for key in module_keys}


def merge(*parts: dict[str, list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part in parts:
        for module, actions in part.items():
            existing = out.setdefault(module, [])
            for action in actions:
                if action not in existing:
                    existing.append(action)
    return out


ALL = {m.key: PERMISSIONS.copy() for m in MODULES}
CLINICAL_VIEW = view(
    'patients','medical_records','appointments','opd','triage','consultation','diagnosis','prescriptions',
    'laboratory','radiology','nursing','wards','beds','maternity','theatre','icu','emergency','dental',
    'physiotherapy','ophthalmology','ent','pediatrics','mental_health','dialysis','oncology','cardiology',
    'specialized_clinics','blood_bank','nutrition'
)

ROLE_TEMPLATES: list[RoleTemplate] = [
    RoleTemplate('Super Administrator','System & Management','Full platform administration across every enabled module.',ALL),
    RoleTemplate('Hospital Administrator','System & Management','Hospital configuration, staff administration and full operational access.',ALL),
    RoleTemplate('Administrator','System & Management','Backward-compatible full administrator role.',ALL),
    RoleTemplate('Medical Director','System & Management','Clinical oversight, approvals, reporting and audit visibility.',merge(
        CLINICAL_VIEW,
        {'consultation':p('VIEW','EDIT'),'diagnosis':p('VIEW','APPROVE'),'laboratory':p('VIEW','APPROVE','PRINT','EXPORT'),
         'radiology':p('VIEW','APPROVE','PRINT','EXPORT'),'theatre':p('VIEW','APPROVE','PRINT','EXPORT'),
         'reports':p('VIEW','PRINT','EXPORT'),'audit':p('VIEW','EXPORT'),'users':p('VIEW'),'configuration':p('VIEW')}
    )),
    RoleTemplate('Department Manager','System & Management','Department oversight baseline; administrators can narrow it to a specific department.',merge(
        view('patients','medical_records','inventory','users','audit'),
        {'reports':p('VIEW','PRINT','EXPORT'),'inventory':p('VIEW','APPROVE','VERIFY','PRINT','EXPORT')}
    )),

    RoleTemplate('Receptionist','Front Office', 'Patient reception, appointments, check-in and OPD initiation.',{
        'patients':p('VIEW','CREATE','EDIT'),'medical_records':p('VIEW'),'reception':p('VIEW','CREATE','EDIT','PRINT'),
        'appointments':p('VIEW','CREATE','EDIT','PRINT'),'opd':p('VIEW','CREATE'),'billing':p('VIEW')
    }),
    RoleTemplate('Registration Officer','Front Office','Patient registration and demographic maintenance.',{
        'patients':p('VIEW','CREATE','EDIT','PRINT'),'medical_records':p('VIEW'),'reception':p('VIEW')
    }),
    RoleTemplate('Appointment Officer','Front Office','Appointment scheduling, rescheduling and reception coordination.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'appointments':p('VIEW','CREATE','EDIT','PRINT','EXPORT'),'reception':p('VIEW','EDIT')
    }),
    RoleTemplate('Medical Records Officer','Front Office','Custody, review and controlled export of longitudinal medical records.',{
        'patients':p('VIEW','EDIT'),'medical_records':p('VIEW','CREATE','EDIT','PRINT','EXPORT'),'documents':p('VIEW','CREATE','EDIT','PRINT','EXPORT')
    }),

    RoleTemplate('Doctor','Clinical','General doctor / medical officer clinical workflow.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'appointments':p('VIEW'),'opd':p('VIEW','CREATE','EDIT'),
        'triage':p('VIEW'),'consultation':p('VIEW','CREATE','EDIT'),'diagnosis':p('VIEW','CREATE','EDIT'),
        'prescriptions':p('VIEW','CREATE','EDIT'),'laboratory':p('VIEW','CREATE'),'radiology':p('VIEW','CREATE'),
        'wards':p('VIEW','CREATE','EDIT'),'beds':p('VIEW'),'nursing':p('VIEW'),'reports':p('VIEW'),
        'maternity':p('VIEW'),'emergency':p('VIEW','CREATE','EDIT'),'icu':p('VIEW'),'theatre':p('VIEW')
    }),
    RoleTemplate('Medical Officer','Clinical','General medical officer; equivalent default scope to Doctor.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'appointments':p('VIEW'),'opd':p('VIEW','CREATE','EDIT'),
        'triage':p('VIEW'),'consultation':p('VIEW','CREATE','EDIT'),'diagnosis':p('VIEW','CREATE','EDIT'),
        'prescriptions':p('VIEW','CREATE','EDIT'),'laboratory':p('VIEW','CREATE'),'radiology':p('VIEW','CREATE'),
        'wards':p('VIEW','CREATE','EDIT'),'beds':p('VIEW'),'nursing':p('VIEW'),'emergency':p('VIEW','CREATE','EDIT')
    }),
    RoleTemplate('Clinical Officer','Clinical','OPD clinical assessment, diagnosis and treatment within assigned scope.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'opd':p('VIEW','CREATE','EDIT'),'triage':p('VIEW'),
        'consultation':p('VIEW','CREATE','EDIT'),'diagnosis':p('VIEW','CREATE','EDIT'),'prescriptions':p('VIEW','CREATE'),
        'laboratory':p('VIEW','CREATE'),'reports':p('VIEW')
    }),
    RoleTemplate('Specialist Doctor','Clinical','Specialist clinician with broad specialty-clinic access.',merge(
        view('patients','medical_records','appointments','triage','laboratory','radiology','nursing','wards','beds'),
        {'opd':p('VIEW','CREATE','EDIT'),'consultation':p('VIEW','CREATE','EDIT'),'diagnosis':p('VIEW','CREATE','EDIT','APPROVE'),
         'prescriptions':p('VIEW','CREATE','EDIT'),'laboratory':p('VIEW','CREATE'),'radiology':p('VIEW','CREATE'),
         'specialized_clinics':p('VIEW','CREATE','EDIT','VERIFY','APPROVE','PRINT')}
    )),
    RoleTemplate('Nurse','Nursing','General nursing, triage, ward and emergency care.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'appointments':p('VIEW'),'opd':p('VIEW'),
        'triage':p('VIEW','CREATE','EDIT'),'consultation':p('VIEW'),'wards':p('VIEW','CREATE','EDIT'),
        'beds':p('VIEW','EDIT'),'nursing':p('VIEW','CREATE','EDIT','PRINT'),'emergency':p('VIEW','CREATE','EDIT'),
        'maternity':p('VIEW','CREATE','EDIT'),'icu':p('VIEW','CREATE','EDIT')
    }),
    RoleTemplate('Triage Nurse','Nursing','Triage queue and vital-sign capture.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'reception':p('VIEW'),'opd':p('VIEW'),'triage':p('VIEW','CREATE','EDIT','PRINT')
    }),
    RoleTemplate('Ward Nurse','Nursing','Inpatient ward, bed and nursing-care operations.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'wards':p('VIEW','CREATE','EDIT','PRINT'),
        'beds':p('VIEW','EDIT'),'nursing':p('VIEW','CREATE','EDIT','PRINT'),'prescriptions':p('VIEW'),'laboratory':p('VIEW')
    }),
    RoleTemplate('ICU Nurse','Nursing','ICU nursing and critical-care documentation.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'triage':p('VIEW','CREATE','EDIT'),'icu':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),
        'nursing':p('VIEW','CREATE','EDIT','PRINT'),'wards':p('VIEW'),'beds':p('VIEW','EDIT'),'prescriptions':p('VIEW'),'laboratory':p('VIEW')
    }),
    RoleTemplate('Midwife','Nursing','Maternity, maternal triage and nursing documentation.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'triage':p('VIEW','CREATE','EDIT'),'maternity':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),
        'nursing':p('VIEW','CREATE','EDIT','PRINT'),'wards':p('VIEW'),'beds':p('VIEW','EDIT'),'prescriptions':p('VIEW')
    }),

    RoleTemplate('Surgeon','Theatre','Surgical clinical workflow and theatre approvals.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'consultation':p('VIEW','CREATE','EDIT'),'diagnosis':p('VIEW','CREATE','EDIT'),
        'prescriptions':p('VIEW','CREATE','EDIT'),'laboratory':p('VIEW','CREATE'),'radiology':p('VIEW','CREATE'),
        'theatre':p('VIEW','CREATE','EDIT','VERIFY','APPROVE','PRINT'),'wards':p('VIEW'),'beds':p('VIEW'),'icu':p('VIEW')
    }),
    RoleTemplate('Anaesthetist','Theatre','Anaesthesia assessment and intra-operative documentation.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'triage':p('VIEW'),'laboratory':p('VIEW'),'theatre':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),
        'icu':p('VIEW','CREATE','EDIT'),'prescriptions':p('VIEW','CREATE')
    }),
    RoleTemplate('Theatre Nurse','Theatre','Theatre nursing, preparation and peri-operative records.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'theatre':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),
        'nursing':p('VIEW','CREATE','EDIT'),'inventory':p('VIEW'),'cssd':p('VIEW','CREATE','EDIT')
    }),
    RoleTemplate('Theatre Technician','Theatre','Theatre equipment, room preparation and technical records.',{
        'patients':p('VIEW'),'theatre':p('VIEW','CREATE','EDIT','PRINT'),'inventory':p('VIEW'),'cssd':p('VIEW','CREATE','EDIT'),
        'medical_equipment':p('VIEW','CREATE','EDIT')
    }),
    RoleTemplate('Theatre Staff','Theatre','General theatre support role for facilities that do not split theatre support duties.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'theatre':p('VIEW','CREATE','EDIT','PRINT'),
        'nursing':p('VIEW'),'inventory':p('VIEW'),'cssd':p('VIEW','CREATE','EDIT')
    }),

    RoleTemplate('Lab Technician','Laboratory','Laboratory order processing and result entry; cannot approve.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'laboratory':p('VIEW','CREATE','EDIT','PRINT')
    }),
    RoleTemplate('Lab Scientist','Laboratory','Laboratory processing with verification authority.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'laboratory':p('VIEW','CREATE','EDIT','VERIFY','PRINT','EXPORT')
    }),
    RoleTemplate('Lab Supervisor','Laboratory','Laboratory supervision, verification and approval.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'laboratory':p('VIEW','CREATE','EDIT','VERIFY','APPROVE','PRINT','EXPORT')
    }),

    RoleTemplate('Pharmacist','Pharmacy','Prescription review, dispensing and stock operations.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'prescriptions':p('VIEW'),'pharmacy':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),
        'inventory':p('VIEW','EDIT')
    }),
    RoleTemplate('Pharmacy Technician','Pharmacy','Dispensing support under pharmacist supervision.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'prescriptions':p('VIEW'),'pharmacy':p('VIEW','EDIT','PRINT'),'inventory':p('VIEW')
    }),
    RoleTemplate('Pharmacy Supervisor','Pharmacy','Pharmacy approvals, dispensing oversight and stock reporting.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'prescriptions':p('VIEW'),'pharmacy':p('VIEW','CREATE','EDIT','VERIFY','APPROVE','PRINT','EXPORT'),
        'inventory':p('VIEW','CREATE','EDIT','VERIFY','APPROVE','PRINT','EXPORT'),'reports':p('VIEW','EXPORT')
    }),

    RoleTemplate('Radiologist','Radiology','Radiology interpretation, verification and approval.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'radiology':p('VIEW','CREATE','EDIT','VERIFY','APPROVE','PRINT','EXPORT')
    }),
    RoleTemplate('Radiographer','Radiology','Imaging acquisition and radiology workflow documentation.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'radiology':p('VIEW','CREATE','EDIT','VERIFY','PRINT')
    }),
    RoleTemplate('Sonographer','Radiology','Ultrasound/sonography workflow and reporting.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'radiology':p('VIEW','CREATE','EDIT','VERIFY','PRINT')
    }),

    RoleTemplate('Cashier','Finance','Collect and record patient payments.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'billing':p('VIEW','CREATE','EDIT','PRINT'),'reports':p('VIEW')
    }),
    RoleTemplate('Billing Officer','Finance','Patient and corporate billing operations.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'billing':p('VIEW','CREATE','EDIT','PRINT','EXPORT'),
        'corporate_billing':p('VIEW','CREATE','EDIT','PRINT','EXPORT'),'insurance':p('VIEW')
    }),
    RoleTemplate('Insurance Officer','Finance','Insurance claims/authorization records and billing coordination.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'billing':p('VIEW'),'insurance':p('VIEW','CREATE','EDIT','VERIFY','PRINT','EXPORT'),
        'corporate_billing':p('VIEW','CREATE','EDIT','PRINT')
    }),
    RoleTemplate('Accountant','Finance','Accounting, billing review and financial reporting.',{
        'billing':p('VIEW','VERIFY','PRINT','EXPORT'),'finance':p('VIEW','CREATE','EDIT','VERIFY','PRINT','EXPORT'),
        'corporate_billing':p('VIEW','VERIFY','PRINT','EXPORT'),'reports':p('VIEW','PRINT','EXPORT'),'procurement':p('VIEW'),'payroll':p('VIEW')
    }),
    RoleTemplate('Finance Manager','Finance','Financial approval, accounting oversight and reporting.',{
        'billing':p('VIEW','VERIFY','APPROVE','PRINT','EXPORT'),'finance':p('VIEW','CREATE','EDIT','VERIFY','APPROVE','PRINT','EXPORT'),
        'corporate_billing':p('VIEW','VERIFY','APPROVE','PRINT','EXPORT'),'insurance':p('VIEW','APPROVE','EXPORT'),
        'procurement':p('VIEW','APPROVE','EXPORT'),'payroll':p('VIEW','APPROVE','EXPORT'),'reports':p('VIEW','PRINT','EXPORT'),'audit':p('VIEW')
    }),

    RoleTemplate('Storekeeper','Inventory & Procurement','Store receipts, issues and stock adjustments.',{
        'inventory':p('VIEW','CREATE','EDIT','PRINT','EXPORT'),'procurement':p('VIEW'),'pharmacy':p('VIEW'),'assets':p('VIEW')
    }),
    RoleTemplate('Procurement Officer','Inventory & Procurement','Procurement requests, supplier processes and purchasing records.',{
        'procurement':p('VIEW','CREATE','EDIT','VERIFY','PRINT','EXPORT'),'inventory':p('VIEW'),'finance':p('VIEW'),'assets':p('VIEW')
    }),
    RoleTemplate('Inventory Manager','Inventory & Procurement','Inventory approvals, stock controls and reporting.',{
        'inventory':p('VIEW','CREATE','EDIT','VERIFY','APPROVE','PRINT','EXPORT'),'procurement':p('VIEW','VERIFY','APPROVE','PRINT','EXPORT'),
        'assets':p('VIEW','PRINT','EXPORT'),'reports':p('VIEW','EXPORT')
    }),

    RoleTemplate('HR Officer','Administration','Human-resource records and staff administration.',{
        'hr':p('VIEW','CREATE','EDIT','VERIFY','PRINT','EXPORT'),'users':p('VIEW'),'payroll':p('VIEW'),'documents':p('VIEW','CREATE','EDIT')
    }),
    RoleTemplate('Payroll Officer','Administration','Payroll preparation and controlled payroll reporting.',{
        'payroll':p('VIEW','CREATE','EDIT','VERIFY','PRINT','EXPORT'),'hr':p('VIEW'),'finance':p('VIEW')
    }),
    RoleTemplate('Auditor','Administration','Read-only operational oversight plus audit/report export.',merge(
        {m.key:p('VIEW') for m in MODULES},
        {'audit':p('VIEW','PRINT','EXPORT'),'reports':p('VIEW','PRINT','EXPORT')}
    )),
    RoleTemplate('Document Officer','Administration','Document registration, maintenance, print and export.',{
        'documents':p('VIEW','CREATE','EDIT','PRINT','EXPORT'),'patients':p('VIEW'),'medical_records':p('VIEW')
    }),
    RoleTemplate('Asset Officer','Administration','Asset register and lifecycle management.',{
        'assets':p('VIEW','CREATE','EDIT','VERIFY','PRINT','EXPORT'),'inventory':p('VIEW'),'procurement':p('VIEW'),'maintenance':p('VIEW')
    }),
    RoleTemplate('Maintenance Officer','Administration','Facility maintenance work records and equipment coordination.',{
        'maintenance':p('VIEW','CREATE','EDIT','VERIFY','PRINT','EXPORT'),'assets':p('VIEW'),'medical_equipment':p('VIEW','CREATE','EDIT')
    }),

    RoleTemplate('Blood Bank Technician','Other Hospital Services','Blood-bank records, verification and stock-related workflow.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'laboratory':p('VIEW'),'blood_bank':p('VIEW','CREATE','EDIT','VERIFY','PRINT','EXPORT')
    }),
    RoleTemplate('Mortuary Attendant','Other Hospital Services','Mortuary admission, release and operational documentation.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'mortuary':p('VIEW','CREATE','EDIT','VERIFY','PRINT')
    }),
    RoleTemplate('Nutritionist / Dietitian','Other Hospital Services','Nutrition assessment, dietetic plans and inpatient coordination.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'nutrition':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),'wards':p('VIEW'),'nursing':p('VIEW')
    }),
    RoleTemplate('Physiotherapist','Other Hospital Services','Physiotherapy assessment and treatment records.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'physiotherapy':p('VIEW','CREATE','EDIT','VERIFY','PRINT')
    }),
    RoleTemplate('Ambulance / EMS Staff','Other Hospital Services','Ambulance dispatch/case records and emergency handoff.',{
        'patients':p('VIEW'),'ambulance':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),'emergency':p('VIEW','CREATE','EDIT'),'triage':p('VIEW','CREATE')
    }),
    RoleTemplate('Biomedical Equipment Technician','Other Hospital Services','Medical equipment service and maintenance records.',{
        'medical_equipment':p('VIEW','CREATE','EDIT','VERIFY','PRINT','EXPORT'),'maintenance':p('VIEW','CREATE','EDIT'),'assets':p('VIEW')
    }),
    RoleTemplate('CSSD Technician','Other Hospital Services','Sterile supply processing and theatre-support documentation.',{
        'cssd':p('VIEW','CREATE','EDIT','VERIFY','PRINT','EXPORT'),'theatre':p('VIEW'),'inventory':p('VIEW')
    }),
    RoleTemplate('Catering / Kitchen Staff','Other Hospital Services','Kitchen/catering service records and diet coordination.',{
        'catering':p('VIEW','CREATE','EDIT','PRINT'),'nutrition':p('VIEW'),'wards':p('VIEW')
    }),
    RoleTemplate('Laundry Staff','Other Hospital Services','Laundry-service operational records.',{
        'laundry':p('VIEW','CREATE','EDIT','PRINT'),'wards':p('VIEW')
    }),

    RoleTemplate('Dental Clinician','Specialty Clinical','Dental clinical records.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'dental':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),'prescriptions':p('VIEW','CREATE')
    }),
    RoleTemplate('Ophthalmology Clinician','Specialty Clinical','Ophthalmology clinical records.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'ophthalmology':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),'prescriptions':p('VIEW','CREATE')
    }),
    RoleTemplate('ENT Clinician','Specialty Clinical','ENT clinical records.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'ent':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),'prescriptions':p('VIEW','CREATE')
    }),
    RoleTemplate('Pediatrician','Specialty Clinical','Pediatric clinical records.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'pediatrics':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),'prescriptions':p('VIEW','CREATE'),'laboratory':p('VIEW','CREATE')
    }),
    RoleTemplate('Mental Health Clinician','Specialty Clinical','Mental-health clinical records.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'mental_health':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),'prescriptions':p('VIEW','CREATE')
    }),
    RoleTemplate('Dialysis Clinician','Specialty Clinical','Dialysis treatment and verification records.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'dialysis':p('VIEW','CREATE','EDIT','VERIFY','PRINT'),'laboratory':p('VIEW')
    }),
    RoleTemplate('Oncologist','Specialty Clinical','Oncology clinical records.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'oncology':p('VIEW','CREATE','EDIT','VERIFY','APPROVE','PRINT'),'prescriptions':p('VIEW','CREATE'),'laboratory':p('VIEW','CREATE'),'radiology':p('VIEW','CREATE')
    }),
    RoleTemplate('Cardiologist','Specialty Clinical','Cardiology clinical records.',{
        'patients':p('VIEW'),'medical_records':p('VIEW'),'cardiology':p('VIEW','CREATE','EDIT','VERIFY','APPROVE','PRINT'),'prescriptions':p('VIEW','CREATE'),'laboratory':p('VIEW','CREATE'),'radiology':p('VIEW','CREATE')
    }),
]

ROLE_TEMPLATE_BY_NAME = {r.name: r for r in ROLE_TEMPLATES}


def template_payload(template: RoleTemplate) -> dict:
    return {
        'name': template.name,
        'category': template.category,
        'description': template.description,
        'permissions': template.permissions,
    }


def validate_role_templates() -> list[str]:
    module_keys = {m.key for m in MODULES}
    errors: list[str] = []
    seen: set[str] = set()
    for role in ROLE_TEMPLATES:
        if role.name in seen:
            errors.append(f'duplicate role template: {role.name}')
        seen.add(role.name)
        for module, actions in role.permissions.items():
            if module not in module_keys:
                errors.append(f'{role.name}: unknown module {module}')
            for action in actions:
                if action not in PERMISSIONS:
                    errors.append(f'{role.name}/{module}: unknown action {action}')
    return errors
