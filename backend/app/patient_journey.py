"""End-to-end hospital visit / patient journey workflow.

This module is intentionally additive.  It links the existing Patient, Encounter,
Invoice, LabOrder, Prescription, Ward/Bed and Admission records through a per-visit
file without changing the schema of those mature tables.
"""
from __future__ import annotations

from datetime import datetime, date
import json
import os
import urllib.request
import urllib.error
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, Float, UniqueConstraint, JSON, func, or_
from sqlalchemy.orm import Mapped, mapped_column, Session

from .database import Base, get_db
from .models import (
    Hospital, HospitalModule, Role, User, Patient, Encounter, Vital, LabOrder,
    Prescription, Invoice, Payment, InventoryItem, StockTransaction, Ward, Bed,
    Admission,
)
from .security import current_user, ensure_access
from .audit import record

router = APIRouter(prefix="/api/journey", tags=["Patient Journey"])


# ---------------------------------------------------------------------------
# New additive tables
# ---------------------------------------------------------------------------
class JourneySetting(Base):
    __tablename__ = "journey_settings"
    __table_args__ = (UniqueConstraint("hospital_id", name="uq_journey_settings_hospital"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    consultation_fee: Mapped[float] = mapped_column(Float, default=10000)
    consultation_fee_label: Mapped[str] = mapped_column(String(120), default="Doctor consultation")
    currency: Mapped[str] = mapped_column(String(10), default="TZS")
    require_consultation_payment: Mapped[bool] = mapped_column(Boolean, default=True)
    require_triage: Mapped[bool] = mapped_column(Boolean, default=False)
    require_lab_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    require_pharmacy_payment: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_lab_results: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_assign_doctor: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VisitFile(Base):
    __tablename__ = "visit_files"
    __table_args__ = (
        UniqueConstraint("hospital_id", "file_no", name="uq_visit_file_no"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    encounter_id: Mapped[int] = mapped_column(ForeignKey("encounters.id"), index=True)
    file_no: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    stage: Mapped[str] = mapped_column(String(50), default="AWAITING_PAYMENT", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    consultation_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    pharmacy_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    initial_doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    current_doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_room: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pharmacy_choice: Mapped[str | None] = mapped_column(String(20), nullable=True)
    admission_id: Mapped[int | None] = mapped_column(ForeignKey("admissions.id"), nullable=True)
    admission_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    doctor_close_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    doctor_close_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discharge_decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discharge_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)


class VisitEvent(Base):
    __tablename__ = "visit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column("event_details", JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class DoctorShift(Base):
    __tablename__ = "doctor_shifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    room_number: Mapped[str] = mapped_column(String(80))
    availability: Mapped[str] = mapped_column(String(20), default="AVAILABLE")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class InpatientProgress(Base):
    __tablename__ = "inpatient_progress"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), index=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id", ondelete="CASCADE"), index=True)
    note_type: Mapped[str] = mapped_column(String(30), default="PROGRESS")
    note: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SmsOutbox(Base):
    __tablename__ = "sms_outbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int | None] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), nullable=True, index=True)
    phone: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(60), default="GENERAL")
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    provider_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------
class VisitOpenIn(BaseModel):
    patient_id: int
    reason: str | None = None
    priority: str = "NORMAL"
    payer_type: str = "CASH"
    payer_name: str | None = None
    member_no: str | None = None
    authorization_status: str = "NOT_REQUIRED"
    department: str = "OPD"
    referral_source: str | None = None

class RegisterOpenIn(BaseModel):
    first_name: str
    last_name: str
    sex: str = "Unknown"
    date_of_birth: date | None = None
    phone: str | None = None
    address: str | None = None
    next_of_kin: str | None = None
    reason: str | None = None
    priority: str = "NORMAL"
    payer_type: str = "CASH"
    payer_name: str | None = None
    member_no: str | None = None
    authorization_status: str = "NOT_REQUIRED"
    department: str = "OPD"
    referral_source: str | None = None

class JourneySettingIn(BaseModel):
    consultation_fee: float | None = Field(default=None, ge=0)
    consultation_fee_label: str | None = None
    currency: str | None = None
    require_consultation_payment: bool | None = None
    require_triage: bool | None = None
    require_lab_verification: bool | None = None
    require_pharmacy_payment: bool | None = None
    sms_enabled: bool | None = None
    sms_lab_results: bool | None = None
    auto_assign_doctor: bool | None = None

class TriageIn(BaseModel):
    temperature_c: float | None = None
    pulse: int | None = None
    systolic: int | None = None
    diastolic: int | None = None
    spo2: int | None = None
    weight_kg: float | None = None
    height_cm: float | None = None

class ShiftStartIn(BaseModel):
    room_number: str = Field(min_length=1, max_length=80)

class AvailabilityIn(BaseModel):
    availability: str

class ConsultationIn(BaseModel):
    chief_complaint: str | None = None
    clinical_notes: str | None = None
    diagnosis: str | None = None

class LabOrderBatchIn(BaseModel):
    tests: list[str]

class PrescriptionItemIn(BaseModel):
    inventory_item_id: int | None = None
    medicine: str
    dose: str
    frequency: str
    duration: str
    quantity: int = Field(default=1, ge=1)
    instructions: str | None = None

class PrescriptionBatchIn(BaseModel):
    medicines: list[PrescriptionItemIn]
    source: str = "HOSPITAL"

class OutcomeIn(BaseModel):
    outcome: str
    pharmacy_choice: str | None = None
    note: str | None = None

class AdmissionIn(BaseModel):
    ward_id: int
    bed_id: int

class ProgressIn(BaseModel):
    note_type: str = "PROGRESS"
    note: str = Field(min_length=1)

class DischargeDecisionIn(BaseModel):
    summary: str = Field(min_length=1)

class SmsRetryIn(BaseModel):
    ids: list[int] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
OPEN_STAGES = {
    "AWAITING_PAYMENT", "TRIAGE", "WAITING_DOCTOR", "WITH_DOCTOR", "LAB_PENDING",
    "LAB_RESULTS_READY", "PHARMACY_PENDING", "PHARMACY_READY", "ADMISSION_PENDING",
    "ADMITTED", "DISCHARGE_PENDING", "CLOSING_PENDING_PHARMACY",
}


def _owned(db: Session, model, item_id: int, hospital_id: int, label: str):
    item = db.get(model, item_id)
    if not item or getattr(item, "hospital_id", hospital_id) != hospital_id:
        raise HTTPException(404, f"{label} not found")
    return item


def _settings(db: Session, hospital_id: int) -> JourneySetting:
    item = db.query(JourneySetting).filter_by(hospital_id=hospital_id).first()
    if not item:
        item = JourneySetting(hospital_id=hospital_id)
        db.add(item)
        db.flush()
    return item


def _can(user: User, db: Session, module_key: str, permission: str = "VIEW") -> bool:
    try:
        ensure_access(user, db, module_key, permission)
        return True
    except HTTPException:
        return False


def _require_any(user: User, db: Session, requirements: list[tuple[str, str]]) -> None:
    for module, permission in requirements:
        if _can(user, db, module, permission):
            return
    raise HTTPException(403, "Your role does not have access to this patient-journey action")


def _visit(db: Session, visit_id: int, hid: int) -> VisitFile:
    return _owned(db, VisitFile, visit_id, hid, "Visit file")


def _event(db: Session, visit: VisitFile, event_type: str, user_id: int | None, note: str | None = None, details: dict | None = None):
    db.add(VisitEvent(
        hospital_id=visit.hospital_id, visit_id=visit.id, event_type=event_type,
        note=note, details=details or {}, created_by=user_id,
    ))


def _patient_label(p: Patient) -> str:
    return f"{p.patient_no} — {p.first_name} {p.last_name}"


def _invoice_state(db: Session, invoice_id: int | None):
    if not invoice_id:
        return None
    inv = db.get(Invoice, invoice_id)
    if not inv:
        return None
    return {
        "id": inv.id, "amount": inv.amount, "paid_amount": inv.paid_amount,
        "balance": max(0, round(inv.amount - inv.paid_amount, 2)), "status": inv.status,
        "description": inv.description,
    }


def _active_shift(db: Session, doctor_id: int, hid: int) -> DoctorShift | None:
    return db.query(DoctorShift).filter_by(hospital_id=hid, doctor_id=doctor_id, ended_at=None).order_by(DoctorShift.id.desc()).first()


def _available_shifts(db: Session, hid: int) -> list[DoctorShift]:
    return db.query(DoctorShift).filter_by(hospital_id=hid, ended_at=None, availability="AVAILABLE").order_by(DoctorShift.started_at).all()


def _doctor_name(db: Session, doctor_id: int | None) -> str | None:
    if not doctor_id:
        return None
    u = db.get(User, doctor_id)
    return u.full_name if u else None


def _queue_position(db: Session, visit: VisitFile) -> int | None:
    if not visit.current_doctor_id or visit.status == "CLOSED":
        return None
    ids = [x.id for x in db.query(VisitFile).filter(
        VisitFile.hospital_id == visit.hospital_id,
        VisitFile.current_doctor_id == visit.current_doctor_id,
        VisitFile.status == "OPEN",
        VisitFile.stage.in_(["WAITING_DOCTOR", "LAB_RESULTS_READY", "WITH_DOCTOR"]),
    ).order_by(VisitFile.opened_at, VisitFile.id).all()]
    try:
        return ids.index(visit.id) + 1
    except ValueError:
        return None


def _visit_payload(db: Session, v: VisitFile, detail: bool = False) -> dict[str, Any]:
    p = db.get(Patient, v.patient_id)
    enc = db.get(Encounter, v.encounter_id)
    out = {
        "id": v.id, "file_no": v.file_no, "status": v.status, "stage": v.stage,
        "priority": v.priority, "reason": v.reason, "patient_id": v.patient_id,
        "patient_no": p.patient_no if p else None,
        "patient_name": f"{p.first_name} {p.last_name}" if p else None,
        "phone": p.phone if p else None,
        "encounter_id": v.encounter_id,
        "doctor_id": v.current_doctor_id,
        "doctor_name": _doctor_name(db, v.current_doctor_id),
        "room": v.assigned_room,
        "queue_position": _queue_position(db, v),
        "pharmacy_choice": v.pharmacy_choice,
        "admission_id": v.admission_id,
        "admission_requested": v.admission_requested,
        "doctor_close_requested": v.doctor_close_requested,
        "opened_at": v.opened_at, "closed_at": v.closed_at,
        "consultation_invoice": _invoice_state(db, v.consultation_invoice_id),
        "pharmacy_invoice": _invoice_state(db, v.pharmacy_invoice_id),
    }
    if detail:
        out["patient"] = {
            "id": p.id, "patient_no": p.patient_no, "first_name": p.first_name,
            "last_name": p.last_name, "sex": p.sex, "phone": p.phone,
            "address": p.address, "allergies": p.allergies, "blood_group": p.blood_group,
        } if p else None
        out["encounter"] = {
            "id": enc.id, "status": enc.status, "chief_complaint": enc.chief_complaint,
            "clinical_notes": enc.clinical_notes, "diagnosis": enc.diagnosis,
        } if enc else None
        out["vitals"] = [{
            "id": x.id, "temperature_c": x.temperature_c, "pulse": x.pulse,
            "systolic": x.systolic, "diastolic": x.diastolic, "spo2": x.spo2,
            "weight_kg": x.weight_kg, "height_cm": x.height_cm, "created_at": x.created_at,
        } for x in db.query(Vital).filter_by(encounter_id=v.encounter_id).order_by(Vital.id.desc()).all()]
        out["labs"] = [{
            "id": x.id, "test_name": x.test_name, "status": x.status,
            "result": x.result, "verified": x.verified, "approved": x.approved,
            "created_at": x.created_at,
        } for x in db.query(LabOrder).filter_by(hospital_id=v.hospital_id, encounter_id=v.encounter_id).order_by(LabOrder.id).all()]
        out["prescriptions"] = [{
            "id": x.id, "inventory_item_id": x.inventory_item_id, "medicine": x.medicine,
            "dose": x.dose, "frequency": x.frequency, "duration": x.duration,
            "quantity": x.quantity, "instructions": x.instructions, "status": x.status,
        } for x in db.query(Prescription).filter_by(hospital_id=v.hospital_id, encounter_id=v.encounter_id).order_by(Prescription.id).all()]
        out["events"] = [{
            "id": x.id, "event_type": x.event_type, "note": x.note,
            "details": x.details or {}, "created_by": x.created_by, "created_at": x.created_at,
        } for x in db.query(VisitEvent).filter_by(visit_id=v.id).order_by(VisitEvent.id).all()]
        if v.admission_id:
            adm = db.get(Admission, v.admission_id)
            if adm:
                ward = db.get(Ward, adm.ward_id)
                bed = db.get(Bed, adm.bed_id)
                out["admission"] = {
                    "id": adm.id, "status": adm.status, "ward_id": adm.ward_id,
                    "ward_name": ward.name if ward else None, "bed_id": adm.bed_id,
                    "bed_code": bed.code if bed else None, "admitted_at": adm.admitted_at,
                    "discharged_at": adm.discharged_at,
                }
                out["progress"] = [{
                    "id": n.id, "note_type": n.note_type, "note": n.note,
                    "created_by": n.created_by, "created_at": n.created_at,
                } for n in db.query(InpatientProgress).filter_by(visit_id=v.id).order_by(InpatientProgress.id.desc()).all()]
    return out


def _next_stage_after_payment(db: Session, v: VisitFile) -> str:
    s = _settings(db, v.hospital_id)
    return "TRIAGE" if s.require_triage else "WAITING_DOCTOR"


def _all_lab_ready(db: Session, v: VisitFile) -> bool:
    rows = db.query(LabOrder).filter_by(hospital_id=v.hospital_id, encounter_id=v.encounter_id).all()
    if not rows:
        return False
    s = _settings(db, v.hospital_id)
    if s.require_lab_verification:
        return all(bool(x.result) and x.verified for x in rows)
    return all(bool(x.result) for x in rows)


def _all_hospital_prescriptions_dispensed(db: Session, v: VisitFile) -> bool:
    rows = db.query(Prescription).filter_by(hospital_id=v.hospital_id, encounter_id=v.encounter_id).all()
    if not rows:
        return True
    relevant = [x for x in rows if x.status != "EXTERNAL"]
    return bool(relevant) and all(x.status == "DISPENSED" for x in relevant)


def _finalize_close(db: Session, v: VisitFile, user_id: int | None, reason: str):
    if v.status == "CLOSED":
        return
    v.status = "CLOSED"
    v.stage = "CLOSED"
    v.closed_at = datetime.utcnow()
    v.closed_by = user_id or v.closed_by or v.current_doctor_id
    v.close_reason = reason
    enc = db.get(Encounter, v.encounter_id)
    if enc and enc.status == "OPEN":
        enc.status = "COMPLETED"
    _event(db, v, "FILE_CLOSED", user_id, reason)


def _assign_visit_to_doctor(db: Session, v: VisitFile, prefer_doctor_id: int | None = None, notify: bool = False):
    if v.status == "CLOSED":
        return None
    shifts = _available_shifts(db, v.hospital_id)
    if not shifts:
        v.current_doctor_id = None
        v.assigned_room = None
        return None
    selected = None
    if prefer_doctor_id:
        selected = next((s for s in shifts if s.doctor_id == prefer_doctor_id), None)
    if not selected:
        # Least queued available doctor keeps assignment fair and room-aware.
        def queue_count(s: DoctorShift):
            return db.query(VisitFile).filter(
                VisitFile.hospital_id == v.hospital_id,
                VisitFile.current_doctor_id == s.doctor_id,
                VisitFile.status == "OPEN",
                VisitFile.stage.in_(["WAITING_DOCTOR", "LAB_RESULTS_READY", "WITH_DOCTOR"]),
            ).count()
        selected = min(shifts, key=lambda s: (queue_count(s), s.started_at, s.id))
    v.current_doctor_id = selected.doctor_id
    if not v.initial_doctor_id:
        v.initial_doctor_id = selected.doctor_id
    v.assigned_room = selected.room_number
    _event(db, v, "DOCTOR_ASSIGNED", None, details={"doctor_id": selected.doctor_id, "room": selected.room_number})
    if notify:
        p = db.get(Patient, v.patient_id)
        doctor = db.get(User, selected.doctor_id)
        if p and p.phone:
            msg = f"Your results are ready. Please proceed to {doctor.full_name if doctor else 'the doctor'}, Room {selected.room_number}. Please wait if the room is occupied."
            _queue_sms(db, v, p.phone, msg, "LAB_RESULTS_READY")
    return selected


def _assign_waiting_to_new_doctor(db: Session, shift: DoctorShift):
    rows = db.query(VisitFile).filter(
        VisitFile.hospital_id == shift.hospital_id,
        VisitFile.status == "OPEN",
        VisitFile.current_doctor_id.is_(None),
        VisitFile.stage.in_(["WAITING_DOCTOR", "LAB_RESULTS_READY"]),
    ).order_by(VisitFile.priority.desc(), VisitFile.opened_at).all()
    for v in rows:
        v.current_doctor_id = shift.doctor_id
        if not v.initial_doctor_id:
            v.initial_doctor_id = shift.doctor_id
        v.assigned_room = shift.room_number
        _event(db, v, "DOCTOR_ASSIGNED", shift.doctor_id, details={"doctor_id": shift.doctor_id, "room": shift.room_number})
        if v.stage == "LAB_RESULTS_READY":
            p = db.get(Patient, v.patient_id)
            doctor = db.get(User, shift.doctor_id)
            if p and p.phone:
                _queue_sms(db, v, p.phone, f"Your results are ready. Please proceed to {doctor.full_name if doctor else 'the doctor'}, Room {shift.room_number}. Please wait if the room is occupied.", "LAB_RESULTS_READY")


def _queue_sms(db: Session, v: VisitFile | None, phone: str, message: str, event_type: str):
    s = _settings(db, v.hospital_id if v else 0) if v else None
    if s is not None and not s.sms_enabled:
        return None
    row = SmsOutbox(
        hospital_id=v.hospital_id if v else 0, visit_id=v.id if v else None,
        phone=phone, message=message, event_type=event_type, status="QUEUED",
    )
    db.add(row)
    db.flush()
    _try_send_sms(row)
    return row


def _try_send_sms(row: SmsOutbox):
    """Send to a generic hospital SMS webhook when configured.

    Set HMS_SMS_WEBHOOK_URL to an endpoint that accepts JSON:
    {to, message, event_type, visit_id}.  HMS_SMS_API_KEY is sent as Bearer token.
    Without a configured webhook, messages remain QUEUED and are visible in the outbox.
    """
    url = os.getenv("HMS_SMS_WEBHOOK_URL", "").strip()
    if not url:
        return
    payload = json.dumps({
        "to": row.phone, "message": row.message, "event_type": row.event_type,
        "visit_id": row.visit_id,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    key = os.getenv("HMS_SMS_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=8) as res:
            body = res.read(1000).decode("utf-8", "replace")
            row.status = "SENT"
            row.sent_at = datetime.utcnow()
            row.provider_response = f"HTTP {res.status}: {body}"[:2000]
    except Exception as exc:
        row.status = "FAILED"
        row.provider_response = str(exc)[:2000]


def _open_visit(
    db: Session, patient: Patient, reason: str | None, priority: str, user: User,
    *, payer_type: str = "CASH", payer_name: str | None = None, member_no: str | None = None,
    authorization_status: str = "NOT_REQUIRED", department: str = "OPD", referral_source: str | None = None,
) -> VisitFile:
    existing = db.query(VisitFile).filter_by(hospital_id=user.hospital_id, patient_id=patient.id, status="OPEN").first()
    if existing:
        raise HTTPException(409, f"Patient already has open visit file {existing.file_no}")
    priority = (priority or "NORMAL").upper()
    if priority not in {"NORMAL", "URGENT", "EMERGENCY"}:
        raise HTTPException(400, "priority must be NORMAL, URGENT or EMERGENCY")
    payer_type = (payer_type or "CASH").upper()
    authorization_status = (authorization_status or "NOT_REQUIRED").upper()
    if payer_type not in {"CASH", "INSURANCE", "CORPORATE", "EXEMPT"}:
        raise HTTPException(400, "payer_type must be CASH, INSURANCE, CORPORATE or EXEMPT")
    if authorization_status not in {"NOT_REQUIRED", "PENDING", "APPROVED", "AUTHORIZED", "DECLINED"}:
        raise HTTPException(400, "Invalid authorization_status")
    sponsored_clearance = payer_type == "EXEMPT" or (payer_type in {"INSURANCE", "CORPORATE"} and authorization_status in {"APPROVED", "AUTHORIZED"})
    enc = Encounter(
        hospital_id=user.hospital_id, patient_id=patient.id, encounter_type="EMERGENCY" if priority == "EMERGENCY" else "OPD",
        status="OPEN", chief_complaint=reason,
    )
    db.add(enc)
    db.flush()
    settings = _settings(db, user.hospital_id)
    inv = None
    if settings.consultation_fee > 0:
        inv = Invoice(
            hospital_id=user.hospital_id, patient_id=patient.id,
            amount=settings.consultation_fee, paid_amount=0,
            description=settings.consultation_fee_label,
            status="UNPAID",
        )
        db.add(inv)
        db.flush()
    emergency_bypass = False
    if priority == "EMERGENCY":
        try:
            from .care_pathways import emergency_bypass_enabled
            emergency_bypass = emergency_bypass_enabled(db, user.hospital_id)
        except Exception:
            emergency_bypass = True
    needs_payment = settings.require_consultation_payment and bool(inv and inv.amount > 0) and not emergency_bypass and not sponsored_clearance
    if priority == "EMERGENCY":
        # Emergency clinical care is never hidden behind a cashier queue.  The
        # charge can remain open and be settled later according to hospital policy.
        stage = "TRIAGE"
    else:
        stage = "AWAITING_PAYMENT" if needs_payment else ("TRIAGE" if settings.require_triage else "WAITING_DOCTOR")
    v = VisitFile(
        hospital_id=user.hospital_id, patient_id=patient.id, encounter_id=enc.id,
        file_no="PENDING", status="OPEN", stage=stage,
        priority=priority, reason=reason, consultation_invoice_id=inv.id if inv else None,
        opened_by=user.id,
    )
    db.add(v)
    db.flush()
    v.file_no = f"F{datetime.utcnow():%Y%m%d}-{v.id:06d}"
    try:
        from .care_pathways import _admin_context
        a = _admin_context(db, v)
        a.payer_type = payer_type
        a.payer_name = payer_name
        a.member_no = member_no
        a.authorization_status = authorization_status
        a.department = "EMERGENCY" if priority == "EMERGENCY" else (department or "OPD")
        a.referral_source = referral_source
    except Exception:
        pass
    _event(db, v, "FILE_OPENED", user.id, reason, {"patient_no": patient.patient_no, "priority": v.priority})
    if inv:
        _event(db, v, "CONSULTATION_INVOICE_CREATED", user.id, details={"invoice_id": inv.id, "amount": inv.amount})
    if emergency_bypass:
        try:
            from .care_pathways import _admin_context
            a = _admin_context(db, v); a.emergency_payment_bypass = True; a.department = "EMERGENCY"
        except Exception:
            pass
        _event(db, v, "EMERGENCY_PAYMENT_DEFERRED", user.id, "Emergency care allowed before payment")
    if stage == "WAITING_DOCTOR" and settings.auto_assign_doctor:
        _assign_visit_to_doctor(db, v)
    record(db, user, "OPEN_VISIT_FILE", "visit_file", v.id, {"file_no": v.file_no, "patient_id": patient.id})
    return v


# ---------------------------------------------------------------------------
# Compatibility hooks for existing HMS endpoints
# ---------------------------------------------------------------------------
def journey_after_payment(db: Session, invoice: Invoice, user: User | None = None):
    v = db.query(VisitFile).filter(
        VisitFile.hospital_id == invoice.hospital_id,
        or_(VisitFile.consultation_invoice_id == invoice.id, VisitFile.pharmacy_invoice_id == invoice.id),
    ).first()
    if not v or v.status == "CLOSED":
        return
    if invoice.status != "PAID":
        return
    if v.consultation_invoice_id == invoice.id and v.stage == "AWAITING_PAYMENT":
        v.stage = _next_stage_after_payment(db, v)
        _event(db, v, "CONSULTATION_FEE_PAID", user.id if user else None, details={"invoice_id": invoice.id})
        if v.stage == "WAITING_DOCTOR" and _settings(db, v.hospital_id).auto_assign_doctor:
            _assign_visit_to_doctor(db, v)
    if v.pharmacy_invoice_id == invoice.id:
        _event(db, v, "PHARMACY_PAYMENT_COMPLETED", user.id if user else None, details={"invoice_id": invoice.id})
        if v.stage in {"PHARMACY_PENDING", "CLOSING_PENDING_PHARMACY"}:
            v.stage = "PHARMACY_READY"
        if v.doctor_close_requested and _all_hospital_prescriptions_dispensed(db, v):
            _finalize_close(db, v, v.current_doctor_id, "Outpatient treatment completed")


def journey_after_vitals(db: Session, encounter_id: int, user: User | None = None):
    v = db.query(VisitFile).filter_by(encounter_id=encounter_id).first()
    if not v or v.status == "CLOSED":
        return
    if v.stage == "TRIAGE":
        v.stage = "WAITING_DOCTOR"
        _event(db, v, "TRIAGE_COMPLETED", user.id if user else None)
        if _settings(db, v.hospital_id).auto_assign_doctor:
            _assign_visit_to_doctor(db, v)


def journey_after_lab_order(db: Session, lab: LabOrder, user: User | None = None):
    v = db.query(VisitFile).filter_by(encounter_id=lab.encounter_id).first()
    if not v or v.status == "CLOSED":
        return
    v.stage = "LAB_PENDING"
    _event(db, v, "LAB_ORDERED", user.id if user else None, lab.test_name, {"lab_order_id": lab.id})


def journey_after_lab_update(db: Session, lab: LabOrder, user: User | None = None):
    v = db.query(VisitFile).filter_by(encounter_id=lab.encounter_id).first()
    if not v or v.status == "CLOSED":
        return
    _event(db, v, "LAB_RESULT_UPDATED", user.id if user else None, lab.test_name, {"lab_order_id": lab.id, "status": lab.status})
    if _all_lab_ready(db, v):
        v.stage = "LAB_RESULTS_READY"
        s = _settings(db, v.hospital_id)
        if s.auto_assign_doctor:
            _assign_visit_to_doctor(db, v, prefer_doctor_id=v.initial_doctor_id, notify=s.sms_lab_results)
        elif s.sms_lab_results:
            p = db.get(Patient, v.patient_id)
            if p and p.phone:
                _queue_sms(db, v, p.phone, "Your laboratory results are ready. Please return to the OPD doctor review queue.", "LAB_RESULTS_READY")


def _visit_payment_sponsored(db: Session, v: VisitFile) -> bool:
    try:
        from .care_pathways import visit_payment_sponsored
        return visit_payment_sponsored(db, v)
    except Exception:
        return False


def ensure_dispense_allowed(db: Session, prescription: Prescription):
    """Enforce visit-level payment policy before medicine leaves the hospital pharmacy."""
    v = db.query(VisitFile).filter_by(encounter_id=prescription.encounter_id).first()
    if not v or v.status == "CLOSED" or v.pharmacy_choice != "HOSPITAL":
        return
    if not _settings(db, v.hospital_id).require_pharmacy_payment or _visit_payment_sponsored(db, v):
        return
    inv = db.get(Invoice, v.pharmacy_invoice_id) if v.pharmacy_invoice_id else None
    if not inv:
        raise HTTPException(409, {"code":"PHARMACY_BILL_REQUIRED","message":"Prepare the pharmacy bill before dispensing"})
    if inv.status != "PAID":
        raise HTTPException(409, {"code":"PHARMACY_PAYMENT_REQUIRED","balance":max(0,round(inv.amount-inv.paid_amount,2))})


def journey_after_dispense(db: Session, prescription: Prescription, user: User | None = None):
    v = db.query(VisitFile).filter_by(encounter_id=prescription.encounter_id).first()
    if not v or v.status == "CLOSED":
        return
    _event(db, v, "MEDICINE_DISPENSED", user.id if user else None, prescription.medicine, {"prescription_id": prescription.id})
    invoice = db.get(Invoice, v.pharmacy_invoice_id) if v.pharmacy_invoice_id else None
    paid_ok = (not _settings(db, v.hospital_id).require_pharmacy_payment) or _visit_payment_sponsored(db, v) or (invoice and invoice.status == "PAID")
    if v.doctor_close_requested and paid_ok and _all_hospital_prescriptions_dispensed(db, v):
        _finalize_close(db, v, v.current_doctor_id, "Outpatient treatment completed")


def journey_after_admission(db: Session, admission: Admission, user: User | None = None):
    if not admission.encounter_id:
        return
    v = db.query(VisitFile).filter_by(encounter_id=admission.encounter_id).first()
    if not v or v.status == "CLOSED":
        return
    v.admission_id = admission.id
    v.admission_requested = True
    v.stage = "ADMITTED"
    _event(db, v, "PATIENT_ADMITTED", user.id if user else None, details={"admission_id": admission.id, "ward_id": admission.ward_id, "bed_id": admission.bed_id})


def journey_after_discharge(db: Session, admission: Admission, user: User | None = None):
    v = db.query(VisitFile).filter_by(admission_id=admission.id).first()
    if not v or v.status == "CLOSED":
        return
    _event(db, v, "PATIENT_DISCHARGED", user.id if user else None, details={"admission_id": admission.id})
    _finalize_close(db, v, user.id if user else v.current_doctor_id, "Inpatient discharge completed")


# ---------------------------------------------------------------------------
# Settings & workspace
# ---------------------------------------------------------------------------
@router.get("/settings")
def get_journey_settings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_any(user, db, [("reception", "VIEW"), ("consultation", "VIEW"), ("configuration", "VIEW")])
    s = _settings(db, user.hospital_id)
    db.commit(); db.refresh(s)
    return {c.name: getattr(s, c.name) for c in JourneySetting.__table__.columns if c.name not in {"id", "hospital_id"}}


@router.patch("/settings")
def update_journey_settings(data: JourneySettingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "EDIT")
    s = _settings(db, user.hospital_id)
    changes = data.model_dump(exclude_unset=True)
    if "currency" in changes and changes["currency"]:
        changes["currency"] = changes["currency"].upper()[:10]
    for key, val in changes.items():
        if val is not None:
            setattr(s, key, val)
    record(db, user, "EDIT", "journey_settings", s.id, changes)
    db.commit(); db.refresh(s)
    return {c.name: getattr(s, c.name) for c in JourneySetting.__table__.columns if c.name not in {"id", "hospital_id"}}


@router.get("/workspace")
def workspace(user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_any(user, db, [
        ("reception", "VIEW"), ("triage", "VIEW"), ("consultation", "VIEW"),
        ("laboratory", "VIEW"), ("pharmacy", "VIEW"), ("billing", "VIEW"), ("wards", "VIEW"),
    ])
    visits = db.query(VisitFile).filter_by(hospital_id=user.hospital_id, status="OPEN").order_by(VisitFile.opened_at).all()
    s = _settings(db, user.hospital_id)
    shift = _active_shift(db, user.id, user.hospital_id)
    return {
        "settings": {"consultation_fee": s.consultation_fee, "currency": s.currency, "require_triage": s.require_triage},
        "open_visits": [_visit_payload(db, x) for x in visits],
        "my_shift": _shift_payload(db, shift) if shift else None,
        "permissions": user.role.permissions or {},
        "role": user.role.name,
    }


# ---------------------------------------------------------------------------
# Reception / file opening
# ---------------------------------------------------------------------------
@router.get("/visits")
def list_visits(q: str | None = None, status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_any(user, db, [("reception", "VIEW"), ("medical_records", "VIEW"), ("consultation", "VIEW")])
    query = db.query(VisitFile).filter_by(hospital_id=user.hospital_id)
    if status:
        query = query.filter(VisitFile.status == status.upper())
    rows = query.order_by(VisitFile.id.desc()).limit(500).all()
    if q:
        s = q.lower().strip()
        filtered = []
        for v in rows:
            p = db.get(Patient, v.patient_id)
            hay = f"{v.file_no} {p.patient_no if p else ''} {p.first_name if p else ''} {p.last_name if p else ''} {p.phone if p else ''}".lower()
            if s in hay:
                filtered.append(v)
        rows = filtered
    return [_visit_payload(db, x) for x in rows]


@router.get("/visits/{visit_id}")
def visit_detail(visit_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_any(user, db, [
        ("reception", "VIEW"), ("medical_records", "VIEW"), ("consultation", "VIEW"),
        ("laboratory", "VIEW"), ("pharmacy", "VIEW"), ("wards", "VIEW"),
    ])
    return _visit_payload(db, _visit(db, visit_id, user.hospital_id), True)


@router.post("/visits")
def open_visit(data: VisitOpenIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "reception", "CREATE")
    p = _owned(db, Patient, data.patient_id, user.hospital_id, "Patient")
    v = _open_visit(db, p, data.reason, data.priority, user, payer_type=data.payer_type, payer_name=data.payer_name,
                    member_no=data.member_no, authorization_status=data.authorization_status, department=data.department,
                    referral_source=data.referral_source)
    db.commit(); db.refresh(v)
    return _visit_payload(db, v, True)


@router.post("/register-and-open")
def register_and_open(data: RegisterOpenIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "reception", "CREATE")
    ensure_access(user, db, "patients", "CREATE")
    next_no = (db.query(func.max(Patient.id)).scalar() or 0) + 1
    p = Patient(
        hospital_id=user.hospital_id, patient_no=f"P{next_no:06d}", first_name=data.first_name,
        last_name=data.last_name, sex=data.sex, date_of_birth=data.date_of_birth, phone=data.phone,
        address=data.address, next_of_kin=data.next_of_kin,
    )
    db.add(p); db.flush(); record(db, user, "CREATE", "patient", p.id)
    v = _open_visit(db, p, data.reason, data.priority, user, payer_type=data.payer_type, payer_name=data.payer_name,
                    member_no=data.member_no, authorization_status=data.authorization_status, department=data.department,
                    referral_source=data.referral_source)
    db.commit(); db.refresh(v)
    return _visit_payload(db, v, True)


# ---------------------------------------------------------------------------
# Cashier / triage
# ---------------------------------------------------------------------------
@router.get("/billing-queue")
def billing_queue(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "billing", "VIEW")
    rows = db.query(VisitFile).filter_by(hospital_id=user.hospital_id, status="OPEN").order_by(VisitFile.id).all()
    out = []
    for v in rows:
        seen_invoice_ids = set()
        charge_refs = [("CONSULTATION", v.consultation_invoice_id), ("PHARMACY", v.pharmacy_invoice_id)]
        try:
            from .care_pathways import ServiceOrder
            charge_refs += [(o.module_key.upper(), o.invoice_id) for o in db.query(ServiceOrder).filter_by(visit_id=v.id).all() if o.invoice_id]
        except Exception:
            pass
        for kind, invoice_id in charge_refs:
            if not invoice_id or invoice_id in seen_invoice_ids:
                continue
            seen_invoice_ids.add(invoice_id)
            inv = db.get(Invoice, invoice_id)
            if inv and inv.status != "PAID":
                p = db.get(Patient, v.patient_id)
                out.append({
                    "visit_id": v.id, "file_no": v.file_no, "patient_no": p.patient_no,
                    "patient_name": f"{p.first_name} {p.last_name}", "kind": kind,
                    "invoice": _invoice_state(db, inv.id), "stage": v.stage,
                })
    return out


@router.get("/triage-queue")
def triage_queue(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "triage", "VIEW")
    rows = db.query(VisitFile).filter_by(hospital_id=user.hospital_id, status="OPEN", stage="TRIAGE").order_by(VisitFile.opened_at).all()
    return [_visit_payload(db, x) for x in rows]


@router.post("/visits/{visit_id}/triage")
def complete_triage(visit_id: int, data: TriageIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "triage", "CREATE")
    v = _visit(db, visit_id, user.hospital_id)
    if v.stage != "TRIAGE":
        raise HTTPException(400, f"Visit is not waiting for triage (current stage: {v.stage})")
    vital = Vital(encounter_id=v.encounter_id, **data.model_dump())
    db.add(vital); db.flush(); record(db, user, "CREATE", "vitals", vital.id)
    journey_after_vitals(db, v.encounter_id, user)
    db.commit(); db.refresh(v)
    return _visit_payload(db, v, True)


# ---------------------------------------------------------------------------
# Doctor availability and queue
# ---------------------------------------------------------------------------
def _shift_payload(db: Session, s: DoctorShift | None):
    if not s:
        return None
    u = db.get(User, s.doctor_id)
    end = s.ended_at or datetime.utcnow()
    minutes = max(0, int((end - s.started_at).total_seconds() // 60))
    queued = db.query(VisitFile).filter_by(hospital_id=s.hospital_id, current_doctor_id=s.doctor_id, status="OPEN").filter(VisitFile.stage.in_(["WAITING_DOCTOR", "LAB_RESULTS_READY", "WITH_DOCTOR"])).count()
    return {
        "id": s.id, "doctor_id": s.doctor_id, "doctor_name": u.full_name if u else None,
        "room_number": s.room_number, "availability": s.availability,
        "started_at": s.started_at, "ended_at": s.ended_at, "minutes": minutes,
        "queue_count": queued,
    }


@router.get("/doctors")
def doctor_status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_any(user, db, [("reception", "VIEW"), ("consultation", "VIEW"), ("configuration", "VIEW")])
    shifts = db.query(DoctorShift).filter_by(hospital_id=user.hospital_id, ended_at=None).order_by(DoctorShift.started_at).all()
    return [_shift_payload(db, x) for x in shifts]


@router.post("/doctor/shift/start")
def start_shift(data: ShiftStartIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "consultation", "VIEW")
    if _active_shift(db, user.id, user.hospital_id):
        raise HTTPException(409, "You already have an active doctor shift")
    collision = db.query(DoctorShift).filter_by(hospital_id=user.hospital_id, room_number=data.room_number.strip(), ended_at=None).first()
    if collision:
        raise HTTPException(409, f"Room {data.room_number} is already assigned to another active doctor")
    s = DoctorShift(hospital_id=user.hospital_id, doctor_id=user.id, room_number=data.room_number.strip(), availability="AVAILABLE")
    db.add(s); db.flush(); record(db, user, "SHIFT_START", "doctor_shift", s.id, {"room": s.room_number})
    _assign_waiting_to_new_doctor(db, s)
    db.commit(); db.refresh(s)
    return _shift_payload(db, s)


@router.patch("/doctor/availability")
def set_availability(data: AvailabilityIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "consultation", "VIEW")
    s = _active_shift(db, user.id, user.hospital_id)
    if not s:
        raise HTTPException(400, "Start your shift first")
    status = data.availability.upper()
    if status not in {"AVAILABLE", "AWAY"}:
        raise HTTPException(400, "availability must be AVAILABLE or AWAY")
    s.availability = status
    record(db, user, "DOCTOR_AVAILABILITY", "doctor_shift", s.id, {"availability": status})
    if status == "AVAILABLE":
        _assign_waiting_to_new_doctor(db, s)
    db.commit(); db.refresh(s)
    return _shift_payload(db, s)


@router.post("/doctor/shift/stop")
def stop_shift(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "consultation", "VIEW")
    s = _active_shift(db, user.id, user.hospital_id)
    if not s:
        raise HTTPException(400, "No active shift")
    s.ended_at = datetime.utcnow(); s.availability = "OFF_DUTY"
    # Return waiting patients to the unassigned queue; they can be picked by another doctor.
    waiting = db.query(VisitFile).filter(
        VisitFile.hospital_id == user.hospital_id, VisitFile.current_doctor_id == user.id,
        VisitFile.status == "OPEN", VisitFile.stage.in_(["WAITING_DOCTOR", "LAB_RESULTS_READY"]),
    ).all()
    for v in waiting:
        v.current_doctor_id = None; v.assigned_room = None
        _event(db, v, "DOCTOR_UNASSIGNED", user.id, "Doctor ended shift")
        if _settings(db, user.hospital_id).auto_assign_doctor:
            _assign_visit_to_doctor(db, v, prefer_doctor_id=v.initial_doctor_id, notify=v.stage == "LAB_RESULTS_READY")
    record(db, user, "SHIFT_STOP", "doctor_shift", s.id)
    db.commit(); db.refresh(s)
    return _shift_payload(db, s)


@router.get("/doctor/queue")
def doctor_queue(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "consultation", "VIEW")
    rows = db.query(VisitFile).filter(
        VisitFile.hospital_id == user.hospital_id, VisitFile.status == "OPEN",
        or_(VisitFile.current_doctor_id == user.id, VisitFile.current_doctor_id.is_(None)),
        VisitFile.stage.in_(["WAITING_DOCTOR", "LAB_RESULTS_READY", "WITH_DOCTOR"]),
    ).order_by(VisitFile.priority.desc(), VisitFile.opened_at).all()
    return [_visit_payload(db, x) for x in rows]


@router.post("/visits/{visit_id}/claim")
def claim_visit(visit_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "consultation", "EDIT")
    shift = _active_shift(db, user.id, user.hospital_id)
    if not shift or shift.availability != "AVAILABLE":
        raise HTTPException(400, "You must be on an AVAILABLE doctor shift to claim a patient")
    v = _visit(db, visit_id, user.hospital_id)
    if v.stage not in {"WAITING_DOCTOR", "LAB_RESULTS_READY", "WITH_DOCTOR"}:
        raise HTTPException(400, f"Visit is not ready for doctor review (stage: {v.stage})")
    if v.current_doctor_id and v.current_doctor_id != user.id:
        raise HTTPException(409, "Visit is assigned to another doctor")
    v.current_doctor_id = user.id; v.initial_doctor_id = v.initial_doctor_id or user.id; v.assigned_room = shift.room_number; v.stage = "WITH_DOCTOR"
    _event(db, v, "DOCTOR_OPENED_FILE", user.id, details={"room": shift.room_number})
    db.commit(); db.refresh(v)
    return _visit_payload(db, v, True)


@router.patch("/visits/{visit_id}/consultation")
def update_consultation(visit_id: int, data: ConsultationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "consultation", "EDIT")
    ensure_access(user, db, "diagnosis", "EDIT")
    v = _visit(db, visit_id, user.hospital_id)
    if v.current_doctor_id not in {None, user.id}:
        raise HTTPException(409, "Visit is assigned to another doctor")
    enc = _owned(db, Encounter, v.encounter_id, user.hospital_id, "Encounter")
    if data.chief_complaint is not None: enc.chief_complaint = data.chief_complaint
    if data.clinical_notes is not None: enc.clinical_notes = data.clinical_notes
    if data.diagnosis is not None: enc.diagnosis = data.diagnosis
    v.current_doctor_id = user.id; v.initial_doctor_id = v.initial_doctor_id or user.id
    shift = _active_shift(db, user.id, user.hospital_id)
    if shift: v.assigned_room = shift.room_number
    v.stage = "WITH_DOCTOR"
    _event(db, v, "CONSULTATION_UPDATED", user.id, data.clinical_notes)
    record(db, user, "EDIT", "consultation", enc.id)
    db.commit(); db.refresh(v)
    return _visit_payload(db, v, True)


@router.post("/visits/{visit_id}/lab-orders")
def order_labs(visit_id: int, data: LabOrderBatchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "laboratory", "CREATE")
    v = _visit(db, visit_id, user.hospital_id)
    if not data.tests or not any(x.strip() for x in data.tests):
        raise HTTPException(400, "At least one laboratory test is required")
    created = []
    for name in data.tests:
        name = name.strip()
        if not name: continue
        item = LabOrder(hospital_id=user.hospital_id, encounter_id=v.encounter_id, test_name=name, status="ORDERED")
        db.add(item); db.flush(); record(db, user, "CREATE", "lab_order", item.id); journey_after_lab_order(db, item, user); created.append(item.id)
    db.commit(); db.refresh(v)
    return {"created": created, "visit": _visit_payload(db, v, True)}


@router.post("/visits/{visit_id}/prescriptions")
def prescribe(visit_id: int, data: PrescriptionBatchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "prescriptions", "CREATE")
    v = _visit(db, visit_id, user.hospital_id)
    source = data.source.upper()
    if source not in {"HOSPITAL", "EXTERNAL"}:
        raise HTTPException(400, "source must be HOSPITAL or EXTERNAL")
    created = []
    for med in data.medicines:
        if med.inventory_item_id:
            _owned(db, InventoryItem, med.inventory_item_id, user.hospital_id, "Inventory item")
        item = Prescription(hospital_id=user.hospital_id, encounter_id=v.encounter_id, **med.model_dump())
        if source == "EXTERNAL":
            item.status = "EXTERNAL"
        db.add(item); db.flush(); record(db, user, "CREATE", "prescription", item.id); created.append(item.id)
    v.pharmacy_choice = source
    _event(db, v, "PRESCRIPTION_PLAN", user.id, details={"source": source, "prescription_ids": created})
    if source == "HOSPITAL":
        v.stage = "PHARMACY_PENDING"
    db.commit(); db.refresh(v)
    return {"created": created, "visit": _visit_payload(db, v, True)}


@router.post("/visits/{visit_id}/outcome")
def set_outcome(visit_id: int, data: OutcomeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "consultation", "EDIT")
    v = _visit(db, visit_id, user.hospital_id)
    outcome = data.outcome.upper()
    if outcome == "ADMIT":
        ensure_access(user, db, "wards", "CREATE")
        v.admission_requested = True; v.stage = "ADMISSION_PENDING"
        _event(db, v, "ADMISSION_REQUESTED", user.id, data.note)
    elif outcome == "OUTPATIENT":
        from .care_pathways import active_clinical_blockers
        blockers = active_clinical_blockers(db, v.id)
        if blockers:
            raise HTTPException(409, {"code": "ACTIVE_CARE_BLOCKERS", "items": blockers})
        choice = (data.pharmacy_choice or v.pharmacy_choice or "NONE").upper()
        if choice not in {"HOSPITAL", "EXTERNAL", "NONE"}:
            raise HTTPException(400, "pharmacy_choice must be HOSPITAL, EXTERNAL or NONE")
        v.pharmacy_choice = choice
        v.doctor_close_requested = True; v.doctor_close_requested_at = datetime.utcnow(); v.closed_by = user.id
        _event(db, v, "OUTPATIENT_DISCHARGE_DECISION", user.id, data.note, {"pharmacy_choice": choice})
        if choice in {"EXTERNAL", "NONE"}:
            _finalize_close(db, v, user.id, "Outpatient consultation completed")
        else:
            inv = db.get(Invoice, v.pharmacy_invoice_id) if v.pharmacy_invoice_id else None
            paid_ok = (not _settings(db, v.hospital_id).require_pharmacy_payment) or _visit_payment_sponsored(db, v) or (inv and inv.status == "PAID")
            if paid_ok and _all_hospital_prescriptions_dispensed(db, v):
                _finalize_close(db, v, user.id, "Outpatient treatment completed")
            else:
                v.stage = "CLOSING_PENDING_PHARMACY"
    elif outcome == "REFER":
        from .care_pathways import active_clinical_blockers
        blockers = active_clinical_blockers(db, v.id)
        if blockers:
            raise HTTPException(409, {"code": "ACTIVE_CARE_BLOCKERS", "items": blockers})
        v.doctor_close_requested = True; v.doctor_close_requested_at = datetime.utcnow(); v.closed_by = user.id
        _event(db, v, "REFERRED", user.id, data.note)
        _finalize_close(db, v, user.id, "Referred to another service/facility")
    else:
        raise HTTPException(400, "outcome must be OUTPATIENT, ADMIT or REFER")
    db.commit(); db.refresh(v)
    return _visit_payload(db, v, True)


# ---------------------------------------------------------------------------
# Laboratory, pharmacy, inpatient queues
# ---------------------------------------------------------------------------
@router.get("/lab-queue")
def lab_queue(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "laboratory", "VIEW")
    visits = {v.encounter_id: v for v in db.query(VisitFile).filter_by(hospital_id=user.hospital_id, status="OPEN").all()}
    rows = db.query(LabOrder).filter_by(hospital_id=user.hospital_id).filter(LabOrder.status.in_(["ORDERED", "RESULTED", "VERIFIED"])).order_by(LabOrder.id).all()
    out = []
    for x in rows:
        v = visits.get(x.encounter_id)
        if not v: continue
        p = db.get(Patient, v.patient_id)
        out.append({
            "id": x.id, "visit_id": v.id, "file_no": v.file_no, "patient_no": p.patient_no,
            "patient_name": f"{p.first_name} {p.last_name}", "test_name": x.test_name,
            "status": x.status, "result": x.result, "verified": x.verified,
        })
    return out


@router.get("/pharmacy-queue")
def pharmacy_queue(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "pharmacy", "VIEW")
    rows = db.query(VisitFile).filter(
        VisitFile.hospital_id == user.hospital_id, VisitFile.status == "OPEN",
        VisitFile.pharmacy_choice == "HOSPITAL",
        VisitFile.stage.in_(["PHARMACY_PENDING", "PHARMACY_READY", "CLOSING_PENDING_PHARMACY"]),
    ).order_by(VisitFile.opened_at).all()
    return [_visit_payload(db, x, True) for x in rows]


@router.post("/visits/{visit_id}/pharmacy/prepare")
def prepare_pharmacy_bill(visit_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "pharmacy", "VIEW")
    ensure_access(user, db, "billing", "CREATE") if _can(user, db, "billing", "CREATE") else None
    v = _visit(db, visit_id, user.hospital_id)
    if v.pharmacy_choice != "HOSPITAL":
        raise HTTPException(400, "Patient did not choose the hospital pharmacy")
    if v.pharmacy_invoice_id:
        inv = db.get(Invoice, v.pharmacy_invoice_id)
        return {"invoice": _invoice_state(db, inv.id), "visit": _visit_payload(db, v, True)}
    prescriptions = db.query(Prescription).filter_by(hospital_id=user.hospital_id, encounter_id=v.encounter_id).filter(Prescription.status != "EXTERNAL").all()
    if not prescriptions:
        raise HTTPException(400, "No hospital-pharmacy prescriptions found")
    amount = 0.0
    missing = []
    for rx in prescriptions:
        stock = db.get(InventoryItem, rx.inventory_item_id) if rx.inventory_item_id else db.query(InventoryItem).filter(InventoryItem.hospital_id == user.hospital_id, func.lower(InventoryItem.name) == rx.medicine.lower()).first()
        if not stock:
            missing.append(rx.medicine); continue
        amount += float(stock.unit_price or 0) * int(rx.quantity)
    if missing:
        raise HTTPException(400, "Set inventory/price for: " + ", ".join(missing))
    inv = Invoice(hospital_id=user.hospital_id, patient_id=v.patient_id, amount=round(amount, 2), paid_amount=0, description=f"Pharmacy medicines - {v.file_no}", status="UNPAID")
    db.add(inv); db.flush(); v.pharmacy_invoice_id = inv.id
    if _visit_payment_sponsored(db, v) and v.stage in {"PHARMACY_PENDING", "CLOSING_PENDING_PHARMACY"}:
        v.stage = "PHARMACY_READY"
    _event(db, v, "PHARMACY_INVOICE_CREATED", user.id, details={"invoice_id": inv.id, "amount": inv.amount, "sponsored": _visit_payment_sponsored(db, v)})
    record(db, user, "CREATE", "invoice", inv.id, {"visit_id": v.id, "kind": "PHARMACY"})
    db.commit(); db.refresh(v)
    return {"invoice": _invoice_state(db, inv.id), "visit": _visit_payload(db, v, True)}


@router.get("/admission-queue")
def admission_queue(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "wards", "VIEW")
    pending = db.query(VisitFile).filter_by(hospital_id=user.hospital_id, status="OPEN", stage="ADMISSION_PENDING").order_by(VisitFile.opened_at).all()
    admitted = db.query(VisitFile).filter_by(hospital_id=user.hospital_id, status="OPEN", stage="ADMITTED").order_by(VisitFile.opened_at).all()
    discharge = db.query(VisitFile).filter_by(hospital_id=user.hospital_id, status="OPEN", stage="DISCHARGE_PENDING").order_by(VisitFile.opened_at).all()
    return {"pending": [_visit_payload(db, x) for x in pending], "admitted": [_visit_payload(db, x) for x in admitted], "discharge_pending": [_visit_payload(db, x) for x in discharge]}


@router.post("/visits/{visit_id}/admit")
def admit_visit(visit_id: int, data: AdmissionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "wards", "CREATE"); ensure_access(user, db, "beds", "EDIT")
    v = _visit(db, visit_id, user.hospital_id)
    if v.stage != "ADMISSION_PENDING":
        raise HTTPException(400, f"No pending admission decision for this visit (stage: {v.stage})")
    ward = _owned(db, Ward, data.ward_id, user.hospital_id, "Ward")
    bed = _owned(db, Bed, data.bed_id, user.hospital_id, "Bed")
    if bed.ward_id != ward.id: raise HTTPException(400, "Bed does not belong to selected ward")
    if bed.status != "AVAILABLE": raise HTTPException(400, "Bed is not available")
    adm = Admission(hospital_id=user.hospital_id, patient_id=v.patient_id, encounter_id=v.encounter_id, ward_id=ward.id, bed_id=bed.id)
    db.add(adm); db.flush(); bed.status = "OCCUPIED"; record(db, user, "ADMIT", "admission", adm.id, {"visit_id": v.id, "bed_id": bed.id}); journey_after_admission(db, adm, user)
    db.commit(); db.refresh(v)
    return _visit_payload(db, v, True)


@router.post("/visits/{visit_id}/progress")
def add_progress(visit_id: int, data: ProgressIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_any(user, db, [("wards", "EDIT"), ("nursing", "CREATE"), ("consultation", "EDIT")])
    v = _visit(db, visit_id, user.hospital_id)
    if v.stage not in {"ADMITTED", "DISCHARGE_PENDING"} or not v.admission_id:
        raise HTTPException(400, "Patient is not currently admitted")
    note = InpatientProgress(hospital_id=user.hospital_id, visit_id=v.id, admission_id=v.admission_id, note_type=data.note_type.upper(), note=data.note, created_by=user.id)
    db.add(note); db.flush(); _event(db, v, "INPATIENT_PROGRESS", user.id, data.note, {"note_type": note.note_type, "note_id": note.id})
    record(db, user, "CREATE", "inpatient_progress", note.id, {"visit_id": v.id})
    db.commit(); db.refresh(note)
    return {"id": note.id, "note_type": note.note_type, "note": note.note, "created_at": note.created_at}


@router.post("/visits/{visit_id}/discharge-decision")
def discharge_decision(visit_id: int, data: DischargeDecisionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "consultation", "EDIT")
    v = _visit(db, visit_id, user.hospital_id)
    if v.stage != "ADMITTED" or not v.admission_id:
        raise HTTPException(400, "Patient is not currently admitted")
    from .care_pathways import active_clinical_blockers
    blockers = active_clinical_blockers(db, v.id)
    if blockers:
        raise HTTPException(409, {"code": "ACTIVE_CARE_BLOCKERS", "items": blockers})
    v.discharge_decided_at = datetime.utcnow(); v.discharge_summary = data.summary; v.stage = "DISCHARGE_PENDING"; v.closed_by = user.id
    # Keep discharge planning native to the doctor workflow.  A hospital may require
    # a discharge plan before the ward can physically discharge the patient; creating
    # the initial plan from the doctor's discharge decision preserves the old one-click
    # workflow while still leaving the plan editable by the clinical team.
    from .care_pathways import DischargePlan
    plan = db.query(DischargePlan).filter_by(hospital_id=v.hospital_id, visit_id=v.id).first()
    encounter = db.get(Encounter, v.encounter_id) if v.encounter_id else None
    final_diagnosis = (encounter.diagnosis if encounter else None) or "Clinical discharge"
    if not plan:
        plan = DischargePlan(
            hospital_id=v.hospital_id, visit_id=v.id, final_diagnosis=final_diagnosis,
            instructions=data.summary or "Follow clinical discharge advice.",
            created_by=user.id,
        )
        db.add(plan)
    else:
        plan.final_diagnosis = plan.final_diagnosis or final_diagnosis
        plan.instructions = plan.instructions or data.summary or "Follow clinical discharge advice."
    _event(db, v, "DISCHARGE_DECISION", user.id, data.summary)
    db.commit(); db.refresh(v)
    return _visit_payload(db, v, True)


@router.post("/visits/{visit_id}/discharge")
def complete_discharge(visit_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "wards", "EDIT"); ensure_access(user, db, "beds", "EDIT")
    v = _visit(db, visit_id, user.hospital_id)
    if v.stage != "DISCHARGE_PENDING" or not v.admission_id:
        raise HTTPException(400, "A doctor discharge decision is required first")
    from .care_pathways import discharge_blockers
    blockers = discharge_blockers(db, v)
    if blockers:
        raise HTTPException(409, {"code": "DISCHARGE_BLOCKED", "items": blockers})
    adm = _owned(db, Admission, v.admission_id, user.hospital_id, "Admission")
    if adm.status != "ADMITTED": raise HTTPException(400, "Admission is not active")
    bed = _owned(db, Bed, adm.bed_id, user.hospital_id, "Bed")
    bed.status = "AVAILABLE"; adm.status = "DISCHARGED"; adm.discharged_at = datetime.utcnow()
    record(db, user, "DISCHARGE", "admission", adm.id, {"visit_id": v.id}); journey_after_discharge(db, adm, user)
    db.commit(); db.refresh(v)
    return _visit_payload(db, v, True)


# ---------------------------------------------------------------------------
# Attendance, SMS outbox, admin
# ---------------------------------------------------------------------------
@router.get("/admin/doctor-attendance")
def doctor_attendance(date_from: date | None = None, date_to: date | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "VIEW")
    query = db.query(DoctorShift).filter_by(hospital_id=user.hospital_id)
    if date_from: query = query.filter(DoctorShift.started_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to: query = query.filter(DoctorShift.started_at < datetime.combine(date_to, datetime.max.time()))
    rows = query.order_by(DoctorShift.started_at.desc()).limit(1000).all()
    data = [_shift_payload(db, x) for x in rows]
    totals: dict[int, dict[str, Any]] = {}
    for x in data:
        t = totals.setdefault(x["doctor_id"], {"doctor_id": x["doctor_id"], "doctor_name": x["doctor_name"], "minutes": 0, "sessions": 0})
        t["minutes"] += x["minutes"]; t["sessions"] += 1
    for t in totals.values(): t["hours"] = round(t["minutes"] / 60, 2)
    return {"sessions": data, "totals": list(totals.values())}


@router.get("/sms-outbox")
def sms_outbox(user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_any(user, db, [("configuration", "VIEW"), ("reception", "VIEW")])
    rows = db.query(SmsOutbox).filter_by(hospital_id=user.hospital_id).order_by(SmsOutbox.id.desc()).limit(300).all()
    return [{
        "id": x.id, "visit_id": x.visit_id, "phone": x.phone, "message": x.message,
        "event_type": x.event_type, "status": x.status, "provider_response": x.provider_response,
        "created_at": x.created_at, "sent_at": x.sent_at,
    } for x in rows]


@router.post("/sms-outbox/retry")
def retry_sms(data: SmsRetryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "EDIT")
    query = db.query(SmsOutbox).filter_by(hospital_id=user.hospital_id)
    if data.ids: query = query.filter(SmsOutbox.id.in_(data.ids))
    else: query = query.filter(SmsOutbox.status.in_(["QUEUED", "FAILED"]))
    rows = query.limit(200).all()
    for x in rows: _try_send_sms(x)
    db.commit()
    return {"processed": len(rows), "sent": sum(1 for x in rows if x.status == "SENT")}
