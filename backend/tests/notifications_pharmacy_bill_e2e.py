import os, sys, tempfile
from pathlib import Path
from datetime import datetime, timedelta

DB=Path(tempfile.gettempdir())/'onehms_notifications_pharmacy_e2e.db'
try: DB.unlink()
except FileNotFoundError: pass
os.environ['DATABASE_URL']=f'sqlite:///{DB}'
os.environ['JWT_SECRET']='notifications-pharmacy-e2e-secret-12345678901234567890'
os.environ.pop('HMS_SMS_GATEWAY_URL',None)
os.environ.pop('HMS_SMS_GATEWAY_SECRET',None)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.notifications import NotificationJob, NotificationCampaign, OtpChallenge
from app.patient_journey import SmsOutbox

checks=[]
def ok(name,cond=True):
    if not cond: raise AssertionError(name)
    checks.append(name)
def req(r,code=200):
    if r.status_code!=code: raise AssertionError(f'{r.request.method} {r.request.url}: {r.status_code} {r.text}')
    return r.json() if r.text else None
def login(c,email,pwd):
    d=req(c.post('/api/auth/login',json={'email':email,'password':pwd}));return {'Authorization':'Bearer '+d['access_token']}
def events(c,h): return req(c.get('/api/notifications/outbox',headers=h))
def event_count(c,h,kind): return sum(1 for x in events(c,h) if x['event_type']==kind)

with TestClient(app) as c:
    admin=login(c,'admin@onehms.com','Admin123!')
    reception=login(c,'reception@onehms.com','Demo123!')
    doctor=login(c,'doctor@onehms.com','Demo123!')
    pharmacy=login(c,'pharmacy@onehms.com','Demo123!')
    cashier=login(c,'cashier@onehms.com','Demo123!')
    ok('seeded users login')

    # Turn on every poster event category.
    settings=req(c.get('/api/notifications/settings',headers=admin))
    patch={k:True for k in [
        'enabled','appointment_confirmations','appointment_reminders','lab_results','prescription_medication',
        'followup_reminders','health_campaigns','hospital_promotions','satisfaction_surveys','billing_payments',
        'emergency_notifications','staff_communication','queue_notifications','otp_sms']}
    patch.update({'appointment_reminder_hours':24,'followup_reminder_hours':24,'medication_reminder_days':2,
                  'satisfaction_delay_hours':24,'queue_notify_threshold':3,'timezone_name':'Africa/Dar_es_Salaam'})
    settings=req(c.patch('/api/notifications/settings',headers=admin,json=patch))
    ok('all poster SMS event categories configurable', all(settings[k] for k in patch if isinstance(patch[k],bool)))

    # Patient consent: operational on, marketing on for P1; marketing off for P2.
    p1=req(c.post('/api/patients',headers=reception,json={'first_name':'Amina','last_name':'SMS','sex':'Female','phone':'0710000111','patient_category':'COST_SHARING','sms_operational_opt_in':True,'sms_marketing_opt_in':True}))
    p2=req(c.post('/api/patients',headers=reception,json={'first_name':'NoPromo','last_name':'Patient','sex':'Male','phone':'0710000222','patient_category':'COST_SHARING','sms_operational_opt_in':True,'sms_marketing_opt_in':False}))
    ok('patient operational and marketing SMS consent stored',p1['sms_operational_opt_in'] and p1['sms_marketing_opt_in'] and not p2['sms_marketing_opt_in'])

    # Appointment confirmation + future reminder, then cancellation must cancel reminder.
    before=event_count(c,admin,'APPOINTMENT_CONFIRMATION')
    appt=req(c.post('/api/appointments',headers=reception,json={'patient_id':p1['id'],'scheduled_at':(datetime.utcnow()+timedelta(days=2)).isoformat(),'department':'OPD','clinician':'Dr Test','reason':'Review'}))
    ok('appointment confirmation SMS created',event_count(c,admin,'APPOINTMENT_CONFIRMATION')==before+1)
    jobs=req(c.get('/api/notifications/jobs',headers=admin))
    rem=next(x for x in jobs if x['event_type']=='APPOINTMENT_REMINDER')
    ok('appointment reminder scheduled',rem['status']=='SCHEDULED')
    req(c.patch(f"/api/appointments/{appt['id']}/status",headers=reception,json={'status':'CANCELLED'}))
    jobs=req(c.get('/api/notifications/jobs',headers=admin)); rem2=next(x for x in jobs if x['id']==rem['id'])
    ok('cancelled appointment cannot send stale reminder',rem2['status']=='CANCELLED')
    ok('appointment cancellation SMS created',event_count(c,admin,'APPOINTMENT_CANCELLED')==1)

    # Billing + payment SMS.
    inv=req(c.post('/api/invoices',headers=cashier,json={'patient_id':p1['id'],'amount':12500,'description':'Clinical services'}))
    ok('billing notification created',event_count(c,admin,'BILLING_NOTIFICATION')>=1)
    req(c.post(f"/api/invoices/{inv['id']}/payments",headers=cashier,json={'amount':12500,'method':'CASH'}))
    ok('payment confirmation created',event_count(c,admin,'PAYMENT_CONFIRMATION')>=1)

    # Staff phone enables staff communication.
    users=req(c.get('/api/users',headers=admin)); doc=next(u for u in users if u['email']=='doctor@onehms.com')
    req(c.patch(f"/api/users/{doc['id']}",headers=admin,json={'phone':'0710000333'}))
    users=req(c.get('/api/users',headers=admin)); doc=next(u for u in users if u['id']==doc['id'])
    ok('staff SMS phone is configurable',doc['phone']=='0710000333')

    # Marketing audience respects consent.
    camp=req(c.post('/api/notifications/campaigns',headers=admin,json={'campaign_type':'HEALTH_CAMPAIGN','audience':'PATIENTS','title':'Screening','message':'Free screening clinic this Friday.'}))
    ok('health campaign created',camp['recipient_count']>=1)
    out=events(c,admin); hc=[x for x in out if x['event_type']=='HEALTH_CAMPAIGN']
    ok('marketing campaign excludes non-opted-in patient',any(x['phone']=='0710000111' for x in hc) and not any(x['phone']=='0710000222' for x in hc))
    promo=req(c.post('/api/notifications/campaigns',headers=admin,json={'campaign_type':'HOSPITAL_PROMOTION','audience':'PATIENTS','title':'Clinic','message':'New specialist clinic is now available.'}))
    ok('hospital promotions supported',promo['recipient_count']>=1)
    staff=req(c.post('/api/notifications/campaigns',headers=admin,json={'campaign_type':'STAFF_COMMUNICATION','audience':'STAFF','title':'Shift','message':'Staff briefing at 08:00.'}))
    ok('staff communication supported',staff['recipient_count']>=1 and any(x['event_type']=='STAFF_COMMUNICATION' and x['phone']=='0710000333' for x in events(c,admin)))
    emergency=req(c.post('/api/notifications/campaigns',headers=admin,json={'campaign_type':'EMERGENCY_NOTIFICATION','audience':'BOTH','title':'Emergency','message':'Emergency service update. Follow hospital instructions.'}))
    ok('emergency notifications support patients and staff',emergency['recipient_count']>=3)

    # OTP event exists and does not reveal code via endpoint.
    otp=req(c.post('/api/notifications/otp/request',headers=admin,json={'phone':'0710000444','purpose':'PORTAL_LOGIN'}))
    ok('OTP challenge generated without exposing code','code' not in otp and otp['challenge_id']>0)
    ok('OTP SMS queued',any(x['event_type']=='OTP' and x['phone']=='0710000444' for x in events(c,admin)))

    # Build a real visit + mixed hospital/external prescription, then print one complete medicine bill.
    req(c.patch('/api/journey/settings',headers=admin,json={'consultation_fee':0,'require_consultation_payment':False,'require_triage':False,'require_pharmacy_payment':False,'auto_assign_doctor':False}))
    req(c.post('/api/journey/doctor/shift/start',headers=doctor,json={'room_number':'OPD-SMS'}))
    v=req(c.post('/api/journey/visits',headers=reception,json={'patient_id':p1['id'],'reason':'Medicine document test','priority':'NORMAL'}))
    v=req(c.post(f"/api/journey/visits/{v['id']}/claim",headers=doctor,json={}))
    catalog=req(c.get('/api/prescription-catalog',headers=doctor)); para=next(x for x in catalog if x['name']=='Paracetamol 500mg')
    rxs=req(c.post(f"/api/journey/visits/{v['id']}/prescriptions",headers=doctor,json={'source':'HOSPITAL','medicines':[
        {'inventory_item_id':para['id'],'medicine':para['name'],'dose':'500 mg','frequency':'TDS','duration':'3 days','quantity':6,'instructions':'After meals'},
        {'inventory_item_id':None,'medicine':'Special External Medicine','dose':'10 mg','frequency':'OD','duration':'7 days','quantity':7,'instructions':'Take at night'}]}))
    vd=req(c.get(f"/api/journey/visits/{v['id']}",headers=pharmacy)); ext=next(x for x in vd['prescriptions'] if x['medicine']=='Special External Medicine')
    req(c.patch(f"/api/prescriptions/{ext['id']}/unavailable",headers=pharmacy,json={'reason':'Not stocked by hospital'}))
    bill=req(c.get(f"/api/pharmacy-documents/visits/{v['id']}/medicine-bill",headers=pharmacy))
    ok('medicine bill contains every prescribed medicine',len(bill['lines'])==2 and {x['medicine'] for x in bill['lines']}=={'Paracetamol 500mg','Special External Medicine'})
    e=next(x for x in bill['lines'] if x['medicine']=='Special External Medicine')
    h=next(x for x in bill['lines'] if x['medicine']=='Paracetamol 500mg')
    ok('external medicine remains on bill with directions',e['source']=='EXTERNAL' and e['dose']=='10 mg' and e['frequency']=='OD' and e['duration']=='7 days')
    ok('hospital payable total excludes external pharmacy price',bill['hospital_payable_total']==h['hospital_line_total'])
    html=c.get(f"/api/pharmacy-documents/visits/{v['id']}/medicine-bill/print",headers=pharmacy)
    ok('printable medicine bill available',html.status_code==200 and 'Special External Medicine' in html.text and 'External price' in html.text and 'Hospital payable total' in html.text)

    # Prescription completion creates medication reminders.
    # external item is complete; dispense hospital item.
    h_rx=next(x for x in vd['prescriptions'] if x['medicine']=='Paracetamol 500mg')
    req(c.patch(f"/api/prescriptions/{h_rx['id']}/dispense",headers=pharmacy,json={}))
    ok('prescription-ready SMS created',event_count(c,admin,'PRESCRIPTION_READY')>=1)
    jobs=req(c.get('/api/notifications/jobs',headers=admin))
    ok('medication reminders scheduled',sum(1 for x in jobs if x['event_type']=='MEDICATION_REMINDER')==2)

    # Follow-up confirmation + reminder via native discharge-plan API.
    follow=datetime.utcnow()+timedelta(days=5)
    req(c.put(f"/api/care/visits/{v['id']}/discharge-plan",headers=doctor,json={'disposition':'HOME','final_diagnosis':'Stable','condition_at_discharge':'Stable','instructions':'Return for review','follow_up_at':follow.isoformat(),'follow_up_department':'OPD'}))
    ok('follow-up confirmation SMS created',event_count(c,admin,'FOLLOW_UP')>=1)
    jobs=req(c.get('/api/notifications/jobs',headers=admin))
    ok('follow-up reminder scheduled',any(x['event_type']=='FOLLOW_UP_REMINDER' for x in jobs))

    # Complete outpatient care: post-visit satisfaction survey is scheduled.
    closed=req(c.post(f"/api/journey/visits/{v['id']}/outcome",headers=doctor,json={'outcome':'OUTPATIENT','pharmacy_choice':'HOSPITAL','note':'Treatment completed'}))
    ok('completed visit closes after medication plan',closed['status']=='CLOSED')
    jobs=req(c.get('/api/notifications/jobs',headers=admin))
    ok('patient satisfaction survey scheduled after visit close',any(x['event_type']=='SATISFACTION_SURVEY' and x['visit_id']==v['id'] for x in jobs))

    # Queue event: with automatic assignment enabled, a waiting patient gets a room/position update.
    req(c.patch('/api/journey/settings',headers=admin,json={'auto_assign_doctor':True}))
    qv=req(c.post('/api/journey/visits',headers=reception,json={'patient_id':p2['id'],'reason':'Queue notification test','priority':'NORMAL'}))
    ok('available doctor is assigned to waiting patient',qv.get('doctor_name') is not None and qv.get('room')=='OPD-SMS')
    ok('queue-position notification created',any(x['event_type']=='QUEUE_NOTIFICATION' and x['visit_id']==qv['id'] for x in events(c,admin)))

    # Outbox and settings are admin-auditable; gateway-unconfigured state never breaks clinical actions.
    gw=req(c.get('/api/journey/sms-gateway/status',headers=admin))
    ok('unconfigured gateway reported safely',gw['configured'] is False)
    ok('queued SMS remain auditable',len(events(c,admin))>=10)

print(f'NOTIFICATIONS + PHARMACY BILL E2E: PASS ({len(checks)}/{len(checks)})')
for i,n in enumerate(checks,1): print(f'{i:02d}. PASS - {n}')
