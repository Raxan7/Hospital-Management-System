import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / 'smoke.db'
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB}'
if TEST_DB.exists(): TEST_DB.unlink()

from fastapi.testclient import TestClient
from app.main import app


def run():
    with TestClient(app) as c:
        def call(method, path, expected=200, **kwargs):
            r = getattr(c, method)(path, **kwargs)
            assert r.status_code == expected, f'{method.upper()} {path}: {r.status_code} {r.text}'
            return r.json() if 'application/json' in r.headers.get('content-type', '') else r.text

        assert 'NEOVAM HMS' in call('get', '/')
        login = call('post', '/api/auth/login', json={'email':'admin@onehms.com','password':'Admin123!'})
        H = {'Authorization': f"Bearer {login['access_token']}"}
        patient = call('post','/api/patients',headers=H,json={'first_name':'Smoke','last_name':'Patient','sex':'Female'})
        appointment = call('post','/api/appointments',headers=H,json={'patient_id':patient['id'],'scheduled_at':'2026-09-10T10:00:00','department':'OPD'})
        call('patch',f"/api/appointments/{appointment['id']}/status",headers=H,json={'status':'ARRIVED'})
        encounter = call('post','/api/encounters',headers=H,json={'patient_id':patient['id'],'appointment_id':appointment['id'],'encounter_type':'OPD','chief_complaint':'Fever'})
        call('post','/api/vitals',headers=H,json={'encounter_id':encounter['id'],'temperature_c':38.0,'pulse':90,'systolic':120,'diastolic':80,'spo2':98})
        call('patch',f"/api/encounters/{encounter['id']}/consultation",headers=H,json={'clinical_notes':'Stable','diagnosis':'Viral syndrome','status':'OPEN'})
        lab = call('post','/api/lab-orders',headers=H,json={'encounter_id':encounter['id'],'test_name':'CBC'})
        call('patch',f"/api/lab-orders/{lab['id']}/result",headers=H,json={'result':'Normal','verified':True})
        item = call('post','/api/inventory',headers=H,json={'sku':'SMOKE-MED','name':'Smoke Medicine','category':'Medicine','quantity':10,'reorder_level':2,'unit_price':500})
        rx = call('post','/api/prescriptions',headers=H,json={'encounter_id':encounter['id'],'inventory_item_id':item['id'],'medicine':'Smoke Medicine','dose':'1 tab','frequency':'BID','duration':'3 days','quantity':4})
        call('patch',f"/api/prescriptions/{rx['id']}/dispense",headers=H)
        call('patch',f"/api/prescriptions/{rx['id']}/dispense",expected=400,headers=H)
        invoice = call('post','/api/invoices',headers=H,json={'patient_id':patient['id'],'amount':10000,'description':'Consultation'})
        call('post',f"/api/invoices/{invoice['id']}/payments",headers=H,json={'amount':4000,'method':'CASH'})
        call('post',f"/api/invoices/{invoice['id']}/payments",headers=H,json={'amount':6000,'method':'MOBILE_MONEY','reference':'SMOKE'})
        call('post',f"/api/invoices/{invoice['id']}/payments",expected=400,headers=H,json={'amount':1,'method':'CASH'})
        ward = call('post','/api/wards',headers=H,json={'name':'Smoke Ward','ward_type':'GENERAL'})
        bed = call('post','/api/beds',headers=H,json={'ward_id':ward['id'],'code':'SW-01'})
        admission = call('post','/api/admissions',headers=H,json={'patient_id':patient['id'],'ward_id':ward['id'],'bed_id':bed['id']})
        call('post','/api/admissions',expected=400,headers=H,json={'patient_id':patient['id'],'ward_id':ward['id'],'bed_id':bed['id']})
        call('patch',f"/api/admissions/{admission['id']}/discharge",headers=H)
        call('get','/api/operations/theatre',expected=403,headers=H)
        call('patch','/api/modules/theatre',headers=H,json={'enabled':True})
        call('post','/api/operations/theatre',headers=H,json={'patient_id':patient['id'],'title':'Surgical review','status':'PLANNED','details':{}})
        role = call('post','/api/roles',headers=H,json={'name':'Smoke Viewer','permissions':{'patients':['VIEW']}})
        call('post','/api/users',headers=H,json={'full_name':'Smoke Viewer','email':'smoke.viewer@example.com','password':'secret12','role_id':role['id']})
        viewer = call('post','/api/auth/login',json={'email':'smoke.viewer@example.com','password':'secret12'})
        VH = {'Authorization': f"Bearer {viewer['access_token']}"}
        call('get','/api/patients',headers=VH)
        call('post','/api/patients',expected=403,headers=VH,json={'first_name':'Blocked','last_name':'Write'})
        print('ONE HMS SMOKE TEST: PASS')


if __name__ == '__main__':
    try: run()
    finally:
        if TEST_DB.exists(): TEST_DB.unlink()
