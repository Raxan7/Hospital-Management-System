import os, subprocess, time, urllib.request, httpx
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; BACKEND=ROOT/'backend'; DB=Path(__file__).resolve().parent/'prescription_pharmacy_browser.db'; PORT=8142; BASE=f'http://127.0.0.1:{PORT}'
try: DB.unlink()
except FileNotFoundError: pass
results=[]
def check(name,cond=True,detail=''):
    if not cond: raise AssertionError(detail or name)
    results.append(name); print('PASS',name,flush=True)
def login(email,pwd):
    r=httpx.post(BASE+'/api/auth/login',json={'email':email,'password':pwd});r.raise_for_status();return {'Authorization':'Bearer '+r.json()['access_token']}
def api(method,path,headers,**kwargs):
    r=httpx.request(method,BASE+path,headers=headers,timeout=10,**kwargs)
    if r.status_code>=400: raise AssertionError(f'{method} {path}: {r.status_code} {r.text}')
    return r.json()

env=os.environ.copy();env['DATABASE_URL']=f'sqlite:///{DB}';env['JWT_SECRET']='rx-pharmacy-browser-secret-at-least-thirty-two-bytes';env['PYTHONPATH']=str(BACKEND)
server=subprocess.Popen(['python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT)],cwd=BACKEND,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            if urllib.request.urlopen(BASE+'/api/health',timeout=1).status==200: break
        except Exception: time.sleep(.1)
    else: raise RuntimeError('server did not start')

    admin=login('admin@onehms.com','Admin123!'); reception=login('reception@onehms.com','Demo123!'); doctor=login('doctor@onehms.com','Demo123!'); cashier=login('cashier@onehms.com','Demo123!')
    amox=api('POST','/api/inventory',admin,json={'sku':'MED-AMOX-UI-OOS','name':'Amoxicillin 500mg','category':'Medicine','quantity':0,'reorder_level':10,'unit_price':500})
    api('PATCH','/api/journey/settings',admin,json={'consultation_fee':10000,'require_consultation_payment':True,'require_triage':False,'require_pharmacy_payment':True,'auto_assign_doctor':False})
    api('POST','/api/journey/doctor/shift/start',doctor,json={'room_number':'OPD-RX-UI'})
    v=api('POST','/api/journey/register-and-open',reception,json={'first_name':'BrowserRx','last_name':'Patient','sex':'Female','phone':'+255710000098','reason':'Prescription UI regression'})
    api('POST',f"/api/invoices/{v['consultation_invoice']['id']}/payments",cashier,json={'amount':10000,'method':'CASH'})

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        css=(BACKEND/'web'/'styles.css').read_text()+(BACKEND/'web'/'patient_journey.css').read_text()+(BACKEND/'web'/'care_pathways.css').read_text()
        js=(BACKEND/'web'/'app.js').read_text();jjs=(BACKEND/'web'/'patient_journey.js').read_text();cjs=(BACKEND/'web'/'care_pathways.js').read_text()
        shim="const __store=()=>({d:{},getItem(k){return this.d[k]||null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}});Object.defineProperty(window,'localStorage',{value:__store()});Object.defineProperty(window,'sessionStorage',{value:__store()});"

        def make_page():
            page=browser.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(8000);page.on('pageerror',lambda e:errs.append(str(e)))
            def proxy(route,request):
                path=request.url.replace('http://onehms.local','',1);h={k:v for k,v in request.headers.items() if k.lower() not in {'host','content-length','origin','referer'}};r=httpx.request(request.method,BASE+path,headers=h,content=request.post_data_buffer or b'',timeout=10);route.fulfill(status=r.status_code,headers={'content-type':r.headers.get('content-type','application/json')},body=r.content)
            page.route('http://onehms.local/api/**',proxy)
            page.route('http://onehms.local/static/**',lambda route: route.abort())
            page.set_content("<!doctype html><html><head><base href='http://onehms.local/'></head><body><div id='root'></div></body></html>")
            page.add_script_tag(content=shim);page.add_script_tag(content=js);page.add_script_tag(content=jjs);page.add_script_tag(content=cjs)
            return page

        errs=[];page=make_page()
        page.locator('#email').fill('doctor@onehms.com');page.locator('#password').fill('Demo123!');page.locator('#loginBtn').click();page.get_by_role('heading',name='Hospital overview').wait_for()
        page.locator('[data-journey-nav]').click();page.get_by_role('button',name='Doctor',exact=True).click();page.get_by_text('BrowserRx Patient',exact=False).wait_for()
        page.locator('[data-jdoctor-open]').first.click();page.get_by_text('Clinical record').wait_for()
        check('doctor visit file shows Prescribe action',page.locator('[data-jprescribe]').is_visible())
        page.locator('[data-jprescribe]').click();page.get_by_text('Prescribe medicine',exact=True).wait_for()
        check('prescribe modal opens for doctor without Inventory permission')
        options=page.locator('#jRx select[name="inventory_item_id"] option').all_text_contents()
        check('safe medication catalog loads into prescribe modal',any('Amoxicillin 500mg' in x for x in options))
        page.locator('#jRx select[name="inventory_item_id"]').select_option(str(amox['id']))
        page.locator('#jRx input[name="dose"]').fill('500 mg');page.locator('#jRx input[name="frequency"]').fill('TDS');page.locator('#jRx input[name="duration"]').fill('5 days');page.locator('#jRx input[name="quantity"]').fill('15');page.locator('#jRx button.primary').click();page.wait_for_timeout(500)
        visit=api('GET',f"/api/journey/visits/{v['id']}",doctor)
        check('doctor can submit prescription from Patient Journey',any(x['medicine']=='Amoxicillin 500mg' for x in visit['prescriptions']))
        api('POST',f"/api/journey/visits/{v['id']}/outcome",doctor,json={'outcome':'OUTPATIENT','pharmacy_choice':'HOSPITAL','note':'Use prescribed medicine'})

        page.close();page=make_page()
        page.locator('#email').fill('pharmacy@onehms.com');page.locator('#password').fill('Demo123!');page.locator('#loginBtn').click();page.locator('.appShell').wait_for();page.locator('[data-journey-nav]').click();page.locator('[data-jtab="pharmacy"]').click();page.locator('[data-junavailable]').wait_for()
        check('pharmacy queue shows prescribed medicine',page.get_by_text('Amoxicillin 500mg',exact=True).count()>=1)
        check('pharmacy has Not available here action',page.locator('[data-junavailable]').is_visible())
        page.once('dialog',lambda d:d.accept('Out of stock at hospital pharmacy'))
        page.locator('[data-junavailable]').click();page.wait_for_timeout(500)
        visit=api('GET',f"/api/journey/visits/{v['id']}",doctor)
        check('pharmacy can record unavailable medicine in UI',any(x['event_type']=='MEDICINE_UNAVAILABLE' and x['note']=='Out of stock at hospital pharmacy' for x in visit['events']))
        check('no uncaught JavaScript errors',not errs,errs)
        browser.close()
finally:
    server.terminate()
    try: server.wait(timeout=5)
    except Exception: server.kill()
print(f'PRESCRIPTION/PHARMACY BROWSER E2E: {len(results)}/{len(results)} PASS')
