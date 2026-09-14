import os, sys, tempfile
from pathlib import Path

DB=Path(tempfile.gettempdir())/'onehms_care_service_matrix.db'
try: DB.unlink()
except FileNotFoundError: pass
os.environ['DATABASE_URL']=f'sqlite:///{DB}'
os.environ['JWT_SECRET']='care-service-matrix-secret-12345678901234567890'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app.care_pathways import CARE_SERVICE_MODULES

checks=[]
def ok(name, cond=True, detail=''):
    if not cond: raise AssertionError(detail or name)
    checks.append(name)
def req(r, code=200):
    if r.status_code!=code: raise AssertionError(f'{r.request.method} {r.request.url}: {r.status_code} {r.text}')
    return r.json() if r.text else None
def login(c,email,pwd='Demo123!'):
    d=req(c.post('/api/auth/login',json={'email':email,'password':pwd}));return {'Authorization':'Bearer '+d['access_token']}

with TestClient(app) as c:
    admin=login(c,'admin@onehms.com','Admin123!')
    # Make every patient-care service available and keep service payment off for a pure workflow matrix.
    for key in sorted(CARE_SERVICE_MODULES): req(c.patch(f'/api/modules/{key}',headers=admin,json={'enabled':True}))
    req(c.patch('/api/care/policy',headers=admin,json={'require_service_payment':False}))
    visit=req(c.post('/api/journey/register-and-open',headers=admin,json={
        'first_name':'Matrix','last_name':'Patient','sex':'Female','phone':'+255710222222',
        'reason':'Cross-department service matrix','priority':'EMERGENCY','payer_type':'EXEMPT',
        'authorization_status':'NOT_REQUIRED'
    }))
    ok('matrix patient visit opens',visit['status']=='OPEN')
    # Admin carries full module permissions; test the common native order -> departmental start -> completion contract.
    for key in sorted(CARE_SERVICE_MODULES):
        order=req(c.post(f"/api/care/visits/{visit['id']}/service-orders",headers=admin,json={
            'module_key':key,'title':f'{key} service','clinical_question':'Matrix verification','priority':'NORMAL','amount':0
        }))
        ok(f'{key}: doctor/service order contract creates queue item',order['module_key']==key and order['status']=='ORDERED')
        queue=req(c.get(f'/api/care/service-orders?module_key={key}',headers=admin))
        ok(f'{key}: departmental queue receives order',any(x['id']==order['id'] for x in queue))
        started=req(c.post(f"/api/care/service-orders/{order['id']}/start",headers=admin,json={}))
        ok(f'{key}: departmental work can start',started['status']=='IN_PROGRESS')
        done=req(c.post(f"/api/care/service-orders/{order['id']}/complete",headers=admin,json={'result_summary':f'{key} completed'}))
        ok(f'{key}: result returns to same visit',done['status']=='COMPLETED' and done['result_summary']==f'{key} completed')
    # Configuration remains authoritative for the same native pathway.
    first=sorted(CARE_SERVICE_MODULES)[0]
    req(c.patch(f'/api/modules/{first}',headers=admin,json={'enabled':False}))
    blocked=c.post(f"/api/care/visits/{visit['id']}/service-orders",headers=admin,json={'module_key':first,'title':'blocked test','amount':0})
    ok('module disable blocks native care order immediately',blocked.status_code==403)

print(f'CARE SERVICE MATRIX E2E: {len(checks)}/{len(checks)} PASS')
