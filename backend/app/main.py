from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db, SessionLocal
from .models import *
from .modules import MODULES, MODULE_BY_KEY, MODULE_DEPENDENCIES, PERMISSIONS, preset_enabled
from .schemas import *
from .security import verify_password, hash_password, create_access_token, current_user, require, ensure_access
from .seed import seed, ensure_role_templates, ensure_hospital_modules
from .roles import ROLE_TEMPLATES, ROLE_TEMPLATE_BY_NAME, template_payload
from .audit import record

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try: seed(db)
    finally: db.close()
    yield

app = FastAPI(title='One HMS API', version='1.3.1', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(',') if x.strip()], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])


def owned(db, model, item_id, hospital_id, label='Record'):
    item = db.get(model, item_id)
    if not item or getattr(item, 'hospital_id', hospital_id) != hospital_id:
        raise HTTPException(404, f'{label} not found')
    return item

def patient_owned(db, patient_id, hid):
    return owned(db, Patient, patient_id, hid, 'Patient')

def encounter_owned(db, encounter_id, hid):
    return owned(db, Encounter, encounter_id, hid, 'Encounter')

def commit_refresh(db, item):
    db.commit(); db.refresh(item); return item

def module_state_map(db: Session, hospital_id: int) -> dict[str, bool]:
    """Return an authoritative state for every registered module."""
    rows={x.module_key:x.enabled for x in db.query(HospitalModule).filter_by(hospital_id=hospital_id).all()}
    return {m.key:rows.get(m.key,preset_enabled('SMALL',m) if m.core else False) for m in MODULES}

@app.get('/api/health')
def health(): return {'status':'ok','service':'one-hms','version':'1.3.1','port':8082}

@app.post('/api/auth/login', response_model=LoginOut)
def login(data: LoginIn, db: Session=Depends(get_db)):
    user=db.query(User).filter(func.lower(User.email)==data.email.lower()).first()
    if not user or not user.active or not verify_password(data.password,user.password_hash): raise HTTPException(401,'Invalid email or password')
    return LoginOut(access_token=create_access_token(user), user=UserOut.model_validate(user))

@app.get('/api/me')
def me(user:User=Depends(current_user), db:Session=Depends(get_db)):
    hospital=db.get(Hospital,user.hospital_id)
    # Keep upgraded installations aligned with the current registry.
    ensure_hospital_modules(db,hospital); db.commit()
    states=module_state_map(db,user.hospital_id)
    return {'id':user.id,'full_name':user.full_name,'email':user.email,'role':user.role.name,'role_id':user.role_id,
            'hospital':{'id':hospital.id,'name':hospital.name,'facility_type':hospital.facility_type,'address':hospital.address,'phone':hospital.phone},
            'permissions':user.role.permissions or {},'modules':states}

@app.get('/api/dashboard')
def dashboard(user:User=Depends(require('reports','VIEW')), db:Session=Depends(get_db)):
    hid=user.hospital_id; today=datetime.utcnow().date()
    states=module_state_map(db,hid)
    return {'patients':db.query(Patient).filter_by(hospital_id=hid).count(),
            'appointments_today':db.query(Appointment).filter(Appointment.hospital_id==hid,func.date(Appointment.scheduled_at)==today).count(),
            'open_encounters':db.query(Encounter).filter_by(hospital_id=hid,status='OPEN').count(),
            'unpaid_invoices':db.query(Invoice).filter(Invoice.hospital_id==hid,Invoice.status!='PAID').count(),
            'outstanding_amount':float(db.query(func.coalesce(func.sum(Invoice.amount-Invoice.paid_amount),0)).filter(Invoice.hospital_id==hid).scalar() or 0),
            'revenue':float(db.query(func.coalesce(func.sum(Payment.amount),0)).filter(Payment.hospital_id==hid).scalar() or 0),
            'low_stock':db.query(InventoryItem).filter(InventoryItem.hospital_id==hid,InventoryItem.quantity<=InventoryItem.reorder_level).count(),
            'admitted':db.query(Admission).filter_by(hospital_id=hid,status='ADMITTED').count(),
            'enabled_modules':sum(1 for enabled in states.values() if enabled)}

# Hospital + module configuration
@app.get('/api/modules', response_model=list[ModuleOut])
def list_modules(user:User=Depends(current_user), db:Session=Depends(get_db)):
    hospital=db.get(Hospital,user.hospital_id)
    ensure_hospital_modules(db,hospital); db.commit()
    states=module_state_map(db,user.hospital_id)
    return [ModuleOut(key=m.key,name=m.name,group=m.group,core=m.core,enabled=states[m.key]) for m in MODULES]

@app.patch('/api/modules/{module_key}', response_model=ModuleOut)
def toggle_module(module_key:str,data:ModuleToggle,user:User=Depends(require('configuration','EDIT')),db:Session=Depends(get_db)):
    module=MODULE_BY_KEY.get(module_key)
    if not module: raise HTTPException(404,'Module not found')
    if module.core and not data.enabled: raise HTTPException(400,'Core modules cannot be disabled')
    hospital=db.get(Hospital,user.hospital_id)
    rows=ensure_hospital_modules(db,hospital)
    row=rows[module_key]
    if row: row.enabled=data.enabled
    cascaded={}
    if data.enabled:
        # A dependent workflow cannot be switched on while its structural parent
        # remains unavailable.  Enable the required parent atomically.
        for dependency in MODULE_DEPENDENCIES.get(module_key,set()):
            if not rows[dependency].enabled:
                rows[dependency].enabled=True;cascaded[dependency]=True
    else:
        # Disabling a parent switches off dependent workflows in the same commit.
        for child,dependencies in MODULE_DEPENDENCIES.items():
            if module_key in dependencies and rows[child].enabled:
                rows[child].enabled=False;cascaded[child]=False
    record(db,user,'MODULE_TOGGLE','hospital_module',module_key,{'enabled':data.enabled,'cascaded':cascaded}); db.commit()
    return ModuleOut(key=module.key,name=module.name,group=module.group,core=module.core,enabled=row.enabled)

@app.patch('/api/hospital')
def update_hospital(data:FacilityUpdate,user:User=Depends(require('configuration','EDIT')),db:Session=Depends(get_db)):
    h=db.get(Hospital,user.hospital_id)
    if data.name is not None: h.name=data.name
    if data.address is not None: h.address=data.address
    if data.phone is not None: h.phone=data.phone
    if data.facility_type is not None:
        ft=data.facility_type.upper()
        if ft not in {'SMALL','DISTRICT','REFERRAL'}: raise HTTPException(400,'facility_type must be SMALL, DISTRICT or REFERRAL')
        h.facility_type=ft
    if data.apply_preset:
        # Apply the currently selected/saved facility type even when the caller
        # does not resend facility_type.  This makes "Apply preset" a complete,
        # independent configuration action for API clients as well as the UI.
        ft=h.facility_type.upper()
        rows=ensure_hospital_modules(db,h)
        for m in MODULES:
            rows[m.key].enabled=preset_enabled(ft,m)
    record(db,user,'EDIT','hospital',h.id,{'facility_type':h.facility_type}); db.commit(); db.refresh(h)
    return {'id':h.id,'name':h.name,'facility_type':h.facility_type,'address':h.address,'phone':h.phone}

# Reception queue / check-in
@app.get('/api/reception/queue')
def reception_queue(user:User=Depends(require('reception','VIEW')),db:Session=Depends(get_db)):
    hid=user.hospital_id
    appointments=db.query(Appointment).filter_by(hospital_id=hid).order_by(Appointment.scheduled_at.asc()).limit(200).all()
    patients={p.id:p for p in db.query(Patient).filter(Patient.hospital_id==hid, Patient.id.in_([a.patient_id for a in appointments] or [-1])).all()}
    return [{'id':a.id,'patient_id':a.patient_id,'patient_name':f"{patients[a.patient_id].first_name} {patients[a.patient_id].last_name}" if a.patient_id in patients else f'#{a.patient_id}','patient_no':patients[a.patient_id].patient_no if a.patient_id in patients else None,'scheduled_at':a.scheduled_at,'department':a.department,'clinician':a.clinician,'reason':a.reason,'status':a.status} for a in appointments]

@app.post('/api/reception/check-in/{appointment_id}', response_model=AppointmentOut)
def reception_check_in(appointment_id:int,user:User=Depends(require('reception','EDIT')),db:Session=Depends(get_db)):
    item=owned(db,Appointment,appointment_id,user.hospital_id,'Appointment')
    if item.status in {'COMPLETED','CANCELLED','NO_SHOW'}: raise HTTPException(400,f'Cannot check in appointment with status {item.status}')
    item.status='ARRIVED'; record(db,user,'CHECK_IN','appointment',item.id); return commit_refresh(db,item)

# Roles and users
@app.get('/api/role-templates', response_model=list[RoleTemplateOut])
def role_templates(user:User=Depends(require('users','VIEW'))):
    return [RoleTemplateOut(**template_payload(t)) for t in ROLE_TEMPLATES]

@app.post('/api/role-templates/install')
def install_role_templates(user:User=Depends(require('users','CREATE')),db:Session=Depends(get_db)):
    before={r.name for r in db.query(Role).filter_by(hospital_id=user.hospital_id).all()}
    roles=ensure_role_templates(db,user.hospital_id)
    db.commit()
    installed=sorted(set(roles)-before)
    record(db,user,'INSTALL_ROLE_TEMPLATES','role',None,{'installed':installed}); db.commit()
    return {'installed':installed,'installed_count':len(installed),'total_templates':len(ROLE_TEMPLATES)}

@app.post('/api/roles/{role_id}/reset-template', response_model=RoleOut)
def reset_role_template(role_id:int,user:User=Depends(require('users','EDIT')),db:Session=Depends(get_db)):
    item=owned(db,Role,role_id,user.hospital_id,'Role')
    template=ROLE_TEMPLATE_BY_NAME.get(item.name)
    if not template: raise HTTPException(400,'Role is not a built-in template')
    item.permissions=template.permissions
    record(db,user,'RESET_ROLE_TEMPLATE','role',item.id,{'template':item.name})
    return commit_refresh(db,item)

@app.get('/api/roles', response_model=list[RoleOut])
def roles(user:User=Depends(require('users','VIEW')),db:Session=Depends(get_db)):
    return db.query(Role).filter_by(hospital_id=user.hospital_id).order_by(Role.name).all()

@app.post('/api/roles', response_model=RoleOut)
def create_role(data:RoleIn,user:User=Depends(require('users','CREATE')),db:Session=Depends(get_db)):
    clean={k:[p for p in v if p in PERMISSIONS or p=='*'] for k,v in data.permissions.items() if k in MODULE_BY_KEY}
    item=Role(hospital_id=user.hospital_id,name=data.name,permissions=clean); db.add(item)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409,'Role name already exists')
    record(db,user,'CREATE','role',item.id); return commit_refresh(db,item)

@app.patch('/api/roles/{role_id}', response_model=RoleOut)
def update_role(role_id:int,data:RoleUpdate,user:User=Depends(require('users','EDIT')),db:Session=Depends(get_db)):
    item=owned(db,Role,role_id,user.hospital_id,'Role')
    if data.name is not None: item.name=data.name
    if data.permissions is not None: item.permissions={k:[p for p in v if p in PERMISSIONS or p=='*'] for k,v in data.permissions.items() if k in MODULE_BY_KEY}
    record(db,user,'EDIT','role',item.id)
    try: return commit_refresh(db,item)
    except IntegrityError: db.rollback(); raise HTTPException(409,'Role name already exists')

@app.get('/api/users', response_model=list[UserAdminOut])
def users(user:User=Depends(require('users','VIEW')),db:Session=Depends(get_db)):
    return db.query(User).filter_by(hospital_id=user.hospital_id).order_by(User.full_name).all()

@app.post('/api/users', response_model=UserAdminOut)
def create_user(data:UserIn,user:User=Depends(require('users','CREATE')),db:Session=Depends(get_db)):
    role=owned(db,Role,data.role_id,user.hospital_id,'Role')
    item=User(hospital_id=user.hospital_id,role_id=role.id,full_name=data.full_name,email=data.email.lower(),password_hash=hash_password(data.password),active=True); db.add(item)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409,'Email already exists')
    record(db,user,'CREATE','user',item.id); return commit_refresh(db,item)

@app.patch('/api/users/{user_id}', response_model=UserAdminOut)
def update_user(user_id:int,data:UserUpdate,user:User=Depends(require('users','EDIT')),db:Session=Depends(get_db)):
    item=owned(db,User,user_id,user.hospital_id,'User')
    if data.full_name is not None:item.full_name=data.full_name
    if data.role_id is not None: owned(db,Role,data.role_id,user.hospital_id,'Role'); item.role_id=data.role_id
    if data.active is not None:
        if item.id==user.id and not data.active: raise HTTPException(400,'You cannot deactivate your own account')
        item.active=data.active
    if data.password: item.password_hash=hash_password(data.password)
    record(db,user,'EDIT','user',item.id); return commit_refresh(db,item)

# Patients
@app.get('/api/patients', response_model=list[PatientOut])
def patients(q:str|None=None,user:User=Depends(require('patients','VIEW')),db:Session=Depends(get_db)):
    query=db.query(Patient).filter_by(hospital_id=user.hospital_id)
    if q:
        s=f'%{q}%'; query=query.filter((Patient.patient_no.ilike(s))|(Patient.first_name.ilike(s))|(Patient.last_name.ilike(s))|(Patient.phone.ilike(s)))
    return query.order_by(Patient.id.desc()).all()

@app.post('/api/patients', response_model=PatientOut)
def create_patient(data:PatientIn,user:User=Depends(require('patients','CREATE')),db:Session=Depends(get_db)):
    next_no=(db.query(func.max(Patient.id)).scalar() or 0)+1
    item=Patient(hospital_id=user.hospital_id,patient_no=f'P{next_no:06d}',**data.model_dump()); db.add(item); db.flush(); record(db,user,'CREATE','patient',item.id); return commit_refresh(db,item)

@app.get('/api/patients/{patient_id}')
def patient_detail(patient_id:int,user:User=Depends(require('medical_records','VIEW')),db:Session=Depends(get_db)):
    p=patient_owned(db,patient_id,user.hospital_id)
    return {'patient':PatientOut.model_validate(p),'appointments':[AppointmentOut.model_validate(x) for x in db.query(Appointment).filter_by(hospital_id=user.hospital_id,patient_id=p.id).order_by(Appointment.id.desc()).limit(20)],'encounters':[EncounterOut.model_validate(x) for x in db.query(Encounter).filter_by(hospital_id=user.hospital_id,patient_id=p.id).order_by(Encounter.id.desc()).limit(20)],'invoices':[InvoiceOut.model_validate(x) for x in db.query(Invoice).filter_by(hospital_id=user.hospital_id,patient_id=p.id).order_by(Invoice.id.desc()).limit(20)]}

@app.patch('/api/patients/{patient_id}',response_model=PatientOut)
def update_patient(patient_id:int,data:PatientUpdate,user:User=Depends(require('patients','EDIT')),db:Session=Depends(get_db)):
    item=patient_owned(db,patient_id,user.hospital_id)
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(item,k,v)
    record(db,user,'EDIT','patient',item.id); return commit_refresh(db,item)

# Appointments
@app.get('/api/appointments',response_model=list[AppointmentOut])
def appointments(user:User=Depends(require('appointments','VIEW')),db:Session=Depends(get_db)):
    return db.query(Appointment).filter_by(hospital_id=user.hospital_id).order_by(Appointment.scheduled_at.desc()).all()

@app.post('/api/appointments',response_model=AppointmentOut)
def create_appointment(data:AppointmentIn,user:User=Depends(require('appointments','CREATE')),db:Session=Depends(get_db)):
    patient_owned(db,data.patient_id,user.hospital_id); item=Appointment(hospital_id=user.hospital_id,**data.model_dump()); db.add(item); db.flush(); record(db,user,'CREATE','appointment',item.id); return commit_refresh(db,item)

@app.patch('/api/appointments/{appointment_id}/status',response_model=AppointmentOut)
def appointment_status(appointment_id:int,data:StatusIn,user:User=Depends(require('appointments','EDIT')),db:Session=Depends(get_db)):
    item=owned(db,Appointment,appointment_id,user.hospital_id,'Appointment'); status=data.status.upper()
    if status not in {'BOOKED','ARRIVED','COMPLETED','CANCELLED','NO_SHOW'}: raise HTTPException(400,'Invalid appointment status')
    item.status=status; record(db,user,'EDIT','appointment',item.id,{'status':item.status}); return commit_refresh(db,item)

# Encounters, triage, consultation
@app.get('/api/encounters',response_model=list[EncounterOut])
def encounters(user:User=Depends(require('opd','VIEW')),db:Session=Depends(get_db)):
    return db.query(Encounter).filter_by(hospital_id=user.hospital_id).order_by(Encounter.id.desc()).all()

@app.post('/api/encounters',response_model=EncounterOut)
def create_encounter(data:EncounterIn,user:User=Depends(require('opd','CREATE')),db:Session=Depends(get_db)):
    patient_owned(db,data.patient_id,user.hospital_id)
    if data.appointment_id:
        appt=owned(db,Appointment,data.appointment_id,user.hospital_id,'Appointment')
        if appt.patient_id != data.patient_id: raise HTTPException(400,'Appointment belongs to a different patient')
        appt.status='ARRIVED'
    item=Encounter(hospital_id=user.hospital_id,**data.model_dump()); db.add(item); db.flush(); record(db,user,'CREATE','encounter',item.id); return commit_refresh(db,item)

@app.get('/api/encounters/{encounter_id}')
def encounter_detail(encounter_id:int,user:User=Depends(require('opd','VIEW')),db:Session=Depends(get_db)):
    e=encounter_owned(db,encounter_id,user.hospital_id); p=patient_owned(db,e.patient_id,user.hospital_id)
    return {'encounter':EncounterOut.model_validate(e),'patient':PatientOut.model_validate(p),
            'vitals':[VitalOut.model_validate(x) for x in db.query(Vital).filter_by(encounter_id=e.id).order_by(Vital.id.desc())],
            'labs':[LabOrderOut.model_validate(x) for x in db.query(LabOrder).filter_by(hospital_id=user.hospital_id,encounter_id=e.id).order_by(LabOrder.id.desc())],
            'prescriptions':[PrescriptionOut.model_validate(x) for x in db.query(Prescription).filter_by(hospital_id=user.hospital_id,encounter_id=e.id).order_by(Prescription.id.desc())]}

@app.post('/api/vitals',response_model=VitalOut)
def create_vitals(data:VitalIn,user:User=Depends(require('triage','CREATE')),db:Session=Depends(get_db)):
    encounter_owned(db,data.encounter_id,user.hospital_id); item=Vital(**data.model_dump()); db.add(item); db.flush(); record(db,user,'CREATE','vitals',item.id); return commit_refresh(db,item)

@app.patch('/api/encounters/{encounter_id}/consultation',response_model=EncounterOut)
def consultation(encounter_id:int,data:ConsultationUpdate,user:User=Depends(require('consultation','EDIT')),db:Session=Depends(get_db)):
    item=encounter_owned(db,encounter_id,user.hospital_id); ensure_access(user,db,'diagnosis','EDIT'); status=data.status.upper()
    if status not in {'OPEN','COMPLETED','REFERRED'}: raise HTTPException(400,'Invalid encounter status')
    item.clinical_notes=data.clinical_notes; item.diagnosis=data.diagnosis; item.status=status; record(db,user,'EDIT','consultation',item.id); return commit_refresh(db,item)

# Laboratory
@app.get('/api/lab-orders',response_model=list[LabOrderOut])
def lab_orders(user:User=Depends(require('laboratory','VIEW')),db:Session=Depends(get_db)):
    return db.query(LabOrder).filter_by(hospital_id=user.hospital_id).order_by(LabOrder.id.desc()).all()

@app.post('/api/lab-orders',response_model=LabOrderOut)
def create_lab(data:LabOrderIn,user:User=Depends(require('laboratory','CREATE')),db:Session=Depends(get_db)):
    encounter_owned(db,data.encounter_id,user.hospital_id); item=LabOrder(hospital_id=user.hospital_id,**data.model_dump()); db.add(item); db.flush(); record(db,user,'CREATE','lab_order',item.id); return commit_refresh(db,item)

@app.patch('/api/lab-orders/{order_id}/result',response_model=LabOrderOut)
def lab_result(order_id:int,data:LabResultIn,user:User=Depends(require('laboratory','EDIT')),db:Session=Depends(get_db)):
    item=owned(db,LabOrder,order_id,user.hospital_id,'Lab order')
    if data.verified: ensure_access(user,db,'laboratory','VERIFY')
    item.result=data.result; item.verified=data.verified; item.status='VERIFIED' if data.verified else 'RESULTED'; record(db,user,'RESULT','lab_order',item.id,{'verified':data.verified}); return commit_refresh(db,item)

@app.patch('/api/lab-orders/{order_id}/verify',response_model=LabOrderOut)
def verify_lab(order_id:int,user:User=Depends(require('laboratory','VERIFY')),db:Session=Depends(get_db)):
    item=owned(db,LabOrder,order_id,user.hospital_id,'Lab order')
    if not item.result: raise HTTPException(400,'Enter a result before verification')
    item.verified=True; item.status='VERIFIED'; record(db,user,'VERIFY','lab_order',item.id); return commit_refresh(db,item)

@app.post('/api/lab-orders/{order_id}/approve',response_model=LabOrderOut)
def approve_lab(order_id:int,user:User=Depends(require('laboratory','APPROVE')),db:Session=Depends(get_db)):
    item=owned(db,LabOrder,order_id,user.hospital_id,'Lab order')
    if not item.verified: raise HTTPException(400,'Verify the result before approval')
    item.approved=True; item.approved_at=datetime.utcnow(); item.status='APPROVED'; record(db,user,'APPROVE','lab_order',item.id); return commit_refresh(db,item)

@app.get('/api/lab-orders/{order_id}/print',response_class=HTMLResponse)
def print_lab(order_id:int,user:User=Depends(require('laboratory','PRINT')),db:Session=Depends(get_db)):
    item=owned(db,LabOrder,order_id,user.hospital_id,'Lab order')
    enc=encounter_owned(db,item.encounter_id,user.hospital_id); patient=patient_owned(db,enc.patient_id,user.hospital_id)
    record(db,user,'PRINT','lab_order',item.id); db.commit()
    return HTMLResponse(f"<!doctype html><html><head><title>Lab result #{item.id}</title></head><body><h1>Laboratory Result</h1><p>Patient: {patient.patient_no} - {patient.first_name} {patient.last_name}</p><p>Test: {item.test_name}</p><p>Result: {item.result or 'Pending'}</p><p>Verified: {item.verified} | Approved: {item.approved}</p></body></html>")

@app.get('/api/laboratory/export.csv',response_class=PlainTextResponse)
def export_laboratory(user:User=Depends(require('laboratory','EXPORT')),db:Session=Depends(get_db)):
    import csv, io
    rows=db.query(LabOrder).filter_by(hospital_id=user.hospital_id).order_by(LabOrder.id).all()
    out=io.StringIO(); w=csv.writer(out); w.writerow(['id','encounter_id','test_name','status','result','verified','approved','created_at'])
    for x in rows: w.writerow([x.id,x.encounter_id,x.test_name,x.status,x.result or '',x.verified,x.approved,x.created_at.isoformat()])
    record(db,user,'EXPORT','laboratory',None,{'rows':len(rows)}); db.commit()
    return PlainTextResponse(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=laboratory-results.csv'})

# Prescription + pharmacy
@app.get('/api/prescriptions',response_model=list[PrescriptionOut])
def prescriptions(user:User=Depends(require('prescriptions','VIEW')),db:Session=Depends(get_db)):
    return db.query(Prescription).filter_by(hospital_id=user.hospital_id).order_by(Prescription.id.desc()).all()

@app.post('/api/prescriptions',response_model=PrescriptionOut)
def create_prescription(data:PrescriptionIn,user:User=Depends(require('prescriptions','CREATE')),db:Session=Depends(get_db)):
    encounter_owned(db,data.encounter_id,user.hospital_id)
    if data.inventory_item_id: owned(db,InventoryItem,data.inventory_item_id,user.hospital_id,'Inventory item')
    item=Prescription(hospital_id=user.hospital_id,**data.model_dump()); db.add(item); db.flush(); record(db,user,'CREATE','prescription',item.id); return commit_refresh(db,item)

@app.patch('/api/prescriptions/{prescription_id}/dispense',response_model=PrescriptionOut)
def dispense(prescription_id:int,user:User=Depends(require('pharmacy','EDIT')),db:Session=Depends(get_db)):
    item=owned(db,Prescription,prescription_id,user.hospital_id,'Prescription')
    if item.status=='DISPENSED': raise HTTPException(400,'Already dispensed')
    stock=None
    if item.inventory_item_id: stock=owned(db,InventoryItem,item.inventory_item_id,user.hospital_id,'Inventory item')
    else: stock=db.query(InventoryItem).filter(InventoryItem.hospital_id==user.hospital_id,func.lower(InventoryItem.name)==item.medicine.lower()).first()
    if not stock: raise HTTPException(400,'Link this prescription to an inventory medicine before dispensing')
    if stock.quantity<item.quantity: raise HTTPException(400,f'Insufficient stock. Available: {stock.quantity}')
    stock.quantity-=item.quantity; item.status='DISPENSED'; item.dispensed_at=datetime.utcnow(); db.add(StockTransaction(hospital_id=user.hospital_id,item_id=stock.id,delta=-item.quantity,reason=f'Dispensed prescription #{item.id}',user_id=user.id)); record(db,user,'DISPENSE','prescription',item.id,{'quantity':item.quantity,'stock_id':stock.id}); return commit_refresh(db,item)

# Billing and payments
@app.get('/api/invoices',response_model=list[InvoiceOut])
def invoices(user:User=Depends(require('billing','VIEW')),db:Session=Depends(get_db)):
    return db.query(Invoice).filter_by(hospital_id=user.hospital_id).order_by(Invoice.id.desc()).all()

@app.post('/api/invoices',response_model=InvoiceOut)
def create_invoice(data:InvoiceIn,user:User=Depends(require('billing','CREATE')),db:Session=Depends(get_db)):
    patient_owned(db,data.patient_id,user.hospital_id); item=Invoice(hospital_id=user.hospital_id,**data.model_dump()); db.add(item); db.flush(); record(db,user,'CREATE','invoice',item.id); return commit_refresh(db,item)

@app.post('/api/invoices/{invoice_id}/payments',response_model=PaymentOut)
def pay_invoice(invoice_id:int,data:PaymentIn,user:User=Depends(require('billing','EDIT')),db:Session=Depends(get_db)):
    inv=owned(db,Invoice,invoice_id,user.hospital_id,'Invoice'); due=round(inv.amount-inv.paid_amount,2)
    method=data.method.upper()
    if method not in {'CASH','CARD','MOBILE_MONEY','BANK','INSURANCE'}: raise HTTPException(400,'Invalid payment method')
    if due<=0: raise HTTPException(400,'Invoice is already paid')
    if data.amount>due+0.0001: raise HTTPException(400,f'Payment exceeds balance of {due}')
    p=Payment(hospital_id=user.hospital_id,invoice_id=inv.id,amount=data.amount,method=method,reference=data.reference,received_by=user.id); db.add(p); db.flush(); inv.paid_amount=round(inv.paid_amount+data.amount,2); inv.status='PAID' if inv.paid_amount>=inv.amount else 'PARTIAL'; record(db,user,'PAY','invoice',inv.id,{'amount':data.amount,'method':p.method}); db.commit(); db.refresh(p); return p

@app.get('/api/invoices/{invoice_id}/payments',response_model=list[PaymentOut])
def invoice_payments(invoice_id:int,user:User=Depends(require('billing','VIEW')),db:Session=Depends(get_db)):
    owned(db,Invoice,invoice_id,user.hospital_id,'Invoice'); return db.query(Payment).filter_by(hospital_id=user.hospital_id,invoice_id=invoice_id).order_by(Payment.id.desc()).all()

# Inventory
@app.get('/api/inventory',response_model=list[InventoryOut])
def inventory(user:User=Depends(require('inventory','VIEW')),db:Session=Depends(get_db)):
    return db.query(InventoryItem).filter_by(hospital_id=user.hospital_id).order_by(InventoryItem.name).all()

@app.post('/api/inventory',response_model=InventoryOut)
def create_inventory(data:InventoryIn,user:User=Depends(require('inventory','CREATE')),db:Session=Depends(get_db)):
    item=InventoryItem(hospital_id=user.hospital_id,**data.model_dump()); db.add(item)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409,'SKU already exists')
    if item.quantity: db.add(StockTransaction(hospital_id=user.hospital_id,item_id=item.id,delta=item.quantity,reason='Opening stock',user_id=user.id))
    record(db,user,'CREATE','inventory',item.id); return commit_refresh(db,item)

@app.post('/api/inventory/{item_id}/adjust',response_model=InventoryOut)
def adjust_inventory(item_id:int,data:StockAdjustIn,user:User=Depends(require('inventory','EDIT')),db:Session=Depends(get_db)):
    item=owned(db,InventoryItem,item_id,user.hospital_id,'Inventory item')
    if item.quantity+data.delta<0: raise HTTPException(400,'Adjustment would make stock negative')
    item.quantity+=data.delta; db.add(StockTransaction(hospital_id=user.hospital_id,item_id=item.id,delta=data.delta,reason=data.reason,user_id=user.id)); record(db,user,'STOCK_ADJUST','inventory',item.id,{'delta':data.delta,'reason':data.reason}); return commit_refresh(db,item)

@app.get('/api/inventory/{item_id}/transactions')
def stock_transactions(item_id:int,user:User=Depends(require('inventory','VIEW')),db:Session=Depends(get_db)):
    owned(db,InventoryItem,item_id,user.hospital_id,'Inventory item'); rows=db.query(StockTransaction).filter_by(hospital_id=user.hospital_id,item_id=item_id).order_by(StockTransaction.id.desc()).all(); return [{'id':x.id,'delta':x.delta,'reason':x.reason,'user_id':x.user_id,'created_at':x.created_at} for x in rows]

# Inpatient / bed management
@app.get('/api/wards',response_model=list[WardOut])
def wards(user:User=Depends(require('wards','VIEW')),db:Session=Depends(get_db)):
    return db.query(Ward).filter_by(hospital_id=user.hospital_id).order_by(Ward.name).all()

@app.post('/api/wards',response_model=WardOut)
def create_ward(data:WardIn,user:User=Depends(require('wards','CREATE')),db:Session=Depends(get_db)):
    item=Ward(hospital_id=user.hospital_id,**data.model_dump()); db.add(item); db.flush(); record(db,user,'CREATE','ward',item.id); return commit_refresh(db,item)

@app.get('/api/beds',response_model=list[BedOut])
def beds(user:User=Depends(require('beds','VIEW')),db:Session=Depends(get_db)):
    return db.query(Bed).filter_by(hospital_id=user.hospital_id).order_by(Bed.code).all()

@app.post('/api/beds',response_model=BedOut)
def create_bed(data:BedIn,user:User=Depends(require('beds','CREATE')),db:Session=Depends(get_db)):
    owned(db,Ward,data.ward_id,user.hospital_id,'Ward'); item=Bed(hospital_id=user.hospital_id,**data.model_dump()); db.add(item)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409,'Bed code already exists')
    record(db,user,'CREATE','bed',item.id); return commit_refresh(db,item)

@app.get('/api/admissions',response_model=list[AdmissionOut])
def admissions(user:User=Depends(require('wards','VIEW')),db:Session=Depends(get_db)):
    return db.query(Admission).filter_by(hospital_id=user.hospital_id).order_by(Admission.id.desc()).all()

@app.post('/api/admissions',response_model=AdmissionOut)
def admit(data:AdmissionIn,user:User=Depends(require('wards','CREATE')),db:Session=Depends(get_db)):
    patient_owned(db,data.patient_id,user.hospital_id); ward=owned(db,Ward,data.ward_id,user.hospital_id,'Ward'); bed=owned(db,Bed,data.bed_id,user.hospital_id,'Bed')
    ensure_access(user,db,'beds','EDIT')
    if bed.ward_id!=ward.id: raise HTTPException(400,'Bed does not belong to selected ward')
    if bed.status!='AVAILABLE': raise HTTPException(400,'Bed is not available')
    if data.encounter_id:
        enc=encounter_owned(db,data.encounter_id,user.hospital_id)
        if enc.patient_id != data.patient_id: raise HTTPException(400,'Encounter belongs to a different patient')
    item=Admission(hospital_id=user.hospital_id,**data.model_dump()); bed.status='OCCUPIED'; db.add(item); db.flush(); record(db,user,'ADMIT','admission',item.id,{'bed_id':bed.id}); return commit_refresh(db,item)

@app.patch('/api/admissions/{admission_id}/discharge',response_model=AdmissionOut)
def discharge(admission_id:int,user:User=Depends(require('wards','EDIT')),db:Session=Depends(get_db)):
    item=owned(db,Admission,admission_id,user.hospital_id,'Admission')
    if item.status!='ADMITTED': raise HTTPException(400,'Patient is not currently admitted')
    ensure_access(user,db,'beds','EDIT'); bed=owned(db,Bed,item.bed_id,user.hospital_id,'Bed'); bed.status='AVAILABLE'; item.status='DISCHARGED'; item.discharged_at=datetime.utcnow(); record(db,user,'DISCHARGE','admission',item.id,{'bed_id':bed.id}); return commit_refresh(db,item)

# Generic operational records for every configurable specialist module.
def specialist_module(module_key: str):
    module=MODULE_BY_KEY.get(module_key)
    if not module: raise HTTPException(404,'Unknown module')
    if module.core or module_key in {'wards','beds'}: raise HTTPException(400,'Use the dedicated workflow for this module')
    return module

@app.get('/api/operations/{module_key}',response_model=list[ServiceRecordOut])
def operation_list(module_key:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    specialist_module(module_key); ensure_access(user,db,module_key,'VIEW')
    return db.query(ServiceRecord).filter_by(hospital_id=user.hospital_id,module_key=module_key).order_by(ServiceRecord.id.desc()).all()

@app.post('/api/operations/{module_key}',response_model=ServiceRecordOut)
def operation_create(module_key:str,data:ServiceRecordIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    specialist_module(module_key); ensure_access(user,db,module_key,'CREATE')
    if data.patient_id: patient_owned(db,data.patient_id,user.hospital_id)
    item=ServiceRecord(hospital_id=user.hospital_id,module_key=module_key,**data.model_dump()); db.add(item); db.flush(); record(db,user,'CREATE',module_key,item.id); return commit_refresh(db,item)

@app.patch('/api/operations/{module_key}/{record_id}',response_model=ServiceRecordOut)
def operation_update(module_key:str,record_id:int,data:ServiceRecordUpdate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    specialist_module(module_key); ensure_access(user,db,module_key,'EDIT'); item=owned(db,ServiceRecord,record_id,user.hospital_id,'Service record')
    if item.module_key!=module_key: raise HTTPException(404,'Service record not found')
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(item,k,v)
    record(db,user,'EDIT',module_key,item.id); return commit_refresh(db,item)

@app.delete('/api/operations/{module_key}/{record_id}')
def operation_delete(module_key:str,record_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    specialist_module(module_key); ensure_access(user,db,module_key,'DELETE'); item=owned(db,ServiceRecord,record_id,user.hospital_id,'Service record')
    if item.module_key!=module_key: raise HTTPException(404,'Service record not found')
    rid=item.id; db.delete(item); record(db,user,'DELETE',module_key,rid); db.commit(); return {'deleted':True,'id':rid}

@app.post('/api/operations/{module_key}/{record_id}/approve',response_model=ServiceRecordOut)
def operation_approve(module_key:str,record_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    specialist_module(module_key); ensure_access(user,db,module_key,'APPROVE'); item=owned(db,ServiceRecord,record_id,user.hospital_id,'Service record')
    if item.module_key!=module_key: raise HTTPException(404,'Service record not found')
    item.approved=True; item.approved_at=datetime.utcnow(); record(db,user,'APPROVE',module_key,item.id); return commit_refresh(db,item)

@app.post('/api/operations/{module_key}/{record_id}/verify',response_model=ServiceRecordOut)
def operation_verify(module_key:str,record_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    specialist_module(module_key); ensure_access(user,db,module_key,'VERIFY'); item=owned(db,ServiceRecord,record_id,user.hospital_id,'Service record')
    if item.module_key!=module_key: raise HTTPException(404,'Service record not found')
    item.verified=True; item.verified_at=datetime.utcnow(); record(db,user,'VERIFY',module_key,item.id); return commit_refresh(db,item)

@app.get('/api/operations/{module_key}/{record_id}/print',response_class=HTMLResponse)
def operation_print(module_key:str,record_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    module=specialist_module(module_key); ensure_access(user,db,module_key,'PRINT'); item=owned(db,ServiceRecord,record_id,user.hospital_id,'Service record')
    if item.module_key!=module_key: raise HTTPException(404,'Service record not found')
    patient=patient_owned(db,item.patient_id,user.hospital_id) if item.patient_id else None
    record(db,user,'PRINT',module_key,item.id); db.commit()
    return HTMLResponse(f"<!doctype html><html><head><title>{module.name} record #{item.id}</title></head><body><h1>{module.name}</h1><h2>{item.title}</h2><p>Status: {item.status}</p><p>Patient: {patient.patient_no + ' - ' + patient.first_name + ' ' + patient.last_name if patient else 'Not linked'}</p><pre>{item.details}</pre><p>Approved: {item.approved} | Verified: {item.verified}</p></body></html>")

@app.get('/api/operations/{module_key}/actions/export',response_class=PlainTextResponse)
def operation_export(module_key:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    specialist_module(module_key); ensure_access(user,db,module_key,'EXPORT')
    rows=db.query(ServiceRecord).filter_by(hospital_id=user.hospital_id,module_key=module_key).order_by(ServiceRecord.id).all()
    import csv, io, json
    out=io.StringIO(); w=csv.writer(out); w.writerow(['id','patient_id','title','status','approved','verified','details','created_at'])
    for x in rows: w.writerow([x.id,x.patient_id or '',x.title,x.status,x.approved,x.verified,json.dumps(x.details,ensure_ascii=False),x.created_at.isoformat()])
    record(db,user,'EXPORT',module_key,None,{'rows':len(rows)}); db.commit()
    return PlainTextResponse(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename={module_key}-records.csv'})

# Reports + audit
@app.get('/api/reports/summary')
def report_summary(user:User=Depends(require('reports','VIEW')),db:Session=Depends(get_db)):
    hid=user.hospital_id
    by_status={s:int(c) for s,c in db.query(Invoice.status,func.count(Invoice.id)).filter_by(hospital_id=hid).group_by(Invoice.status).all()}
    top_stock=[{'name':x.name,'quantity':x.quantity,'reorder_level':x.reorder_level} for x in db.query(InventoryItem).filter_by(hospital_id=hid).order_by(InventoryItem.quantity.asc()).limit(10)]
    return {'billing_status':by_status,'revenue':float(db.query(func.coalesce(func.sum(Payment.amount),0)).filter_by(hospital_id=hid).scalar() or 0),'patients':db.query(Patient).filter_by(hospital_id=hid).count(),'encounters':db.query(Encounter).filter_by(hospital_id=hid).count(),'lab_orders':db.query(LabOrder).filter_by(hospital_id=hid).count(),'low_stock_items':top_stock}

@app.get('/api/audit')
def audit(user:User=Depends(require('audit','VIEW')),db:Session=Depends(get_db)):
    rows=db.query(AuditLog).filter_by(hospital_id=user.hospital_id).order_by(AuditLog.id.desc()).limit(250).all(); return [{'id':x.id,'user_id':x.user_id,'action':x.action,'entity':x.entity,'entity_id':x.entity_id,'details':x.details,'created_at':x.created_at} for x in rows]


WEB_DIR = Path(__file__).resolve().parent.parent / 'web'
if WEB_DIR.exists():
    app.mount('/static', StaticFiles(directory=str(WEB_DIR)), name='static')

    @app.get('/', include_in_schema=False)
    def web_app():
        return FileResponse(str(WEB_DIR / 'index.html'))
