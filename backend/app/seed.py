from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import Hospital, HospitalModule, Role, User, Patient, InventoryItem, Ward, Bed, Appointment, Encounter, Invoice
from .modules import MODULES, preset_enabled
from .roles import ROLE_TEMPLATES, ROLE_TEMPLATE_BY_NAME, validate_role_templates
from .security import hash_password


def ensure_role_templates(db: Session, hospital_id: int) -> dict[str, Role]:
    """Install missing built-in roles without overwriting hospital customisations."""
    errors = validate_role_templates()
    if errors:
        raise RuntimeError('Invalid built-in role templates: ' + '; '.join(errors))
    existing = {r.name: r for r in db.query(Role).filter_by(hospital_id=hospital_id).all()}
    for template in ROLE_TEMPLATES:
        if template.name not in existing:
            role = Role(hospital_id=hospital_id, name=template.name, permissions=template.permissions)
            db.add(role)
            db.flush()
            existing[template.name] = role
    return existing


def ensure_all_hospitals_role_templates(db: Session) -> None:
    changed = False
    for hospital in db.query(Hospital).all():
        before = db.query(Role).filter_by(hospital_id=hospital.id).count()
        ensure_role_templates(db, hospital.id)
        after = db.query(Role).filter_by(hospital_id=hospital.id).count()
        changed = changed or after != before
    if changed:
        db.commit()


def seed(db: Session):
    hospital = db.query(Hospital).first()
    if hospital:
        # Upgrade-safe: existing installations receive only missing built-in roles.
        ensure_all_hospitals_role_templates(db)
        return

    hospital = Hospital(name='One HMS Demo Hospital', facility_type='DISTRICT', address='Tanzania', phone='+255 700 000 000')
    db.add(hospital); db.flush()
    for module in MODULES:
        db.add(HospitalModule(hospital_id=hospital.id,module_key=module.key,enabled=preset_enabled(hospital.facility_type,module)))

    roles = ensure_role_templates(db, hospital.id)
    demos=[
        ('System Administrator','admin@onehms.com','Administrator','Admin123!'),
        ('Dr. Neema Mushi','doctor@onehms.com','Doctor','Demo123!'),
        ('Nurse Asha Said','nurse@onehms.com','Nurse','Demo123!'),
        ('Reception Desk','reception@onehms.com','Receptionist','Demo123!'),
        ('Lab Supervisor','lab@onehms.com','Lab Supervisor','Demo123!'),
        ('Pharmacy Desk','pharmacy@onehms.com','Pharmacist','Demo123!'),
        ('Cashier Desk','cashier@onehms.com','Cashier','Demo123!'),
        ('Theatre Surgeon','surgeon@onehms.com','Surgeon','Demo123!'),
        ('Theatre Nurse','theatre.nurse@onehms.com','Theatre Nurse','Demo123!'),
    ]
    for full,email,role,pwd in demos:
        db.add(User(hospital_id=hospital.id,role_id=roles[role].id,full_name=full,email=email,password_hash=hash_password(pwd)))

    p=Patient(hospital_id=hospital.id,patient_no='P000001',first_name='Amina',last_name='Msuya',sex='Female',phone='+255700000001',address='Tanzania',blood_group='O+',allergies='None recorded',next_of_kin='Hamisi Msuya')
    db.add(p); db.flush()
    inv=InventoryItem(hospital_id=hospital.id,sku='MED-PARA-500',name='Paracetamol 500mg',category='Medicine',quantity=250,reorder_level=50,unit_price=100)
    db.add(inv)
    ward=Ward(hospital_id=hospital.id,name='General Ward',ward_type='GENERAL'); db.add(ward); db.flush()
    db.add_all([Bed(hospital_id=hospital.id,ward_id=ward.id,code='GW-01'),Bed(hospital_id=hospital.id,ward_id=ward.id,code='GW-02')])
    appt=Appointment(hospital_id=hospital.id,patient_id=p.id,scheduled_at=datetime.utcnow()+timedelta(hours=3),department='OPD',clinician='Dr. Neema Mushi',reason='General review')
    db.add(appt)
    enc=Encounter(hospital_id=hospital.id,patient_id=p.id,encounter_type='OPD',chief_complaint='Headache and fever',status='OPEN'); db.add(enc)
    db.add(Invoice(hospital_id=hospital.id,patient_id=p.id,amount=15000,paid_amount=0,description='Consultation'))
    db.commit()
