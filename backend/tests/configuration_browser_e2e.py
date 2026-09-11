import os, subprocess, time, urllib.request, json, httpx
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
BACKEND=ROOT/'backend'
DB=Path(__file__).resolve().parent/'configuration_browser_e2e.db'
REPORT=Path(__file__).resolve().parent/'CONFIGURATION_BROWSER_E2E_TEST_REPORT.md'
JSON_REPORT=Path(__file__).resolve().parent/'configuration_browser_e2e_results.json'
PORT=8142; BASE=f'http://127.0.0.1:{PORT}'
if DB.exists(): DB.unlink()
results=[]

def check(name,fn):
    try: fn(); results.append({'name':name,'status':'PASS','detail':''}); print('PASS',name,flush=True)
    except Exception as e: results.append({'name':name,'status':'FAIL','detail':str(e)[:500]}); print('FAIL',name,e,flush=True)

def assert_true(v,msg='assertion failed'): assert v,msg

def nav(page,key): page.locator(f'button[data-page="{key}"]').click(); page.wait_for_timeout(250)
def login(page,email,password):
    page.locator('#email').fill(email); page.locator('#password').fill(password); page.locator('#loginBtn').click(); page.wait_for_selector('.appShell',timeout=7000)
def switch(page,key): return page.locator(f'button[data-module="{key}"]')
def is_on(page,key): return 'on' in (switch(page,key).get_attribute('class') or '').split()
def click_switch(page,key): switch(page,key).click(); page.wait_for_timeout(350)
def write_report():
    passed=sum(x['status']=='PASS' for x in results)
    lines=['# One HMS — Configuration Browser E2E Test Report','',f'- Checks: **{len(results)}**',f'- Passed: **{passed}**',f'- Failed: **{len(results)-passed}**','',
           'This suite uses two real Chromium sessions to verify that hospital configuration switches affect navigation and module availability for currently logged-in staff.','',
           '| Check | Result | Detail |','|---|---|---|']
    for x in results: lines.append(f"| {x['name']} | {x['status']} | {x['detail'].replace('|','\\|')} |")
    REPORT.write_text('\n'.join(lines)); JSON_REPORT.write_text(json.dumps(results,indent=2))

def main():
    env=os.environ.copy(); env['DATABASE_URL']=f'sqlite:///{DB}'; env['JWT_SECRET']='config-browser-secret-longer-than-thirty-two-bytes'; env['PYTHONPATH']=str(BACKEND)
    server=subprocess.Popen(['python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT)],cwd=BACKEND,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                with urllib.request.urlopen(BASE+'/api/health',timeout=1) as r:
                    if r.status==200: break
            except Exception: time.sleep(.12)
        else: raise RuntimeError('server did not start')
        css=(BACKEND/'web'/'styles.css').read_text(); js=(BACKEND/'web'/'app.js').read_text()
        shim="const __store=()=>({d:{},getItem(k){return this.d[k]||null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}});Object.defineProperty(window,'localStorage',{value:__store()});Object.defineProperty(window,'sessionStorage',{value:__store()});"
        html=f"<!doctype html><html><head><base href='http://onehms.local/'><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><style>{css}</style></head><body><div id='root'></div><script>{shim}</script><script>{js}</script></body></html>"
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            def prepare(page):
                def proxy_api(route, request):
                    path=request.url.replace('http://onehms.local','',1)
                    headers={k:v for k,v in request.headers.items() if k.lower() not in {'host','content-length','origin','referer'}}
                    r=httpx.request(request.method,BASE+path,headers=headers,content=request.post_data_buffer or b'',timeout=10.0)
                    route.fulfill(status=r.status_code,headers={'content-type':r.headers.get('content-type','application/json')},body=r.content)
                page.route('http://onehms.local/api/**',proxy_api); page.set_content(html,wait_until='load')
            admin=browser.new_context(viewport={'width':1440,'height':1000}).new_page(); admin.set_default_timeout(7000); prepare(admin)
            login(admin,'admin@onehms.com','Admin123!'); nav(admin,'modules')
            check('Configuration page loads for administrator',lambda: admin.get_by_role('heading',name='Hospital & Module Configuration').wait_for())
            check('Core Patient Registration switch is locked',lambda: assert_true(switch(admin,'patients').is_disabled()))
            check('District preset starts with Theatre disabled',lambda: assert_true(not is_on(admin,'theatre')))
            click_switch(admin,'theatre')
            check('Theatre can be enabled through the real UI',lambda: assert_true(is_on(admin,'theatre')))

            surgeon=browser.new_context(viewport={'width':1280,'height':900}).new_page(); surgeon.set_default_timeout(7000); prepare(surgeon)
            login(surgeon,'surgeon@onehms.com','Demo123!')
            check('Surgeon sees Specialist Modules when Theatre is enabled',lambda: surgeon.locator('button[data-page="operations"]').wait_for(state='visible'))

            # Disable Theatre in the admin session. Surgeon session remains open.
            click_switch(admin,'theatre')
            check('Admin UI immediately shows Theatre disabled',lambda: assert_true(not is_on(admin,'theatre')))
            surgeon.locator('button[data-page="operations"]').click(); surgeon.wait_for_timeout(450)
            check('Existing Surgeon session refreshes configuration on next navigation',lambda: assert_true(surgeon.locator('#opSelect option[value="theatre"]').count()==0,'disabled Theatre remained selectable'))
            check('Disabled Theatre does not produce an error screen for current staff session',lambda: assert_true(surgeon.locator('.error').count()==0,'error screen shown'))

            click_switch(admin,'theatre')
            check('Admin can re-enable Theatre',lambda: assert_true(is_on(admin,'theatre')))
            # Trigger a fresh screen transition in the still-open surgeon session.
            surgeon.locator('button[data-page="patients"]').click(); surgeon.wait_for_timeout(250); surgeon.locator('button[data-page="operations"]').click(); surgeon.wait_for_timeout(350)
            check('Existing Surgeon session sees re-enabled Theatre without re-login',lambda: assert_true(surgeon.locator('#opSelect option[value="theatre"]').count()==1,'re-enabled Theatre option missing'))

            # Dependency behavior: District starts with wards+beds on.
            check('Wards are enabled before dependency test',lambda: assert_true(is_on(admin,'wards')))
            check('Beds are enabled before dependency test',lambda: assert_true(is_on(admin,'beds')))
            click_switch(admin,'wards')
            check('Disabling Wards switches Wards off',lambda: assert_true(not is_on(admin,'wards')))
            check('Disabling Wards automatically switches Beds off',lambda: assert_true(not is_on(admin,'beds')))
            click_switch(admin,'beds')
            check('Enabling Beds switches Beds on',lambda: assert_true(is_on(admin,'beds')))
            check('Enabling Beds automatically switches required Wards on',lambda: assert_true(is_on(admin,'wards')))

            # Presets from the actual facility settings dialog.
            admin.locator('#editHospital').click(); admin.locator('#hf select[name="facility_type"]').select_option('SMALL'); admin.locator('#hf input[name="apply_preset"]').check(); admin.locator('#saveHospital').click(); admin.wait_for_timeout(450)
            check('SMALL preset applied through UI changes facility label',lambda: assert_true('SMALL' in admin.locator('.facilityPill').first.inner_text()))
            check('SMALL preset disables every optional switch in UI',lambda: assert_true(admin.locator('button.switch:not([disabled]).on').count()==0,'optional modules remained enabled'))

            admin.locator('#editHospital').click(); admin.locator('#hf select[name="facility_type"]').select_option('REFERRAL'); admin.locator('#hf input[name="apply_preset"]').check(); admin.locator('#saveHospital').click(); admin.wait_for_timeout(450)
            optional_count=admin.locator('button.switch:not([disabled])').count()
            check('REFERRAL preset enables every optional switch in UI',lambda: assert_true(admin.locator('button.switch:not([disabled]).on').count()==optional_count,'not all optional modules enabled'))
            check('REFERRAL preset keeps every core switch enabled',lambda: assert_true(admin.locator('button.switch[disabled]:not(.on)').count()==0,'a core switch is off'))

            nav(admin,'dashboard'); nav(admin,'modules')
            check('Configuration survives normal screen transitions',lambda: assert_true(admin.locator('button.switch:not([disabled]).on').count()==admin.locator('button.switch:not([disabled])').count()))
            check('Facility type remains REFERRAL after screen transitions',lambda: assert_true('REFERRAL' in admin.locator('.facilityPill').first.inner_text()))
            browser.close()
    finally:
        server.terminate()
        try: server.wait(timeout=5)
        except Exception: server.kill()
        write_report()
        if DB.exists(): DB.unlink()
    failures=[x for x in results if x['status']=='FAIL']
    print(f'CONFIGURATION BROWSER E2E: {len(results)-len(failures)}/{len(results)} PASS')
    if failures: raise SystemExit(1)

if __name__=='__main__': main()
