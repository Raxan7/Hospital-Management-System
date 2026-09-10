import os, json
from pathlib import Path
from collections import defaultdict
from types import SimpleNamespace

TEST_DB = Path(__file__).resolve().parent / 'role_catalog_e2e.db'
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB}'
os.environ['JWT_SECRET'] = 'role-catalog-e2e-secret-that-is-longer-than-thirty-two-bytes'
if TEST_DB.exists(): TEST_DB.unlink()

from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Role, User, Hospital, HospitalModule
from app.modules import MODULES, PERMISSIONS
from app.roles import ROLE_TEMPLATES, ROLE_TEMPLATE_BY_NAME, validate_role_templates
from app.security import ensure_access
from app.seed import ensure_role_templates

OUT = Path(__file__).resolve().parent
REPORT = OUT / 'ROLE_CATALOG_E2E_TEST_REPORT.md'
JSON_REPORT = OUT / 'role_catalog_e2e_results.json'
results=[]

def add(category,name,ok,detail=''):
    results.append({'category':category,'name':name,'status':'PASS' if ok else 'FAIL','detail':str(detail)[:600]})
    if not ok: print('FAIL',category,name,detail)

def case(category,name,fn):
    try: fn(); add(category,name,True)
    except Exception as e: add(category,name,False,e)

def expect(resp,status):
    assert resp.status_code==status,f'expected {status}, got {resp.status_code}: {resp.text}'
    return resp

def J(resp,status=200): return expect(resp,status).json()
def H(token): return {'Authorization':f'Bearer {token}'}
def assert_true(v,m='assertion failed'): assert v,m
def assert_eq(a,b): assert a==b,f'{a!r} != {b!r}'

def login(c,email,password='Demo123!'):
    return H(J(c.post('/api/auth/login',json={'email':email,'password':password}))['access_token'])

def create_user_for_role(c,admin_h,role_name,email):
    roles=J(c.get('/api/roles',headers=admin_h)); role=next(r for r in roles if r['name']==role_name)
    J(c.post('/api/users',headers=admin_h,json={'full_name':f'E2E {role_name}','email':email,'password':'RoleTest123!','role_id':role['id']}))
    return login(c,email,'RoleTest123!')

def test_permission_matrix(db,hospital_id):
    # All modules enabled so this validates role permissions rather than facility switches.
    for row in db.query(HospitalModule).filter_by(hospital_id=hospital_id): row.enabled=True
    db.commit()
    installed={r.name:r for r in db.query(Role).filter_by(hospital_id=hospital_id).all()}
    for template in ROLE_TEMPLATES:
        role=installed[template.name]
        user=SimpleNamespace(hospital_id=hospital_id,role=role)
        def all_grants_work(t=template,u=user):
            for module,actions in t.permissions.items():
                for action in actions:
                    ensure_access(u,db,module,action)
        case('Role permission matrix',f'{template.name}: every granted permission is accepted by authorization engine',all_grants_work)

        # Find one permission omitted from this role and prove denial. Full-admin templates intentionally have none.
        denied=None
        for module in MODULES:
            have=set(template.permissions.get(module.key,[]))
            for action in PERMISSIONS:
                if action not in have:
                    denied=(module.key,action); break
            if denied: break
        if denied:
            def denied_is_denied(u=user,d=denied):
                try:
                    ensure_access(u,db,d[0],d[1])
                except HTTPException as exc:
                    assert_eq(exc.status_code,403)
                    detail=exc.detail if isinstance(exc.detail,dict) else {}
                    assert_eq(detail.get('code'),'PERMISSION_DENIED')
                    return
                raise AssertionError(f'{d} was unexpectedly allowed')
            case('Role permission matrix',f'{template.name}: an ungranted permission is denied',denied_is_denied)
        else:
            case('Role permission matrix',f'{template.name}: full administrator template intentionally has all permissions',lambda: None)

def run():
    with TestClient(app) as c:
        admin=login(c,'admin@onehms.com','Admin123!')
        me=J(c.get('/api/me',headers=admin)); hid=me['hospital']['id']
        templates=J(c.get('/api/role-templates',headers=admin)); roles=J(c.get('/api/roles',headers=admin))
        tnames={x['name'] for x in templates}; rnames={x['name'] for x in roles}

        required_explicit={'Administrator','Doctor','Nurse','Receptionist','Lab Technician','Lab Supervisor','Surgeon','Theatre Staff','Theatre Nurse'}
        required_broader={
            'Super Administrator','Hospital Administrator','Medical Director','Department Manager','Registration Officer','Appointment Officer','Medical Records Officer',
            'Medical Officer','Clinical Officer','Specialist Doctor','Triage Nurse','Ward Nurse','ICU Nurse','Midwife','Anaesthetist','Theatre Technician',
            'Lab Scientist','Pharmacist','Pharmacy Technician','Pharmacy Supervisor','Radiologist','Radiographer','Sonographer','Cashier','Billing Officer','Insurance Officer',
            'Accountant','Finance Manager','Storekeeper','Procurement Officer','Inventory Manager','HR Officer','Payroll Officer','Auditor','Document Officer','Asset Officer',
            'Maintenance Officer','Blood Bank Technician','Mortuary Attendant','Nutritionist / Dietitian','Physiotherapist','Ambulance / EMS Staff',
            'Biomedical Equipment Technician','CSSD Technician','Catering / Kitchen Staff','Laundry Staff','Dental Clinician','Ophthalmology Clinician','ENT Clinician',
            'Pediatrician','Mental Health Clinician','Dialysis Clinician','Oncologist','Cardiologist'
        }
        case('Role catalogue','Built-in role templates validate with no unknown module/action',lambda: assert_eq(validate_role_templates(),[]))
        case('Role catalogue','63 predefined hospital role templates are published',lambda: assert_eq(len(templates),63))
        case('Role catalogue','Every explicitly discussed role type is predefined',lambda: assert_true(required_explicit.issubset(tnames),sorted(required_explicit-tnames)))
        case('Role catalogue','Broader hospital role catalogue is predefined',lambda: assert_true(required_broader.issubset(tnames),sorted(required_broader-tnames)))
        case('Role catalogue','Every template is installed as a selectable hospital role',lambda: assert_eq(tnames,rnames & tnames))
        case('Role catalogue','Template categories and descriptions are exposed',lambda: assert_true(all(x['category'] and x['description'] for x in templates),'missing role metadata'))
        case('Role catalogue','Every template permission map matches installed default on fresh DB',lambda: assert_true(all(next(r for r in roles if r['name']==t['name'])['permissions']==t['permissions'] for t in templates),'installed/template mismatch'))

        # Upgrade-safe behavior: installer must not overwrite hospital-customized permissions.
        doctor=next(r for r in roles if r['name']=='Doctor')
        J(c.patch(f"/api/roles/{doctor['id']}",headers=admin,json={'permissions':{'patients':['VIEW']}}))
        install=J(c.post('/api/role-templates/install',headers=admin))
        doctor_after=next(r for r in J(c.get('/api/roles',headers=admin)) if r['name']=='Doctor')
        case('Upgrade safety','Installing missing defaults does not overwrite customized existing role',lambda: assert_eq(doctor_after['permissions'],{'patients':['VIEW']}))
        case('Upgrade safety','Installer reports no missing templates on complete installation',lambda: assert_eq(install['installed_count'],0))
        reset=J(c.post(f"/api/roles/{doctor['id']}/reset-template",headers=admin))
        case('Upgrade safety','Built-in role can be reset to its recommended default permissions',lambda: assert_eq(reset['permissions'],ROLE_TEMPLATE_BY_NAME['Doctor'].permissions))

        # Simulate upgrading an older/partial hospital database: add only a customized Doctor, then install missing templates.
        udb=SessionLocal()
        try:
            old_h=Hospital(name='Upgrade Simulation Hospital',facility_type='SMALL')
            udb.add(old_h); udb.flush()
            custom={'patients':['VIEW']}
            old_doctor=Role(hospital_id=old_h.id,name='Doctor',permissions=custom)
            udb.add(old_doctor); udb.flush()
            upgraded=ensure_role_templates(udb,old_h.id); udb.commit()
            old_roles={r.name:r for r in udb.query(Role).filter_by(hospital_id=old_h.id).all()}
            case('Upgrade safety','Partial existing hospital receives all missing predefined roles',lambda: assert_true(set(ROLE_TEMPLATE_BY_NAME).issubset(old_roles), 'missing role after upgrade'))
            case('Upgrade safety','Upgrade preserves an existing customized Doctor role',lambda: assert_eq(old_roles['Doctor'].permissions,custom))
            case('Upgrade safety','Upgrade installs Surgeon and Theatre Staff into existing hospital',lambda: assert_true({'Surgeon','Theatre Staff'}.issubset(old_roles),'theatre roles missing'))
        finally:
            udb.close()

        # Referral preset enables optional services for realistic specialty role testing.
        J(c.patch('/api/hospital',headers=admin,json={'facility_type':'REFERRAL','apply_preset':True}))
        patient=J(c.post('/api/patients',headers=admin,json={'first_name':'Role','last_name':'Matrix','sex':'Female'}))
        encounter=J(c.post('/api/encounters',headers=admin,json={'patient_id':patient['id'],'encounter_type':'OPD','chief_complaint':'Role test'}))

        # Actual endpoint tests for the roles explicitly discussed in the original requirements.
        receptionist=login(c,'reception@onehms.com')
        case('Explicit role E2E','Receptionist can read reception queue',lambda: expect(c.get('/api/reception/queue',headers=receptionist),200))
        case('Explicit role E2E','Receptionist can register patient',lambda: expect(c.post('/api/patients',headers=receptionist,json={'first_name':'Reception','last_name':'Created'}),200))
        case('Explicit role E2E','Receptionist cannot enter laboratory results',lambda: expect(c.get('/api/lab-orders',headers=receptionist),403))

        nurse=login(c,'nurse@onehms.com')
        case('Explicit role E2E','Nurse can capture triage vitals',lambda: expect(c.post('/api/vitals',headers=nurse,json={'encounter_id':encounter['id'],'temperature_c':37.2,'spo2':99}),200))
        case('Explicit role E2E','Nurse cannot edit doctor diagnosis',lambda: expect(c.patch(f"/api/encounters/{encounter['id']}/consultation",headers=nurse,json={'clinical_notes':'x','diagnosis':'x','status':'OPEN'}),403))

        doctor_h=login(c,'doctor@onehms.com')
        case('Explicit role E2E','Doctor can document consultation and diagnosis',lambda: expect(c.patch(f"/api/encounters/{encounter['id']}/consultation",headers=doctor_h,json={'clinical_notes':'Reviewed','diagnosis':'Test diagnosis','status':'OPEN'}),200))
        case('Explicit role E2E','Doctor cannot administer users',lambda: expect(c.get('/api/users',headers=doctor_h),403))

        labtech=create_user_for_role(c,admin,'Lab Technician','role.labtech@example.com')
        lab=J(c.post('/api/lab-orders',headers=doctor_h,json={'encounter_id':encounter['id'],'test_name':'Role CBC'}))
        J(c.patch(f"/api/lab-orders/{lab['id']}/result",headers=labtech,json={'result':'Normal','verified':False}))
        case('Explicit role E2E','Lab Technician can print a result',lambda: expect(c.get(f"/api/lab-orders/{lab['id']}/print",headers=labtech),200))
        case('Explicit role E2E','Lab Technician cannot verify',lambda: expect(c.patch(f"/api/lab-orders/{lab['id']}/verify",headers=labtech),403))
        case('Explicit role E2E','Lab Technician cannot approve',lambda: expect(c.post(f"/api/lab-orders/{lab['id']}/approve",headers=labtech),403))
        labsup=login(c,'lab@onehms.com')
        case('Explicit role E2E','Lab Supervisor can verify result',lambda: expect(c.patch(f"/api/lab-orders/{lab['id']}/verify",headers=labsup),200))
        case('Explicit role E2E','Lab Supervisor can approve verified result',lambda: expect(c.post(f"/api/lab-orders/{lab['id']}/approve",headers=labsup),200))
        case('Explicit role E2E','Lab Supervisor can export laboratory results',lambda: expect(c.get('/api/laboratory/export.csv',headers=labsup),200))

        surgeon=login(c,'surgeon@onehms.com')
        surgery=J(c.post('/api/operations/theatre',headers=surgeon,json={'patient_id':patient['id'],'title':'Appendectomy plan','details':{'procedure':'appendectomy'}}))
        case('Explicit role E2E','Surgeon can create theatre record',lambda: assert_true(surgery['id']>0))
        case('Explicit role E2E','Surgeon can verify theatre record',lambda: expect(c.post(f"/api/operations/theatre/{surgery['id']}/verify",headers=surgeon),200))
        case('Explicit role E2E','Surgeon can approve theatre record',lambda: expect(c.post(f"/api/operations/theatre/{surgery['id']}/approve",headers=surgeon),200))
        case('Explicit role E2E','Surgeon cannot administer users',lambda: expect(c.get('/api/users',headers=surgeon),403))

        theatre_staff=create_user_for_role(c,admin,'Theatre Staff','role.theatrestaff@example.com')
        theatre_rec=J(c.post('/api/operations/theatre',headers=theatre_staff,json={'patient_id':patient['id'],'title':'Theatre preparation'}))
        case('Explicit role E2E','Theatre Staff can create theatre support record',lambda: assert_true(theatre_rec['id']>0))
        case('Explicit role E2E','Theatre Staff cannot approve surgery',lambda: expect(c.post(f"/api/operations/theatre/{theatre_rec['id']}/approve",headers=theatre_staff),403))

        # Module-level switch must still override a valid surgeon role.
        J(c.patch('/api/modules/theatre',headers=admin,json={'enabled':False}))
        blocked=c.get('/api/operations/theatre',headers=surgeon)
        case('Explicit role E2E','Disabled Theatre overrides Surgeon role permissions',lambda: (expect(blocked,403),assert_eq(blocked.json()['detail']['code'],'MODULE_DISABLED')))
        J(c.patch('/api/modules/theatre',headers=admin,json={'enabled':True}))

        # Representative specialty/admin roles operate against their actual module workspaces.
        representative=[
            ('Radiologist','radiology','role.radiologist@example.com'),('Midwife','maternity','role.midwife@example.com'),
            ('Insurance Officer','insurance','role.insurance@example.com'),('Procurement Officer','procurement','role.procurement@example.com'),
            ('HR Officer','hr','role.hr@example.com'),('Blood Bank Technician','blood_bank','role.bloodbank@example.com'),
            ('Physiotherapist','physiotherapy','role.physio@example.com'),('Biomedical Equipment Technician','medical_equipment','role.biomed@example.com'),
            ('Oncologist','oncology','role.oncology@example.com'),('Cardiologist','cardiology','role.cardiology@example.com')
        ]
        for name,module,email in representative:
            rh=create_user_for_role(c,admin,name,email)
            rec=J(c.post(f'/api/operations/{module}',headers=rh,json={'patient_id':patient['id'],'title':f'{name} E2E record'}))
            case('Representative department E2E',f'{name} can create record in {module}',lambda rec=rec: assert_true(rec['id']>0))
            case('Representative department E2E',f'{name} can read {module} workspace',lambda rh=rh,module=module: expect(c.get(f'/api/operations/{module}',headers=rh),200))
            case('Representative department E2E',f'{name} cannot create staff accounts',lambda rh=rh,name=name: expect(c.post('/api/users',headers=rh,json={'full_name':'Denied','email':f'denied.{name.lower().replace(" ",".").replace("/",".")}@example.com','password':'Denied123!','role_id':1}),403))

        db=SessionLocal()
        try:
            test_permission_matrix(db,hid)
        finally: db.close()

        # Final role metadata/category coverage.
        categories={t['category'] for t in templates}
        expected_categories={'System & Management','Front Office','Clinical','Nursing','Theatre','Laboratory','Pharmacy','Radiology','Finance','Inventory & Procurement','Administration','Other Hospital Services','Specialty Clinical'}
        case('Role catalogue','All hospital role categories are represented',lambda: assert_true(expected_categories.issubset(categories),sorted(expected_categories-categories)))

    write_report()
    failed=[r for r in results if r['status']=='FAIL']
    print(f'ROLE CATALOG E2E: {len(results)-len(failed)}/{len(results)} PASS')
    if failed: raise SystemExit(1)


def write_report():
    JSON_REPORT.write_text(json.dumps(results,indent=2))
    grouped=defaultdict(list)
    for r in results: grouped[r['category']].append(r)
    passed=sum(r['status']=='PASS' for r in results); failed=len(results)-passed
    lines=['# One HMS — Role Catalogue & Authorization E2E Test Report','',f'- Test cases: **{len(results)}**',f'- Passed: **{passed}**',f'- Failed: **{failed}**',f'- Built-in role templates: **{len(ROLE_TEMPLATES)}**','',
           'This suite validates every predefined hospital role, its permission mapping, upgrade-safe template installation, explicit requirement roles, module-disable precedence, and representative department workflows.','']
    for cat,items in grouped.items():
        lines += [f'## {cat}','', '| Test case | Result | Detail |','|---|---|---|']
        for r in items:
            d=(r['detail'] or '').replace('|','\\|').replace('\n',' ')
            lines.append(f"| {r['name']} | {r['status']} | {d} |")
        lines.append('')
    REPORT.write_text('\n'.join(lines))

if __name__=='__main__':
    try: run()
    finally:
        if TEST_DB.exists(): TEST_DB.unlink()
