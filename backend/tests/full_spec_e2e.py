import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

TEST_DB = Path(__file__).resolve().parent / 'full_spec_e2e.db'
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB}'
os.environ['JWT_SECRET'] = 'full-spec-e2e-secret-that-is-longer-than-thirty-two-bytes'
if TEST_DB.exists():
    TEST_DB.unlink()

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Hospital, HospitalModule, Role, User, Patient, Appointment, InventoryItem, Ward, Bed
from app.modules import MODULES, PERMISSIONS, preset_enabled
from app.security import hash_password

EXPECTED_CORE = {
    'patients','medical_records','reception','appointments','opd','triage','consultation','diagnosis',
    'prescriptions','pharmacy','laboratory','billing','inventory','reports','users','audit','configuration'
}
EXPECTED_OPTIONAL = {
    'radiology','nursing','wards','beds','maternity','theatre','icu','emergency','ambulance','dental',
    'physiotherapy','ophthalmology','ent','pediatrics','mental_health','dialysis','oncology','cardiology',
    'specialized_clinics','insurance','corporate_billing','finance','procurement','hr','payroll','assets',
    'maintenance','documents','mortuary','blood_bank','nutrition','laundry','catering','cssd','medical_equipment'
}
EXPECTED_DISTRICT = {'radiology','nursing','wards','beds','maternity','emergency','insurance'}
EXPECTED_PERMISSIONS = {'VIEW','CREATE','EDIT','DELETE','APPROVE','VERIFY','PRINT','EXPORT'}

results=[]
state={}

def add_result(category, name, ok, detail=''):
    results.append({'category':category,'name':name,'status':'PASS' if ok else 'FAIL','detail':str(detail)[:500]})
    if not ok:
        print(f'FAIL [{category}] {name}: {detail}')

def case(category, name, fn):
    try:
        fn()
        add_result(category,name,True)
    except Exception as exc:
        add_result(category,name,False,exc)

def expect_status(resp, expected, context=''):
    assert resp.status_code == expected, f'{context} expected {expected}, got {resp.status_code}: {resp.text}'
    return resp

def j(resp, expected=200, context=''):
    expect_status(resp,expected,context)
    return resp.json()

def auth(token): return {'Authorization':f'Bearer {token}'}

def run():
    with TestClient(app) as c:
        # --- Auth/platform ---
        case('Platform','Health endpoint',lambda: expect_status(c.get('/api/health'),200))
        case('Platform','Web UI root served',lambda: ('NEOVAM HMS' in expect_status(c.get('/'),200).text) or (_ for _ in ()).throw(AssertionError('NEOVAM HMS missing from UI')))
        case('Platform','Browser JavaScript asset is served',lambda: assert_true('pages.dashboard' in expect_status(c.get('/static/app.js'),200).text,'app.js not served'))
        case('Platform','Browser stylesheet asset is served',lambda: assert_true(len(expect_status(c.get('/static/styles.css'),200).text)>100,'styles.css not served'))
        login=j(c.post('/api/auth/login',json={'email':'admin@onehms.com','password':'Admin123!'}),200,'admin login')
        H=auth(login['access_token']); state['H']=H
        case('Authentication','Admin login succeeds',lambda: None)
        case('Authentication','Bad password rejected',lambda: expect_status(c.post('/api/auth/login',json={'email':'admin@onehms.com','password':'wrong'}),401))
        case('Authentication','Protected endpoint rejects missing token',lambda: expect_status(c.get('/api/me'),401))
        case('Authentication','Current user returns hospital, role, permissions and modules',lambda: (
            (lambda m: (assert_keys(m,{'hospital','role','permissions','modules'})))(j(c.get('/api/me',headers=H)))
        ))

        # --- Exact specification registry ---
        mods=j(c.get('/api/modules',headers=H)); by={m['key']:m for m in mods}
        case('Specification','All specified core modules exist',lambda: assert_equal({k for k,v in by.items() if v['core']},EXPECTED_CORE))
        case('Specification','All specified optional/configurable modules exist',lambda: assert_equal({k for k,v in by.items() if not v['core']},EXPECTED_OPTIONAL))
        case('Specification','Permission vocabulary is exactly eight required actions',lambda: assert_equal(set(PERMISSIONS),EXPECTED_PERMISSIONS))
        case('Specification','All core modules start enabled',lambda: assert_true(all(by[k]['enabled'] for k in EXPECTED_CORE),'one or more core modules disabled'))
        case('Specification','District seed includes required district modules incl. Nursing',lambda: assert_true(EXPECTED_DISTRICT.issubset({k for k,v in by.items() if v['enabled']}),'district defaults incomplete'))

        # --- Presets and module toggles ---
        def apply_preset(ft):
            j(c.patch('/api/hospital',headers=H,json={'facility_type':ft,'apply_preset':True}),200)
            return {x['key']:x for x in j(c.get('/api/modules',headers=H))}
        case('Facility presets','SMALL enables core only',lambda: check_small(apply_preset('SMALL')))
        case('Facility presets','Core module cannot be disabled',lambda: expect_status(c.patch('/api/modules/patients',headers=H,json={'enabled':False}),400))
        case('Facility presets','DISTRICT matches specified default set',lambda: check_district(apply_preset('DISTRICT')))
        case('Facility presets','REFERRAL enables every module',lambda: check_referral(apply_preset('REFERRAL')))
        case('Facility presets','Invalid facility type rejected',lambda: expect_status(c.patch('/api/hospital',headers=H,json={'facility_type':'CLINIC_X','apply_preset':True}),400))
        case('Module configuration','Unknown module toggle rejected',lambda: expect_status(c.patch('/api/modules/not_real',headers=H,json={'enabled':True}),404))
        case('Module configuration','Optional module can be disabled then enabled',lambda: check_toggle(c,H,'theatre'))

        # Keep referral for optional module test coverage
        apply_preset('REFERRAL')

        # --- Patient & records ---
        p1=j(c.post('/api/patients',headers=H,json={'first_name':'E2E','last_name':'Alpha','sex':'Female','date_of_birth':'1999-01-02','phone':'+255700111001','address':'Arusha','blood_group':'O+','allergies':'Penicillin','next_of_kin':'Kin Alpha'})); state['p1']=p1
        p2=j(c.post('/api/patients',headers=H,json={'first_name':'E2E','last_name':'Beta','sex':'Male','phone':'+255700111002'})); state['p2']=p2
        case('Patients','Patient registration persists all supplied demographics',lambda: check_patient(p1))
        case('Patients','Patient numbers are unique',lambda: assert_true(p1['patient_no']!=p2['patient_no'],'duplicate patient number'))
        case('Patients','Search by phone/name/patient number works',lambda: assert_true(any(x['id']==p1['id'] for x in j(c.get('/api/patients?q=700111001',headers=H))),'patient not found'))
        case('Patients','Patient demographics update works',lambda: assert_equal(j(c.patch(f"/api/patients/{p1['id']}",headers=H,json={'address':'Dodoma'}))['address'],'Dodoma'))
        case('Medical records','Longitudinal patient detail endpoint works',lambda: assert_equal(j(c.get(f"/api/patients/{p1['id']}",headers=H))['patient']['id'],p1['id']))
        case('Patients','Unknown patient returns 404',lambda: expect_status(c.get('/api/patients/999999',headers=H),404))

        # --- Appointment + reception ---
        at=(datetime.utcnow()+timedelta(hours=1)).replace(microsecond=0).isoformat()
        ap1=j(c.post('/api/appointments',headers=H,json={'patient_id':p1['id'],'scheduled_at':at,'department':'OPD','clinician':'Dr E2E','reason':'Review'})); state['ap1']=ap1
        ap2=j(c.post('/api/appointments',headers=H,json={'patient_id':p2['id'],'scheduled_at':at,'department':'OPD'})); state['ap2']=ap2
        case('Appointments','Appointment booking works',lambda: assert_equal(ap1['patient_id'],p1['id']))
        case('Appointments','Appointment list includes booking',lambda: assert_true(any(x['id']==ap1['id'] for x in j(c.get('/api/appointments',headers=H))),'appointment missing'))
        case('Appointments','Invalid appointment status rejected',lambda: expect_status(c.patch(f"/api/appointments/{ap1['id']}/status",headers=H,json={'status':'MAGIC'}),400))
        case('Reception','Reception queue includes booked patient',lambda: assert_true(any(x['id']==ap1['id'] for x in j(c.get('/api/reception/queue',headers=H))),'queue missing appointment'))
        case('Reception','Reception check-in marks appointment ARRIVED',lambda: assert_equal(j(c.post(f"/api/reception/check-in/{ap1['id']}",headers=H))['status'],'ARRIVED'))
        case('Reception','Cancelled appointment cannot be checked in',lambda: check_cancelled_checkin(c,H,ap2['id']))

        # --- OPD / Triage / Consultation / diagnosis ---
        enc1=j(c.post('/api/encounters',headers=H,json={'patient_id':p1['id'],'appointment_id':ap1['id'],'encounter_type':'OPD','chief_complaint':'Fever'})); state['enc1']=enc1
        case('OPD','Encounter starts from matching appointment',lambda: assert_equal(enc1['patient_id'],p1['id']))
        case('OPD','Encounter automatically keeps linked appointment ARRIVED',lambda: assert_equal(next(x for x in j(c.get('/api/appointments',headers=H)) if x['id']==ap1['id'])['status'],'ARRIVED'))
        case('OPD','Mismatched appointment/patient is blocked',lambda: expect_status(c.post('/api/encounters',headers=H,json={'patient_id':p1['id'],'appointment_id':ap2['id'],'encounter_type':'OPD'}),400))
        vital=j(c.post('/api/vitals',headers=H,json={'encounter_id':enc1['id'],'temperature_c':38.2,'pulse':94,'systolic':122,'diastolic':81,'spo2':97,'weight_kg':62.5,'height_cm':168})); state['vital']=vital
        case('Triage','Vital signs save against encounter',lambda: assert_equal(vital['encounter_id'],enc1['id']))
        case('Triage','SpO2 validation rejects >100',lambda: expect_status(c.post('/api/vitals',headers=H,json={'encounter_id':enc1['id'],'spo2':101}),422))
        cons=j(c.patch(f"/api/encounters/{enc1['id']}/consultation",headers=H,json={'clinical_notes':'Examined. Stable.','diagnosis':'Viral syndrome','status':'OPEN'})); state['cons']=cons
        case('Consultation','Doctor clinical notes persist',lambda: assert_equal(cons['clinical_notes'],'Examined. Stable.'))
        case('Diagnosis','Diagnosis persists separately in encounter data',lambda: assert_equal(cons['diagnosis'],'Viral syndrome'))
        case('Consultation','Invalid encounter status rejected',lambda: expect_status(c.patch(f"/api/encounters/{enc1['id']}/consultation",headers=H,json={'clinical_notes':'x','diagnosis':'y','status':'BAD'}),400))

        # --- Laboratory ---
        lab=j(c.post('/api/lab-orders',headers=H,json={'encounter_id':enc1['id'],'test_name':'CBC'})); state['lab']=lab
        case('Laboratory','Lab order creation works',lambda: assert_equal(lab['status'],'ORDERED'))
        case('Laboratory','Cannot verify lab order before result',lambda: check_verify_before_result(c,H,enc1['id']))
        lab_res=j(c.patch(f"/api/lab-orders/{lab['id']}/result",headers=H,json={'result':'Normal indices','verified':False}));
        case('Laboratory','Lab result entry works',lambda: assert_equal(lab_res['status'],'RESULTED'))
        lab_ver=j(c.patch(f"/api/lab-orders/{lab['id']}/verify",headers=H));
        case('Laboratory','Lab verification works',lambda: assert_true(lab_ver['verified'],'lab not verified'))

        # --- Inventory + pharmacy ---
        inv=j(c.post('/api/inventory',headers=H,json={'sku':'E2E-PARA','name':'E2E Paracetamol','category':'Medicine','quantity':10,'reorder_level':3,'unit_price':250})); state['inv']=inv
        case('Inventory','Inventory item creation with opening stock works',lambda: assert_equal(inv['quantity'],10))
        case('Inventory','Duplicate SKU blocked in same hospital',lambda: expect_status(c.post('/api/inventory',headers=H,json={'sku':'E2E-PARA','name':'Dup','quantity':1}),409))
        case('Inventory','Positive stock adjustment works',lambda: assert_equal(j(c.post(f"/api/inventory/{inv['id']}/adjust",headers=H,json={'delta':5,'reason':'Received'}))['quantity'],15))
        case('Inventory','Negative stock adjustment cannot go below zero',lambda: expect_status(c.post(f"/api/inventory/{inv['id']}/adjust",headers=H,json={'delta':-1000,'reason':'Bad'}),400))
        rx=j(c.post('/api/prescriptions',headers=H,json={'encounter_id':enc1['id'],'inventory_item_id':inv['id'],'medicine':'E2E Paracetamol','dose':'500mg','frequency':'BID','duration':'3 days','quantity':4,'instructions':'After meals'})); state['rx']=rx
        case('Prescriptions','Prescription creation works',lambda: assert_equal(rx['status'],'PENDING'))
        disp=j(c.patch(f"/api/prescriptions/{rx['id']}/dispense",headers=H));
        case('Pharmacy','Dispensing marks prescription dispensed',lambda: assert_equal(disp['status'],'DISPENSED'))
        case('Pharmacy','Dispensing deducts exact stock quantity',lambda: assert_equal(next(x for x in j(c.get('/api/inventory',headers=H)) if x['id']==inv['id'])['quantity'],11))
        case('Pharmacy','Dispensing creates stock movement',lambda: assert_true(any(x['delta']==-4 for x in j(c.get(f"/api/inventory/{inv['id']}/transactions",headers=H))),'dispense movement missing'))
        case('Pharmacy','Double dispensing is blocked',lambda: expect_status(c.patch(f"/api/prescriptions/{rx['id']}/dispense",headers=H),400))
        low_inv=j(c.post('/api/inventory',headers=H,json={'sku':'E2E-LOW','name':'E2E Low Stock Med','category':'Medicine','quantity':1,'reorder_level':1,'unit_price':100}));
        low_rx=j(c.post('/api/prescriptions',headers=H,json={'encounter_id':enc1['id'],'inventory_item_id':low_inv['id'],'medicine':'E2E Low Stock Med','dose':'1','frequency':'OD','duration':'5d','quantity':2}));
        case('Pharmacy','Insufficient stock blocks dispensing',lambda: expect_status(c.patch(f"/api/prescriptions/{low_rx['id']}/dispense",headers=H),400))
        manual_rx=j(c.post('/api/prescriptions',headers=H,json={'encounter_id':enc1['id'],'medicine':'Not In Inventory','dose':'1','frequency':'OD','duration':'1d','quantity':1}));
        case('Pharmacy','Unlinked/non-stock medicine cannot be dispensed',lambda: expect_status(c.patch(f"/api/prescriptions/{manual_rx['id']}/dispense",headers=H),400))

        # --- Billing/payments ---
        invoice=j(c.post('/api/invoices',headers=H,json={'patient_id':p1['id'],'amount':10000,'description':'E2E services'})); state['invoice']=invoice
        pay1=j(c.post(f"/api/invoices/{invoice['id']}/payments",headers=H,json={'amount':4000,'method':'CASH'}));
        case('Billing','Partial payment is recorded',lambda: assert_equal(pay1['amount'],4000))
        inv_after=next(x for x in j(c.get('/api/invoices',headers=H)) if x['id']==invoice['id'])
        case('Billing','Invoice moves to PARTIAL after partial payment',lambda: assert_equal(inv_after['status'],'PARTIAL'))
        case('Billing','Over-payment blocked',lambda: expect_status(c.post(f"/api/invoices/{invoice['id']}/payments",headers=H,json={'amount':7000,'method':'CASH'}),400))
        case('Billing','Invalid payment method blocked',lambda: expect_status(c.post(f"/api/invoices/{invoice['id']}/payments",headers=H,json={'amount':100,'method':'CRYPTO'}),400))
        j(c.post(f"/api/invoices/{invoice['id']}/payments",headers=H,json={'amount':6000,'method':'MOBILE_MONEY','reference':'TX-E2E'}))
        inv_paid=next(x for x in j(c.get('/api/invoices',headers=H)) if x['id']==invoice['id'])
        case('Billing','Full cumulative payment moves invoice to PAID',lambda: (assert_equal(inv_paid['status'],'PAID'),assert_equal(inv_paid['paid_amount'],10000)))
        case('Billing','Paid invoice rejects additional payment',lambda: expect_status(c.post(f"/api/invoices/{invoice['id']}/payments",headers=H,json={'amount':1,'method':'CASH'}),400))
        case('Billing','Invoice payment history returns both payments',lambda: assert_equal(len(j(c.get(f"/api/invoices/{invoice['id']}/payments",headers=H))),2))

        # --- Inpatient/bed management ---
        ward=j(c.post('/api/wards',headers=H,json={'name':'E2E Ward','ward_type':'GENERAL'})); state['ward']=ward
        bed=j(c.post('/api/beds',headers=H,json={'ward_id':ward['id'],'code':'E2E-B01'})); state['bed']=bed
        bed2=j(c.post('/api/beds',headers=H,json={'ward_id':ward['id'],'code':'E2E-B02'}));
        case('Wards','Ward creation works',lambda: assert_equal(ward['name'],'E2E Ward'))
        case('Beds','Bed creation works',lambda: assert_equal(bed['status'],'AVAILABLE'))
        case('Beds','Duplicate bed code blocked',lambda: expect_status(c.post('/api/beds',headers=H,json={'ward_id':ward['id'],'code':'E2E-B01'}),409))
        admission=j(c.post('/api/admissions',headers=H,json={'patient_id':p1['id'],'encounter_id':enc1['id'],'ward_id':ward['id'],'bed_id':bed['id'],'diagnosis':'Observation'})); state['admission']=admission
        case('Inpatient','Patient admission works',lambda: assert_equal(admission['status'],'ADMITTED'))
        case('Beds','Occupied bed cannot be reused',lambda: expect_status(c.post('/api/admissions',headers=H,json={'patient_id':p2['id'],'ward_id':ward['id'],'bed_id':bed['id']}),400))
        case('Inpatient','Admission rejects encounter belonging to another patient',lambda: check_admission_encounter_mismatch(c,H,p2['id'],enc1['id'],ward['id'],bed2['id']))
        dis=j(c.patch(f"/api/admissions/{admission['id']}/discharge",headers=H));
        case('Inpatient','Discharge completes admission',lambda: assert_equal(dis['status'],'DISCHARGED'))
        case('Beds','Discharge releases bed',lambda: assert_equal(next(x for x in j(c.get('/api/beds',headers=H)) if x['id']==bed['id'])['status'],'AVAILABLE'))
        case('Inpatient','Repeat discharge is blocked',lambda: expect_status(c.patch(f"/api/admissions/{admission['id']}/discharge",headers=H),400))

        # --- Reports/dashboard/audit ---
        dash=j(c.get('/api/dashboard',headers=H)); rep=j(c.get('/api/reports/summary',headers=H)); audits=j(c.get('/api/audit',headers=H))
        case('Dashboard','Dashboard returns all required operating KPIs',lambda: assert_keys(dash,{'patients','appointments_today','open_encounters','unpaid_invoices','outstanding_amount','revenue','low_stock','admitted','enabled_modules'}))
        case('Reports','Summary report includes billing, revenue, patients, encounters, labs, stock',lambda: assert_keys(rep,{'billing_status','revenue','patients','encounters','lab_orders','low_stock_items'}))
        case('Audit','Audit log contains clinical and administrative actions',lambda: assert_true(len(audits)>10,'too few audit records'))
        case('Audit','Sensitive workflow actions are audited',lambda: assert_true({'CREATE','PAY','DISPENSE','VERIFY','ADMIT','DISCHARGE'}.issubset({x['action'] for x in audits}),'expected actions missing'))

        # --- User/role management and granular RBAC ---
        role=j(c.post('/api/roles',headers=H,json={'name':'E2E Limited','permissions':{'patients':['VIEW'],'medical_records':['VIEW'],'theatre':['VIEW'],'bogus':['VIEW'],'laboratory':['FLY','VIEW']}})); state['limited_role']=role
        case('RBAC','Unknown modules/actions are sanitized from role permissions',lambda: (assert_true('bogus' not in role['permissions'],'bogus module kept'),assert_equal(role['permissions']['laboratory'],['VIEW'])))
        u=j(c.post('/api/users',headers=H,json={'full_name':'E2E Limited User','email':'e2e.limited@example.com','password':'Secret12!','role_id':role['id']})); state['limited_user']=u
        lim_login=j(c.post('/api/auth/login',json={'email':'e2e.limited@example.com','password':'Secret12!'})); LH=auth(lim_login['access_token']); state['LH']=LH
        case('RBAC','VIEW permission allows reading patients',lambda: expect_status(c.get('/api/patients',headers=LH),200))
        case('RBAC','Missing CREATE permission blocks patient creation',lambda: expect_status(c.post('/api/patients',headers=LH,json={'first_name':'No','last_name':'Write'}),403))
        case('RBAC','VIEW permission on enabled specialist module allows list',lambda: expect_status(c.get('/api/operations/theatre',headers=LH),200))
        case('RBAC','Missing CREATE on specialist module blocks create',lambda: expect_status(c.post('/api/operations/theatre',headers=LH,json={'title':'Blocked'}),403))
        case('RBAC','Module disabled overrides user permission',lambda: check_disabled_overrides_permission(c,H,LH,'theatre'))
        # restore theatre
        j(c.patch('/api/modules/theatre',headers=H,json={'enabled':True}))

        # diagnosis separate permission enforcement
        diag_role=j(c.post('/api/roles',headers=H,json={'name':'Consult No Diagnosis','permissions':{'patients':['VIEW'],'medical_records':['VIEW'],'opd':['VIEW'],'consultation':['VIEW','EDIT'],'diagnosis':['VIEW']}}));
        diag_user=j(c.post('/api/users',headers=H,json={'full_name':'Consult No Diagnosis','email':'consult.nodiag@example.com','password':'Secret12!','role_id':diag_role['id']}));
        diag_login=j(c.post('/api/auth/login',json={'email':'consult.nodiag@example.com','password':'Secret12!'})); DH=auth(diag_login['access_token'])
        case('RBAC','Consultation EDIT cannot bypass Diagnosis EDIT permission',lambda: expect_status(c.patch(f"/api/encounters/{enc1['id']}/consultation",headers=DH,json={'clinical_notes':'read','diagnosis':'unauthorized','status':'OPEN'}),403))

        # lab roles from specification
        lab_tech=j(c.post('/api/auth/login',json={'email':'lab@onehms.com','password':'Demo123!'})); LTH=auth(lab_tech['access_token'])
        tech_me=j(c.get('/api/me',headers=LTH));
        case('RBAC example','Lab Supervisor has VERIFY/APPROVE/PRINT and operational rights',lambda: assert_true({'VIEW','CREATE','EDIT','VERIFY','APPROVE','PRINT','EXPORT'}.issubset(set(tech_me['permissions']['laboratory'])),'lab supervisor permissions incomplete'))
        # create a technician explicitly from template-like perms and verify denial
        tech_role=j(c.post('/api/roles',headers=H,json={'name':'E2E Lab Technician','permissions':{'patients':['VIEW'],'medical_records':['VIEW'],'laboratory':['VIEW','CREATE','EDIT','PRINT']}}));
        tech_user=j(c.post('/api/users',headers=H,json={'full_name':'E2E Lab Tech','email':'e2e.labtech@example.com','password':'Secret12!','role_id':tech_role['id']}));
        tech_login=j(c.post('/api/auth/login',json={'email':'e2e.labtech@example.com','password':'Secret12!'})); TH=auth(tech_login['access_token'])
        lab2=j(c.post('/api/lab-orders',headers=H,json={'encounter_id':enc1['id'],'test_name':'Malaria RDT'})); j(c.patch(f"/api/lab-orders/{lab2['id']}/result",headers=TH,json={'result':'Negative','verified':False}))
        case('RBAC example','Lab Technician cannot VERIFY',lambda: expect_status(c.patch(f"/api/lab-orders/{lab2['id']}/verify",headers=TH),403))
        case('RBAC example','Lab Technician can PRINT',lambda: assert_true('<html>' in expect_status(c.get(f"/api/lab-orders/{lab2['id']}/print",headers=TH),200).text.lower(),'lab print output missing'))
        case('RBAC example','Lab Technician cannot APPROVE',lambda: expect_status(c.post(f"/api/lab-orders/{lab2['id']}/approve",headers=TH),403))
        case('RBAC example','Lab Supervisor can VERIFY',lambda: expect_status(c.patch(f"/api/lab-orders/{lab2['id']}/verify",headers=LTH),200))
        case('RBAC example','Lab Supervisor can APPROVE verified result',lambda: assert_true(j(c.post(f"/api/lab-orders/{lab2['id']}/approve",headers=LTH))['approved'],'lab not approved'))
        case('RBAC example','Lab Supervisor can PRINT',lambda: expect_status(c.get(f"/api/lab-orders/{lab2['id']}/print",headers=LTH),200))
        case('RBAC example','Lab Supervisor can EXPORT',lambda: assert_true('id,encounter_id,test_name,status' in expect_status(c.get('/api/laboratory/export.csv',headers=LTH),200).text,'lab CSV header missing'))

        # password reset + deactivate user
        j(c.patch(f"/api/users/{u['id']}",headers=H,json={'password':'Changed12!'}))
        case('Users','Admin password reset invalidates old password',lambda: expect_status(c.post('/api/auth/login',json={'email':'e2e.limited@example.com','password':'Secret12!'}),401))
        case('Users','Admin password reset enables new password',lambda: expect_status(c.post('/api/auth/login',json={'email':'e2e.limited@example.com','password':'Changed12!'}),200))
        new_lim=j(c.post('/api/auth/login',json={'email':'e2e.limited@example.com','password':'Changed12!'})); newLH=auth(new_lim['access_token'])
        j(c.patch(f"/api/users/{u['id']}",headers=H,json={'active':False}))
        case('Users','Deactivated account cannot use existing token',lambda: expect_status(c.get('/api/me',headers=newLH),401))
        case('Users','Admin cannot deactivate own account',lambda: expect_status(c.patch(f"/api/users/{login['user']['id']}",headers=H,json={'active':False}),400))

        # --- Every optional/configurable module ---
        apply_preset('REFERRAL')
        generic_optional=sorted(EXPECTED_OPTIONAL-{'wards','beds'})
        for mod in generic_optional:
            # admin has all eight permissions
            rec=j(c.post(f'/api/operations/{mod}',headers=H,json={'patient_id':p1['id'],'title':f'E2E {mod}','status':'OPEN','details':{'notes':'full specification test'}}),200,f'{mod} create')
            rid=rec['id']
            case(f'Optional:{mod}','Create operational record',lambda rec=rec: assert_true(rec['id']>0,'no id'))
            case(f'Optional:{mod}','Read/list operational record',lambda mod=mod,rid=rid: assert_true(any(x['id']==rid for x in j(c.get(f'/api/operations/{mod}',headers=H))),'record missing'))
            case(f'Optional:{mod}','Update operational record',lambda mod=mod,rid=rid: assert_equal(j(c.patch(f'/api/operations/{mod}/{rid}',headers=H,json={'status':'IN_PROGRESS'}))['status'],'IN_PROGRESS'))
            case(f'Optional:{mod}','VERIFY permission/action works',lambda mod=mod,rid=rid: assert_true(j(c.post(f'/api/operations/{mod}/{rid}/verify',headers=H))['verified'],'not verified'))
            case(f'Optional:{mod}','APPROVE permission/action works',lambda mod=mod,rid=rid: assert_true(j(c.post(f'/api/operations/{mod}/{rid}/approve',headers=H))['approved'],'not approved'))
            case(f'Optional:{mod}','PRINT permission/action works',lambda mod=mod,rid=rid: assert_true('<html>' in expect_status(c.get(f'/api/operations/{mod}/{rid}/print',headers=H),200).text.lower(),'print output not html'))
            case(f'Optional:{mod}','EXPORT permission/action works',lambda mod=mod: assert_true('id,patient_id,title,status' in expect_status(c.get(f'/api/operations/{mod}/actions/export',headers=H),200).text,'csv header missing'))
            case(f'Optional:{mod}','DELETE permission/action works',lambda mod=mod,rid=rid: assert_true(j(c.delete(f'/api/operations/{mod}/{rid}',headers=H))['deleted'],'not deleted'))
            case(f'Optional:{mod}','Deleted record disappears from list',lambda mod=mod,rid=rid: assert_true(all(x['id']!=rid for x in j(c.get(f'/api/operations/{mod}',headers=H))),'deleted record still listed'))
        case('Optional modules','Generic operations reject core modules',lambda: expect_status(c.get('/api/operations/patients',headers=H),400))
        case('Optional modules','Wards use dedicated workflow instead of generic records',lambda: expect_status(c.get('/api/operations/wards',headers=H),400))
        case('Optional modules','Beds use dedicated workflow instead of generic records',lambda: expect_status(c.get('/api/operations/beds',headers=H),400))

        # disable every optional module and verify server blocking
        apply_preset('SMALL')
        for mod in sorted(EXPECTED_OPTIONAL-{'wards','beds'}):
            case(f'Disabled:{mod}','Disabled module is blocked at API',lambda mod=mod: expect_status(c.get(f'/api/operations/{mod}',headers=H),403))
        case('Disabled:wards','Disabled wards endpoint blocked',lambda: expect_status(c.get('/api/wards',headers=H),403))
        case('Disabled:beds','Disabled beds endpoint blocked',lambda: expect_status(c.get('/api/beds',headers=H),403))

        # --- Multi-hospital isolation ---
        setup_second_hospital()
        second=j(c.post('/api/auth/login',json={'email':'second.admin@onehms.org','password':'Second123!'})); SH=auth(second['access_token'])
        sp=j(c.post('/api/patients',headers=SH,json={'first_name':'Second','last_name':'Hospital','sex':'Female'}));
        case('Multi-hospital','Second hospital user can operate same platform independently',lambda: assert_true(sp['id']>0,'second patient not created'))
        case('Multi-hospital','Hospital A cannot read Hospital B patient',lambda: expect_status(c.get(f"/api/patients/{sp['id']}",headers=H),404))
        case('Multi-hospital','Hospital B cannot read Hospital A patient',lambda: expect_status(c.get(f"/api/patients/{p1['id']}",headers=SH),404))
        case('Multi-hospital','Patient lists are tenant-isolated',lambda: assert_true(all(x['id']!=p1['id'] for x in j(c.get('/api/patients',headers=SH))),'cross-hospital patient leaked'))
        case('Multi-hospital','Module configuration is independent per hospital',lambda: check_second_module_independence(c,H,SH))

        # --- Role update uniqueness and permission persistence ---
        rA=j(c.post('/api/roles',headers=H,json={'name':'Role A','permissions':{'patients':['VIEW']}}));
        rB=j(c.post('/api/roles',headers=H,json={'name':'Role B','permissions':{'patients':['VIEW']}}));
        case('Roles','Duplicate role rename returns conflict instead of server error',lambda: expect_status(c.patch(f"/api/roles/{rB['id']}",headers=H,json={'name':'Role A'}),409))
        changed=j(c.patch(f"/api/roles/{rA['id']}",headers=H,json={'permissions':{'patients':['VIEW','CREATE'],'audit':['VIEW']}}));
        case('Roles','Role permission edits persist',lambda: assert_equal(set(changed['permissions']['patients']),{'VIEW','CREATE'}))

        # --- Final report files ---
        write_reports(results)

    failures=[r for r in results if r['status']=='FAIL']
    print(f'FULL SPEC E2E: {len(results)-len(failures)}/{len(results)} PASS')
    if failures:
        for r in failures[:30]: print(' -',r)
        raise SystemExit(1)


def assert_true(value,msg='assertion failed'):
    assert value,msg

def assert_equal(a,b):
    assert a==b,f'{a!r} != {b!r}'

def assert_keys(d,keys):
    missing=set(keys)-set(d)
    assert not missing,f'missing keys: {sorted(missing)}'

def check_small(mods):
    assert_true(all(mods[k]['enabled'] for k in EXPECTED_CORE),'core not all enabled')
    assert_true(all(not mods[k]['enabled'] for k in EXPECTED_OPTIONAL),'optional module enabled in SMALL')

def check_district(mods):
    assert_true(all(mods[k]['enabled'] for k in EXPECTED_CORE),'core not all enabled')
    actual={k for k in EXPECTED_OPTIONAL if mods[k]['enabled']}
    assert_equal(actual,EXPECTED_DISTRICT)

def check_referral(mods):
    assert_true(all(x['enabled'] for x in mods.values()),'not all modules enabled')

def check_toggle(c,H,module):
    a=j(c.patch(f'/api/modules/{module}',headers=H,json={'enabled':False})); assert_equal(a['enabled'],False)
    expect_status(c.get(f'/api/operations/{module}',headers=H),403)
    b=j(c.patch(f'/api/modules/{module}',headers=H,json={'enabled':True})); assert_equal(b['enabled'],True)

def check_patient(p):
    assert_equal(p['first_name'],'E2E'); assert_equal(p['last_name'],'Alpha'); assert_equal(p['blood_group'],'O+'); assert_equal(p['allergies'],'Penicillin')

def check_cancelled_checkin(c,H,appointment_id):
    j(c.patch(f'/api/appointments/{appointment_id}/status',headers=H,json={'status':'CANCELLED'}))
    expect_status(c.post(f'/api/reception/check-in/{appointment_id}',headers=H),400)

def check_verify_before_result(c,H,encounter_id):
    order=j(c.post('/api/lab-orders',headers=H,json={'encounter_id':encounter_id,'test_name':'No Result Yet'}))
    expect_status(c.patch(f"/api/lab-orders/{order['id']}/verify",headers=H),400)

def check_admission_encounter_mismatch(c,H,patient_id,encounter_id,ward_id,bed_id):
    expect_status(c.post('/api/admissions',headers=H,json={'patient_id':patient_id,'encounter_id':encounter_id,'ward_id':ward_id,'bed_id':bed_id}),400)

def check_disabled_overrides_permission(c,H,LH,module):
    j(c.patch(f'/api/modules/{module}',headers=H,json={'enabled':False}))
    r=c.get(f'/api/operations/{module}',headers=LH); expect_status(r,403)
    body=r.json(); detail=body.get('detail',{})
    assert_equal(detail.get('code'),'MODULE_DISABLED')

def setup_second_hospital():
    db=SessionLocal()
    try:
        h=Hospital(name='Second Test Hospital',facility_type='SMALL',address='Mwanza')
        db.add(h); db.flush()
        for m in MODULES:
            db.add(HospitalModule(hospital_id=h.id,module_key=m.key,enabled=preset_enabled('SMALL',m)))
        role=Role(hospital_id=h.id,name='Administrator',permissions={m.key:PERMISSIONS.copy() for m in MODULES})
        db.add(role); db.flush()
        db.add(User(hospital_id=h.id,role_id=role.id,full_name='Second Admin',email='second.admin@onehms.org',password_hash=hash_password('Second123!'),active=True))
        db.commit()
    finally: db.close()

def check_second_module_independence(c,H,SH):
    # Main hospital currently SMALL, so theatre disabled there; second is also SMALL. Enable only second.
    j(c.patch('/api/modules/theatre',headers=SH,json={'enabled':True}))
    main={x['key']:x['enabled'] for x in j(c.get('/api/modules',headers=H))}
    second={x['key']:x['enabled'] for x in j(c.get('/api/modules',headers=SH))}
    assert_equal(main['theatre'],False); assert_equal(second['theatre'],True)

def write_reports(rows):
    out_dir=Path(__file__).resolve().parent
    json_path=out_dir/'full_spec_results.json'
    md_path=out_dir/'FULL_SPEC_TEST_REPORT.md'
    json_path.write_text(json.dumps(rows,indent=2,default=str))
    grouped=defaultdict(list)
    for r in rows: grouped[r['category']].append(r)
    passed=sum(r['status']=='PASS' for r in rows); failed=len(rows)-passed
    lines=['# One HMS — Full Specification E2E Test Report','',f'- Total test cases: **{len(rows)}**',f'- Passed: **{passed}**',f'- Failed: **{failed}**','', 'The suite tests the exact modular architecture plus end-to-end operational behavior, RBAC, tenant isolation, negative/error paths, and every configurable module workspace.','']
    for cat,items in grouped.items():
        lines += [f'## {cat}','', '| Test case | Result | Detail |','|---|---|---|']
        for r in items:
            detail=(r['detail'] or '').replace('|','\\|').replace('\n',' ')
            lines.append(f"| {r['name']} | {r['status']} | {detail} |")
        lines.append('')
    md_path.write_text('\n'.join(lines))

if __name__=='__main__':
    try:
        run()
    finally:
        if TEST_DB.exists(): TEST_DB.unlink()
