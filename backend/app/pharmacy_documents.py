"""Printable medicine bill / prescription sheet for the pharmacy.

The document deliberately lists *all* prescribed medicines, including items the
hospital pharmacy cannot supply and the patient must source externally.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import get_db
from .models import Hospital, Patient, User, Prescription, InventoryItem, Invoice, Encounter
from .patient_journey import VisitFile
from .security import current_user, ensure_access
from .audit import record

router = APIRouter(prefix="/api/pharmacy-documents", tags=["Pharmacy Documents"])


def _visit(db: Session, visit_id: int, hospital_id: int) -> VisitFile:
    v = db.get(VisitFile, visit_id)
    if not v or v.hospital_id != hospital_id:
        raise HTTPException(404, "Visit file not found")
    return v


def _bill_payload(db: Session, v: VisitFile) -> dict:
    patient = db.get(Patient, v.patient_id)
    hospital = db.get(Hospital, v.hospital_id)
    doctor = db.get(User, v.current_doctor_id or v.initial_doctor_id) if (v.current_doctor_id or v.initial_doctor_id) else None
    rxs = db.query(Prescription).filter_by(hospital_id=v.hospital_id, encounter_id=v.encounter_id).order_by(Prescription.id).all()
    lines = []
    calculated_hospital_total = 0.0
    for rx in rxs:
        stock = db.get(InventoryItem, rx.inventory_item_id) if rx.inventory_item_id else db.query(InventoryItem).filter(
            InventoryItem.hospital_id == v.hospital_id, func.lower(InventoryItem.name) == rx.medicine.lower()
        ).first()
        external = rx.status == "EXTERNAL" or v.pharmacy_choice == "EXTERNAL"
        source = "EXTERNAL" if external else "HOSPITAL"
        available_qty = int(stock.quantity or 0) if stock else 0
        unit_price = float(stock.unit_price or 0) if stock else None
        hospital_line_total = round((unit_price or 0) * int(rx.quantity or 0), 2) if source == "HOSPITAL" and stock else None
        if hospital_line_total is not None:
            calculated_hospital_total += hospital_line_total
        lines.append({
            "prescription_id": rx.id,
            "medicine": rx.medicine,
            "dose": rx.dose,
            "frequency": rx.frequency,
            "duration": rx.duration,
            "quantity": rx.quantity,
            "instructions": rx.instructions,
            "status": rx.status,
            "source": source,
            "available_at_hospital": bool(stock and available_qty >= int(rx.quantity or 0)),
            "available_quantity": available_qty,
            "hospital_unit_price": unit_price,
            "hospital_line_total": hospital_line_total,
        })
    invoice = db.get(Invoice, v.pharmacy_invoice_id) if v.pharmacy_invoice_id else None
    hospital_total = float(invoice.amount) if invoice else round(calculated_hospital_total, 2)
    return {
        "bill_no": f"MED-{v.id:06d}",
        "generated_at": datetime.utcnow(),
        "hospital": {"name": hospital.name if hospital else "Hospital", "address": hospital.address if hospital else None, "phone": hospital.phone if hospital else None},
        "patient": {"id": patient.id if patient else None, "patient_no": patient.patient_no if patient else None, "name": f"{patient.first_name} {patient.last_name}" if patient else "Unknown", "phone": patient.phone if patient else None},
        "visit": {"id": v.id, "file_no": v.file_no, "status": v.status, "pharmacy_choice": v.pharmacy_choice},
        "doctor": doctor.full_name if doctor else None,
        "lines": lines,
        "hospital_payable_total": hospital_total,
        "pharmacy_invoice": {"id": invoice.id, "status": invoice.status, "amount": invoice.amount, "paid_amount": invoice.paid_amount} if invoice else None,
        "external_count": sum(1 for x in lines if x["source"] == "EXTERNAL"),
    }


@router.get("/visits/{visit_id}/medicine-bill")
def medicine_bill(visit_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "pharmacy", "VIEW")
    v = _visit(db, visit_id, user.hospital_id)
    return _bill_payload(db, v)


def _money(v):
    if v is None:
        return "—"
    return f"TZS {float(v):,.0f}"


@router.get("/visits/{visit_id}/medicine-bill/print", response_class=HTMLResponse)
def print_medicine_bill(visit_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "pharmacy", "VIEW")
    v = _visit(db, visit_id, user.hospital_id)
    d = _bill_payload(db, v)
    record(db, user, "PRINT", "medicine_bill", v.id, {"file_no": v.file_no})
    db.commit()
    rows = "".join(
        f"<tr><td>{i}</td><td><b>{escape(x['medicine'])}</b><br><small>{escape(x['instructions'] or '')}</small></td>"
        f"<td>{escape(x['dose'])}</td><td>{escape(x['frequency'])}</td><td>{escape(x['duration'])}</td><td>{x['quantity']}</td>"
        f"<td><span class='src {x['source'].lower()}'>{escape(x['source'])}</span></td>"
        f"<td>{'In stock' if x['available_at_hospital'] else ('External purchase' if x['source']=='EXTERNAL' else 'Unavailable / confirm with pharmacy')}</td>"
        f"<td>{_money(x['hospital_unit_price']) if x['source']=='HOSPITAL' else 'External price'}</td>"
        f"<td>{_money(x['hospital_line_total']) if x['source']=='HOSPITAL' else '—'}</td></tr>"
        for i, x in enumerate(d["lines"], 1)
    ) or "<tr><td colspan='10'>No medicines prescribed.</td></tr>"
    h=d['hospital']; p=d['patient']; vv=d['visit']
    return HTMLResponse(f"""<!doctype html><html><head><meta charset='utf-8'><title>{escape(d['bill_no'])} · Medicine Bill</title>
<style>body{{font:14px Arial,sans-serif;color:#172033;margin:34px}}.head{{display:flex;justify-content:space-between;border-bottom:3px solid #1357c5;padding-bottom:16px}}h1{{margin:0;color:#1357c5}}.meta{{display:grid;grid-template-columns:1fr 1fr;gap:6px 28px;margin:22px 0}}table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{border:1px solid #dfe5ee;padding:8px;vertical-align:top}}th{{background:#f3f7fc;text-align:left}}.src{{font-weight:700}}.external{{color:#a14b00}}.hospital{{color:#0a6b47}}.total{{margin-top:18px;text-align:right;font-size:18px;font-weight:700}}.note{{margin-top:20px;padding:12px;background:#f6f8fb;border-radius:8px}}small{{color:#667085}}@media print{{button{{display:none}}body{{margin:10mm}}}}</style></head><body>
<div class='head'><div><h1>{escape(h['name'])}</h1><div>MEDICINE BILL / PRESCRIPTION LIST</div><small>{escape(h.get('address') or '')} {escape(h.get('phone') or '')}</small></div><div><b>{escape(d['bill_no'])}</b><br>{d['generated_at'].strftime('%d %b %Y %H:%M')}</div></div>
<div class='meta'><div><b>Patient:</b> {escape(p['name'])}</div><div><b>Patient No:</b> {escape(p['patient_no'] or '—')}</div><div><b>Visit file:</b> {escape(vv['file_no'])}</div><div><b>Doctor:</b> {escape(d['doctor'] or '—')}</div></div>
<table><thead><tr><th>#</th><th>Medicine / instructions</th><th>Dose</th><th>Frequency</th><th>Duration</th><th>Qty</th><th>Source</th><th>Availability</th><th>Hospital unit price</th><th>Hospital amount</th></tr></thead><tbody>{rows}</tbody></table>
<div class='total'>Hospital payable total: {_money(d['hospital_payable_total'])}</div>
<div class='note'><b>Important:</b> This sheet lists every medicine prescribed for this visit. Medicines marked <b>EXTERNAL</b> should be sourced from another licensed pharmacy; external pharmacy prices are not set by this hospital. Follow the dose, frequency, duration and instructions shown above.</div>
<p><button onclick='window.print()'>Print</button></p></body></html>""")


@router.get("/prescriptions/{prescription_id}/medicine-bill/print", response_class=HTMLResponse)
def print_bill_from_prescription(prescription_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "pharmacy", "VIEW")
    rx = db.get(Prescription, prescription_id)
    if not rx or rx.hospital_id != user.hospital_id:
        raise HTTPException(404, "Prescription not found")
    v = db.query(VisitFile).filter_by(hospital_id=user.hospital_id, encounter_id=rx.encounter_id).first()
    if not v:
        raise HTTPException(404, "No visit file linked to this prescription")
    return print_medicine_bill(v.id, user, db)
