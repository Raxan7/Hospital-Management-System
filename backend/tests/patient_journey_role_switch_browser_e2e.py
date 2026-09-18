import os, subprocess, time, urllib.request, httpx
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BACKEND=ROOT/'backend'
DB=Path(__file__).resolve().parent/'journey_role_switch_browser.db'
PORT=8147
BASE=f'http://127.0.0.1:{PORT}'
try: DB.unlink()
except FileNotFoundError: pass

results=[]
def check(name, cond=True, detail=''):
    if not cond: raise AssertionError(detail or name)
    results.append(name); print('PASS', name, flush=True)

env=os.environ.copy()
env['DATABASE_URL']=f'sqlite:///{DB}'
env['JWT_SECRET']='journey-role-switch-browser-secret-at-least-thirty-two-bytes'
env['PYTHONPATH']=str(BACKEND)
server=subprocess.Popen(['python3','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT)],cwd=BACKEND,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            if urllib.request.urlopen(BASE+'/api/health',timeout=1).status==200: break
        except Exception: time.sleep(.1)
    else: raise RuntimeError('server did not start')

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.set_default_timeout(8000)
        errs=[]
        page.on('pageerror',lambda e:errs.append(str(e)))
        def proxy(route,request):
            path=request.url.replace('http://onehms.local','',1)
            h={k:v for k,v in request.headers.items() if k.lower() not in {'host','content-length','origin','referer'}}
            r=httpx.request(request.method,BASE+path,headers=h,content=request.post_data_buffer or b'',timeout=10)
            route.fulfill(status=r.status_code,headers={'content-type':r.headers.get('content-type','application/json')},body=r.content)
        page.route('http://onehms.local/api/**',proxy)
        css=(BACKEND/'web'/'styles.css').read_text()+(BACKEND/'web'/'patient_journey.css').read_text()
        js=(BACKEND/'web'/'app.js').read_text(); jjs=(BACKEND/'web'/'patient_journey.js').read_text()
        shim="const __store=()=>({d:{},getItem(k){return this.d[k]||null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}});Object.defineProperty(window,'localStorage',{value:__store()});Object.defineProperty(window,'sessionStorage',{value:__store()});"
        page.set_content(f"<!doctype html><html><head><base href='http://onehms.local/'><style>{css}</style></head><body><div id='root'></div><script>{shim}</script><script>{js}</script><script>{jjs}</script></body></html>", wait_until="domcontentloaded", timeout=20000)

        def login(email,password):
            page.locator('#email').fill(email)
            page.locator('#password').fill(password)
            page.locator('#loginBtn').click()

        def logout():
            page.locator('#logout').click()
            page.get_by_role('heading',name='Welcome back').wait_for()

        # Admin leaves the SPA on the privileged Workflow Admin tab.
        login('admin@onehms.com','Admin123!')
        page.get_by_role('heading',name='Hospital overview').wait_for()
        page.locator('[data-journey-nav]').click()
        page.get_by_role('heading',name='Patient Journey').wait_for()
        page.locator('main').get_by_role('button',name='Workflow Admin',exact=True).click()
        page.get_by_text('Hospital visit policy').wait_for()
        check('admin can open Workflow Admin tab')
        logout()

        # Doctor logs in without a page reload. page and journeyTab are still retained in JS.
        login('doctor@onehms.com','Demo123!')
        page.get_by_role('heading',name='Patient Journey').wait_for()
        check('doctor is normalized to Patient Journey overview after admin logout',page.locator('[data-jtab="overview"].active').count()==1)
        check('doctor does not get permission-denied screen',page.get_by_text('The requested screen could not load').count()==0)
        check('doctor cannot see Workflow Admin tab',page.locator('[data-jtab="admin"]').count()==0)
        page.locator('main').get_by_role('button',name='Doctor',exact=True).click()
        page.get_by_text('My shift').wait_for()
        check('doctor tab still works')
        logout()

        # Cashier inherits the stale Doctor tab unless role-aware normalization runs.
        login('cashier@onehms.com','Demo123!')
        page.get_by_role('heading',name='Patient Journey').wait_for()
        check('cashier is normalized to Patient Journey overview after doctor logout',page.locator('[data-jtab="overview"].active').count()==1)
        check('cashier does not get permission-denied screen',page.get_by_text('The requested screen could not load').count()==0)
        check('cashier only receives allowed journey tabs',page.locator('[data-jtab="cashier"]').count()==1 and page.locator('[data-jtab="doctor"]').count()==0)
        page.locator('main').get_by_role('button',name='Cashier',exact=True).click()
        page.get_by_role('heading',name='Visit payments').wait_for()
        check('cashier tab still works')
        logout()

        # Lab user inherits stale Cashier tab and must also safely fall back.
        login('lab@onehms.com','Demo123!')
        page.get_by_role('heading',name='Patient Journey').wait_for()
        check('laboratory role is normalized to overview after cashier logout',page.locator('[data-jtab="overview"].active').count()==1)
        check('laboratory role does not get permission-denied screen',page.get_by_text('The requested screen could not load').count()==0)
        check('laboratory tab is available',page.locator('[data-jtab="lab"]').count()==1)
        page.locator('main').get_by_role('button',name='Laboratory',exact=True).click()
        page.get_by_role('heading',name='Ordered tests').wait_for()
        check('laboratory tab still works')
        logout()

        # Pharmacy inherits the stale Laboratory tab.
        login('pharmacy@onehms.com','Demo123!')
        page.get_by_role('heading',name='Patient Journey').wait_for()
        check('pharmacy role is normalized to overview after laboratory logout',page.locator('[data-jtab="overview"].active').count()==1)
        check('pharmacy role does not get permission-denied screen',page.get_by_text('The requested screen could not load').count()==0)
        page.locator('main').get_by_role('button',name='Pharmacy',exact=True).click()
        page.get_by_role('heading',name='Prescription queue').wait_for()
        check('pharmacy tab still works')
        logout()

        # Nurse inherits the stale Pharmacy tab.
        login('nurse@onehms.com','Demo123!')
        page.get_by_role('heading',name='Patient Journey').wait_for()
        check('nurse role is normalized to overview after pharmacy logout',page.locator('[data-jtab="overview"].active').count()==1)
        check('nurse role does not get permission-denied screen',page.get_by_text('The requested screen could not load').count()==0)
        page.locator('main').get_by_role('button',name='Inpatient',exact=True).click()
        page.get_by_role('heading',name='Waiting for bed').wait_for()
        check('nurse inpatient tab still works')
        logout()

        # Reception inherits the stale Inpatient tab.
        login('reception@onehms.com','Demo123!')
        page.get_by_role('heading',name='Patient Journey').wait_for()
        check('reception role is normalized to overview after nurse logout',page.locator('[data-jtab="overview"].active').count()==1)
        check('reception role does not get permission-denied screen',page.get_by_text('The requested screen could not load').count()==0)
        page.locator('main').get_by_role('button',name='Reception',exact=True).click()
        page.get_by_role('heading',name='Open a visit file').wait_for()
        check('reception tab still works')

        check('no uncaught JavaScript errors',not errs,errs)
        browser.close()
finally:
    server.terminate()
    try: server.wait(timeout=5)
    except Exception: server.kill()

print(f'PATIENT JOURNEY ROLE-SWITCH BROWSER E2E: {len(results)}/{len(results)} PASS')
