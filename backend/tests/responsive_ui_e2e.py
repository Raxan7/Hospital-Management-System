import os, subprocess, time, urllib.request, httpx, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
BACKEND=ROOT/'backend'
DB=Path(__file__).resolve().parent/'responsive_ui_e2e.db'
REPORT=Path(__file__).resolve().parent/'RESPONSIVE_UI_E2E_TEST_REPORT.md'
JSON_REPORT=Path(__file__).resolve().parent/'responsive_ui_e2e_results.json'
PORT=8133
BASE=f'http://127.0.0.1:{PORT}'
if DB.exists(): DB.unlink()
results=[]

def check(name, fn):
    try:
        fn(); results.append((name,'PASS','')); print('PASS',name,flush=True)
    except Exception as e:
        results.append((name,'FAIL',str(e)[:400])); print('FAIL',name,e,flush=True)

def write_report():
    passed=sum(s=='PASS' for _,s,_ in results)
    lines=['# One HMS — Responsive UI E2E Test Report','',f'- Checks: **{len(results)}**',f'- Passed: **{passed}**',f'- Failed: **{len(results)-passed}**','',
           'This suite runs the production UI at desktop, tablet, and mobile viewport sizes in Chromium.','',
           '| Check | Result | Detail |','|---|---|---|']
    for n,s,d in results: lines.append(f"| {n} | {s} | {d.replace('|','\\|')} |")
    REPORT.write_text('\n'.join(lines)); JSON_REPORT.write_text(json.dumps([{'name':n,'status':s,'detail':d} for n,s,d in results],indent=2))

def main():
    env=os.environ.copy(); env['DATABASE_URL']=f'sqlite:///{DB}'; env['JWT_SECRET']='responsive-e2e-secret-longer-than-thirty-two-bytes'; env['PYTHONPATH']=str(BACKEND)
    server=subprocess.Popen(['python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(PORT)],cwd=BACKEND,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                with urllib.request.urlopen(BASE+'/api/health',timeout=1) as r:
                    if r.status==200: break
            except Exception: time.sleep(.12)
        else: raise RuntimeError('Uvicorn did not start')
        css=(BACKEND/'web'/'styles.css').read_text(); js=(BACKEND/'web'/'app.js').read_text()
        shim="const __store=()=>({d:{},getItem(k){return this.d[k]||null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}});Object.defineProperty(window,'localStorage',{value:__store()});Object.defineProperty(window,'sessionStorage',{value:__store()});"
        html=f"<!doctype html><html><head><base href='http://onehms.local/'><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><style>{css}</style></head><body><div id='root'></div><script>{shim}</script><script>{js}</script></body></html>"
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            for label,w,h in [('Desktop',1440,950),('Tablet',820,1050),('Mobile',390,844)]:
                page=browser.new_page(viewport={'width':w,'height':h}); page.set_default_timeout(7000)
                def proxy_api(route, request):
                    path=request.url.replace('http://onehms.local','',1)
                    headers={k:v for k,v in request.headers.items() if k.lower() not in {'host','content-length','origin','referer'}}
                    r=httpx.request(request.method,BASE+path,headers=headers,content=request.post_data_buffer or b'',timeout=10.0)
                    route.fulfill(status=r.status_code,headers={'content-type':r.headers.get('content-type','application/json')},body=r.content)
                page.route('http://onehms.local/api/**',proxy_api); page.set_content(html,wait_until='load')
                check(f'{label}: login fits viewport',lambda p=page,w=w: (_ for _ in ()).throw(AssertionError('horizontal overflow')) if p.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth') else None)
                check(f'{label}: login form visible',lambda p=page: p.locator('#loginBtn').wait_for(state='visible'))
                page.locator('#loginBtn').click(); page.get_by_role('heading',name='Hospital overview').wait_for()
                check(f'{label}: dashboard has no page-level horizontal overflow',lambda p=page: (_ for _ in ()).throw(AssertionError('horizontal overflow')) if p.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth') else None)
                check(f'{label}: dashboard cards visible',lambda p=page: p.locator('.stat').first.wait_for(state='visible'))
                if label=='Desktop':
                    check('Desktop: persistent sidebar visible',lambda p=page: p.locator('#sidebar').wait_for(state='visible'))
                    check('Desktop: mobile menu hidden',lambda p=page: (_ for _ in ()).throw(AssertionError('mobile menu visible')) if p.locator('#openNav').is_visible() else None)
                if label=='Tablet':
                    check('Tablet: mobile navigation trigger visible',lambda p=page: p.locator('#openNav').wait_for(state='visible'))
                    page.locator('#openNav').click()
                    check('Tablet: navigation drawer opens',lambda p=page: p.locator('#sidebar.mobileOpen').wait_for(state='visible'))
                    page.locator('#sidebarOverlay').click()
                if label=='Mobile':
                    check('Mobile: navigation trigger visible',lambda p=page: p.locator('#openNav').wait_for(state='visible'))
                    page.locator('#openNav').click(); check('Mobile: drawer opens',lambda p=page: p.locator('#sidebar.mobileOpen').wait_for(state='visible'))
                    pbtn=page.locator('button[data-page="patients"]'); pbtn.click(); page.get_by_role('heading',name='Patients').wait_for()
                    check('Mobile: selecting navigation closes drawer',lambda p=page: (_ for _ in ()).throw(AssertionError('drawer remained open')) if p.locator('#sidebar.mobileOpen').count() else None)
                    page.locator('#newPatient').click();
                    check('Mobile: form modal fits viewport width',lambda p=page,w=w: (_ for _ in ()).throw(AssertionError(p.locator('.modal').bounding_box())) if (p.locator('.modal').bounding_box()['width'] > w+1) else None)
                    check('Mobile: form fields stack to one column',lambda p=page: (_ for _ in ()).throw(AssertionError('fields did not stack')) if p.locator('#pf .field').nth(1).bounding_box()['y'] <= p.locator('#pf .field').nth(0).bounding_box()['y'] else None)
                    page.locator('[data-close]').click()
                    check('Mobile: patients table scroll does not overflow page',lambda p=page: (_ for _ in ()).throw(AssertionError('page overflow')) if p.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth') else None)
                page.close()
            browser.close()
    finally:
        server.terminate()
        try: server.wait(timeout=5)
        except Exception: server.kill()
        write_report()
        if DB.exists(): DB.unlink()
    if any(s=='FAIL' for _,s,_ in results): raise SystemExit(1)
    print(f'RESPONSIVE UI E2E: {sum(s=="PASS" for _,s,_ in results)}/{len(results)} PASS')

if __name__=='__main__': main()
