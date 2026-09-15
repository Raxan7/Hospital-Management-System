import os, sys, tempfile
from pathlib import Path

DB=Path(tempfile.gettempdir())/'onehms_prescription_pharmacy_e2e.db'
try: DB.unlink()
except FileNotFoundError: pass
os.environ['DATABASE_URL']=f'sqlite:///{DB}'
os.environ['JWT_SECRET']='prescription-pharmacy-e2e-secret-12345678901234567890'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app

checks=[]
def ok(name,cond=True):
    if not cond: raise AssertionError(name)
    checks.append(name)
def req(r,code=200):
    if r.status_code!=code: raise AssertionError(f'{r.request.method} {r.request.url}: {r.status_code} {r.text}')
    return r.json() if r.text else None
def login(c,email,pwd):
    d=req(c.post('/api/auth/login',json={'email':email,'password':pwd}));return {'Authorization':'Bearer '+d['access_token']}

with TestClient(app) as c:
    admin=login(c,'admin@onehms.com','Admin123!')
    reception=login(c,'reception@onehms.com','Demo123!')
    doctor=login(c,'doctor@onehms.com','Demo123!')
    pharmacy=login(c,'pharmacy@onehms.com','Demo123!')
    cashier=login(c,'cashier@onehms.com','Demo123!')
    ok('demo users login')

    # Root cause regression: Doctor may prescribe but must not receive Inventory management access.
    denied=c.get('/api/inventory',headers=doctor)
    ok('doctor still cannot access inventory management',denied.status_code==403)
    catalog=req(c.get('/api/prescription-catalog',headers=doctor))
    para=next(x for x in catalog if x['name']=='Paracetamol 500mg')
    ok('doctor can access safe prescription catalogue',para['quantity']>0 and para['unit_price']==100)

    out=req(c.post('/api/inventory',headers=admin,json={
        'sku':'MED-AMOX-500-OOS','name':'Amoxicillin 500mg','category':'Medicine','quantity':0,'reorder_level':10,'unit_price':500
    }))
    ok('out-of-stock medicine seeded for pharmacy test',out['quantity']==0)
    catalog=req(c.get('/api/prescription-catalog',headers=doctor))
    amox=next(x for x in catalog if x['name']=='Amoxicillin 500mg')
    ok('catalog exposes unavailable medicine without inventory permission',amox['available'] is False and amox['quantity']==0)

    req(c.patch('/api/journey/settings',headers=admin,json={
        'consultation_fee':10000,'require_consultation_payment':True,'require_triage':False,
        'require_pharmacy_payment':True,'auto_assign_doctor':False
    }))
    req(c.post('/api/journey/doctor/shift/start',headers=doctor,json={'room_number':'OPD-RX'}))
    v=req(c.post('/api/journey/register-and-open',headers=reception,json={
        'first_name':'Rx','last_name':'Availability','sex':'Female','phone':'+255710000099','reason':'Prescription workflow test'
    }))
    req(c.post(f"/api/invoices/{v['consultation_invoice']['id']}/payments",headers=cashier,json={'amount':10000,'method':'CASH'}))
    v=req(c.post(f"/api/journey/visits/{v['id']}/claim",headers=doctor,json={}))
    ok('doctor opens paid visit',v['stage']=='WITH_DOCTOR')

    rx=req(c.post(f"/api/journey/visits/{v['id']}/prescriptions",headers=doctor,json={
        'source':'HOSPITAL','medicines':[
            {'inventory_item_id':para['id'],'medicine':para['name'],'dose':'500 mg','frequency':'TDS','duration':'3 days','quantity':6},
            {'inventory_item_id':amox['id'],'medicine':amox['name'],'dose':'500 mg','frequency':'TDS','duration':'5 days','quantity':15},
        ]
    }))
    ok('doctor can save hospital prescription',len(rx['created'])==2)
    ok('prescribing does not prematurely remove patient from doctor',rx['visit']['stage']=='WITH_DOCTOR')
    outc=req(c.post(f"/api/journey/visits/{v['id']}/outcome",headers=doctor,json={
        'outcome':'OUTPATIENT','pharmacy_choice':'HOSPITAL','note':'Use prescribed medicines'
    }))
    ok('doctor outcome moves file to pharmacy completion',outc['stage']=='CLOSING_PENDING_PHARMACY')

    blocked=c.post(f"/api/journey/visits/{v['id']}/pharmacy/prepare",headers=pharmacy,json={})
    ok('pharmacy billing blocks when prescribed stock is unavailable',blocked.status_code==409)
    detail=blocked.json()['detail']
    ok('stock error identifies unavailable prescription',detail['code']=='PHARMACY_STOCK_UNAVAILABLE' and any(x['medicine']=='Amoxicillin 500mg' for x in detail['items']))

    visit=req(c.get(f"/api/journey/visits/{v['id']}",headers=pharmacy))
    amox_rx=next(x for x in visit['prescriptions'] if x['medicine']=='Amoxicillin 500mg')
    para_rx=next(x for x in visit['prescriptions'] if x['medicine']=='Paracetamol 500mg')
    ok('patient journey exposes live stock availability',amox_rx['stock_available'] is False and para_rx['stock_available'] is True)

    external=req(c.patch(f"/api/prescriptions/{amox_rx['id']}/unavailable",headers=pharmacy,json={'reason':'Out of stock at hospital pharmacy'}))
    ok('pharmacy can redirect unavailable medicine externally',external['status']=='EXTERNAL')
    stale=c.patch(f"/api/prescriptions/{amox_rx['id']}/dispense",headers=pharmacy,json={})
    ok('externalized medicine cannot later be hospital-dispensed',stale.status_code==409)

    visit=req(c.get(f"/api/journey/visits/{v['id']}",headers=pharmacy))
    ev=next(x for x in reversed(visit['events']) if x['event_type']=='MEDICINE_UNAVAILABLE')
    ok('unavailability reason is written into visit timeline',ev['note']=='Out of stock at hospital pharmacy' and ev['details']['medicine']=='Amoxicillin 500mg')

    bill=req(c.post(f"/api/journey/visits/{v['id']}/pharmacy/prepare",headers=pharmacy,json={}))['invoice']
    ok('hospital bill excludes externalized medicine',bill['amount']==600)
    req(c.post(f"/api/invoices/{bill['id']}/payments",headers=cashier,json={'amount':600,'method':'CASH'}))
    req(c.patch(f"/api/prescriptions/{para_rx['id']}/dispense",headers=pharmacy,json={}))
    final=req(c.get(f"/api/journey/visits/{v['id']}",headers=doctor))
    ok('visit closes after available hospital medicine is dispensed',final['status']=='CLOSED')
    ok('external medicine remains documented in clinical prescription',next(x for x in final['prescriptions'] if x['id']==amox_rx['id'])['status']=='EXTERNAL')

print(f'PRESCRIPTION/PHARMACY E2E: PASS ({len(checks)}/{len(checks)})')
for i,n in enumerate(checks,1): print(f'{i:02d}. PASS - {n}')
