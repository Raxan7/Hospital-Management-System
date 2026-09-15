// ==========================================================================
// NEOVAM HMS · Premium Receipt (receipt.js)
// Renders a professional, printable hospital payment receipt inside the SPA.
// Reuses globals from app.js: esc, money, modal, field, btn, api, toast, me,
// can, render, page, shell, header, root, receiptId.
// No business logic is changed — all data comes from existing endpoints.
// ==========================================================================

(function(){
  'use strict';
  const CURRENCY='TZS';
  const r2=n=>Math.round((Number(n)||0)*100)/100;
  const fmt=n=>Number(n||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
  const money2=n=>CURRENCY+' '+fmt(n);
  const pad5=n=>String(n).padStart(5,'0');
  const invNo=id=>'INV-'+pad5(id);
  const rctNo=id=>'RCT-'+pad5(id);

  const PAY_METHODS={MOBILE_MONEY:['mm','Mobile Money'],CASH:['cash','Cash'],CARD:['card','Card'],
    BANK:['bank','Bank'],INSURANCE:['insurance','Insurance']};
  const methodName=m=>PAY_METHODS[(m||'').toUpperCase()]?.[1]||(m||'Other');
  const methodCls=m=>(PAY_METHODS[(m||'').toUpperCase()]?.[0]||'other');

  function rBadge(status){
    const s=(status||'UNPAID').toUpperCase().replace('_',' ');
    const map={'PAID':['paid','✓ PAID'],'PARTIALLY PAID':['partial','◐ PARTIALLY PAID'],'PARTIAL':['partial','◐ PARTIALLY PAID'],
      'UNPAID':['unpaid','● UNPAID'],'REFUNDED':['refunded','⟲ REFUNDED'],'CANCELLED':['cancelled','✕ CANCELLED']};
    const [cls,label]=map[s]||['unpaid',esc(s)];
    return `<span class="rbadge ${cls}"><span class="mark"></span>${label}</span>`;
  }
  const dash=v=>v===undefined||v===null||v===''?'—':v;

  function hospitalBlock(){
    const h=me?.hospital||{};
    const lines=[dash(h.name)];
    if(h.address)lines.push(esc(h.address));
    if(h.phone)lines.push('Tel: '+esc(h.phone));
    return `<div class="receiptHospital">
      <img src="/static/assets/neovam-hms-mark.png" alt="NEOVAM HMS" class="neovamMark">
      <div><h2>${dash(h.name)}</h2><div class="receiptHospitalMeta">${lines.slice(1).join(' · ')||'Official payment receipt'}</div></div>
    </div>`;
  }

  function buildReceipt(inv,patient,payments){
    const id=inv.id;
    const total=r2(inv.amount);
    const paid=r2(inv.paid_amount);
    const balance=Math.max(0,r2(total-paid));
    const status=(inv.status||'UNPAID').toUpperCase().replace('_',' ');
    const createdAt=inv.created_at?new Date(inv.created_at):new Date();
    const dateStr=createdAt.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
    const timeStr=createdAt.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});
    const pat=patient||{};
    const patName=[pat.first_name,pat.last_name].filter(Boolean).join(' ')||'—';
    const desc=dash(inv.description);

    const pct=total>0?Math.min(100,Math.round(paid/total*100)):0;
    const isPaid=status==='PAID';
    const isPartial=status==='PARTIALLY PAID'||status==='PARTIAL';
    const fillCls=isPaid?'':(isPartial?' partial':'');

    const itemsRow=`<tr><td><b>${esc(desc)}</b></td><td>1</td><td>${fmt(total)}</td><td class="amount">${fmt(total)}</td></tr>`;

    const totals=`<div class="receiptTotals">
      <div class="rtotalRow"><span class="k">Subtotal</span><span>${fmt(total)}</span></div>
      <div class="rtotalRow"><span class="k">Discount</span><span>0.00</span></div>
      <div class="rtotalRow"><span class="k">Tax</span><span>0.00</span></div>
      <div class="rtotalRow grand"><span class="k">TOTAL</span><span>${fmt(total)}</span></div>
    </div>`;

    const payCells=`<div class="receiptPayGrid">
      <div class="receiptPayCell"><h3>TOTAL AMOUNT</h3><span class="amt">${money2(total)}</span></div>
      <div class="receiptPayCell paid"><h3>PAID</h3><span class="amt positive">${money2(paid)}</span></div>
      <div class="receiptPayCell balance"><h3>OUTSTANDING BALANCE</h3><span class="amt ${isPaid?'positive':'due'}">${money2(balance)}</span></div>
    </div>`;

    const progress=`<div class="receiptProgress">
      <div class="track"><div class="fill${fillCls}" style="width:${pct}%"></div></div>
      <div class="legend"><span><b>${pct}%</b> paid</span><span>Paid <b>${fmt(paid)}</b></span><span>Balance <b>${fmt(balance)}</b></span></div>
    </div>`;

    const history=payments.length
      ?`<table class="receiptTable"><thead><tr><th>Payment ID</th><th>Date &amp; time</th><th>Method</th><th>Reference</th><th>Amount</th></tr></thead><tbody>
        ${payments.map(p=>`<tr><td>PAY-${pad5(p.id)}</td><td>${new Date(p.created_at).toLocaleString('en-GB',{day:'2-digit',month:'short',year:'numeric',hour:'numeric',minute:'2-digit'})}</td>
        <td><span class="payMethodBadge ${methodCls(p.method)}">${esc(methodName(p.method))}</span></td><td>${esc(dash(p.reference))}</td><td class="amount">${fmt(p.amount)}</td></tr>`).join('')}
        </tbody></table>`
      :`<div class="receiptEmpty"><b>No payments recorded</b><span>No payment transactions have been recorded for this invoice.</span></div>`;

    const verifyArea=''; /* reserved — activation requires a backend verification URL */
    const thanksText='Thank you for using our healthcare services.';
    const byline='Generated by NEOVAM HMS · '+dateStr+' · '+timeStr;

    return `<div class="receipt" id="receiptDoc">
      <div class="receiptHead">
        ${hospitalBlock()}
        <div class="receiptMeta">
          <div class="receiptMetaTitle">Receipt<small>OFFICIAL FINANCIAL DOCUMENT</small></div>
          <div class="receiptMetaGrid">
            <span class="k">Receipt No.</span><span>${rctNo(id)}</span>
            <span class="k">Date</span><span>${dateStr}</span>
            <span class="k">Time</span><span>${timeStr}</span>
            <span class="k">Invoice</span><span>${invNo(id)}</span>
          </div>
        </div>
      </div>
      <div class="receiptStatusBlock">
        <div><span class="label">Invoice status</span><br><span class="value">${invNo(id)}</span></div>
        ${rBadge(status)}
      </div>
      <section>
        <h3 class="receiptH">Patient information</h3>
        <div class="receiptPatient">
          <div class="cell"><span class="rlabel">Patient name</span><span class="rvalue trunc">${esc(patName)}</span></div>
          <div class="cell"><span class="rlabel">Patient ID</span><span class="rvalue">${esc(dash(pat.patient_no))}</span></div>
          <div class="cell"><span class="rlabel">Invoice number</span><span class="rvalue">${invNo(id)}</span></div>
          <div class="cell"><span class="rlabel">Service / encounter</span><span class="rvalue">${esc(desc)}</span></div>
          <div class="cell"><span class="rlabel">Date</span><span class="rvalue">${dateStr}</span></div>
          <div class="cell"><span class="rlabel">Department</span><span class="rvalue">—</span></div>
          <div class="cell"><span class="rlabel">Doctor</span><span class="rvalue">—</span></div>
        </div>
      </section>
      <section>
        <h3 class="receiptH">Billing summary</h3>
        <table class="receiptTable">
          <thead><tr><th>Description</th><th>Qty</th><th>Unit price</th><th>Amount</th></tr></thead>
          <tbody>${itemsRow}</tbody>
        </table>
        ${totals}
        <div class="receiptPayPanel">${payCells}${progress}</div>
      </section>
      <section>
        <h3 class="receiptH">Payment history</h3>
        ${history}
      </section>
      <div class="receiptFoot">
        <div class="thanks">${thanksText}</div>
        <div class="byline">${esc(byline)}</div>
      </div>
    </div>`;
  }

  function buildHeading(inv){
    const patInfo=inv?`${invNo(inv.id)} · ${esc(inv.description||'')}`:'';
    return `<div class="receiptHeading">
      <div><h1>Payment receipt</h1><p>${patInfo}</p></div>
      <div class="receiptHeadingActions">
        <button class="ghost" id="recThermal" title="Toggle thermal receipt layout">Thermal</button>
        <button class="ghost" id="recBack">← Back to billing</button>
      </div>
    </div>`;
  }

  function buildBar(inv){
    const isPaid=(inv.status||'').toUpperCase()==='PAID';
    const collect=isPaid?'':`<button class="primary" id="recCollect">Collect payment</button>`;
    return `<div class="receiptBar">
      ${collect}
      <button class="ghost" id="recPrint">${isPaid?'Print receipt':'Print'}</button>
      <button class="ghost" id="recPdf">Download PDF</button>
      <button class="ghost" id="recShare">Share</button>
      <button class="ghost closeBtn" id="recClose" title="Close receipt">Close</button>
    </div>`;
  }

  function bindBar(inv,payments){
    const doc=document.getElementById('receiptDoc');
    const thermal=document.getElementById('recThermal');
    const print=document.getElementById('recPrint');
    const pdf=document.getElementById('recPdf');
    const share=document.getElementById('recShare');
    const close=document.getElementById('recClose');
    const back=document.getElementById('recBack');
    const collect=document.getElementById('recCollect');

    const goBilling=()=>{location.hash='';page='billing';render()};
    back?.addEventListener('click',goBilling);
    close?.addEventListener('click',goBilling);
    if(isThermalEnabled())doc?.classList.add('thermal');
    thermal?.addEventListener('click',()=>{
      const on=doc?.classList.toggle('thermal');
      thermal.textContent=on?'Standard view':'Thermal view';
      if(on)toast('Thermal receipt layout · 80mm');
    });
    print?.addEventListener('click',()=>window.print());
    pdf?.addEventListener('click',()=>{toast('Choose "Save as PDF" in the print dialog');window.print()});
    share?.addEventListener('click',()=>{
      const payload={title:`Receipt ${rctNo(inv.id)}`,text:`Official payment receipt ${rctNo(inv.id)} · ${money2(inv.amount)}`,url:location.href};
      if(navigator.share){navigator.share(payload).catch(()=>{})}
      else if(navigator.clipboard){navigator.clipboard.writeText(location.href).then(()=>toast('Receipt link copied')).catch(()=>toast('Copy the browser address to share'))}
      else toast('Copy the browser address to share');
    });
    if(collect)collect.addEventListener('click',()=>collectPayment(inv));
  }
  function isThermalEnabled(){return (localStorage.getItem('onehms_receipt_thermal')||'')==='1'}

  // --- Collect payment modal (§73) ---
  function collectPayment(inv){
    const total=r2(inv.amount),paid=r2(inv.paid_amount),balance=Math.max(0,r2(total-paid));
    const m=modal('Collect payment',`<form id="recPayForm" class="receiptPayForm">
      <div class="receiptPayInfo">
        <div><span>Invoice total</span><b>${money2(total)}</b></div>
        <div><span>Already paid</span><b>${money2(paid)}</b></div>
        <div><span>Remaining balance</span><b class="rem">${money2(balance)}</b></div>
      </div>
      ${field('Payment amount','<input name="amount" type="number" min="0.01" step="0.01" max="'+balance+'" value="'+balance+'" required>')}
      ${field('Payment method','<select name="method"><option>MOBILE_MONEY</option><option>CASH</option><option>CARD</option><option>BANK</option><option>INSURANCE</option></select>')}
      ${field('Reference','<input name="reference" placeholder="Transaction / receipt reference">')}
      ${field('Notes','<input name="notes" placeholder="Optional internal note (not stored by the system)">')}
      <div class="modalActions span2">${btn('Cancel','recCancel','ghost')}${btn('Record payment','recSave')}</div>
    </form>`);
    m.querySelector('#recCancel').addEventListener('click',()=>m.remove());
    m.querySelector('#recPayForm').onsubmit=async e=>{
      e.preventDefault();
      const o=Object.fromEntries(new FormData(e.target));
      const amount=r2(Number(o.amount));
      if(!amount||amount<=0){toast('Enter a valid payment amount');return}
      if(amount>balance+0.0001){toast('Payment exceeds the remaining balance');return}
      const save=m.querySelector('#recSave');save.disabled=true;save.textContent='Recording…';
      try{
        const p=await api(`/api/invoices/${inv.id}/payments`,{method:'POST',body:JSON.stringify({amount,method:o.method,reference:o.reference?o.reference.trim():null})});
        m.remove();
        showPaymentSuccess(inv.id,p);
        toast('✓ Payment recorded successfully');
        render();
      }catch(err){toast(err.message);save.disabled=false;save.textContent='Record payment'}
    };
  }

  // --- Success state (§74) ---
  function showPaymentSuccess(id,payment){
    const m=modal('Payment successful',`<div class="paySuccess">
      <div class="paySuccessCheck">✓</div>
      <h2>PAYMENT SUCCESSFUL</h2>
      <div class="paySuccessRows">
        <div><span>Receipt</span><b>${rctNo(id)}</b></div>
        <div><span>Amount</span><b>${money2(payment.amount)}</b></div>
        <div><span>Method</span><b>${esc(methodName(payment.method))}</b></div>
        <div><span>Reference</span><b>${esc(dash(payment.reference))}</b></div>
      </div>
      <div class="modalActions">
        ${btn('Print receipt','psPrint')}${btn('Download PDF','psPdf','ghost')}${btn('Close','psClose','ghost')}
      </div>
    </div>`);
    m.querySelector('#psPrint').addEventListener('click',()=>{m.remove();window.print()});
    m.querySelector('#psPdf').addEventListener('click',()=>{m.remove();toast('Choose "Save as PDF" in the print dialog');window.print()});
    m.querySelector('#psClose').addEventListener('click',()=>m.remove());
  }

  // --- Pages hook: registered by app.js via window.ReceiptModule ---
  window.ReceiptPage=async function ReceiptPage(){
    const id=receiptId;
    if(!id)throw new Error('No receipt selected');
    if(!can('billing','PRINT')&&!can('billing','VIEW'))throw new Error('You are not permitted to view receipts');
    const [invoices,patientRows,payments]=await Promise.all([
      api('/api/invoices'),api('/api/patients'),api(`/api/invoices/${id}/payments`)
    ]);
    const inv=invoices.find(x=>x.id===Number(id));
    if(!inv)throw new Error('Invoice not found');
    const patient=patientRows.find(p=>p.id===inv.patient_id)||null;
    const html=buildHeading(inv)+buildReceipt(inv,patient,payments)+buildBar(inv);
    shell(`<div class="receiptPage">${html}</div>`);
    bindBar(inv,payments);
  };
})();