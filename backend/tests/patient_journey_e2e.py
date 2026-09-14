import os, sys, tempfile
from pathlib import Path

DB = Path(tempfile.gettempdir())/'onehms_journey_e2e.db'
try: DB.unlink()
except FileNotFoundError: pass
os.environ['DATABASE_URL']=f'sqlite:///{DB}'
os.environ['JWT_SECRET']='patient-journey-e2e-secret-12345678901234567890'
os.environ.pop('HMS_SMS_WEBHOOK_URL',None)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app

checks=[]
def ok(name, cond=True):
    if not cond: raise AssertionError(name)
    checks.append(name)

def req(r, code=200):
    if r.status_code != code:
        raise AssertionError(f'{r.request.method} {r.request.url}: {r.status_code} {r.text}')
    return r.json() if r.text else None

def login(c,email,pwd):
    d=req(c.post('/api/auth/login',json={'email':email,'password':pwd}));return {'Authorization':'Bearer '+d['access_token']}

with TestClient(app) as c:
    admin=login(c,'admin@onehms.com','Admin123!')
    reception=login(c,'reception@onehms.com','Demo123!')
    doctor=login(c,'doctor@onehms.com','Demo123!')
    lab=login(c,'lab@onehms.com','Demo123!')
    pharmacy=login(c,'pharmacy@onehms.com','Demo123!')
    cashier=login(c,'cashier@onehms.com','Demo123!')
    nurse=login(c,'nurse@onehms.com','Demo123!')
    ok('all demo workflow users login')

    s=req(c.patch('/api/journey/settings',headers=admin,json={
        'consultation_fee':12000,'consultation_fee_label':'OPD doctor consultation','currency':'TZS',
        'require_consultation_payment':True,'require_triage':False,'require_lab_verification':False,
        'require_pharmacy_payment':True,'sms_enabled':True,'sms_lab_results':True,'auto_assign_doctor':True
    }))
    ok('workflow fee configurable',s['consultation_fee']==12000)
    ok('triage configurable off',s['require_triage'] is False)

    shift=req(c.post('/api/journey/doctor/shift/start',headers=doctor,json={'room_number':'OPD-03'}))
    ok('doctor shift starts',shift['room_number']=='OPD-03' and shift['availability']=='AVAILABLE')
    ok('doctor availability listed',len(req(c.get('/api/journey/doctors',headers=reception)))>=1)

    v=req(c.post('/api/journey/register-and-open',headers=reception,json={
        'first_name':'Journey','last_name':'Patient','sex':'Female','phone':'+255710000001','address':'Dodoma',
        'reason':'Headache, nausea and joint pain','priority':'NORMAL'
    }))
    vid=v['id']; patient_id=v['patient_id']; file1=v['file_no']; invoice=v['consultation_invoice']
    ok('reception creates permanent patient number',v['patient_no'].startswith('P'))
    ok('reception creates visit-specific file number',file1.startswith('F'))
    ok('new file waits for consultation payment',v['stage']=='AWAITING_PAYMENT')
    ok('consultation invoice created',invoice['amount']==12000 and invoice['status']=='UNPAID')
    ok('doctor/reception can search open file by patient number',any(x['id']==vid for x in req(c.get('/api/journey/visits?q='+v['patient_no']+'&status=OPEN',headers=doctor))))
    ok('open file can be searched directly by visit file number',any(x['id']==vid for x in req(c.get('/api/journey/visits?q='+file1+'&status=OPEN',headers=doctor))))
    ok('unpaid patient not in doctor queue',all(x['id']!=vid for x in req(c.get('/api/journey/doctor/queue',headers=doctor))))

    q=req(c.get('/api/journey/billing-queue',headers=cashier))
    item=next(x for x in q if x['visit_id']==vid and x['kind']=='CONSULTATION')
    ok('cashier sees consultation charge')
    req(c.post(f"/api/invoices/{item['invoice']['id']}/payments",headers=cashier,json={'amount':12000,'method':'MOBILE_MONEY','reference':'MPESA-001'}))
    v=req(c.get(f'/api/journey/visits/{vid}',headers=reception))
    ok('payment advances visit to doctor queue',v['stage']=='WAITING_DOCTOR')
    ok('available doctor auto assigned',v['doctor_name']=='Dr. Neema Mushi' and v['room']=='OPD-03')
    ok('queue position calculated',v['queue_position'] is not None)

    v=req(c.post(f'/api/journey/visits/{vid}/claim',headers=doctor,json={}))
    ok('doctor opens paid file',v['stage']=='WITH_DOCTOR')
    v=req(c.patch(f'/api/journey/visits/{vid}/consultation',headers=doctor,json={
        'chief_complaint':'Headache, nausea and joint pain','clinical_notes':'Symptoms for two days. Hydrated.','diagnosis':'Malaria versus viral illness'
    }))
    ok('doctor clinical notes saved',v['encounter']['diagnosis']=='Malaria versus viral illness')

    res=req(c.post(f'/api/journey/visits/{vid}/lab-orders',headers=doctor,json={'tests':['Malaria RDT','Full Blood Count']}))
    ok('doctor can order multiple lab tests',len(res['created'])==2)
    ok('visit moves to laboratory',res['visit']['stage']=='LAB_PENDING')
    labq=req(c.get('/api/journey/lab-queue',headers=lab)); orders=[x for x in labq if x['visit_id']==vid]
    ok('lab technician sees ordered tests',len(orders)==2)
    req(c.patch(f"/api/lab-orders/{orders[0]['id']}/result",headers=lab,json={'result':'Positive for P. falciparum','verified':True}))
    mid=req(c.get(f'/api/journey/visits/{vid}',headers=doctor));ok('file waits until all lab results entered',mid['stage']=='LAB_PENDING')
    req(c.patch(f"/api/lab-orders/{orders[1]['id']}/result",headers=lab,json={'result':'Hb 12.8 g/dL; WBC 6.1','verified':True}))
    v=req(c.get(f'/api/journey/visits/{vid}',headers=doctor))
    ok('all lab results return file to doctor review',v['stage']=='LAB_RESULTS_READY')
    ok('original available doctor is preferred after lab',v['doctor_name']=='Dr. Neema Mushi' and v['room']=='OPD-03')
    sms=req(c.get('/api/journey/sms-outbox',headers=reception))
    msg=next(x for x in sms if x['visit_id']==vid and x['event_type']=='LAB_RESULTS_READY')
    ok('patient SMS queued after results',msg['status']=='QUEUED')
    ok('SMS contains room but not sensitive result', 'OPD-03' in msg['message'] and 'Positive' not in msg['message'])

    req(c.post(f'/api/journey/visits/{vid}/claim',headers=doctor,json={}))
    inv=req(c.get('/api/inventory',headers=pharmacy)); med=next(x for x in inv if x['name']=='Paracetamol 500mg'); before=med['quantity']
    v=req(c.post(f'/api/journey/visits/{vid}/prescriptions',headers=doctor,json={'source':'HOSPITAL','medicines':[{
        'inventory_item_id':med['id'],'medicine':med['name'],'dose':'500 mg','frequency':'3 times daily','duration':'5 days','quantity':6,'instructions':'After food'
    }]}))
    ok('doctor chooses hospital pharmacy',v['visit']['pharmacy_choice']=='HOSPITAL')
    out=req(c.post(f'/api/journey/visits/{vid}/outcome',headers=doctor,json={'outcome':'OUTPATIENT','pharmacy_choice':'HOSPITAL','note':'Finish medicine course'}))
    ok('doctor close decision waits for pharmacy completion',out['status']=='OPEN' and out['stage']=='CLOSING_PENDING_PHARMACY' and out['doctor_close_requested'])
    prepared=req(c.post(f'/api/journey/visits/{vid}/pharmacy/prepare',headers=pharmacy,json={}))
    pinv=prepared['invoice'];ok('pharmacy medicine invoice uses inventory price',pinv['amount']==600)
    req(c.post(f"/api/invoices/{pinv['id']}/payments",headers=cashier,json={'amount':600,'method':'CASH','reference':'RCPT-001'}))
    paid=req(c.get(f'/api/journey/visits/{vid}',headers=pharmacy));ok('medicine payment recorded before dispense',paid['pharmacy_invoice']['status']=='PAID')
    rx=paid['prescriptions'][0]
    req(c.patch(f"/api/prescriptions/{rx['id']}/dispense",headers=pharmacy,json={}))
    closed=req(c.get(f'/api/journey/visits/{vid}',headers=doctor))
    ok('doctor-authorized outpatient file closes after paid dispense',closed['status']=='CLOSED' and closed['stage']=='CLOSED')
    stock=req(c.get('/api/inventory',headers=pharmacy));after=next(x for x in stock if x['id']==med['id'])['quantity'];ok('pharmacy dispensing reduces stock',after==before-6)

    v2=req(c.post('/api/journey/visits',headers=reception,json={'patient_id':patient_id,'reason':'Follow-up visit','priority':'NORMAL'}))
    ok('new visit opens a new file for same patient',v2['file_no']!=file1 and v2['status']=='OPEN')
    req(c.post(f"/api/invoices/{v2['consultation_invoice']['id']}/payments",headers=cashier,json={'amount':12000,'method':'CASH'}))
    req(c.post(f"/api/journey/visits/{v2['id']}/claim",headers=doctor,json={}))
    ext=req(c.post(f"/api/journey/visits/{v2['id']}/prescriptions",headers=doctor,json={'source':'EXTERNAL','medicines':[{
        'medicine':'Amoxicillin 500mg','dose':'500 mg','frequency':'3 times daily','duration':'5 days','quantity':15
    }]}))
    ok('external pharmacy choice supported',ext['visit']['pharmacy_choice']=='EXTERNAL')
    extclose=req(c.post(f"/api/journey/visits/{v2['id']}/outcome",headers=doctor,json={'outcome':'OUTPATIENT','pharmacy_choice':'EXTERNAL','note':'Purchase outside hospital'}))
    ok('external pharmacy outpatient file closes immediately by doctor',extclose['status']=='CLOSED')
    ok('external prescription not deducted from hospital stock',extclose['prescriptions'][0]['status']=='EXTERNAL')

    # Admission path with a third patient.
    v3=req(c.post('/api/journey/register-and-open',headers=reception,json={
        'first_name':'Inpatient','last_name':'Case','sex':'Male','phone':'+255710000003','reason':'Severe dehydration','priority':'URGENT'
    }))
    req(c.post(f"/api/invoices/{v3['consultation_invoice']['id']}/payments",headers=cashier,json={'amount':12000,'method':'CASH'}))
    req(c.post(f"/api/journey/visits/{v3['id']}/claim",headers=doctor,json={}))
    adreq=req(c.post(f"/api/journey/visits/{v3['id']}/outcome",headers=doctor,json={'outcome':'ADMIT','note':'Needs IV fluids and observation'}))
    ok('doctor makes admission decision',adreq['stage']=='ADMISSION_PENDING' and adreq['admission_requested'])
    aq=req(c.get('/api/journey/admission-queue',headers=nurse));ok('ward sees pending admission',any(x['id']==v3['id'] for x in aq['pending']))
    wards=req(c.get('/api/wards',headers=nurse));beds=req(c.get('/api/beds',headers=nurse));ward=wards[0];bed=next(x for x in beds if x['ward_id']==ward['id'] and x['status']=='AVAILABLE')
    admitted=req(c.post(f"/api/journey/visits/{v3['id']}/admit",headers=nurse,json={'ward_id':ward['id'],'bed_id':bed['id']}))
    ok('ward nurse assigns bed and file remains open',admitted['stage']=='ADMITTED' and admitted['status']=='OPEN')
    req(c.post(f"/api/journey/visits/{v3['id']}/progress",headers=nurse,json={'note_type':'NURSING','note':'IV fluids commenced. Vitals stable.'}))
    req(c.post(f"/api/journey/visits/{v3['id']}/progress",headers=doctor,json={'note_type':'DOCTOR','note':'Improved clinically; tolerating oral fluids.'}))
    detail=req(c.get(f"/api/journey/visits/{v3['id']}",headers=doctor));ok('inpatient progress stays in same open file',len(detail['progress'])==2 and detail['status']=='OPEN')
    dd=req(c.post(f"/api/journey/visits/{v3['id']}/discharge-decision",headers=doctor,json={'summary':'Stable for discharge. Continue oral hydration and return if symptoms recur.'}))
    ok('doctor approves inpatient discharge',dd['stage']=='DISCHARGE_PENDING')
    final=req(c.post(f"/api/journey/visits/{v3['id']}/discharge",headers=nurse,json={}))
    ok('ward completes discharge and closes file',final['status']=='CLOSED' and final['stage']=='CLOSED')
    beds2=req(c.get('/api/beds',headers=nurse));ok('bed released after discharge',next(x for x in beds2 if x['id']==bed['id'])['status']=='AVAILABLE')

    # Triage policy path.
    req(c.patch('/api/journey/settings',headers=admin,json={'require_triage':True}))
    v4=req(c.post('/api/journey/register-and-open',headers=reception,json={'first_name':'Triage','last_name':'Case','sex':'Female','reason':'Fever'}))
    req(c.post(f"/api/invoices/{v4['consultation_invoice']['id']}/payments",headers=cashier,json={'amount':12000,'method':'CASH'}))
    tr=req(c.get(f"/api/journey/visits/{v4['id']}",headers=nurse));ok('triage policy routes paid patient to triage',tr['stage']=='TRIAGE')
    tr2=req(c.post(f"/api/journey/visits/{v4['id']}/triage",headers=nurse,json={'temperature_c':38.2,'pulse':94,'systolic':118,'diastolic':76,'spo2':98,'weight_kg':61.2}))
    ok('triage completion routes to doctor',tr2['stage']=='WAITING_DOCTOR')

    # Availability / attendance and room collision.
    collision=c.post('/api/journey/doctor/shift/start',headers=admin,json={'room_number':'OPD-03'})
    ok('active doctor room cannot be double-assigned',collision.status_code==409)
    req(c.patch('/api/journey/doctor/availability',headers=doctor,json={'availability':'AWAY'}));d=req(c.get('/api/journey/doctors',headers=reception));ok('doctor can mark away',any(x['doctor_id']==shift['doctor_id'] and x['availability']=='AWAY' for x in d))
    req(c.patch('/api/journey/doctor/availability',headers=doctor,json={'availability':'AVAILABLE'}))
    stopped=req(c.post('/api/journey/doctor/shift/stop',headers=doctor,json={}));ok('doctor shift end recorded',stopped['ended_at'] is not None)
    attendance=req(c.get('/api/journey/admin/doctor-attendance',headers=admin));ok('admin can audit doctor availability time',any(x['doctor_name']=='Dr. Neema Mushi' for x in attendance['totals']))

    # Configuration remains authoritative for admission workflow.
    req(c.patch('/api/modules/wards',headers=admin,json={'enabled':False}))
    blocked=c.get('/api/journey/admission-queue',headers=nurse);ok('disabled wards configuration immediately blocks journey admission',blocked.status_code==403)
    req(c.patch('/api/modules/wards',headers=admin,json={'enabled':True}));me=req(c.get('/api/me',headers=nurse));ok('re-enabled wards visible immediately',me['modules']['wards'] is True)

    # Patient history keeps separate closed visit files.
    hist=req(c.get('/api/journey/visits?q=Journey',headers=reception));ok('patient visit list keeps historical files',len([x for x in hist if x['patient_id']==patient_id])>=2)
    ok('closed historical files stay closed',len([x for x in hist if x['patient_id']==patient_id and x['status']=='CLOSED'])>=2)

print(f'PATIENT JOURNEY E2E: PASS ({len(checks)}/{len(checks)})')
for i,n in enumerate(checks,1): print(f'{i:02d}. PASS - {n}')
