import os, subprocess, time, urllib.request, httpx
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; BACKEND=ROOT/'backend'; DB=Path(__file__).resolve().parent/'notifications_pharmacy_browser.db'; PORT=8148; BASE=f'http://127.0.0.1:{PORT}'
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
    return r.json() if r.text else None

env=os.environ.copy();env['DATABASE_URL']=f'sqlite:///{DB}';env['JWT_SECRET']='notifications-browser-secret-at-least-thirty-two-bytes';env['PYTHONPATH']=str(BACKEND)
server=subprocess.Popen(['python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT)],cwd=BACKEND,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            if urllib.request.urlopen(BASE+'/api/health',timeout=1).status==200: break
        except Exception: time.sleep(.1)
    else: raise RuntimeError('server did not start')

    admin=login('admin@onehms.com','Admin123!'); reception=login('reception@onehms.com','Demo123!'); doctor=login('doctor@onehms.com','Demo123!'); pharmacy=login('pharmacy@onehms.com','Demo123!')
    api('PATCH','/api/notifications/settings',admin,json={'health_campaigns':True,'hospital_promotions':True,'emergency_notifications':True,'staff_communication':True})
    p=api('POST','/api/patients',reception,json={'first_name':'UI','last_name':'Notify','sex':'Female','phone':'0710555000','patient_category':'COST_SHARING','sms_operational_opt_in':True,'sms_marketing_opt_in':True})
    api('PATCH','/api/journey/settings',admin,json={'consultation_fee':0,'require_consultation_payment':False,'require_triage':False,'require_pharmacy_payment':False,'auto_assign_doctor':False})
    api('POST','/api/journey/doctor/shift/start',doctor,json={'room_number':'OPD-NOTIFY'})
    v=api('POST','/api/journey/visits',reception,json={'patient_id':p['id'],'reason':'Medicine bill browser test','priority':'NORMAL'})
    api('POST',f"/api/journey/visits/{v['id']}/claim",doctor,json={})
    cat=api('GET','/api/prescription-catalog',doctor); para=next(x for x in cat if x['name']=='Paracetamol 500mg')
    rx=api('POST',f"/api/journey/visits/{v['id']}/prescriptions",doctor,json={'source':'HOSPITAL','medicines':[{'inventory_item_id':para['id'],'medicine':para['name'],'dose':'500 mg','frequency':'TDS','duration':'3 days','quantity':6},{'medicine':'External Tablet','dose':'5 mg','frequency':'OD','duration':'5 days','quantity':5}]})
    detail=api('GET',f"/api/journey/visits/{v['id']}",pharmacy); ext=next(x for x in detail['prescriptions'] if x['medicine']=='External Tablet')
    api('PATCH',f"/api/prescriptions/{ext['id']}/unavailable",pharmacy,json={'reason':'Not stocked'})
    api('POST',f"/api/journey/visits/{v['id']}/outcome",doctor,json={'outcome':'OUTPATIENT','pharmacy_choice':'HOSPITAL','note':'Complete pharmacy plan'})

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        js=(BACKEND/'web'/'app.js').read_text(); njs=(BACKEND/'web'/'notifications.js').read_text(); rjs=(BACKEND/'web'/'receipt.js').read_text(); jjs=(BACKEND/'web'/'patient_journey.js').read_text(); cjs=(BACKEND/'web'/'care_pathways.js').read_text()
        shim="const __store=()=>({d:{},getItem(k){return this.d[k]||null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}});Object.defineProperty(window,'localStorage',{value:__store()});Object.defineProperty(window,'sessionStorage',{value:__store()});"
        errs=[]
        def make_page():
            page=browser.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(9000);page.on('pageerror',lambda e:errs.append(str(e)))
            def proxy(route,request):
                path=request.url.replace('http://onehms.local','',1);h={k:v for k,v in request.headers.items() if k.lower() not in {'host','content-length','origin','referer'}};r=httpx.request(request.method,BASE+path,headers=h,content=request.post_data_buffer or b'',timeout=10);route.fulfill(status=r.status_code,headers={'content-type':r.headers.get('content-type','application/json')},body=r.content)
            page.route('http://onehms.local/api/**',proxy);page.route('http://onehms.local/static/**',lambda route:route.abort())
            page.set_content("<!doctype html><html><head><base href='http://onehms.local/'></head><body><div id='root'></div></body></html>")
            for code in [shim,js,njs,rjs,jjs,cjs]: page.add_script_tag(content=code)
            return page

        page=make_page();page.locator('#email').fill('admin@onehms.com');page.locator('#password').fill('Admin123!');page.locator('#loginBtn').click();page.locator('.appShell').wait_for()
        page.locator('[data-page="notifications"]').click();page.get_by_role('heading',name='SMS & Notifications').wait_for()
        check('SMS & Notifications is a native admin workspace')
        check('all CEO poster event toggles are visible',page.locator('#nSettings input[type="checkbox"]').count()>=13)
        check('gateway configuration status is visible',page.get_by_text('NEOVAM SMS Gateway',exact=True).is_visible())
        page.locator('#nCampaign select[name="campaign_type"]').select_option('HEALTH_CAMPAIGN');page.locator('#nCampaign select[name="audience"]').select_option('PATIENTS');page.locator('#nCampaign input[name="title"]').fill('Health day');page.locator('#nCampaign textarea[name="message"]').fill('Free health screening is available this Friday.');page.locator('#nCampaign button.primary').click();page.wait_for_timeout(500)
        check('health campaign can be sent from notifications workspace',page.get_by_text('HEALTH_CAMPAIGN',exact=False).count()>=1)

        page.close();page=make_page();page.locator('#email').fill('pharmacy@onehms.com');page.locator('#password').fill('Demo123!');page.locator('#loginBtn').click();page.locator('.appShell').wait_for();page.locator('[data-journey-nav]').click();page.locator('[data-jtab="pharmacy"]').click();page.locator('[data-jmedbill]').wait_for()
        check('pharmacy patient journey exposes full medicine bill action')
        with page.expect_popup() as popinfo: page.locator('[data-jmedbill]').first.click()
        pop=popinfo.value;pop.wait_for_load_state('domcontentloaded');pop.wait_for_timeout(300)
        txt=pop.locator('body').inner_text()
        check('printed medicine bill includes hospital medicine','Paracetamol 500mg' in txt)
        check('printed medicine bill includes external medicine','External Tablet' in txt and 'EXTERNAL' in txt)
        check('printed bill distinguishes external price','External price' in txt and 'Hospital payable total' in txt)
        check('no uncaught JavaScript errors',not errs,errs)
        browser.close()
finally:
    server.terminate()
    try: server.wait(timeout=5)
    except Exception: server.kill()
print(f'NOTIFICATIONS/PHARMACY BROWSER E2E: {len(results)}/{len(results)} PASS')
