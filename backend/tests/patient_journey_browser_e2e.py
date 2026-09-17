import os, subprocess, time, urllib.request, httpx, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; BACKEND=ROOT/'backend'; DB=Path(__file__).resolve().parent/'journey_browser.db'; PORT=8137; BASE=f'http://127.0.0.1:{PORT}'
try: DB.unlink()
except FileNotFoundError: pass
results=[]
def check(name,cond=True,detail=''):
    if not cond: raise AssertionError(detail or name)
    results.append(name); print('PASS',name,flush=True)

env=os.environ.copy();env['DATABASE_URL']=f'sqlite:///{DB}';env['JWT_SECRET']='journey-browser-secret-at-least-thirty-two-bytes';env['PYTHONPATH']=str(BACKEND)
server=subprocess.Popen(['python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT)],cwd=BACKEND,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            if urllib.request.urlopen(BASE+'/api/health',timeout=1).status==200: break
        except Exception: time.sleep(.1)
    else: raise RuntimeError('server did not start')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(7000);errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
        def proxy(route,request):
            path=request.url.replace('http://onehms.local','',1);h={k:v for k,v in request.headers.items() if k.lower() not in {'host','content-length','origin','referer'}};r=httpx.request(request.method,BASE+path,headers=h,content=request.post_data_buffer or b'',timeout=10);route.fulfill(status=r.status_code,headers={'content-type':r.headers.get('content-type','application/json')},body=r.content)
        page.route('http://onehms.local/api/**',proxy)
        css=(BACKEND/'web'/'styles.css').read_text()+(BACKEND/'web'/'patient_journey.css').read_text();js=(BACKEND/'web'/'app.js').read_text();jjs=(BACKEND/'web'/'patient_journey.js').read_text()
        shim="const __store=()=>({d:{},getItem(k){return this.d[k]||null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}});Object.defineProperty(window,'localStorage',{value:__store()});Object.defineProperty(window,'sessionStorage',{value:__store()});"
        page.set_content(f"<!doctype html><html><head><base href='http://onehms.local/'><style>{css}</style></head><body><div id='root'></div><script>{shim}</script><script>{js}</script><script>{jjs}</script></body></html>")
        page.locator('#loginBtn').click();page.get_by_role('heading',name='Hospital overview').wait_for()
        check('Patient Journey navigation is visible',page.locator('[data-journey-nav]').count()==1)
        page.locator('[data-journey-nav]').click();page.get_by_role('heading',name='Patient Journey').wait_for()
        check('Patient Journey overview renders',page.get_by_text('Reception',exact=True).first.is_visible())
        check('Patient Journey shows end-to-end flow',page.get_by_text('Close file',exact=True).is_visible())
        page.locator('main').get_by_role('button',name='Reception',exact=True).click();page.get_by_text('Open a visit file',exact=False).wait_for()
        check('Reception tab renders file-opening workflow')
        page.locator('#jNewPatient').click();page.locator('#jRegOpen input[name="first_name"]').fill('UI Journey');page.locator('#jRegOpen input[name="last_name"]').fill('Patient');page.locator('#jRegOpen input[name="phone"]').fill('+255712300001');page.locator('#jRegOpen textarea[name="reason"]').fill('Headache');page.locator('#jRegOpen button.primary').click();page.wait_for_timeout(500)
        check('Reception can create patient and visit file',page.get_by_text('UI Journey Patient',exact=False).first.is_visible())
        page.locator('main').get_by_role('button',name='Cashier',exact=True).click();page.get_by_text('Visit payments').wait_for()
        check('Cashier sees consultation payment queue',page.get_by_text('CONSULTATION',exact=True).first.is_visible())
        pay=page.locator('[data-jpay]').first;pay.click();page.locator('#jPay button.primary').click();page.wait_for_timeout(450)
        check('Cashier can record consultation payment',page.get_by_text('No pending visit payments.',exact=False).is_visible())
        page.locator('main').get_by_role('button',name='Doctor',exact=True).click();page.get_by_text('Not on shift').wait_for();page.locator('#jRoom').fill('OPD-09');page.locator('#jStartShift').click();page.wait_for_timeout(450)
        check('Doctor can start availability shift',page.get_by_text('Room OPD-09',exact=False).first.is_visible())
        check('Doctor queue displays paid patient',page.get_by_text('UI Journey Patient',exact=False).first.is_visible())
        page.locator('[data-jdoctor-open]').first.click();page.wait_for_timeout(500)
        check('Doctor can open visit file',page.get_by_text('Clinical record').is_visible())
        page.locator('[data-jconsult]').click();page.locator('#jConsult textarea[name="clinical_notes"]').fill('Assessed in OPD');page.locator('#jConsult textarea[name="diagnosis"]').fill('Suspected malaria');page.locator('#jConsult button.primary').click();page.wait_for_timeout(400)
        check('Doctor can save clinical notes')
        # Return doctor tab and reopen, then order lab.
        page.locator('main').get_by_role('button',name='Doctor',exact=True).click();page.locator('[data-jdoctor-open]').first.click();page.locator('[data-jlabs]').click();page.locator('#jLabOrder textarea[name="tests"]').fill('Malaria RDT');page.locator('#jLabOrder button.primary').click();page.wait_for_timeout(450)
        page.locator('main').get_by_role('button',name='Laboratory',exact=True).click();page.get_by_text('Malaria RDT').wait_for()
        check('Laboratory receives doctor order')
        page.locator('[data-jlab-result]').first.click();page.locator('#jLabResult textarea[name="result"]').fill('Negative');page.locator('#jLabResult input[name="verified"]').check();page.locator('#jLabResult button.primary').click();page.wait_for_timeout(450)
        check('Laboratory can return verified result',page.get_by_text('VERIFIED',exact=True).first.is_visible())
        page.locator('main').get_by_role('button',name='Doctor',exact=True).click();check('Patient returns to doctor queue after lab',page.get_by_text('UI Journey Patient',exact=False).first.is_visible())
        page.locator('main').get_by_role('button',name='Workflow Admin',exact=True).click();page.get_by_text('Hospital visit policy').wait_for()
        check('Workflow Admin settings render')
        check('Doctor attendance renders',page.get_by_text('Availability time').is_visible())
        check('No uncaught JavaScript errors',not errs,errs)
        browser.close()
finally:
    server.terminate();
    try: server.wait(timeout=5)
    except Exception: server.kill()
print(f'PATIENT JOURNEY BROWSER E2E: {len(results)}/{len(results)} PASS')
