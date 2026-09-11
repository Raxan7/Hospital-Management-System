import os, subprocess, time, json, urllib.request, httpx
from pathlib import Path
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[2]
BACKEND=ROOT/'backend'
DB=Path(__file__).resolve().parent/'browser_e2e.db'
REPORT=Path(__file__).resolve().parent/'BROWSER_E2E_TEST_REPORT.md'
JSON_REPORT=Path(__file__).resolve().parent/'browser_e2e_results.json'
PORT=8127
BASE=f'http://127.0.0.1:{PORT}'
if DB.exists(): DB.unlink()

results=[]
def result(name, ok=True, detail=''):
    results.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':str(detail)[:500]})
    print(('PASS' if ok else 'FAIL'),name,detail,flush=True)
def case(name, fn):
    try: fn(); result(name)
    except Exception as e: result(name,False,e)
def assert_text(page,text):
    page.get_by_text(text, exact=False).first.wait_for(state='visible',timeout=7000)
def nav(page,key):
    page.locator(f'button[data-page="{key}"]').click(); page.wait_for_timeout(250)
def choose_option_containing(select, fragment):
    op=select.locator('option',has_text=fragment).first
    op.wait_for(state='attached',timeout=7000)
    value=op.get_attribute('value')
    if value is None: raise AssertionError(f'No option value for {fragment}')
    select.select_option(value)

def write_report():
    passed=sum(x['status']=='PASS' for x in results); failed=len(results)-passed
    lines=['# One HMS — Browser End-to-End Test Report','',f'- Browser test cases: **{len(results)}**',f'- Passed: **{passed}**',f'- Failed: **{failed}**','', 'These tests use a real headless Chromium browser against a live Uvicorn server and interact with the actual HMS forms, navigation and buttons.','', '| Test case | Result | Detail |','|---|---|---|']
    for r in results:
        d=(r['detail'] or '').replace('|','\\|').replace('\n',' ')
        lines.append(f"| {r['name']} | {r['status']} | {d} |")
    REPORT.write_text('\n'.join(lines)); JSON_REPORT.write_text(json.dumps(results,indent=2))

def main():
    env=os.environ.copy(); env['DATABASE_URL']=f'sqlite:///{DB}'; env['JWT_SECRET']='browser-e2e-secret-longer-than-thirty-two-bytes'; env['PYTHONPATH']=str(BACKEND)
    server=subprocess.Popen(['python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT)],cwd=BACKEND,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    try:
        for _ in range(80):
            try:
                with urllib.request.urlopen(BASE+'/api/health',timeout=1) as r:
                    if r.status==200: break
            except Exception: time.sleep(.15)
        else: raise RuntimeError('Uvicorn did not start')

        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1000}); page.set_default_timeout(7000)
            page_errors=[]
            page.on('pageerror',lambda e: page_errors.append(str(e)))
            def proxy_api(route, request):
                path=request.url.replace('http://onehms.local','',1)
                headers={k:v for k,v in request.headers.items() if k.lower() not in {'host','content-length','origin','referer'}}
                body=request.post_data_buffer or b''
                r=httpx.request(request.method,BASE+path,headers=headers,content=body,timeout=10.0)
                route.fulfill(status=r.status_code,headers={'content-type':r.headers.get('content-type','application/json')},body=r.content)
            page.route('http://onehms.local/api/**',proxy_api)
            css=(BACKEND/'web'/'styles.css').read_text()
            js=(BACKEND/'web'/'app.js').read_text()
            shim="const __store=()=>({d:{},getItem(k){return this.d[k]||null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}});Object.defineProperty(window,'localStorage',{value:__store()});Object.defineProperty(window,'sessionStorage',{value:__store()});"
            html=f"<!doctype html><html><head><base href='http://onehms.local/'><meta charset='UTF-8'><style>{css}</style></head><body><div id='root'></div><script>{shim}</script><script>{js}</script></body></html>"
            page.set_content(html,wait_until='load')

            case('Login screen renders',lambda: assert_text(page,'One HMS'))
            page.locator('#loginBtn').click(); page.get_by_role('heading',name='Hospital overview').wait_for(timeout=7000)
            case('Admin can log in through browser UI',lambda: assert_text(page,'Hospital overview'))
            case('Core navigation includes Reception',lambda: page.locator('button[data-page="reception"]').wait_for())
            case('Core navigation includes Patients, Appointments, OPD, Lab, Pharmacy, Billing, Inventory, Users, Reports, Audit and Configuration',lambda: [page.locator(f'button[data-page="{k}"]').wait_for() for k in ['patients','appointments','encounters','laboratory','pharmacy','billing','inventory','staff','reports','audit','modules']])

            # Patient registration
            nav(page,'patients'); page.locator('#newPatient').click();
            page.locator('#pf input[name="first_name"]').fill('Browser'); page.locator('#pf input[name="last_name"]').fill('E2E Patient'); page.locator('#pf select[name="sex"]').select_option(label='Female'); page.locator('#pf input[name="phone"]').fill('+255711222333'); page.locator('#pf input[name="blood_group"]').fill('A+'); page.locator('#savePatient').click(); page.wait_for_timeout(400)
            case('Patient can be registered through UI',lambda: assert_text(page,'Browser E2E Patient'))
            row=page.locator('tr',has_text='Browser E2E Patient').first; row.locator('button[data-patient]').click();
            case('Patient medical record/history modal opens',lambda: assert_text(page,'Patient information'))
            page.locator('[data-close]').click()

            # Inventory before prescribing
            nav(page,'inventory'); page.locator('#newItem').click();
            page.locator('#itemf input[name="sku"]').fill('UI-MED-001'); page.locator('#itemf input[name="name"]').fill('UI Test Medicine'); page.locator('#itemf input[name="quantity"]').fill('20'); page.locator('#itemf input[name="reorder_level"]').fill('5'); page.locator('#itemf input[name="unit_price"]').fill('500'); page.locator('#saveItem').click(); page.wait_for_timeout(350)
            case('Inventory medicine can be created through UI',lambda: assert_text(page,'UI Test Medicine'))

            # Appointment
            nav(page,'appointments'); page.locator('#newAppointment').click();
            choose_option_containing(page.locator('#af select[name="patient_id"]'),'Browser E2E Patient'); page.locator('#af input[name="scheduled_at"]').fill('2026-09-10T10:30'); page.locator('#af input[name="department"]').fill('OPD'); page.locator('#af input[name="clinician"]').fill('Dr Browser'); page.locator('#af textarea[name="reason"]').fill('Browser end-to-end test'); page.locator('#saveAppt').click(); page.wait_for_timeout(350)
            case('Appointment can be booked through UI',lambda: assert_text(page,'Dr Browser'))

            # Reception check-in
            nav(page,'reception'); rrow=page.locator('tr',has_text='Browser E2E Patient').first
            case('Reception queue shows booked patient',lambda: rrow.wait_for())
            rrow.locator('button[data-checkin]').click(); page.wait_for_timeout(350)
            case('Reception can check patient in',lambda: assert_text(page,'ARRIVED'))

            # Encounter + triage/lab/prescription/consultation
            nav(page,'encounters'); page.locator('#newEncounter').click(); choose_option_containing(page.locator('#ef select[name="patient_id"]'),'Browser E2E Patient'); page.locator('#ef textarea[name="chief_complaint"]').fill('Fever and headache'); page.locator('#saveEnc').click(); page.wait_for_timeout(350)
            case('OPD encounter can be opened through UI',lambda: assert_text(page,'Fever and headache'))
            erow=page.locator('button.encCard',has_text='Browser E2E Patient').first; erow.click();
            page.locator('#vf input[name="temperature_c"]').fill('38.1'); page.locator('#vf input[name="pulse"]').fill('90'); page.locator('#vf input[name="systolic"]').fill('120'); page.locator('#vf input[name="diastolic"]').fill('80'); page.locator('#vf input[name="spo2"]').fill('98'); page.locator('#saveVitals').click(); page.wait_for_timeout(350)
            case('Triage vital signs can be saved through UI',lambda: assert_text(page,'38.1°C'))
            page.locator('#lf input[name="test_name"]').fill('UI CBC'); page.locator('#saveLab').click(); page.wait_for_timeout(350)
            case('Lab order can be created from encounter UI',lambda: assert_text(page,'UI CBC'))
            choose_option_containing(page.locator('#rf select[name="inventory_item_id"]'),'UI Test Medicine'); page.locator('#rf input[name="dose"]').fill('500mg'); page.locator('#rf input[name="frequency"]').fill('BID'); page.locator('#rf input[name="duration"]').fill('3 days'); page.locator('#rf input[name="quantity"]').fill('4'); page.locator('#saveRx').click(); page.wait_for_timeout(350)
            case('Prescription can be added from encounter UI',lambda: page.locator('.miniRow',has_text='UI Test Medicine').wait_for())
            page.locator('#cf textarea[name="clinical_notes"]').fill('Patient examined and stable'); page.locator('#cf textarea[name="diagnosis"]').fill('Viral syndrome'); page.locator('#cf select[name="status"]').select_option(label='COMPLETED'); page.locator('#saveConsult').click(); page.wait_for_timeout(350)
            case('Consultation and diagnosis can be completed through UI',lambda: assert_text(page,'Viral syndrome'))

            # Lab result
            nav(page,'laboratory'); lrow=page.locator('tr',has_text='UI CBC').first; lrow.locator('button[data-lab]').click(); page.locator('#lrf textarea[name="result"]').fill('Normal'); page.locator('#lrf input[name="verified"]').check(); page.locator('#saveLR').click(); page.wait_for_timeout(350)
            case('Laboratory result can be entered and verified through UI',lambda: page.locator('tr',has_text='UI CBC').get_by_text('VERIFIED',exact=True).wait_for())

            # Pharmacy
            nav(page,'pharmacy'); prow=page.locator('tr',has_text='UI Test Medicine').first; prow.locator('button[data-dispense]').click(); page.wait_for_timeout(450)
            case('Pharmacy can dispense prescription through UI',lambda: page.locator('tr',has_text='UI Test Medicine').get_by_text('DISPENSED',exact=True).wait_for())
            nav(page,'inventory');
            case('Dispensing visibly reduces inventory quantity',lambda: assert_text(page,'16'))

            # Billing
            nav(page,'billing'); page.locator('#newInvoice').click(); choose_option_containing(page.locator('#if select[name="patient_id"]'),'Browser E2E Patient'); page.locator('#if input[name="amount"]').fill('12000'); page.locator('#if input[name="description"]').fill('UI Consultation'); page.locator('#saveInv').click(); page.wait_for_timeout(350)
            brow=page.locator('tr',has_text='UI Consultation').first
            case('Invoice can be created through UI',lambda: brow.wait_for())
            brow.locator('button[data-pay]').click(); page.locator('#payf input[name="amount"]').fill('12000'); page.locator('#payf select[name="method"]').select_option(label='MOBILE_MONEY'); page.locator('#payf input[name="reference"]').fill('UI-TX-1'); page.locator('#savePay').click(); page.wait_for_timeout(350)
            case('Payment can be collected and invoice becomes PAID through UI',lambda: page.locator('tr',has_text='UI Consultation').get_by_text('PAID',exact=True).wait_for())

            # Inpatient
            nav(page,'inpatient'); page.locator('#newWard').click(); page.locator('#wf input[name="name"]').fill('Browser Ward'); page.locator('#saveWard').click(); page.wait_for_timeout(300)
            case('Ward can be created through UI',lambda: assert_text(page,'Browser Ward'))
            page.locator('#newBed').click(); choose_option_containing(page.locator('#bf select[name="ward_id"]'),'Browser Ward'); page.locator('#bf input[name="code"]').fill('BW-01'); page.locator('#saveBed').click(); page.wait_for_timeout(300)
            page.locator('#newAdmission').click(); choose_option_containing(page.locator('#admf select[name="patient_id"]'),'Browser E2E Patient'); choose_option_containing(page.locator('#admWard'),'Browser Ward'); page.wait_for_timeout(150); choose_option_containing(page.locator('#admBed'),'BW-01'); page.locator('#admf textarea[name="diagnosis"]').fill('Observation'); page.locator('#saveAdm').click(); page.wait_for_timeout(400)
            case('Patient can be admitted into an available bed through UI',lambda: page.locator('tr',has_text='Browser E2E Patient').get_by_text('ADMITTED',exact=True).wait_for())
            arow=page.locator('tr',has_text='Browser E2E Patient').filter(has=page.locator('button[data-discharge]')).first; arow.locator('button[data-discharge]').click(); page.wait_for_timeout(350)
            case('Patient can be discharged and admission changes to DISCHARGED',lambda: page.locator('tr',has_text='Browser E2E Patient').get_by_text('DISCHARGED',exact=True).wait_for())

            # Staff/roles
            nav(page,'staff')
            case('Predefined hospital role catalogue is visible in UI',lambda: [assert_text(page,x) for x in ['Surgeon','Theatre Staff','Midwife','Radiologist','Insurance Officer','Procurement Officer','Blood Bank Technician','Biomedical Equipment Technician']])
            case('Role catalogue reports all built-in templates',lambda: assert_text(page,'63 built-in templates'))
            page.locator('#newUser').click()
            case('Staff role selector includes grouped Surgeon template',lambda: choose_option_containing(page.locator('#uf select[name="role_id"]'),'Surgeon'))
            page.locator('[data-close]').click()
            page.locator('#newRole').click(); page.locator('#rolef input[name="name"]').fill('Browser Test Role'); page.locator('#rolef select[name="preset"]').select_option('viewer'); page.locator('#saveRole').click(); page.wait_for_timeout(300)
            case('Role can be created through UI',lambda: assert_text(page,'Browser Test Role'))
            page.locator('#newUser').click(); page.locator('#uf input[name="full_name"]').fill('Browser Staff'); page.locator('#uf input[name="email"]').fill('browser.staff@example.com'); page.locator('#uf input[name="password"]').fill('Browser123!'); choose_option_containing(page.locator('#uf select[name="role_id"]'),'Browser Test Role'); page.locator('#saveUser').click(); page.wait_for_timeout(350)
            case('Staff user can be created and assigned a role through UI',lambda: assert_text(page,'browser.staff@example.com'))

            # Disabled specialist modules must be hidden from operational choices
            nav(page,'operations');
            case('Disabled Theatre is hidden from specialist operational dropdown',lambda: (page.locator('#opSelect option[value="theatre"]').count()==0) or (_ for _ in ()).throw(AssertionError('disabled theatre is visible')))

            # Configuration + specialist module
            nav(page,'modules'); page.locator('#editHospital').click(); page.locator('#hf select[name="facility_type"]').select_option(label='REFERRAL'); page.locator('#hf input[name="apply_preset"]').check(); page.locator('#saveHospital').click(); page.wait_for_timeout(500)
            case('Facility type can be changed to REFERRAL with preset from UI',lambda: assert_text(page,'REFERRAL'))
            case('Nursing module is present in configuration UI',lambda: assert_text(page,'Nursing'))
            case('Theatre module is enabled by referral preset in UI',lambda: page.locator('.moduleRow',has_text='Theatre / Surgery').locator('button.switch.on').wait_for())
            nav(page,'operations'); page.locator('#opSelect').select_option('theatre'); page.wait_for_timeout(350); page.locator('#newOp').click(); choose_option_containing(page.locator('#opf select[name="patient_id"]'),'Browser E2E Patient'); page.locator('#opf input[name="title"]').fill('Browser Surgical Review'); page.locator('#opf textarea[name="notes"]').fill('UI specialist module test'); page.locator('#saveOp').click(); page.wait_for_timeout(350)
            case('Enabled specialist module can create operational record through UI',lambda: assert_text(page,'Browser Surgical Review'))

            nav(page,'reports'); case('Reports screen loads in browser',lambda: assert_text(page,'Operational and financial summary'))
            nav(page,'audit'); case('Audit screen loads in browser and shows actions',lambda: assert_text(page,'Recent clinical and administrative actions'))
            nav(page,'dashboard'); case('Dashboard still loads after complete workflow',lambda: assert_text(page,'Hospital overview'))
            case('No uncaught JavaScript page errors occurred',lambda: (_ for _ in ()).throw(AssertionError(page_errors)) if page_errors else None)

            # Role-based navigation visibility using the limited UI-created user
            page.locator('#logout').click(); page.locator('#email').fill('browser.staff@example.com'); page.locator('#password').fill('Browser123!'); page.locator('#loginBtn').click(); page.get_by_role('heading',name='Hospital overview').wait_for()
            case('Limited staff user can log in',lambda: assert_text(page,'Browser Staff'))
            case('Limited user does not see Configuration navigation',lambda: (page.locator('button[data-page="modules"]').count()==0) or (_ for _ in ()).throw(AssertionError('Configuration visible')))
            case('Limited user does not see Users & Roles navigation',lambda: (page.locator('button[data-page="staff"]').count()==0) or (_ for _ in ()).throw(AssertionError('Staff admin visible')))
            case('Limited user does not see Reception without permission',lambda: (page.locator('button[data-page="reception"]').count()==0) or (_ for _ in ()).throw(AssertionError('Reception visible')))
            nav(page,'patients');
            case('Medical record Open action is hidden without medical_records VIEW',lambda: (page.locator('button[data-patient]').count()==0) or (_ for _ in ()).throw(AssertionError('Medical record action visible')))
            browser.close()
    finally:
        server.terminate()
        try: server.wait(timeout=5)
        except Exception: server.kill()
        write_report()
        if DB.exists(): DB.unlink()
    failures=[x for x in results if x['status']=='FAIL']
    print(f'BROWSER E2E: {len(results)-len(failures)}/{len(results)} PASS')
    if failures: raise SystemExit(1)

if __name__=='__main__': main()
