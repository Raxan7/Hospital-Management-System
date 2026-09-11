import os, json
from pathlib import Path

TEST_DB=Path(__file__).resolve().parent/'configuration_e2e.db'
os.environ['DATABASE_URL']=f'sqlite:///{TEST_DB}'
os.environ['JWT_SECRET']='configuration-e2e-secret-longer-than-thirty-two-bytes'
if TEST_DB.exists(): TEST_DB.unlink()

from fastapi.testclient import TestClient
from app.main import app
from app.modules import MODULES, MODULE_DEPENDENCIES, DISTRICT_DEFAULTS
from app.database import SessionLocal
from app.models import Hospital, HospitalModule, Role, User
from app.security import hash_password
from app.seed import ensure_hospital_modules

REPORT=Path(__file__).resolve().parent/'CONFIGURATION_E2E_TEST_REPORT.md'
JSON_REPORT=Path(__file__).resolve().parent/'configuration_e2e_results.json'
results=[]

def ok(name, detail=''):
    results.append({'name':name,'status':'PASS','detail':detail})

def fail(name, detail):
    results.append({'name':name,'status':'FAIL','detail':str(detail)[:600]})
    print('FAIL',name,detail,flush=True)

def case(name, fn):
    try: fn(); ok(name); print('PASS',name,flush=True)
    except Exception as e: fail(name,e)

def expect(resp,status=200):
    assert resp.status_code==status,f'expected {status}, got {resp.status_code}: {resp.text}'
    return resp

def auth(c,email='admin@onehms.com',password='Admin123!'):
    r=expect(c.post('/api/auth/login',json={'email':email,'password':password})).json()
    return {'Authorization':'Bearer '+r['access_token']}

def modules(c,H): return {m['key']:m for m in expect(c.get('/api/modules',headers=H)).json()}
def me(c,H): return expect(c.get('/api/me',headers=H)).json()
def service_get(c,H,key):
    if key=='wards': return c.get('/api/wards',headers=H)
    if key=='beds': return c.get('/api/beds',headers=H)
    return c.get(f'/api/operations/{key}',headers=H)

def write_report():
    passed=sum(x['status']=='PASS' for x in results); failed=len(results)-passed
    lines=['# One HMS — Configuration End-to-End Test Report','',f'- Checks: **{len(results)}**',f'- Passed: **{passed}**',f'- Failed: **{failed}**','',
           'This suite validates hospital-level module configuration at database, API, permission, preset, dependency, tenant-isolation and persistence layers.','',
           '| Check | Result | Detail |','|---|---|---|']
    for r in results:
        d=(r['detail'] or '').replace('|','\\|').replace('\n',' ')
        lines.append(f"| {r['name']} | {r['status']} | {d} |")
    REPORT.write_text('\n'.join(lines)); JSON_REPORT.write_text(json.dumps(results,indent=2))

def run():
    with TestClient(app) as c:
        H=auth(c)
        reg=modules(c,H)
        core=[m.key for m in MODULES if m.core]
        optional=[m.key for m in MODULES if not m.core]

        case('Registry: every declared module is returned exactly once',lambda: assert_eq(set(reg),{m.key for m in MODULES}))
        case('Database: every registry module has an explicit hospital state row',lambda: assert_eq(db_module_keys(1),{m.key for m in MODULES}))

        # Core modules are invariant and cannot be disabled.
        for key in core:
            case(f'Core:{key}: disable request is rejected',lambda key=key: expect(c.patch(f'/api/modules/{key}',headers=H,json={'enabled':False}),400))
            case(f'Core:{key}: remains enabled in /api/modules and /api/me',lambda key=key: assert_true(modules(c,H)[key]['enabled'] and me(c,H)['modules'][key]))

        # Start from SMALL: all optional modules must be off.
        expect(c.patch('/api/hospital',headers=H,json={'facility_type':'SMALL','apply_preset':True}))
        small=modules(c,H)
        case('Preset SMALL: all optional modules disabled',lambda: assert_true(all(not small[k]['enabled'] for k in optional)))
        case('Preset SMALL: all core modules enabled',lambda: assert_true(all(small[k]['enabled'] for k in core)))

        # Every optional module: enable -> observable -> usable -> relogin -> disable -> blocked.
        for key in optional:
            if key=='beds':
                # Beds dependency is tested separately below.
                continue
            case(f'Toggle:{key}: enable persists to modules/me',lambda key=key: enable_and_assert(c,H,key))
            case(f'Toggle:{key}: enabled endpoint is usable',lambda key=key: expect(service_get(c,H,key),200))
            case(f'Toggle:{key}: enabled state survives a fresh login token',lambda key=key: assert_true(me(c,auth(c))['modules'][key]))
            case(f'Toggle:{key}: disable persists to modules/me',lambda key=key: disable_and_assert(c,H,key))
            case(f'Toggle:{key}: disabled endpoint is blocked',lambda key=key: assert_disabled(service_get(c,H,key),key))

        # Beds / Wards structural dependency.
        expect(c.patch('/api/modules/wards',headers=H,json={'enabled':False}))
        case('Dependency: disabling Wards also disables Beds',lambda: assert_true(not modules(c,H)['wards']['enabled'] and not modules(c,H)['beds']['enabled']))
        expect(c.patch('/api/modules/beds',headers=H,json={'enabled':True}))
        case('Dependency: enabling Beds atomically enables Wards',lambda: assert_true(modules(c,H)['beds']['enabled'] and modules(c,H)['wards']['enabled']))
        case('Dependency: Beds endpoint usable when both are enabled',lambda: expect(c.get('/api/beds',headers=H),200))
        expect(c.patch('/api/modules/wards',headers=H,json={'enabled':False}))
        case('Dependency: Beds endpoint blocked after Wards is disabled',lambda: assert_disabled(c.get('/api/beds',headers=H),'beds'))

        # Preset correctness and manual override semantics.
        expect(c.patch('/api/hospital',headers=H,json={'facility_type':'DISTRICT','apply_preset':True}))
        district=modules(c,H)
        case('Preset DISTRICT: optional set exactly matches configured district defaults',lambda: assert_eq({k for k in optional if district[k]['enabled']},set(DISTRICT_DEFAULTS)))
        expect(c.patch('/api/modules/theatre',headers=H,json={'enabled':True}))
        before={k:v['enabled'] for k,v in modules(c,H).items()}
        expect(c.patch('/api/hospital',headers=H,json={'facility_type':'SMALL','apply_preset':False}))
        after={k:v['enabled'] for k,v in modules(c,H).items()}
        case('Facility type change without Apply Preset preserves manual module choices',lambda: assert_eq(before,after))
        expect(c.patch('/api/hospital',headers=H,json={'apply_preset':True}))
        case('Apply Preset works even when facility_type is omitted from API request',lambda: assert_true(all(not modules(c,H)[k]['enabled'] for k in optional)))
        expect(c.patch('/api/hospital',headers=H,json={'facility_type':'REFERRAL','apply_preset':True}))
        case('Preset REFERRAL: every module enabled',lambda: assert_true(all(v['enabled'] for v in modules(c,H).values())))
        enabled_count=sum(1 for v in modules(c,H).values() if v['enabled'])
        case('Dashboard enabled_modules KPI matches effective module registry',lambda: assert_eq(expect(c.get('/api/dashboard',headers=H)).json()['enabled_modules'],enabled_count))

        # Permission cannot override a disabled hospital module.
        expect(c.patch('/api/modules/theatre',headers=H,json={'enabled':False}))
        SH=auth(c,'surgeon@onehms.com','Demo123!')
        case('RBAC: Surgeon has Theatre permission in role',lambda: assert_true('VIEW' in me(c,SH)['permissions'].get('theatre',[]) or '*' in me(c,SH)['permissions'].get('theatre',[])))
        case('Configuration overrides RBAC: disabled Theatre blocks Surgeon',lambda: assert_disabled(c.get('/api/operations/theatre',headers=SH),'theatre'))
        expect(c.patch('/api/modules/theatre',headers=H,json={'enabled':True}))
        case('Configuration activation takes effect for existing Surgeon token',lambda: expect(c.get('/api/operations/theatre',headers=SH),200))

        # Audit records exist for configuration changes.
        audits=expect(c.get('/api/audit',headers=H)).json()
        case('Audit: module configuration changes are recorded',lambda: assert_true(any(x['action']=='MODULE_TOGGLE' for x in audits)))

        # Multi-hospital isolation.
        create_second_hospital()
        H2=auth(c,'config.admin2@example.com','Second123!')
        expect(c.patch('/api/modules/theatre',headers=H,json={'enabled':False}))
        expect(c.patch('/api/modules/theatre',headers=H2,json={'enabled':True}))
        case('Tenant isolation: Hospital A Theatre can be disabled independently',lambda: assert_true(not me(c,H)['modules']['theatre']))
        case('Tenant isolation: Hospital B Theatre remains enabled',lambda: assert_true(me(c,H2)['modules']['theatre']))
        case('Tenant isolation: Hospital B can use enabled Theatre',lambda: expect(c.get('/api/operations/theatre',headers=H2),200))
        case('Tenant isolation: Hospital A remains blocked',lambda: assert_disabled(c.get('/api/operations/theatre',headers=H),'theatre'))

    # Restart/lifespan persistence against the same file DB.
    with TestClient(app) as c2:
        H=auth(c2)
        case('Persistence: module state survives application restart/lifespan re-entry',lambda: assert_true(not me(c2,H)['modules']['theatre']))
        case('Persistence: complete module-state rows still exist after restart',lambda: assert_eq(db_module_keys(1),{m.key for m in MODULES}))

    write_report()
    failures=[r for r in results if r['status']=='FAIL']
    print(f'CONFIGURATION E2E: {len(results)-len(failures)}/{len(results)} PASS')
    if failures: raise SystemExit(1)
    if TEST_DB.exists(): TEST_DB.unlink()

def assert_true(v,msg='assertion failed'): assert v,msg
def assert_eq(a,b): assert a==b,f'{a!r} != {b!r}'

def enable_and_assert(c,H,key):
    r=expect(c.patch(f'/api/modules/{key}',headers=H,json={'enabled':True})).json(); assert_true(r['enabled'])
    assert_true(modules(c,H)[key]['enabled']); assert_true(me(c,H)['modules'][key])

def disable_and_assert(c,H,key):
    r=expect(c.patch(f'/api/modules/{key}',headers=H,json={'enabled':False})).json(); assert_true(not r['enabled'])
    assert_true(not modules(c,H)[key]['enabled']); assert_true(not me(c,H)['modules'][key])

def assert_disabled(resp,key):
    expect(resp,403); detail=resp.json().get('detail',{}); assert_eq(detail.get('code'),'MODULE_DISABLED'); assert_eq(detail.get('module'),key)

def db_module_keys(hospital_id):
    db=SessionLocal()
    try: return {x.module_key for x in db.query(HospitalModule).filter_by(hospital_id=hospital_id).all()}
    finally: db.close()

def create_second_hospital():
    db=SessionLocal()
    try:
        h=Hospital(name='Configuration Isolation Hospital',facility_type='SMALL',address='Tanzania');db.add(h);db.flush();ensure_hospital_modules(db,h)
        role=Role(hospital_id=h.id,name='Administrator',permissions={m.key:['*'] for m in MODULES});db.add(role);db.flush()
        db.add(User(hospital_id=h.id,role_id=role.id,full_name='Config Admin 2',email='config.admin2@example.com',password_hash=hash_password('Second123!')));db.commit()
    finally: db.close()

if __name__=='__main__': run()
