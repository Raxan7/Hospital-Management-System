/* Patient Journey workflow patch — additive UI layer */
(() => {
  let journeyTab = 'overview';
  let journeyWorkspace = null;
  const jEsc = s => typeof esc === 'function' ? esc(s) : String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const jMoney = n => typeof money === 'function' ? money(n) : `TZS ${Number(n||0).toLocaleString()}`;
  const jApi = (...args) => api(...args);
  const jCan = (m,a='VIEW') => typeof can === 'function' && can(m,a);
  const stageLabel = s => ({
    AWAITING_PAYMENT:'Awaiting consultation payment', TRIAGE:'Waiting for triage', WAITING_DOCTOR:'Waiting for doctor',
    WITH_DOCTOR:'With doctor', LAB_PENDING:'At laboratory', LAB_RESULTS_READY:'Results ready / doctor review',
    PHARMACY_PENDING:'Pharmacy billing', PHARMACY_READY:'Ready for dispensing', CLOSING_PENDING_PHARMACY:'Doctor completed · pharmacy pending',
    ADMISSION_PENDING:'Admission requested', ADMITTED:'Admitted', DISCHARGE_PENDING:'Discharge approved', CLOSED:'Closed'
  }[s] || s);
  const jBadge = s => `<span class="journeyBadge stage-${String(s||'').toLowerCase()}">${jEsc(stageLabel(s))}</span>`;
  const dateTime = x => x ? new Date(x).toLocaleString() : '—';
  const input = (label, html) => `<label class="field"><span>${jEsc(label)}</span>${html}</label>`;
  const jModal = (title, body) => typeof modal === 'function' ? modal(title, body) : null;
  const jToast = m => typeof toast === 'function' ? toast(m) : alert(m);

  // Make Patient Journey a first-class page without rewriting the existing app shell.
  if (typeof pageModule !== 'undefined') pageModule.journey = null;
  if (typeof icon !== 'undefined') icon.journey = '⇄';
  if (typeof pages === 'undefined') return;

  const oldShell = shell;
  shell = function(content){
    oldShell(content);
    const nav = document.querySelector('.sidebar nav');
    if (nav && !nav.querySelector('[data-journey-nav]') && hasJourneyAccess()) {
      const b = document.createElement('button');
      b.dataset.journeyNav = '1';
      b.className = page === 'journey' ? 'active' : '';
      b.innerHTML = `<span class="navIcon">⇄</span><span>Patient Journey</span>`;
      const first = nav.querySelector('button');
      if (first?.nextSibling) nav.insertBefore(b, first.nextSibling); else nav.appendChild(b);
      b.onclick = () => { page='journey'; render(); };
    }
    if (page === 'journey') {
      const title = document.querySelector('.topBarTitle b'); if (title) title.textContent='Patient Journey';
    }
  };

  function hasJourneyAccess(){
    return ['reception','triage','consultation','laboratory','pharmacy','billing','wards','configuration'].some(m => jCan(m));
  }
  function tabs(){
    const list=[['overview','Overview',true],['reception','Reception',jCan('reception')],['cashier','Cashier',jCan('billing')],['triage','Triage',jCan('triage')],['doctor','Doctor',jCan('consultation')],['lab','Laboratory',jCan('laboratory')],['pharmacy','Pharmacy',jCan('pharmacy')],['inpatient','Inpatient',jCan('wards')],['admin','Workflow Admin',jCan('configuration')]];
    return `<div class="journeyTabs">${list.filter(x=>x[2]).map(([id,l])=>`<button data-jtab="${id}" class="${journeyTab===id?'active':''}">${l}</button>`).join('')}</div>`;
  }
  async function refreshWorkspace(){ journeyWorkspace=await jApi('/api/journey/workspace'); return journeyWorkspace; }
  function openVisitsTable(rows){
    return `<div class="panel tableWrap"><table><thead><tr><th>File</th><th>Patient</th><th>Stage</th><th>Doctor / room</th><th>Opened</th><th></th></tr></thead><tbody>${rows.map(v=>`<tr><td><b>${jEsc(v.file_no)}</b><br><small>${jEsc(v.priority)}</small></td><td>${jEsc(v.patient_no)}<br>${jEsc(v.patient_name)}</td><td>${jBadge(v.stage)}</td><td>${jEsc(v.doctor_name||'Unassigned')}<br><small>${v.room?'Room '+jEsc(v.room):'—'}${v.queue_position?` · Queue ${v.queue_position}`:''}</small></td><td>${dateTime(v.opened_at)}</td><td><button class="linkBtn" data-jdetail="${v.id}">Open file</button></td></tr>`).join('')}</tbody></table>${rows.length?'':'<div class="empty">No open visit files</div>'}</div>`;
  }
  function bindDetails(){ document.querySelectorAll('[data-jdetail]').forEach(b=>b.onclick=()=>showVisit(Number(b.dataset.jdetail))); }

  pages.journey = async () => {
    await refreshWorkspace();
    let content='';
    if(journeyTab==='overview') content=renderOverview();
    if(journeyTab==='reception') content=await renderReception();
    if(journeyTab==='cashier') content=await renderCashier();
    if(journeyTab==='triage') content=await renderTriage();
    if(journeyTab==='doctor') content=await renderDoctor();
    if(journeyTab==='lab') content=await renderLab();
    if(journeyTab==='pharmacy') content=await renderPharmacy();
    if(journeyTab==='inpatient') content=await renderInpatient();
    if(journeyTab==='admin') content=await renderAdmin();
    shell(header('Patient Journey','One visit file from reception to clinical completion and discharge')+tabs()+content);
    document.querySelectorAll('[data-jtab]').forEach(b=>b.onclick=()=>{journeyTab=b.dataset.jtab;pages.journey()});
    bindDetails();
    bindTabActions();
  };

  function renderOverview(){
    const rows=journeyWorkspace.open_visits||[];
    const counts={};rows.forEach(v=>counts[v.stage]=(counts[v.stage]||0)+1);
    const cards=[['Open visit files',rows.length],['Awaiting payment',counts.AWAITING_PAYMENT||0],['Waiting doctor',(counts.WAITING_DOCTOR||0)+(counts.LAB_RESULTS_READY||0)],['At lab',counts.LAB_PENDING||0],['Pharmacy',(counts.PHARMACY_PENDING||0)+(counts.PHARMACY_READY||0)+(counts.CLOSING_PENDING_PHARMACY||0)],['Admitted',counts.ADMITTED||0]];
    return `<div class="journeyFlow"><div>Reception</div><span>→</span><div>Payment${journeyWorkspace.settings.require_triage?' / Triage':''}</div><span>→</span><div>Doctor</div><span>→</span><div>Lab / Treatment</div><span>→</span><div>Pharmacy or Ward</div><span>→</span><div>Close file</div></div><div class="journeyStats">${cards.map(([l,v])=>`<div class="journeyStat"><b>${v}</b><span>${l}</span></div>`).join('')}</div>${openVisitsTable(rows)}`;
  }

  async function renderReception(){
    const fee=journeyWorkspace.settings;
    return `<div class="journeySplit"><div class="panel"><div class="journeyPanelHead"><div><span class="eyebrow">Reception</span><h3>Open a visit file</h3><p class="muted">Patient number is permanent; file number is new for every visit.</p></div><button class="primary" id="jNewPatient">+ New patient & visit</button></div><div class="journeySearch"><input id="jPatientSearch" placeholder="Patient no, name or phone"><button class="ghost" id="jSearchPatient">Search</button></div><div id="jPatientResults" class="journeyResults"><div class="empty">Search for an existing patient.</div></div><div class="notice">Consultation fee: <b>${jMoney(fee.consultation_fee)}</b>. ${fee.require_triage?'After payment the patient goes to triage, then the doctor.':'After payment the patient enters the doctor queue.'}</div></div><div class="panel"><span class="eyebrow">Current flow</span><h3>Reception queue</h3><p class="muted">All open files remain visible until outpatient completion or inpatient discharge.</p>${openVisitsTable(journeyWorkspace.open_visits||[])}</div></div>`;
  }
  async function searchPatients(){
    const q=document.getElementById('jPatientSearch').value.trim();if(!q)return;
    const rows=await jApi('/api/patients?q='+encodeURIComponent(q));
    document.getElementById('jPatientResults').innerHTML=rows.length?rows.map(p=>`<div class="journeyPatient"><div><b>${jEsc(p.patient_no)} · ${jEsc(p.first_name)} ${jEsc(p.last_name)}</b><span>${jEsc(p.phone||'No phone')}</span></div><button class="primary" data-open-patient="${p.id}">Open visit</button></div>`).join(''):'<div class="empty">No patients found.</div>';
    document.querySelectorAll('[data-open-patient]').forEach(b=>b.onclick=()=>openExistingVisit(Number(b.dataset.openPatient),rows.find(x=>x.id===Number(b.dataset.openPatient))));
  }
  function openExistingVisit(patientId,p){
    const m=jModal('Open visit file',`<form id="jOpenVisit" class="formGrid"><div class="notice span2"><b>${jEsc(p.patient_no)} · ${jEsc(p.first_name)} ${jEsc(p.last_name)}</b></div>${input('Reason / presenting complaint','<textarea name="reason" rows="3" placeholder="Why has the patient come today?"></textarea>')}${input('Priority','<select name="priority"><option>NORMAL</option><option>URGENT</option><option>EMERGENCY</option></select>')}<div class="modalActions span2"><button class="primary">Open file</button></div></form>`);
    m.querySelector('#jOpenVisit').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target);try{const v=await jApi('/api/journey/visits',{method:'POST',body:JSON.stringify({patient_id:patientId,reason:fd.get('reason'),priority:fd.get('priority')})});m.remove();jToast(`File ${v.file_no} opened`);pages.journey()}catch(x){jToast(x.message)}};
  }
  function newPatientVisit(){
    const m=jModal('Register patient & open visit',`<form id="jRegOpen" class="formGrid">${input('First name','<input name="first_name" required>')}${input('Last name','<input name="last_name" required>')}${input('Sex','<select name="sex"><option>Female</option><option>Male</option><option>Unknown</option></select>')}${input('Phone','<input name="phone" placeholder="+255...">')}${input('Date of birth','<input name="date_of_birth" type="date">')}${input('Address','<input name="address">')}${input('Next of kin','<input name="next_of_kin">')}${input('Priority','<select name="priority"><option>NORMAL</option><option>URGENT</option><option>EMERGENCY</option></select>')}${input('Reason / presenting complaint','<textarea name="reason" rows="3"></textarea>')}<div class="modalActions span2"><button class="primary">Register & open file</button></div></form>`);
    m.querySelector('#jRegOpen').onsubmit=async e=>{e.preventDefault();const o=Object.fromEntries(new FormData(e.target));if(!o.date_of_birth)delete o.date_of_birth;try{const v=await jApi('/api/journey/register-and-open',{method:'POST',body:JSON.stringify(o)});m.remove();jToast(`Patient ${v.patient_no} · file ${v.file_no}`);pages.journey()}catch(x){jToast(x.message)}};
  }

  async function renderCashier(){
    const rows=await jApi('/api/journey/billing-queue');
    return `<div class="panel"><div class="journeyPanelHead"><div><span class="eyebrow">Cashier</span><h3>Visit payments</h3><p class="muted">Consultation payment unlocks the clinical queue. Hospital-pharmacy payment is tracked separately.</p></div></div>${rows.length?`<div class="tableWrap"><table><thead><tr><th>File</th><th>Patient</th><th>Charge</th><th>Amount</th><th>Paid</th><th>Balance</th><th></th></tr></thead><tbody>${rows.map(x=>`<tr><td>${jEsc(x.file_no)}</td><td>${jEsc(x.patient_no)}<br>${jEsc(x.patient_name)}</td><td>${jEsc(x.kind)}</td><td>${jMoney(x.invoice.amount)}</td><td>${jMoney(x.invoice.paid_amount)}</td><td><b>${jMoney(x.invoice.balance)}</b></td><td><div class="actions" style="justify-content:flex-start"><button class="primary" data-jpay="${x.invoice.id}" data-balance="${x.invoice.balance}">Record payment</button>${jCan('billing','PRINT')?`<button class="ghost" data-jreceipt="${x.invoice.id}">Receipt</button>`:''}</div></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">No pending visit payments.</div>'}</div>`;
  }
  function payInvoice(id,balance){
    const m=jModal('Record payment',`<form id="jPay" class="formGrid">${input('Amount',`<input name="amount" type="number" min="0.01" step="0.01" max="${balance}" value="${balance}" required>`)}${input('Method','<select name="method"><option>CASH</option><option>MOBILE_MONEY</option><option>CARD</option><option>BANK</option><option>INSURANCE</option></select>')}${input('Reference','<input name="reference" placeholder="Receipt / transaction reference">')}<div class="modalActions span2"><button class="primary">Save payment</button></div></form>`);
    m.querySelector('#jPay').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target);try{await jApi(`/api/invoices/${id}/payments`,{method:'POST',body:JSON.stringify({amount:Number(fd.get('amount')),method:fd.get('method'),reference:fd.get('reference')||null})});m.remove();jToast('Payment recorded');pages.journey()}catch(x){jToast(x.message)}};
  }

  async function renderTriage(){
    const rows=await jApi('/api/journey/triage-queue');
    return `<div class="panel"><span class="eyebrow">Triage</span><h3>Vitals queue</h3><p class="muted">This step appears only when the hospital enables triage-before-doctor in workflow settings.</p>${rows.length?`<div class="tableWrap"><table><thead><tr><th>File</th><th>Patient</th><th>Reason</th><th></th></tr></thead><tbody>${rows.map(v=>`<tr><td>${jEsc(v.file_no)}</td><td>${jEsc(v.patient_no)}<br>${jEsc(v.patient_name)}</td><td>${jEsc(v.reason||'—')}</td><td><button class="primary" data-jtriage="${v.id}">Record vitals</button></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">No patients waiting for triage.</div>'}</div>`;
  }
  function triageForm(id){
    const m=jModal('Record vitals',`<form id="jTriage" class="formGrid">${input('Temperature °C','<input name="temperature_c" type="number" step="0.1">')}${input('Pulse','<input name="pulse" type="number">')}${input('BP systolic','<input name="systolic" type="number">')}${input('BP diastolic','<input name="diastolic" type="number">')}${input('SpO₂','<input name="spo2" type="number">')}${input('Weight kg','<input name="weight_kg" type="number" step="0.1">')}<div class="modalActions span2"><button class="primary">Complete triage</button></div></form>`);
    m.querySelector('#jTriage').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target),o={};for(const [k,v] of fd)if(v!=='')o[k]=Number(v);try{await jApi(`/api/journey/visits/${id}/triage`,{method:'POST',body:JSON.stringify(o)});m.remove();jToast('Triage completed');pages.journey()}catch(x){jToast(x.message)}};
  }

  async function renderDoctor(){
    const [queue,doctors]=await Promise.all([jApi('/api/journey/doctor/queue'),jApi('/api/journey/doctors')]);
    const s=journeyWorkspace.my_shift;
    return `<div class="journeySplit"><div class="panel"><span class="eyebrow">My shift</span><h3>${s?`Room ${jEsc(s.room_number)} · ${jEsc(s.availability)}`:'Not on shift'}</h3>${s?`<p class="muted">Started ${dateTime(s.started_at)} · ${s.minutes} min tracked · ${s.queue_count} queued</p><div class="actions"><button class="${s.availability==='AVAILABLE'?'ghost':'primary'}" id="jAvail">${s.availability==='AVAILABLE'?'Mark away':'Mark available'}</button><button class="ghost" id="jStopShift">End shift</button></div>`:`<p class="muted">Start a shift and enter your current consultation room so patients can be routed correctly.</p><div class="journeySearch"><input id="jRoom" placeholder="Room e.g. OPD-03"><button class="primary" id="jStartShift">Start shift</button></div>`}</div><div class="panel"><span class="eyebrow">Available doctors</span><h3>Live room status</h3>${doctors.length?doctors.map(d=>`<div class="journeyDoctor"><div><b>${jEsc(d.doctor_name)}</b><span>Room ${jEsc(d.room_number)} · ${d.queue_count} queued</span></div>${jBadge(d.availability)}</div>`).join(''):'<div class="empty">No doctor currently marked available.</div>'}</div></div><div class="panel journeyDoctorSearch"><span class="eyebrow">Find a file</span><h3>Search by patient number or file number</h3><div class="journeySearch"><input id="jDoctorSearch" placeholder="e.g. P000123 or F20260913-000123"><button class="ghost" id="jDoctorSearchBtn">Search</button></div><div id="jDoctorSearchResults"></div></div><div class="panel"><span class="eyebrow">Doctor queue</span><h3>Patients ready for review</h3>${queue.length?`<div class="tableWrap"><table><thead><tr><th>Queue</th><th>File</th><th>Patient</th><th>Stage</th><th>Room</th><th></th></tr></thead><tbody>${queue.map(v=>`<tr><td>${v.queue_position||'—'}</td><td>${jEsc(v.file_no)}</td><td>${jEsc(v.patient_no)}<br>${jEsc(v.patient_name)}</td><td>${jBadge(v.stage)}</td><td>${jEsc(v.room||'—')}</td><td><button class="primary" data-jdoctor-open="${v.id}">Open file</button></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">No patients in your doctor queue.</div>'}</div>`;
  }
  async function doctorOpen(id){
    try{await jApi(`/api/journey/visits/${id}/claim`,{method:'POST',body:'{}'})}catch(x){if(!String(x.message).includes('assigned'))jToast(x.message)}
    await showVisit(id,true);
  }

  async function renderLab(){
    const rows=await jApi('/api/journey/lab-queue');
    return `<div class="panel"><span class="eyebrow">Laboratory</span><h3>Ordered tests</h3><p class="muted">Results return directly to the same visit file. When the required results are ready, the doctor queue and patient SMS are updated.</p>${rows.length?`<div class="tableWrap"><table><thead><tr><th>File</th><th>Patient</th><th>Test</th><th>Status</th><th>Result</th><th></th></tr></thead><tbody>${rows.map(x=>`<tr><td>${jEsc(x.file_no)}</td><td>${jEsc(x.patient_no)}<br>${jEsc(x.patient_name)}</td><td><b>${jEsc(x.test_name)}</b></td><td>${jBadge(x.status)}</td><td>${jEsc(x.result||'Pending')}</td><td><button class="primary" data-jlab-result="${x.id}">Enter result</button></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">No pending laboratory orders.</div>'}</div>`;
  }
  function labResultForm(id){
    const canVerify=jCan('laboratory','VERIFY');
    const m=jModal('Laboratory result',`<form id="jLabResult">${input('Result','<textarea name="result" rows="6" required></textarea>')}${canVerify?'<label class="check"><input name="verified" type="checkbox"> Verify result now</label>':''}<div class="modalActions"><button class="primary">Save result</button></div></form>`);
    m.querySelector('#jLabResult').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target);try{await jApi(`/api/lab-orders/${id}/result`,{method:'PATCH',body:JSON.stringify({result:fd.get('result'),verified:fd.has('verified')})});m.remove();jToast('Lab result saved');pages.journey()}catch(x){jToast(x.message)}};
  }

  async function renderPharmacy(){
    const rows=await jApi('/api/journey/pharmacy-queue');
    return `<div class="panel"><span class="eyebrow">Hospital pharmacy</span><h3>Prescription queue</h3><p class="muted">Patients may choose the hospital pharmacy or an external pharmacy. Only hospital-pharmacy prescriptions enter this queue.</p>${rows.length?rows.map(v=>`<div class="journeyVisitCard"><div class="journeyPanelHead"><div><b>${jEsc(v.file_no)} · ${jEsc(v.patient_name)}</b><span>${jEsc(v.patient_no)} · ${jBadge(v.stage)}</span></div><button class="linkBtn" data-jdetail="${v.id}">Open file</button></div><div class="journeyRx">${v.prescriptions.map(rx=>`<div><b>${jEsc(rx.medicine)}</b><span>${jEsc(rx.dose)} · ${jEsc(rx.frequency)} · Qty ${rx.quantity}</span><em>${jEsc(rx.status)}</em>${rx.status!=='DISPENSED'&&rx.status!=='EXTERNAL'?`<button class="primary" data-jdispense="${rx.id}">Dispense</button>`:''}</div>`).join('')}</div><div class="journeyInvoice">${v.pharmacy_invoice?`Pharmacy bill: <b>${jMoney(v.pharmacy_invoice.amount)}</b> · ${jBadge(v.pharmacy_invoice.status)}`:'<span>No pharmacy invoice yet.</span>'}${!v.pharmacy_invoice?`<button class="ghost" data-jprepare="${v.id}">Prepare medicine bill</button>`:''}</div></div>`).join(''):'<div class="empty">No patients waiting at the hospital pharmacy.</div>'}</div>`;
  }

  async function renderInpatient(){
    const q=await jApi('/api/journey/admission-queue');
    return `<div class="journeySplit"><div class="panel"><span class="eyebrow">Admissions</span><h3>Waiting for bed</h3>${q.pending.length?q.pending.map(v=>`<div class="journeyPatient"><div><b>${jEsc(v.file_no)} · ${jEsc(v.patient_name)}</b><span>${jEsc(v.patient_no)}</span></div><button class="primary" data-jadmit="${v.id}">Assign ward & bed</button></div>`).join(''):'<div class="empty">No pending admissions.</div>'}</div><div class="panel"><span class="eyebrow">Discharge</span><h3>Doctor-approved discharge</h3>${q.discharge_pending.length?q.discharge_pending.map(v=>`<div class="journeyPatient"><div><b>${jEsc(v.file_no)} · ${jEsc(v.patient_name)}</b><span>Ready to complete discharge</span></div><button class="primary" data-jdischarge="${v.id}">Complete discharge</button></div>`).join(''):'<div class="empty">No discharge actions pending.</div>'}</div></div><div class="panel"><span class="eyebrow">Current inpatients</span><h3>Open admitted files</h3>${q.admitted.length?q.admitted.map(v=>`<div class="journeyPatient"><div><b>${jEsc(v.file_no)} · ${jEsc(v.patient_name)}</b><span>${jEsc(v.patient_no)}</span></div><div class="actions"><button class="ghost" data-jprogress="${v.id}">Add progress note</button><button class="linkBtn" data-jdetail="${v.id}">Open file</button></div></div>`).join(''):'<div class="empty">No current inpatients.</div>'}</div>`;
  }
  async function admitForm(id){
    const [wards,beds]=await Promise.all([jApi('/api/wards'),jApi('/api/beds')]);
    const avail=beds.filter(x=>x.status==='AVAILABLE');
    const m=jModal('Assign ward & bed',`<form id="jAdmit" class="formGrid">${input('Ward',`<select name="ward_id" required><option value="">Select ward</option>${wards.map(w=>`<option value="${w.id}">${jEsc(w.name)}</option>`).join('')}</select>`)}${input('Bed',`<select name="bed_id" required><option value="">Select available bed</option>${avail.map(b=>`<option value="${b.id}" data-ward="${b.ward_id}">${jEsc(b.code)}</option>`).join('')}</select>`)}<div class="modalActions span2"><button class="primary">Admit patient</button></div></form>`);
    m.querySelector('#jAdmit').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target);try{await jApi(`/api/journey/visits/${id}/admit`,{method:'POST',body:JSON.stringify({ward_id:Number(fd.get('ward_id')),bed_id:Number(fd.get('bed_id'))})});m.remove();jToast('Patient admitted');pages.journey()}catch(x){jToast(x.message)}};
  }
  function progressForm(id){
    const m=jModal('Inpatient progress note',`<form id="jProgress">${input('Type','<select name="note_type"><option>PROGRESS</option><option>NURSING</option><option>DOCTOR</option><option>MEDICATION</option><option>OBSERVATION</option></select>')}${input('Note','<textarea name="note" rows="6" required></textarea>')}<div class="modalActions"><button class="primary">Save note</button></div></form>`);
    m.querySelector('#jProgress').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target);try{await jApi(`/api/journey/visits/${id}/progress`,{method:'POST',body:JSON.stringify({note_type:fd.get('note_type'),note:fd.get('note')})});m.remove();jToast('Progress note saved');pages.journey()}catch(x){jToast(x.message)}};
  }

  async function renderAdmin(){
    const [s,a,sms]=await Promise.all([jApi('/api/journey/settings'),jApi('/api/journey/admin/doctor-attendance'),jApi('/api/journey/sms-outbox')]);
    return `<div class="journeySplit"><div class="panel"><span class="eyebrow">Workflow settings</span><h3>Hospital visit policy</h3><form id="jSettings" class="formGrid">${input('Consultation fee',`<input name="consultation_fee" type="number" min="0" step="1" value="${s.consultation_fee}">`)}${input('Currency',`<input name="currency" value="${jEsc(s.currency)}">`)}${input('Fee label',`<input name="consultation_fee_label" value="${jEsc(s.consultation_fee_label)}">`)}<label class="check"><input type="checkbox" name="require_consultation_payment" ${s.require_consultation_payment?'checked':''}> Require consultation payment before doctor</label><label class="check"><input type="checkbox" name="require_triage" ${s.require_triage?'checked':''}> Require triage before doctor</label><label class="check"><input type="checkbox" name="require_lab_verification" ${s.require_lab_verification?'checked':''}> Lab results require verification before doctor review</label><label class="check"><input type="checkbox" name="require_pharmacy_payment" ${s.require_pharmacy_payment?'checked':''}> Require pharmacy payment before completion</label><label class="check"><input type="checkbox" name="sms_enabled" ${s.sms_enabled?'checked':''}> Enable patient SMS outbox</label><label class="check"><input type="checkbox" name="sms_lab_results" ${s.sms_lab_results?'checked':''}> SMS when lab results are ready</label><label class="check"><input type="checkbox" name="auto_assign_doctor" ${s.auto_assign_doctor?'checked':''}> Auto-assign available doctor/room</label><div class="modalActions span2"><button class="primary">Save workflow settings</button></div></form></div><div class="panel"><span class="eyebrow">Doctor attendance</span><h3>Availability time</h3>${a.totals.length?a.totals.map(x=>`<div class="journeyDoctor"><div><b>${jEsc(x.doctor_name)}</b><span>${x.sessions} sessions</span></div><strong>${x.hours} h</strong></div>`).join(''):'<div class="empty">No doctor shift sessions yet.</div>'}</div></div><div class="panel"><div class="journeyPanelHead"><div><span class="eyebrow">SMS outbox</span><h3>Patient notifications</h3><p class="muted">Messages are sent automatically when HMS_SMS_WEBHOOK_URL is configured; otherwise they remain queued for integration.</p></div><button class="ghost" id="jRetrySms">Retry queued/failed</button></div>${sms.length?`<div class="tableWrap"><table><thead><tr><th>Time</th><th>Phone</th><th>Event</th><th>Message</th><th>Status</th></tr></thead><tbody>${sms.slice(0,40).map(x=>`<tr><td>${dateTime(x.created_at)}</td><td>${jEsc(x.phone)}</td><td>${jEsc(x.event_type)}</td><td>${jEsc(x.message)}</td><td>${jBadge(x.status)}</td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">No SMS messages yet.</div>'}</div>`;
  }

  async function showVisit(id,doctorMode=false){
    const v=await jApi(`/api/journey/visits/${id}`);
    const e=v.encounter||{};
    const doctorActions=jCan('consultation','EDIT')?`<div class="journeyClinicalActions"><button class="ghost" data-jconsult="${v.id}">Update consultation</button><button class="ghost" data-jlabs="${v.id}">Order lab tests</button><button class="ghost" data-jprescribe="${v.id}">Prescribe</button>${v.stage==='ADMITTED'?`<button class="primary" data-jdischarge-decision="${v.id}">Discharge decision</button>`:''}${!['ADMITTED','DISCHARGE_PENDING'].includes(v.stage)?`<button class="primary" data-joutcome="${v.id}">Set outcome / close</button>`:''}</div>`:'';
    const body=`<div class="journeyFileHead"><div><span class="eyebrow">${jEsc(v.patient_no)} · Visit file</span><h2>${jEsc(v.file_no)} · ${jEsc(v.patient_name)}</h2><p>${jBadge(v.stage)} ${v.doctor_name?`· ${jEsc(v.doctor_name)} ${v.room?'· Room '+jEsc(v.room):''}`:''}</p></div><div><small>Opened</small><b>${dateTime(v.opened_at)}</b></div></div>${doctorActions}<div class="journeyFileGrid"><section><h3>Clinical record</h3><dl><dt>Presenting complaint</dt><dd>${jEsc(e.chief_complaint||v.reason||'—')}</dd><dt>Clinical notes</dt><dd>${jEsc(e.clinical_notes||'—')}</dd><dt>Diagnosis</dt><dd>${jEsc(e.diagnosis||'—')}</dd><dt>Allergies</dt><dd>${jEsc(v.patient?.allergies||'—')}</dd></dl></section><section><h3>Payments</h3><p>Consultation: ${v.consultation_invoice?`${jMoney(v.consultation_invoice.amount)} · ${jBadge(v.consultation_invoice.status)}`:'No charge'}</p><p>Pharmacy: ${v.pharmacy_invoice?`${jMoney(v.pharmacy_invoice.amount)} · ${jBadge(v.pharmacy_invoice.status)}`:'—'}</p><p>Medicine source: <b>${jEsc(v.pharmacy_choice||'Not decided')}</b></p></section></div><div class="journeyFileGrid"><section><h3>Laboratory</h3>${v.labs.length?v.labs.map(x=>`<div class="journeyLine"><div><b>${jEsc(x.test_name)}</b><span>${jEsc(x.result||'Pending')}</span></div>${jBadge(x.status)}</div>`).join(''):'<div class="empty">No lab orders</div>'}</section><section><h3>Prescriptions</h3>${v.prescriptions.length?v.prescriptions.map(x=>`<div class="journeyLine"><div><b>${jEsc(x.medicine)}</b><span>${jEsc(x.dose)} · ${jEsc(x.frequency)} · ${jEsc(x.duration)} · Qty ${x.quantity}</span></div>${jBadge(x.status)}</div>`).join(''):'<div class="empty">No prescriptions</div>'}</section></div>${v.admission?`<div class="panel journeyInner"><h3>Admission · ${jEsc(v.admission.ward_name||'Ward')} / ${jEsc(v.admission.bed_code||'Bed')}</h3>${(v.progress||[]).map(n=>`<div class="timelineItem"><b>${jEsc(n.note_type)}</b><span>${dateTime(n.created_at)}</span><p>${jEsc(n.note)}</p></div>`).join('')||'<div class="empty">No inpatient notes yet.</div>'}</div>`:''}<div class="panel journeyInner"><h3>Visit timeline</h3><div class="journeyTimeline">${v.events.slice().reverse().map(x=>`<div class="timelineItem"><b>${jEsc(x.event_type.replaceAll('_',' '))}</b><span>${dateTime(x.created_at)}</span>${x.note?`<p>${jEsc(x.note)}</p>`:''}</div>`).join('')}</div></div>`;
    const m=jModal(`Visit ${v.file_no}`,body); bindModalActions(m,v);
  }

  function bindModalActions(m,v){
    m.querySelector('[data-jconsult]')?.addEventListener('click',()=>consultForm(v,m));
    m.querySelector('[data-jlabs]')?.addEventListener('click',()=>labOrderForm(v,m));
    m.querySelector('[data-jprescribe]')?.addEventListener('click',()=>prescriptionForm(v,m));
    m.querySelector('[data-joutcome]')?.addEventListener('click',()=>outcomeForm(v,m));
    m.querySelector('[data-jdischarge-decision]')?.addEventListener('click',()=>dischargeDecision(v,m));
  }
  function consultForm(v,parent){
    const e=v.encounter||{};const m=jModal('Consultation notes',`<form id="jConsult">${input('Chief complaint',`<textarea name="chief_complaint" rows="2">${jEsc(e.chief_complaint||v.reason||'')}</textarea>`)}${input('Clinical notes',`<textarea name="clinical_notes" rows="5">${jEsc(e.clinical_notes||'')}</textarea>`)}${input('Diagnosis / assessment',`<textarea name="diagnosis" rows="3">${jEsc(e.diagnosis||'')}</textarea>`)}<div class="modalActions"><button class="primary">Save clinical record</button></div></form>`);m.querySelector('#jConsult').onsubmit=async e=>{e.preventDefault();const o=Object.fromEntries(new FormData(e.target));try{await jApi(`/api/journey/visits/${v.id}/consultation`,{method:'PATCH',body:JSON.stringify(o)});m.remove();parent.remove();jToast('Consultation updated');pages.journey()}catch(x){jToast(x.message)}};
  }
  function labOrderForm(v,parent){
    const m=jModal('Order laboratory tests',`<form id="jLabOrder">${input('Tests','<textarea name="tests" rows="5" placeholder="One test per line, e.g. Full Blood Count&#10;Malaria RDT" required></textarea>')}<div class="modalActions"><button class="primary">Send to laboratory</button></div></form>`);m.querySelector('#jLabOrder').onsubmit=async e=>{e.preventDefault();const tests=new FormData(e.target).get('tests').split('\n').map(x=>x.trim()).filter(Boolean);try{await jApi(`/api/journey/visits/${v.id}/lab-orders`,{method:'POST',body:JSON.stringify({tests})});m.remove();parent.remove();jToast('Lab orders sent');pages.journey()}catch(x){jToast(x.message)}};
  }
  async function prescriptionForm(v,parent){
    const inv=await jApi('/api/inventory');const m=jModal('Prescribe medicine',`<form id="jRx" class="formGrid">${input('Medicine',`<input name="medicine" list="jMedList" required><datalist id="jMedList">${inv.map(x=>`<option value="${jEsc(x.name)}"></option>`).join('')}</datalist>`)}${input('Hospital inventory item',`<select name="inventory_item_id"><option value="">Not linked / external</option>${inv.filter(x=>String(x.category).toLowerCase().includes('med')).map(x=>`<option value="${x.id}">${jEsc(x.name)} · ${jMoney(x.unit_price)} · stock ${x.quantity}</option>`).join('')}</select>`)}${input('Dose','<input name="dose" placeholder="e.g. 500 mg" required>')}${input('Frequency','<input name="frequency" placeholder="e.g. 3 times daily" required>')}${input('Duration','<input name="duration" placeholder="e.g. 5 days" required>')}${input('Quantity','<input name="quantity" type="number" min="1" value="1" required>')}${input('Medicine source','<select name="source"><option>HOSPITAL</option><option>EXTERNAL</option></select>')}${input('Instructions','<textarea name="instructions" rows="2"></textarea>')}<div class="modalActions span2"><button class="primary">Save prescription</button></div></form>`);m.querySelector('#jRx').onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target);const med={medicine:fd.get('medicine'),inventory_item_id:fd.get('inventory_item_id')?Number(fd.get('inventory_item_id')):null,dose:fd.get('dose'),frequency:fd.get('frequency'),duration:fd.get('duration'),quantity:Number(fd.get('quantity')),instructions:fd.get('instructions')||null};try{await jApi(`/api/journey/visits/${v.id}/prescriptions`,{method:'POST',body:JSON.stringify({medicines:[med],source:fd.get('source')})});m.remove();parent.remove();jToast('Prescription saved');pages.journey()}catch(x){jToast(x.message)}};
  }
  function outcomeForm(v,parent){
    const m=jModal('Clinical outcome',`<form id="jOutcome">${input('Outcome','<select name="outcome"><option value="OUTPATIENT">Outpatient — finish consultation</option><option value="ADMIT">Admit to ward</option><option value="REFER">Refer elsewhere</option></select>')}${input('Medicine source','<select name="pharmacy_choice"><option value="HOSPITAL">Hospital pharmacy</option><option value="EXTERNAL">External pharmacy</option><option value="NONE">No medicine</option></select>')}${input('Note','<textarea name="note" rows="3"></textarea>')}<div class="notice">For hospital-pharmacy treatment, the doctor records the close decision now. The visit automatically closes after required medicine payment and dispensing. External/no-medicine outpatient visits close immediately.</div><div class="modalActions"><button class="primary">Confirm outcome</button></div></form>`);m.querySelector('#jOutcome').onsubmit=async e=>{e.preventDefault();const o=Object.fromEntries(new FormData(e.target));try{await jApi(`/api/journey/visits/${v.id}/outcome`,{method:'POST',body:JSON.stringify(o)});m.remove();parent.remove();jToast('Clinical outcome recorded');pages.journey()}catch(x){jToast(x.message)}};
  }
  function dischargeDecision(v,parent){
    const m=jModal('Doctor discharge decision',`<form id="jDD">${input('Discharge summary & instructions','<textarea name="summary" rows="6" required></textarea>')}<div class="modalActions"><button class="primary">Approve discharge</button></div></form>`);m.querySelector('#jDD').onsubmit=async e=>{e.preventDefault();try{await jApi(`/api/journey/visits/${v.id}/discharge-decision`,{method:'POST',body:JSON.stringify({summary:new FormData(e.target).get('summary')})});m.remove();parent.remove();jToast('Discharge approved');pages.journey()}catch(x){jToast(x.message)}};
  }

  function bindTabActions(){
    document.getElementById('jSearchPatient')?.addEventListener('click',searchPatients);
    document.getElementById('jPatientSearch')?.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();searchPatients()}});
    document.getElementById('jNewPatient')?.addEventListener('click',newPatientVisit);
    document.querySelectorAll('[data-jpay]').forEach(b=>b.onclick=()=>payInvoice(Number(b.dataset.jpay),Number(b.dataset.balance)));
    document.querySelectorAll('[data-jreceipt]').forEach(b=>b.onclick=()=>openReceipt(Number(b.dataset.jreceipt)));
    document.querySelectorAll('[data-jtriage]').forEach(b=>b.onclick=()=>triageForm(Number(b.dataset.jtriage)));
    document.getElementById('jStartShift')?.addEventListener('click',async()=>{const room=document.getElementById('jRoom').value.trim();if(!room)return jToast('Enter your room number');try{await jApi('/api/journey/doctor/shift/start',{method:'POST',body:JSON.stringify({room_number:room})});jToast('Doctor shift started');pages.journey()}catch(x){jToast(x.message)}});
    document.getElementById('jAvail')?.addEventListener('click',async()=>{const next=journeyWorkspace.my_shift?.availability==='AVAILABLE'?'AWAY':'AVAILABLE';await jApi('/api/journey/doctor/availability',{method:'PATCH',body:JSON.stringify({availability:next})});pages.journey()});
    document.getElementById('jStopShift')?.addEventListener('click',async()=>{if(confirm('End your active shift?')){await jApi('/api/journey/doctor/shift/stop',{method:'POST',body:'{}'});pages.journey()}});
    document.querySelectorAll('[data-jdoctor-open]').forEach(b=>b.onclick=()=>doctorOpen(Number(b.dataset.jdoctorOpen)));
    const doctorSearch=async()=>{const q=document.getElementById('jDoctorSearch')?.value.trim();if(!q)return;const rows=await jApi('/api/journey/visits?q='+encodeURIComponent(q)+'&status=OPEN');const box=document.getElementById('jDoctorSearchResults');box.innerHTML=rows.length?rows.map(v=>`<div class=\"journeyPatient\"><div><b>${jEsc(v.file_no)} · ${jEsc(v.patient_name)}</b><span>${jEsc(v.patient_no)} · ${jEsc(stageLabel(v.stage))}</span></div><button class=\"primary\" data-jdoctor-search-open=\"${v.id}\">Open file</button></div>`).join(''):'<div class=\"empty\">No open visit file found.</div>';box.querySelectorAll('[data-jdoctor-search-open]').forEach(b=>b.onclick=()=>doctorOpen(Number(b.dataset.jdoctorSearchOpen)));};document.getElementById('jDoctorSearchBtn')?.addEventListener('click',doctorSearch);document.getElementById('jDoctorSearch')?.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();doctorSearch()}});
    document.querySelectorAll('[data-jlab-result]').forEach(b=>b.onclick=()=>labResultForm(Number(b.dataset.jlabResult)));
    document.querySelectorAll('[data-jprepare]').forEach(b=>b.onclick=async()=>{try{await jApi(`/api/journey/visits/${b.dataset.jprepare}/pharmacy/prepare`,{method:'POST',body:'{}'});jToast('Pharmacy bill created');pages.journey()}catch(x){jToast(x.message)}});
    document.querySelectorAll('[data-jdispense]').forEach(b=>b.onclick=async()=>{try{await jApi(`/api/prescriptions/${b.dataset.jdispense}/dispense`,{method:'PATCH',body:'{}'});jToast('Medicine dispensed');pages.journey()}catch(x){jToast(x.message)}});
    document.querySelectorAll('[data-jadmit]').forEach(b=>b.onclick=()=>admitForm(Number(b.dataset.jadmit)));
    document.querySelectorAll('[data-jprogress]').forEach(b=>b.onclick=()=>progressForm(Number(b.dataset.jprogress)));
    document.querySelectorAll('[data-jdischarge]').forEach(b=>b.onclick=async()=>{if(confirm('Complete hospital discharge and close this visit file?')){try{await jApi(`/api/journey/visits/${b.dataset.jdischarge}/discharge`,{method:'POST',body:'{}'});jToast('Patient discharged; visit file closed');pages.journey()}catch(x){jToast(x.message)}}});
    document.getElementById('jSettings')?.addEventListener('submit',async e=>{e.preventDefault();const fd=new FormData(e.target),o={consultation_fee:Number(fd.get('consultation_fee')),consultation_fee_label:fd.get('consultation_fee_label'),currency:fd.get('currency'),require_consultation_payment:fd.has('require_consultation_payment'),require_triage:fd.has('require_triage'),require_lab_verification:fd.has('require_lab_verification'),require_pharmacy_payment:fd.has('require_pharmacy_payment'),sms_enabled:fd.has('sms_enabled'),sms_lab_results:fd.has('sms_lab_results'),auto_assign_doctor:fd.has('auto_assign_doctor')};try{await jApi('/api/journey/settings',{method:'PATCH',body:JSON.stringify(o)});jToast('Workflow settings saved');pages.journey()}catch(x){jToast(x.message)}});
    document.getElementById('jRetrySms')?.addEventListener('click',async()=>{const r=await jApi('/api/journey/sms-outbox/retry',{method:'POST',body:JSON.stringify({ids:null})});jToast(`${r.processed} messages processed`);pages.journey()});
  }
})();
