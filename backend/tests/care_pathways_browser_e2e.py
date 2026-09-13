import os, subprocess, time, urllib.request, httpx, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; BACKEND=ROOT/'backend'; DB=Path(__file__).resolve().parent/'care_pathways_browser.db'; PORT=8148; BASE=f'http://127.0.0.1:{PORT}'
try: DB.unlink()
except FileNotFoundError: pass
results=[]
def check(name,cond=True,detail=''):
    if not cond: raise AssertionError(detail or name)
    results.append(name); print('PASS',name,flush=True)
def api_login(email,pwd='Demo123!'):
    r=httpx.post(BASE+'/api/auth/login',json={'email':email,'password':pwd});r.raise_for_status();return {'Authorization':'Bearer '+r.json()['access_token']}
def req(method,path,h=None,j=None):
    r=httpx.request(method,BASE+path,headers=h,json=j,timeout=10)
    if r.status_code>=400: raise AssertionError(f'{method} {path}: {r.status_code} {r.text}')
    return r.json() if r.text else None

env=os.environ.copy();env['DATABASE_URL']=f'sqlite:///{DB}';env['JWT_SECRET']='care-pathways-browser-secret-at-least-thirty-two-bytes';env['PYTHONPATH']=str(BACKEND)
server=subprocess.Popen(['python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT)],cwd=BACKEND,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            if urllib.request.urlopen(BASE+'/api/health',timeout=1).status==200: break
        except Exception: time.sleep(.1)
    else: raise RuntimeError('server did not start')

    admin=api_login('admin@onehms.com','Admin123!'); receptionist=api_login('reception@onehms.com'); doctor=api_login('doctor@onehms.com'); cashier=api_login('cashier@onehms.com')
    for k in ['radiology','theatre','wards','beds','nursing','emergency']:
        req('PATCH',f'/api/modules/{k}',admin,{'enabled':True})
    req('PATCH','/api/journey/settings',admin,{'consultation_fee':10000,'require_consultation_payment':True,'require_triage':False,'auto_assign_doctor':True})
    req('PATCH','/api/care/policy',admin,{'require_service_payment':False,'emergency_bypass_payment':True,'require_surgical_consent':True,'require_preop_checklist':True})
    roles=req('GET','/api/roles',admin); rid=next(r['id'] for r in roles if r['name']=='Radiographer')
    req('POST','/api/users',admin,{'full_name':'Browser Radiographer','email':'browser.rad@onehms.com','password':'Demo123!','role_id':rid})

    # Create an emergency triage patient for the nurse-native OPD panel.
    emergency=req('POST','/api/journey/register-and-open',receptionist,{'first_name':'Native','last_name':'Emergency','sex':'Male','phone':'+255711111111','reason':'Breathing difficulty','priority':'EMERGENCY'})

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        css=(BACKEND/'web'/'styles.css').read_text()+(BACKEND/'web'/'patient_journey.css').read_text()+(BACKEND/'web'/'care_pathways.css').read_text()
        js=(BACKEND/'web'/'app.js').read_text();jjs=(BACKEND/'web'/'patient_journey.js').read_text();cjs=(BACKEND/'web'/'care_pathways.js').read_text()
        shim="const __store=()=>({d:{},getItem(k){return this.d[k]||null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}});Object.defineProperty(window,'localStorage',{value:__store()});Object.defineProperty(window,'sessionStorage',{value:__store()});"
        def new_login(email,pwd='Demo123!'):
            p=browser.new_page(viewport={'width':1440,'height':1000}); p.set_default_timeout(7000); errs=[];p.on('pageerror',lambda e:errs.append(str(e)))
            def proxy(route,request):
                path=request.url.replace('http://onehms.local','',1);h={k:v for k,v in request.headers.items() if k.lower() not in {'host','content-length','origin','referer'}};r=httpx.request(request.method,BASE+path,headers=h,content=request.post_data_buffer or b'',timeout=10);route.fulfill(status=r.status_code,headers={'content-type':r.headers.get('content-type','application/json')},body=r.content)
            p.route('http://onehms.local/api/**',proxy)
            p.set_content(f"<!doctype html><html><head><base href='http://onehms.local/'><style>{css}</style></head><body><div id='root'></div><script>{shim}</script><script>{js}</script><script>{jjs}</script><script>{cjs}</script></body></html>")
            p.locator('#email').fill(email);p.locator('#password').fill(pwd);p.locator('#loginBtn').click();p.wait_for_selector('.appShell');return p,errs

        # Reception: visit file is part of normal reception page, including payer context.
        p,errs=new_login('reception@onehms.com')
        p.locator('[data-page="reception"]').click();p.get_by_text('Receive patient & open today’s episode',exact=True).wait_for()
        check('Reception page natively contains visit-file intake')
        p.locator('#careOpenVisit').click();p.get_by_role('heading',name='Open patient visit file').wait_for()
        check('Reception intake includes payer selection',p.locator('#careOpen select[name="payer_type"]').count()==1)
        p.locator('#careOpen select[name="patient_id"]').select_option(label='P000001 — Amina Msuya')
        p.locator('#careOpen select[name="payer_type"]').select_option('INSURANCE');p.locator('#careOpen select[name="authorization_status"]').select_option('APPROVED')
        p.locator('#careOpen input[name="payer_name"]').fill('Browser Health Fund');p.locator('#careOpen textarea[name="reason"]').fill('Persistent cough')
        p.locator('#careOpen button.primary').click();p.wait_for_timeout(500)
        check('Reception opens insured visit without leaving reception workspace',p.get_by_text('Amina Msuya',exact=False).first.is_visible())
        check('Reception native UI has no uncaught JS errors',not errs,errs);p.close()

        # Doctor: all core clinical transitions available in OPD, not only Patient Journey.
        p,errs=new_login('doctor@onehms.com')
        p.locator('[data-page="encounters"]').click();p.get_by_text('Doctor queue',exact=True).wait_for()
        check('OPD page natively contains doctor queue')
        p.locator('#careStartShift').click();p.locator('#careShift input[name="room_number"]').fill('OPD-21');p.locator('#careShift button.primary').click();p.wait_for_timeout(500)
        check('Doctor shift controls are native to OPD page',p.get_by_role('heading',name='Room OPD-21 · AVAILABLE',exact=True).is_visible())
        p.locator('#careDoctorSearch').fill('P000001');p.locator('#careDoctorSearchBtn').click();p.wait_for_timeout(350)
        p.locator('#careDoctorResults [data-care-visit]').first.click();p.get_by_text('Clinical episode').wait_for()
        for label in ['Clinical note','Order lab','Prescribe','Order service','Request surgery','Referral / transfer','Disposition']:
            check(f'Doctor care file includes {label} action',p.get_by_role('button',name=label,exact=True).is_visible())
        p.get_by_role('button',name='Order service',exact=True).click();p.locator('#careService select[name="module_key"]').select_option('radiology');p.locator('#careService input[name="title"]').fill('Chest X-ray');p.locator('#careService textarea[name="clinical_question"]').fill('Exclude pneumonia');p.locator('#careService button.primary').click();p.wait_for_timeout(450)
        check('Doctor can send specialist order from native OPD care file',p.get_by_text('Chest X-ray',exact=True).is_visible())
        check('Doctor native UI has no uncaught JS errors',not errs,errs);p.close()

        # Radiology: clinical request appears in normal Specialist Modules workspace.
        p,errs=new_login('browser.rad@onehms.com')
        p.locator('[data-page="operations"]').click();p.wait_for_selector('#opSelect');p.locator('#opSelect').select_option('radiology');p.wait_for_timeout(500)
        p.get_by_text('Patient service requests',exact=True).wait_for()
        check('Radiology workspace natively receives doctor service order',p.get_by_text('Chest X-ray',exact=False).first.is_visible())
        p.locator('[data-care-start]').first.click();p.wait_for_timeout(300);p.locator('[data-care-complete]').first.click();p.locator('#careComplete textarea[name="result_summary"]').fill('No acute chest abnormality.');p.locator('#careComplete button.primary').click();p.wait_for_timeout(450)
        check('Radiographer completes order in normal departmental workspace')
        check('Specialist native UI has no uncaught JS errors',not errs,errs);p.close()

        # Nurse: triage lives in OPD page, and nursing users are not shown doctor shift controls.
        p,errs=new_login('nurse@onehms.com')
        p.locator('[data-page="encounters"]').click();p.get_by_text('Triage queue',exact=True).wait_for()
        check('Nurse OPD page natively contains triage queue')
        check('Nurse is not offered doctor Start shift control',p.locator('#careStartShift').count()==0)
        p.locator(f'[data-care-visit="{emergency["id"]}"]').first.click();p.get_by_role('button',name='Record triage',exact=True).click();p.locator('#careTriage input[name="pulse"]').fill('108');p.locator('#careTriage input[name="spo2"]').fill('96');p.locator('#careTriage button.primary').click();p.wait_for_timeout(450)
        check('Nurse can complete emergency triage from OPD workspace')
        p.locator('[data-page="inpatient"]').click();p.get_by_text('Admission, ward care, transfers and discharge',exact=True).wait_for()
        check('Inpatient page natively exposes episode-based ward workflow')
        check('Nursing native UI has no uncaught JS errors',not errs,errs);p.close()

        browser.close()
finally:
    server.terminate()
    try: server.wait(timeout=5)
    except Exception: server.kill()

print(f'CARE PATHWAYS BROWSER E2E: {len(results)}/{len(results)} PASS')
