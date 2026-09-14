import os, sys, tempfile
from pathlib import Path
from datetime import datetime, timedelta

DB = Path(tempfile.gettempdir()) / 'onehms_care_pathways_e2e.db'
try: DB.unlink()
except FileNotFoundError: pass
os.environ['DATABASE_URL'] = f'sqlite:///{DB}'
os.environ['JWT_SECRET'] = 'care-pathways-e2e-secret-12345678901234567890'
os.environ.pop('HMS_SMS_WEBHOOK_URL', None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app

checks=[]
def ok(name, cond=True, detail=''):
    if not cond: raise AssertionError(detail or name)
    checks.append(name)

def req(r, code=200):
    if r.status_code != code:
        raise AssertionError(f'{r.request.method} {r.request.url}: {r.status_code} {r.text}')
    return r.json() if r.text else None

def login(c,email,pwd='Demo123!'):
    d=req(c.post('/api/auth/login',json={'email':email,'password':pwd}))
    return {'Authorization':'Bearer '+d['access_token']}

def pay(c,h,invoice,amount=None,ref='TEST'):
    amt=amount if amount is not None else invoice['balance']
    return req(c.post(f"/api/invoices/{invoice['id']}/payments",headers=h,json={'amount':amt,'method':'CASH','reference':ref}))

def open_patient(c,reception,first,last,reason='Care pathway test',priority='NORMAL',**extra):
    payload={'first_name':first,'last_name':last,'sex':'Female','phone':'+255710123456','reason':reason,'priority':priority}
    payload.update(extra)
    return req(c.post('/api/journey/register-and-open',headers=reception,json=payload))

with TestClient(app) as c:
    admin=login(c,'admin@onehms.com','Admin123!')
    reception=login(c,'reception@onehms.com')
    doctor=login(c,'doctor@onehms.com')
    nurse=login(c,'nurse@onehms.com')
    cashier=login(c,'cashier@onehms.com')
    surgeon=login(c,'surgeon@onehms.com')
    pharmacy=login(c,'pharmacy@onehms.com')
    ok('seeded multidisciplinary users login')

    # Enable all services exercised by this suite.
    for key in ['radiology','theatre','icu','wards','beds','nursing','physiotherapy','mortuary','emergency']:
        req(c.patch(f'/api/modules/{key}',headers=admin,json={'enabled':True}))
    me=req(c.get('/api/me',headers=admin))
    ok('required care pathway modules enabled', all(me['modules'].get(k) for k in ['radiology','theatre','wards','beds','physiotherapy','mortuary']))

    req(c.patch('/api/journey/settings',headers=admin,json={
        'consultation_fee':10000,'require_consultation_payment':True,'require_triage':False,
        'require_pharmacy_payment':True,'auto_assign_doctor':True,'sms_enabled':True
    }))
    pol=req(c.patch('/api/care/policy',headers=admin,json={
        'emergency_bypass_payment':True,'require_service_payment':True,
        'require_surgical_consent':True,'require_preop_checklist':True,
        'require_inpatient_financial_clearance':True,'require_discharge_plan':True,
        'auto_followup_sms':True
    }))
    ok('extended care policy configurable',pol['require_service_payment'] and pol['require_discharge_plan'])

    # Create real departmental demo users from predefined roles.
    roles=req(c.get('/api/roles',headers=admin)); by_name={r['name']:r for r in roles}
    for role,email,name in [
        ('Radiographer','radiographer@onehms.com','Radiographer Demo'),
        ('Physiotherapist','physio@onehms.com','Physiotherapist Demo'),
    ]:
        req(c.post('/api/users',headers=admin,json={'full_name':name,'email':email,'password':'Demo123!','role_id':by_name[role]['id']}))
    radiographer=login(c,'radiographer@onehms.com'); physio=login(c,'physio@onehms.com')
    ok('specialist departmental users can login')

    shift=req(c.post('/api/journey/doctor/shift/start',headers=doctor,json={'room_number':'OPD-12'}))
    ok('doctor shift available for routing',shift['availability']=='AVAILABLE')

    # ------------------------------------------------------------------
    # Emergency care: clinical care must not wait for cash payment.
    # ------------------------------------------------------------------
    ev=open_patient(c,reception,'Emergency','Patient','Severe abdominal pain',priority='EMERGENCY')
    ok('emergency visit bypasses cashier gate',ev['stage']=='TRIAGE')
    ok('emergency consultation invoice remains trackable',ev['consultation_invoice']['status']=='UNPAID')
    care=req(c.get(f"/api/care/visits/{ev['id']}",headers=doctor))
    ok('emergency visit is natively tagged to emergency department',care['administrative']['department']=='EMERGENCY' and care['administrative']['emergency_payment_bypass'])
    req(c.post(f"/api/journey/visits/{ev['id']}/triage",headers=nurse,json={'pulse':116,'systolic':102,'diastolic':68,'spo2':98,'temperature_c':38.3}))
    em2=req(c.get(f"/api/journey/visits/{ev['id']}",headers=doctor))
    ok('emergency triage routes to doctor without prior payment',em2['stage']=='WAITING_DOCTOR')

    # ------------------------------------------------------------------
    # Cash radiology workflow: fee, queue, result, doctor review.
    # ------------------------------------------------------------------
    rv=open_patient(c,reception,'Radiology','Cash','Chest pain and cough')
    pay(c,cashier,rv['consultation_invoice'],ref='CONS-RAD')
    req(c.post(f"/api/journey/visits/{rv['id']}/claim",headers=doctor,json={}))
    order=req(c.post(f"/api/care/visits/{rv['id']}/service-orders",headers=doctor,json={
        'module_key':'RADIOLOGY','title':'Chest X-ray PA','clinical_question':'Exclude pneumonia','priority':'URGENT','amount':5000
    }))
    ok('doctor can order radiology natively from visit',order['module_key']=='radiology' and order['status']=='AWAITING_PAYMENT')
    bq=req(c.get('/api/journey/billing-queue',headers=cashier))
    bill=next(x for x in bq if x['visit_id']==rv['id'] and x['kind']=='RADIOLOGY')
    ok('radiology charge appears in normal cashier queue',bill['invoice']['balance']==5000)
    blocked=c.post(f"/api/care/service-orders/{order['id']}/start",headers=radiographer,json={})
    ok('cash specialist service cannot start before required payment',blocked.status_code==400)
    pay(c,cashier,bill['invoice'],ref='RAD-001')
    started=req(c.post(f"/api/care/service-orders/{order['id']}/start",headers=radiographer,json={}))
    ok('radiographer starts paid order from departmental queue',started['status']=='IN_PROGRESS')
    done=req(c.post(f"/api/care/service-orders/{order['id']}/complete",headers=radiographer,json={'result_summary':'No focal consolidation. Heart size normal.'}))
    ok('radiology completion is linked to same visit',done['status']=='COMPLETED' and done['result_summary'].startswith('No focal'))
    oprecs=req(c.get('/api/operations/radiology',headers=radiographer))
    rec=next(x for x in oprecs if x['id']==done['service_record_id'])
    ok('completed order also appears in existing radiology module',rec['details']['visit_id']==rv['id'])
    ok('radiographer verification permission is respected',rec['verified'] is True)
    rv2=req(c.get(f"/api/journey/visits/{rv['id']}",headers=doctor))
    ok('specialist result returns outpatient to doctor review',rv2['stage']=='LAB_RESULTS_READY')
    close=req(c.post(f"/api/journey/visits/{rv['id']}/outcome",headers=doctor,json={'outcome':'OUTPATIENT','pharmacy_choice':'NONE','note':'Supportive care'}))
    ok('doctor can close after specialist work is complete',close['status']=='CLOSED')

    # ------------------------------------------------------------------
    # Insurance authorization: invoice remains but care does not wait for cash.
    # ------------------------------------------------------------------
    iv=open_patient(c,reception,'Insurance','Patient','Back pain',payer_type='INSURANCE',payer_name='Demo Health Fund',member_no='NH-1001',authorization_status='APPROVED')
    ok('authorized insurance visit skips cash consultation gate',iv['stage']=='WAITING_DOCTOR' and iv['consultation_invoice']['status']=='UNPAID')
    req(c.post(f"/api/journey/visits/{iv['id']}/claim",headers=doctor,json={}))
    io=req(c.post(f"/api/care/visits/{iv['id']}/service-orders",headers=doctor,json={'module_key':'radiology','title':'Lumbar X-ray','clinical_question':'Persistent pain','amount':7500}))
    ok('authorized insurance specialist order is receivable but not cash-gated',io['status']=='ORDERED' and io['invoice']['status']=='UNPAID')
    req(c.post(f"/api/care/service-orders/{io['id']}/start",headers=radiographer,json={}))
    req(c.post(f"/api/care/service-orders/{io['id']}/complete",headers=radiographer,json={'result_summary':'No acute bony injury.'}))
    ok('authorized insurer service can complete before invoice settlement')
    fin=req(c.get(f"/api/care/visits/{iv['id']}",headers=doctor))['financial']
    ok('insurance receivable remains visible in visit financial summary',fin['balance']>=17500)

    # ------------------------------------------------------------------
    # Pharmacy: hospital medicine cannot leave before required cash payment;
    # authorized sponsored care can proceed while the insurer receivable remains.
    # ------------------------------------------------------------------
    med=next(x for x in req(c.get('/api/inventory',headers=admin)) if x['name']=='Paracetamol 500mg')
    pv=open_patient(c,reception,'Pharmacy','Cash','Pain treatment')
    pay(c,cashier,pv['consultation_invoice'],ref='CONS-PHARM')
    req(c.post(f"/api/journey/visits/{pv['id']}/claim",headers=doctor,json={}))
    req(c.post(f"/api/journey/visits/{pv['id']}/prescriptions",headers=doctor,json={'source':'HOSPITAL','medicines':[{'inventory_item_id':med['id'],'medicine':med['name'],'dose':'500 mg','frequency':'3 times daily','duration':'3 days','quantity':6}]}))
    req(c.post(f"/api/journey/visits/{pv['id']}/outcome",headers=doctor,json={'outcome':'OUTPATIENT','pharmacy_choice':'HOSPITAL','note':'Analgesia'}))
    prepared=req(c.post(f"/api/journey/visits/{pv['id']}/pharmacy/prepare",headers=pharmacy,json={}))
    rx=req(c.get(f"/api/journey/visits/{pv['id']}",headers=pharmacy))['prescriptions'][0]
    blocked_dispense=c.patch(f"/api/prescriptions/{rx['id']}/dispense",headers=pharmacy,json={})
    ok('cash hospital pharmacy blocks medicine release before payment',blocked_dispense.status_code==409 and blocked_dispense.json()['detail']['code']=='PHARMACY_PAYMENT_REQUIRED')
    pay(c,cashier,prepared['invoice'],ref='PHARM-001')
    req(c.patch(f"/api/prescriptions/{rx['id']}/dispense",headers=pharmacy,json={}))
    ok('paid pharmacy medicine can be dispensed and closes doctor-authorized visit',req(c.get(f"/api/journey/visits/{pv['id']}",headers=doctor))['status']=='CLOSED')

    sp=open_patient(c,reception,'Sponsored','Pharmacy','Insured medicine',payer_type='INSURANCE',payer_name='Demo Health Fund',member_no='RX-100',authorization_status='APPROVED')
    req(c.post(f"/api/journey/visits/{sp['id']}/claim",headers=doctor,json={}))
    req(c.post(f"/api/journey/visits/{sp['id']}/prescriptions",headers=doctor,json={'source':'HOSPITAL','medicines':[{'inventory_item_id':med['id'],'medicine':med['name'],'dose':'500 mg','frequency':'2 times daily','duration':'2 days','quantity':4}]}))
    req(c.post(f"/api/journey/visits/{sp['id']}/outcome",headers=doctor,json={'outcome':'OUTPATIENT','pharmacy_choice':'HOSPITAL','note':'Insured medicine'}))
    sprep=req(c.post(f"/api/journey/visits/{sp['id']}/pharmacy/prepare",headers=pharmacy,json={}))
    sprx=req(c.get(f"/api/journey/visits/{sp['id']}",headers=pharmacy))['prescriptions'][0]
    ok('authorized insurer pharmacy bill remains an unpaid receivable',sprep['invoice']['status']=='UNPAID')
    req(c.patch(f"/api/prescriptions/{sprx['id']}/dispense",headers=pharmacy,json={}))
    ok('authorized sponsored medicine may dispense without cash collection',req(c.get(f"/api/journey/visits/{sp['id']}",headers=doctor))['status']=='CLOSED')

    # ------------------------------------------------------------------
    # Internal referral integrates with department order, not a duplicate workflow.
    # ------------------------------------------------------------------
    ref=req(c.post(f"/api/care/visits/{iv['id']}/referrals",headers=doctor,json={'kind':'INTERNAL','target_module':'physiotherapy','reason':'Assess mechanical back pain'}))
    ok('doctor creates internal referral',ref['status']=='REQUESTED')
    pq=req(c.get('/api/care/service-orders?module_key=physiotherapy',headers=physio))
    po=next(x for x in pq if x['visit_id']==iv['id'])
    req(c.post(f"/api/care/service-orders/{po['id']}/start",headers=physio,json={}))
    req(c.post(f"/api/care/service-orders/{po['id']}/complete",headers=physio,json={'result_summary':'Mechanical pain; exercise programme issued.'}))
    ivcare=req(c.get(f"/api/care/visits/{iv['id']}",headers=doctor))
    iref=next(x for x in ivcare['referrals'] if x['id']==ref['id'])
    ok('completing referred service automatically completes referral',iref['status']=='COMPLETED')

    # ------------------------------------------------------------------
    # Surgery -> recovery -> ward admission -> inpatient care -> discharge.
    # ------------------------------------------------------------------
    sv=open_patient(c,reception,'Surgical','Patient','Acute appendicitis suspected')
    pay(c,cashier,sv['consultation_invoice'],ref='CONS-SURG')
    req(c.post(f"/api/journey/visits/{sv['id']}/claim",headers=doctor,json={}))
    req(c.patch(f"/api/journey/visits/{sv['id']}/consultation",headers=doctor,json={'chief_complaint':'RIF pain','clinical_notes':'Tenderness RIF','diagnosis':'Acute appendicitis'}))
    sc=req(c.post(f"/api/care/visits/{sv['id']}/surgery",headers=doctor,json={'procedure_name':'Appendicectomy','clinical_question':'Acute appendicitis','urgency':'URGENT','amount':50000}))
    ok('doctor request creates structured theatre case',sc['status']=='REQUESTED')
    sbill=next(x for x in req(c.get('/api/journey/billing-queue',headers=cashier)) if x['visit_id']==sv['id'] and x['kind']=='THEATRE')
    pay(c,cashier,sbill['invoice'],ref='SURG-001')
    future=(datetime.utcnow()+timedelta(hours=1)).isoformat()
    sc=req(c.patch(f"/api/care/surgery/{sc['id']}/schedule",headers=surgeon,json={'theatre_room':'TH-01','scheduled_at':future,'surgeon_id':None,'anaesthetist_id':None}))
    ok('theatre case can be scheduled',sc['status']=='SCHEDULED' and sc['theatre_room']=='TH-01')
    fail=c.post(f"/api/care/surgery/{sc['id']}/start",headers=surgeon,json={})
    ok('surgery cannot start without required consent/checklist',fail.status_code==400)
    req(c.post(f"/api/care/surgery/{sc['id']}/consent",headers=surgeon,json={'consent_type':'SURGERY','status':'SIGNED','signed_by_name':'Surgical Patient','relationship':'SELF','notes':'Procedure explained'}))
    pre=req(c.post(f"/api/care/surgery/{sc['id']}/preop",headers=surgeon,json={'checklist':{'identity':True,'site':True,'allergy':True,'blood':True},'anaesthesia_note':'ASA II; fasting confirmed'}))
    ok('signed consent unlocks pre-op readiness',pre['status']=='PREOP_READY')
    req(c.post(f"/api/care/surgery/{sc['id']}/start",headers=surgeon,json={}))
    comp=req(c.post(f"/api/care/surgery/{sc['id']}/complete",headers=surgeon,json={'operative_note':'Inflamed appendix removed; haemostasis achieved.'}))
    ok('operative note moves case to recovery',comp['status']=='RECOVERY')
    recovery=req(c.post(f"/api/care/surgery/{sc['id']}/recovery",headers=surgeon,json={'recovery_note':'Stable in recovery; pain controlled.','destination':'WARD'}))
    ok('recovery completes surgery',recovery['status']=='COMPLETED')
    sv2=req(c.get(f"/api/journey/visits/{sv['id']}",headers=nurse))
    ok('post-operative ward destination creates admission request naturally',sv2['stage']=='ADMISSION_PENDING' and sv2['admission_requested'])

    wards=req(c.get('/api/wards',headers=nurse)); beds=req(c.get('/api/beds',headers=nurse)); w1=wards[0]; b1=next(x for x in beds if x['ward_id']==w1['id'] and x['status']=='AVAILABLE')
    adm=req(c.post(f"/api/journey/visits/{sv['id']}/admit",headers=nurse,json={'patient_id':sv2['patient_id'],'encounter_id':sv2['encounter_id'],'ward_id':w1['id'],'bed_id':b1['id'],'diagnosis':'Post appendicectomy'}))
    ok('ward assigns bed while preserving same visit file',adm['stage']=='ADMITTED' and adm['admission_id'])
    req(c.post(f"/api/journey/visits/{sv['id']}/progress",headers=nurse,json={'note_type':'NURSING','note':'Vitals stable; wound dry.'}))
    mar=req(c.post(f"/api/care/visits/{sv['id']}/medication-administrations",headers=nurse,json={'medicine':'Ceftriaxone','dose':'1 g','route':'IV','status':'GIVEN','notes':'Administered as ordered'}))
    ok('inpatient medication administration is part of same episode',mar['status']=='GIVEN')

    # Bed transfer across wards.
    w2=req(c.post('/api/wards',headers=admin,json={'name':'Surgical Ward','ward_type':'SURGICAL'}))
    b2=req(c.post('/api/beds',headers=admin,json={'ward_id':w2['id'],'code':'SW-01'}))
    mv=req(c.post(f"/api/care/visits/{sv['id']}/bed-transfer",headers=nurse,json={'ward_id':w2['id'],'bed_id':b2['id'],'reason':'Transfer to surgical ward'}))
    ok('inpatient bed transfer updates the active admission',mv['ward_id']==w2['id'] and mv['bed_id']==b2['id'])
    beds_after=req(c.get('/api/beds',headers=nurse));
    ok('bed movement releases old bed and occupies new bed',next(x for x in beds_after if x['id']==b1['id'])['status']=='AVAILABLE' and next(x for x in beds_after if x['id']==b2['id'])['status']=='OCCUPIED')

    # Active clinical order blocks discharge until department completes it.
    rf=req(c.post(f"/api/care/visits/{sv['id']}/referrals",headers=doctor,json={'kind':'INTERNAL','target_module':'physiotherapy','reason':'Post-op mobilisation'}))
    premature=c.post(f"/api/journey/visits/{sv['id']}/discharge-decision",headers=doctor,json={'summary':'Fit for discharge'})
    ok('doctor cannot discharge with unfinished clinical work',premature.status_code==409)
    porder=next(x for x in req(c.get('/api/care/service-orders?module_key=physiotherapy',headers=physio)) if x['visit_id']==sv['id'] and x['status']!='COMPLETED')
    req(c.post(f"/api/care/service-orders/{porder['id']}/start",headers=physio,json={}))
    req(c.post(f"/api/care/service-orders/{porder['id']}/complete",headers=physio,json={'result_summary':'Mobilising independently; safe for home.'}))
    decision=req(c.post(f"/api/journey/visits/{sv['id']}/discharge-decision",headers=doctor,json={'summary':'Stable post appendicectomy. Wound care advice given.'}))
    ok('doctor discharge decision creates discharge plan and moves to pending',decision['stage']=='DISCHARGE_PENDING')
    care_after=req(c.get(f"/api/care/visits/{sv['id']}",headers=doctor))
    ok('doctor discharge decision automatically seeds native discharge plan',care_after['discharge_plan'] is not None and care_after['discharge_plan']['instructions'])
    follow=(datetime.utcnow()+timedelta(days=7)).replace(microsecond=0).isoformat()
    req(c.put(f"/api/care/visits/{sv['id']}/discharge-plan",headers=doctor,json={'disposition':'HOME','final_diagnosis':'Acute appendicitis, post appendicectomy','condition_at_discharge':'Stable','instructions':'Keep wound clean; return for fever or worsening pain.','follow_up_at':follow,'follow_up_department':'Surgical clinic'}))
    outbox=req(c.get('/api/journey/sms-outbox',headers=reception))
    ok('follow-up plan can queue patient reminder SMS',any(x['visit_id']==sv['id'] and x['event_type']=='FOLLOW_UP' for x in outbox))
    clr=req(c.post(f"/api/care/visits/{sv['id']}/financial-clearance",headers=cashier,json={'status':'CLEARED'}))
    ok('cashier can clear fully settled inpatient episode',clr['status']=='CLEARED' and clr['financial']['balance']==0)
    discharged=req(c.post(f"/api/journey/visits/{sv['id']}/discharge",headers=nurse,json={}))
    ok('ward physical discharge closes the same visit file',discharged['status']=='CLOSED')
    ok('destination bed released on physical discharge',next(x for x in req(c.get('/api/beds',headers=nurse)) if x['id']==b2['id'])['status']=='AVAILABLE')

    # ------------------------------------------------------------------
    # Cash financial clearance cannot lie about outstanding charges.
    # ------------------------------------------------------------------
    fv=open_patient(c,reception,'Finance','Guard','Needs imaging')
    pay(c,cashier,fv['consultation_invoice'],ref='CONS-FIN')
    req(c.post(f"/api/journey/visits/{fv['id']}/claim",headers=doctor,json={}))
    fo=req(c.post(f"/api/care/visits/{fv['id']}/service-orders",headers=doctor,json={'module_key':'radiology','title':'CT head','amount':25000}))
    conflict=c.post(f"/api/care/visits/{fv['id']}/financial-clearance",headers=cashier,json={'status':'CLEARED'})
    ok('cash financial clearance rejects outstanding visit balance',conflict.status_code==409 and conflict.json()['detail']['code']=='OUTSTANDING_BALANCE')

    # ------------------------------------------------------------------
    # Terminal pathways: transfer and death are explicit episode outcomes.
    # ------------------------------------------------------------------
    tv=open_patient(c,reception,'Transfer','Patient','Needs tertiary service',payer_type='EXEMPT',authorization_status='NOT_REQUIRED')
    req(c.post(f"/api/care/visits/{tv['id']}/referrals",headers=doctor,json={'kind':'TRANSFER','target_facility':'National Referral Hospital','reason':'Requires tertiary specialist care'}))
    tr=req(c.post(f"/api/care/visits/{tv['id']}/terminal-outcome",headers=doctor,json={'disposition':'TRANSFERRED','final_diagnosis':'Complex condition','condition_at_discharge':'Stable for transfer','instructions':'Transfer with clinical summary'}))
    ok('inter-facility transfer closes episode with explicit disposition',tr['status']=='CLOSED' and tr['discharge_plan']['disposition']=='TRANSFERRED')

    dv=open_patient(c,reception,'Deceased','Patient','Cardiorespiratory arrest',priority='EMERGENCY')
    death=req(c.post(f"/api/care/visits/{dv['id']}/terminal-outcome",headers=doctor,json={'disposition':'DECEASED','final_diagnosis':'Cardiorespiratory arrest','condition_at_discharge':'Deceased','instructions':'Mortuary transfer'}))
    ok('death closes clinical episode explicitly',death['status']=='CLOSED' and death['discharge_plan']['disposition']=='DECEASED')
    mort=req(c.get('/api/care/service-orders?module_key=mortuary',headers=admin))
    ok('death creates mortuary transfer task when mortuary is enabled',any(x['visit_id']==dv['id'] and x['title']=='Mortuary transfer' for x in mort))

    # ------------------------------------------------------------------
    # Configuration remains authoritative across integrated pathways.
    # ------------------------------------------------------------------
    req(c.patch('/api/modules/radiology',headers=admin,json={'enabled':False}))
    disabled=c.post(f"/api/care/visits/{fv['id']}/service-orders",headers=doctor,json={'module_key':'radiology','title':'Repeat CT','amount':0})
    ok('disabled specialist module blocks native doctor order immediately',disabled.status_code==403)
    req(c.patch('/api/modules/radiology',headers=admin,json={'enabled':True}))
    ok('re-enabling specialist module restores workflow',req(c.get('/api/me',headers=doctor))['modules']['radiology'] is True)

    # Native workspace endpoints expose role-specific queues, not a monolithic workflow only.
    ok('reception has native active visit queue','visits' in req(c.get('/api/care/native/reception',headers=reception)))
    ok('doctor has native clinical queue','visits' in req(c.get('/api/care/native/doctor',headers=doctor)))
    ok('ward has native inpatient queue','visits' in req(c.get('/api/care/native/inpatient',headers=nurse)))

print(f'CARE PATHWAYS E2E: PASS ({len(checks)}/{len(checks)})')
for i,n in enumerate(checks,1): print(f'{i:02d}. PASS - {n}')
