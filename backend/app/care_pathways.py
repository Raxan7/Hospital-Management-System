"""Native care-pathway orchestration for One/NEOVAM HMS.

This module intentionally sits between the existing departmental modules instead of
replacing them.  A VisitFile remains the clinical episode backbone while each
service (radiology, theatre, wards, nursing, pharmacy, laboratory, etc.) keeps its
own normal queue and permissions.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, or_
from sqlalchemy.orm import Mapped, mapped_column, Session

from .database import Base, get_db
from .models import (
    Admission, Bed, Encounter, HospitalModule, Invoice, Patient, Prescription,
    Role, ServiceRecord, User, Ward,
)
from .modules import MODULE_BY_KEY, MODULE_DEPENDENCIES
from .security import current_user, ensure_access
from .audit import record
from .patient_journey import (
    VisitFile, _event, _finalize_close, _owned, _queue_sms, _settings,
    _visit, _visit_payload,
)

router = APIRouter(prefix="/api/care", tags=["Care Pathways"])

CARE_SERVICE_MODULES = {
    "radiology", "maternity", "theatre", "icu", "emergency", "ambulance",
    "dental", "physiotherapy", "ophthalmology", "ent", "pediatrics",
    "mental_health", "dialysis", "oncology", "cardiology",
    "specialized_clinics", "blood_bank", "nutrition", "mortuary",
}

ACTIVE_ORDER_STATUSES = {"ORDERED", "ACCEPTED", "IN_PROGRESS", "AWAITING_PAYMENT", "SCHEDULED"}
ACTIVE_SURGERY_STATUSES = {"REQUESTED", "SCHEDULED", "PREOP_READY", "IN_THEATRE", "RECOVERY"}


# ---------------------------------------------------------------------------
# Additive data model
# ---------------------------------------------------------------------------
class CarePolicy(Base):
    __tablename__ = "care_policies"
    __table_args__ = (UniqueConstraint("hospital_id", name="uq_care_policy_hospital"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    emergency_bypass_payment: Mapped[bool] = mapped_column(Boolean, default=True)
    require_service_payment: Mapped[bool] = mapped_column(Boolean, default=False)
    require_surgical_consent: Mapped[bool] = mapped_column(Boolean, default=True)
    require_preop_checklist: Mapped[bool] = mapped_column(Boolean, default=True)
    require_inpatient_financial_clearance: Mapped[bool] = mapped_column(Boolean, default=False)
    require_discharge_plan: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_followup_sms: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VisitAdministrative(Base):
    __tablename__ = "visit_administrative"
    __table_args__ = (UniqueConstraint("visit_id", name="uq_visit_admin_visit"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), index=True)
    payer_type: Mapped[str] = mapped_column(String(30), default="CASH")
    payer_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    member_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    authorization_status: Mapped[str] = mapped_column(String(30), default="NOT_REQUIRED")
    department: Mapped[str] = mapped_column(String(100), default="OPD")
    referral_source: Mapped[str | None] = mapped_column(String(180), nullable=True)
    emergency_payment_bypass: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CareTask(Base):
    __tablename__ = "care_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), index=True)
    module_key: Mapped[str] = mapped_column(String(80), index=True)
    task_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(220))
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL")
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    room: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ServiceOrder(Base):
    __tablename__ = "service_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), index=True)
    module_key: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(220))
    clinical_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL")
    status: Mapped[str] = mapped_column(String(30), default="ORDERED", index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_record_id: Mapped[int | None] = mapped_column(ForeignKey("service_records.id"), nullable=True)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ConsentRecord(Base):
    __tablename__ = "consent_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), index=True)
    consent_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    signed_by_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    relationship: Mapped[str | None] = mapped_column(String(100), nullable=True)
    witnessed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SurgicalCase(Base):
    __tablename__ = "surgical_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), index=True)
    service_order_id: Mapped[int] = mapped_column(ForeignKey("service_orders.id", ondelete="CASCADE"), index=True)
    procedure_name: Mapped[str] = mapped_column(String(220))
    urgency: Mapped[str] = mapped_column(String(30), default="ELECTIVE")
    status: Mapped[str] = mapped_column(String(30), default="REQUESTED", index=True)
    theatre_room: Mapped[str | None] = mapped_column(String(80), nullable=True)
    surgeon_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    anaesthetist_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    preop_checklist: Mapped[dict] = mapped_column(JSON, default=dict)
    anaesthesia_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    operative_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovery_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MedicationAdministration(Base):
    __tablename__ = "medication_administrations"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), index=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id", ondelete="CASCADE"), index=True)
    prescription_id: Mapped[int | None] = mapped_column(ForeignKey("prescriptions.id"), nullable=True)
    medicine: Mapped[str] = mapped_column(String(180))
    dose: Mapped[str] = mapped_column(String(100))
    route: Mapped[str] = mapped_column(String(60), default="ORAL")
    status: Mapped[str] = mapped_column(String(30), default="GIVEN")
    administered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    administered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class BedMovement(Base):
    __tablename__ = "bed_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), index=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id", ondelete="CASCADE"), index=True)
    from_ward_id: Mapped[int | None] = mapped_column(ForeignKey("wards.id"), nullable=True)
    from_bed_id: Mapped[int | None] = mapped_column(ForeignKey("beds.id"), nullable=True)
    to_ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    to_bed_id: Mapped[int] = mapped_column(ForeignKey("beds.id"))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    moved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    moved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReferralTransfer(Base):
    __tablename__ = "referral_transfers"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="INTERNAL")
    target_module: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_facility: Mapped[str | None] = mapped_column(String(220), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="REQUESTED")
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    accepted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DischargePlan(Base):
    __tablename__ = "discharge_plans"
    __table_args__ = (UniqueConstraint("visit_id", name="uq_discharge_plan_visit"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit_files.id", ondelete="CASCADE"), index=True)
    disposition: Mapped[str] = mapped_column(String(40), default="HOME")
    final_diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition_at_discharge: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    follow_up_department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    financial_clearance: Mapped[str] = mapped_column(String(30), default="NOT_REQUIRED")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------
class CarePolicyIn(BaseModel):
    emergency_bypass_payment: bool | None = None
    require_service_payment: bool | None = None
    require_surgical_consent: bool | None = None
    require_preop_checklist: bool | None = None
    require_inpatient_financial_clearance: bool | None = None
    require_discharge_plan: bool | None = None
    auto_followup_sms: bool | None = None


class AdminContextIn(BaseModel):
    payer_type: str = "CASH"
    payer_name: str | None = None
    member_no: str | None = None
    authorization_status: str = "NOT_REQUIRED"
    department: str = "OPD"
    referral_source: str | None = None


class ServiceOrderIn(BaseModel):
    module_key: str
    title: str
    clinical_question: str | None = None
    priority: str = "NORMAL"
    amount: float = Field(default=0, ge=0)


class ServiceResultIn(BaseModel):
    result_summary: str
    status: str = "COMPLETED"


class SurgeryRequestIn(BaseModel):
    procedure_name: str
    urgency: str = "ELECTIVE"
    clinical_question: str | None = None
    amount: float = Field(default=0, ge=0)


class SurgeryScheduleIn(BaseModel):
    theatre_room: str
    surgeon_id: int | None = None
    anaesthetist_id: int | None = None
    scheduled_at: datetime


class ConsentIn(BaseModel):
    consent_type: str
    status: str = "SIGNED"
    signed_by_name: str | None = None
    relationship: str | None = None
    notes: str | None = None


class PreopIn(BaseModel):
    checklist: dict = Field(default_factory=dict)
    anaesthesia_note: str | None = None


class SurgeryCompleteIn(BaseModel):
    operative_note: str


class RecoveryIn(BaseModel):
    recovery_note: str
    destination: str = "WARD"  # WARD / ICU / DOCTOR_REVIEW


class MedicationAdminIn(BaseModel):
    prescription_id: int | None = None
    medicine: str
    dose: str
    route: str = "ORAL"
    status: str = "GIVEN"
    notes: str | None = None


class BedTransferIn(BaseModel):
    ward_id: int
    bed_id: int
    reason: str | None = None


class ReferralIn(BaseModel):
    kind: str = "INTERNAL"
    target_module: str | None = None
    target_facility: str | None = None
    reason: str


class ReferralStatusIn(BaseModel):
    status: str


class DischargePlanIn(BaseModel):
    disposition: str = "HOME"
    final_diagnosis: str | None = None
    condition_at_discharge: str | None = None
    instructions: str | None = None
    follow_up_at: datetime | None = None
    follow_up_department: str | None = None


class ClearanceIn(BaseModel):
    status: str = "CLEARED"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _policy(db: Session, hid: int) -> CarePolicy:
    row = db.query(CarePolicy).filter_by(hospital_id=hid).first()
    if not row:
        row = CarePolicy(hospital_id=hid)
        db.add(row); db.flush()
    return row


def _module_enabled(db: Session, hid: int, module_key: str) -> bool:
    module = MODULE_BY_KEY.get(module_key)
    if not module:
        return False
    row = db.query(HospitalModule).filter_by(hospital_id=hid, module_key=module_key).first()
    enabled = module.core if row is None else bool(row.enabled)
    if not enabled:
        return False
    for dependency in MODULE_DEPENDENCIES.get(module_key, set()):
        dep = MODULE_BY_KEY[dependency]
        drow = db.query(HospitalModule).filter_by(hospital_id=hid, module_key=dependency).first()
        if not (dep.core if drow is None else bool(drow.enabled)):
            return False
    return True


def _require_enabled(db: Session, hid: int, module_key: str):
    if module_key not in MODULE_BY_KEY:
        raise HTTPException(404, "Unknown hospital module")
    if not _module_enabled(db, hid, module_key):
        raise HTTPException(403, {"code": "MODULE_DISABLED", "module": module_key})


def _can(user: User, db: Session, module: str, perm: str) -> bool:
    try:
        ensure_access(user, db, module, perm); return True
    except HTTPException:
        return False


def _require_any(user: User, db: Session, pairs: list[tuple[str, str]]):
    for m, p in pairs:
        if _can(user, db, m, p): return
    raise HTTPException(403, {"code": "PERMISSION_DENIED", "requirements": pairs})


def _admin_context(db: Session, v: VisitFile) -> VisitAdministrative:
    row = db.query(VisitAdministrative).filter_by(visit_id=v.id).first()
    if not row:
        row = VisitAdministrative(hospital_id=v.hospital_id, visit_id=v.id)
        db.add(row); db.flush()
    return row


def visit_payment_sponsored(db: Session, v: VisitFile) -> bool:
    a=_admin_context(db,v)
    return a.payer_type == "EXEMPT" or (a.payer_type in {"INSURANCE","CORPORATE"} and a.authorization_status in {"APPROVED","AUTHORIZED"})


def _patient(db: Session, v: VisitFile) -> Patient:
    p = db.get(Patient, v.patient_id)
    if not p: raise HTTPException(404, "Patient not found")
    return p


def _invoice_state(db: Session, invoice_id: int | None):
    if not invoice_id: return None
    inv = db.get(Invoice, invoice_id)
    if not inv: return None
    return {"id": inv.id, "amount": inv.amount, "paid_amount": inv.paid_amount, "status": inv.status,
            "balance": max(0, round(inv.amount - inv.paid_amount, 2)), "description": inv.description}


def _order_payload(db: Session, o: ServiceOrder):
    v = db.get(VisitFile, o.visit_id); p = db.get(Patient, v.patient_id) if v else None
    assignee = db.get(User, o.assigned_user_id) if o.assigned_user_id else None
    return {
        "id": o.id, "visit_id": o.visit_id, "file_no": v.file_no if v else None,
        "patient_id": p.id if p else None, "patient_no": p.patient_no if p else None,
        "patient_name": f"{p.first_name} {p.last_name}" if p else None,
        "module_key": o.module_key, "title": o.title, "clinical_question": o.clinical_question,
        "priority": o.priority, "status": o.status, "amount": o.amount,
        "invoice": _invoice_state(db, o.invoice_id), "assigned_user_id": o.assigned_user_id,
        "assigned_user_name": assignee.full_name if assignee else None,
        "result_summary": o.result_summary, "service_record_id": o.service_record_id,
        "ordered_at": o.ordered_at, "started_at": o.started_at, "completed_at": o.completed_at,
    }


def active_clinical_blockers(db: Session, visit_id: int) -> list[str]:
    blockers=[]
    orders=db.query(ServiceOrder).filter(ServiceOrder.visit_id==visit_id, ServiceOrder.status.in_(list(ACTIVE_ORDER_STATUSES))).all()
    blockers.extend([f"{x.module_key}:{x.title}" for x in orders])
    cases=db.query(SurgicalCase).filter(SurgicalCase.visit_id==visit_id, SurgicalCase.status.in_(list(ACTIVE_SURGERY_STATUSES))).all()
    blockers.extend([f"theatre:{x.procedure_name}" for x in cases])
    refs=db.query(ReferralTransfer).filter(ReferralTransfer.visit_id==visit_id, ReferralTransfer.kind=='INTERNAL', ReferralTransfer.status.in_(['REQUESTED','ACCEPTED','IN_PROGRESS'])).all()
    blockers.extend([f"referral:{x.target_module or 'internal'}" for x in refs])
    return blockers


def discharge_blockers(db: Session, v: VisitFile) -> list[str]:
    blockers = active_clinical_blockers(db, v.id)
    p = _policy(db, v.hospital_id)
    if p.require_discharge_plan:
        plan = db.query(DischargePlan).filter_by(visit_id=v.id).first()
        if not plan or not (plan.final_diagnosis or plan.instructions): blockers.append("discharge-plan")
    if p.require_inpatient_financial_clearance:
        plan = db.query(DischargePlan).filter_by(visit_id=v.id).first()
        if not plan or plan.financial_clearance != "CLEARED": blockers.append("financial-clearance")
    return blockers


def emergency_bypass_enabled(db: Session, hid: int) -> bool:
    return bool(_policy(db, hid).emergency_bypass_payment)


def _create_invoice(db: Session, v: VisitFile, description: str, amount: float) -> Invoice | None:
    if amount <= 0: return None
    inv = Invoice(hospital_id=v.hospital_id, patient_id=v.patient_id, amount=amount, paid_amount=0,
                  description=description, status="UNPAID")
    db.add(inv); db.flush()
    try:
        from .notifications import invoice_created
        invoice_created(db, inv, v.id)
    except Exception:
        pass
    return inv


def _visit_invoices(db: Session, v: VisitFile) -> list[Invoice]:
    ids=[]
    for iid in [v.consultation_invoice_id, v.pharmacy_invoice_id]:
        if iid and iid not in ids: ids.append(iid)
    for o in db.query(ServiceOrder).filter_by(visit_id=v.id).all():
        if o.invoice_id and o.invoice_id not in ids: ids.append(o.invoice_id)
    return [inv for iid in ids if (inv:=db.get(Invoice,iid)) is not None]

def _financial_summary(db: Session, v: VisitFile) -> dict:
    rows=_visit_invoices(db,v)
    total=round(sum(float(x.amount or 0) for x in rows),2)
    paid=round(sum(float(x.paid_amount or 0) for x in rows),2)
    return {"total":total,"paid":paid,"balance":round(max(0,total-paid),2),
            "invoices":[_invoice_state(db,x.id) for x in rows]}

def _visit_summary(db: Session, v: VisitFile):
    base = _visit_payload(db, v, True)
    admin = _admin_context(db, v)
    orders = db.query(ServiceOrder).filter_by(visit_id=v.id).order_by(ServiceOrder.id).all()
    surgeries = db.query(SurgicalCase).filter_by(visit_id=v.id).order_by(SurgicalCase.id).all()
    refs = db.query(ReferralTransfer).filter_by(visit_id=v.id).order_by(ReferralTransfer.id).all()
    consents = db.query(ConsentRecord).filter_by(visit_id=v.id).order_by(ConsentRecord.id).all()
    meds = db.query(MedicationAdministration).filter_by(visit_id=v.id).order_by(MedicationAdministration.id.desc()).limit(200).all()
    moves = db.query(BedMovement).filter_by(visit_id=v.id).order_by(BedMovement.id.desc()).limit(100).all()
    plan = db.query(DischargePlan).filter_by(visit_id=v.id).first()
    base.update({
        "administrative": {"payer_type": admin.payer_type, "payer_name": admin.payer_name, "member_no": admin.member_no,
                           "authorization_status": admin.authorization_status, "department": admin.department,
                           "referral_source": admin.referral_source, "emergency_payment_bypass": admin.emergency_payment_bypass},
        "service_orders": [_order_payload(db, x) for x in orders],
        "surgeries": [{"id":x.id,"service_order_id":x.service_order_id,"procedure_name":x.procedure_name,"urgency":x.urgency,
                       "status":x.status,"theatre_room":x.theatre_room,"surgeon_id":x.surgeon_id,"anaesthetist_id":x.anaesthetist_id,
                       "scheduled_at":x.scheduled_at,"consent_status":x.consent_status,"preop_checklist":x.preop_checklist,
                       "anaesthesia_note":x.anaesthesia_note,"operative_note":x.operative_note,"recovery_note":x.recovery_note,
                       "started_at":x.started_at,"completed_at":x.completed_at} for x in surgeries],
        "referrals": [{"id":x.id,"kind":x.kind,"target_module":x.target_module,"target_facility":x.target_facility,
                       "reason":x.reason,"status":x.status,"created_at":x.created_at,"completed_at":x.completed_at} for x in refs],
        "consents": [{"id":x.id,"consent_type":x.consent_type,"status":x.status,"signed_by_name":x.signed_by_name,
                      "relationship":x.relationship,"notes":x.notes,"signed_at":x.signed_at} for x in consents],
        "medication_administrations": [{"id":x.id,"prescription_id":x.prescription_id,"medicine":x.medicine,"dose":x.dose,
                                         "route":x.route,"status":x.status,"administered_by":x.administered_by,
                                         "administered_at":x.administered_at,"notes":x.notes} for x in meds],
        "bed_movements": [{"id":x.id,"from_ward_id":x.from_ward_id,"from_bed_id":x.from_bed_id,"to_ward_id":x.to_ward_id,
                           "to_bed_id":x.to_bed_id,"reason":x.reason,"moved_at":x.moved_at} for x in moves],
        "discharge_plan": None if not plan else {"id":plan.id,"disposition":plan.disposition,"final_diagnosis":plan.final_diagnosis,
                                                  "condition_at_discharge":plan.condition_at_discharge,"instructions":plan.instructions,
                                                  "follow_up_at":plan.follow_up_at,"follow_up_department":plan.follow_up_department,
                                                  "financial_clearance":plan.financial_clearance},
        "close_blockers": active_clinical_blockers(db, v.id),
        "financial": _financial_summary(db, v),
    })
    return base


# ---------------------------------------------------------------------------
# Policy + visit administrative context
# ---------------------------------------------------------------------------
@router.get("/policy")
def get_policy(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "VIEW")
    p=_policy(db,user.hospital_id)
    return {k:getattr(p,k) for k in ["emergency_bypass_payment","require_service_payment","require_surgical_consent","require_preop_checklist","require_inpatient_financial_clearance","require_discharge_plan","auto_followup_sms"]}


@router.patch("/policy")
def update_policy(data: CarePolicyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "EDIT")
    p=_policy(db,user.hospital_id)
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(p,k,v)
    record(db,user,"EDIT","care_policy",p.id,data.model_dump(exclude_unset=True));db.commit();db.refresh(p)
    return {k:getattr(p,k) for k in ["emergency_bypass_payment","require_service_payment","require_surgical_consent","require_preop_checklist","require_inpatient_financial_clearance","require_discharge_plan","auto_followup_sms"]}


@router.get("/visits/{visit_id}")
def care_visit(visit_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    _require_any(user,db,[("reception","VIEW"),("medical_records","VIEW"),("consultation","VIEW"),("laboratory","VIEW"),("pharmacy","VIEW"),("wards","VIEW")]+[(m,"VIEW") for m in CARE_SERVICE_MODULES])
    return _visit_summary(db,_visit(db,visit_id,user.hospital_id))


@router.patch("/visits/{visit_id}/administrative")
def update_admin_context(visit_id:int,data:AdminContextIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"reception","EDIT")
    v=_visit(db,visit_id,user.hospital_id);a=_admin_context(db,v)
    payer=data.payer_type.upper()
    if payer not in {"CASH","INSURANCE","CORPORATE","EXEMPT"}: raise HTTPException(400,"payer_type must be CASH, INSURANCE, CORPORATE or EXEMPT")
    for k,vv in data.model_dump().items(): setattr(a,k,vv.upper() if k in {"payer_type","authorization_status"} and isinstance(vv,str) else vv)
    sponsored = a.payer_type == "EXEMPT" or (a.payer_type in {"INSURANCE","CORPORATE"} and a.authorization_status in {"APPROVED","AUTHORIZED"})
    if sponsored and v.stage == "AWAITING_PAYMENT":
        from .patient_journey import _next_stage_after_payment, _assign_visit_to_doctor
        v.stage=_next_stage_after_payment(db,v)
        if v.stage=="WAITING_DOCTOR" and _settings(db,v.hospital_id).auto_assign_doctor:
            _assign_visit_to_doctor(db,v)
        _event(db,v,"SPONSORED_CARE_AUTHORIZED",user.id,details={"payer_type":a.payer_type,"authorization_status":a.authorization_status})
    _event(db,v,"ADMINISTRATIVE_CONTEXT_UPDATED",user.id,details={"payer_type":a.payer_type,"department":a.department})
    db.commit();return _visit_summary(db,v)


# ---------------------------------------------------------------------------
# Cross-department service orders
# ---------------------------------------------------------------------------
@router.post("/visits/{visit_id}/service-orders")
def create_service_order(visit_id:int,data:ServiceOrderIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    module=data.module_key.strip().lower()
    _require_any(user,db,[("consultation","EDIT"),(module,"CREATE")])
    if module not in CARE_SERVICE_MODULES: raise HTTPException(400,"This service is not a patient care-order module")
    _require_enabled(db,user.hospital_id,module)
    v=_visit(db,visit_id,user.hospital_id)
    inv=_create_invoice(db,v,f"{MODULE_BY_KEY[module].name}: {data.title}",data.amount)
    status="ORDERED"
    policy=_policy(db,v.hospital_id)
    if inv and policy.require_service_payment and not (v.priority=="EMERGENCY" and policy.emergency_bypass_payment) and not visit_payment_sponsored(db,v): status="AWAITING_PAYMENT"
    o=ServiceOrder(hospital_id=v.hospital_id,visit_id=v.id,module_key=module,title=data.title,clinical_question=data.clinical_question,
                   priority=data.priority.upper(),status=status,amount=data.amount,invoice_id=inv.id if inv else None,requested_by=user.id)
    db.add(o);db.flush()
    db.add(CareTask(hospital_id=v.hospital_id,visit_id=v.id,module_key=module,task_type="SERVICE_ORDER",title=data.title,
                    priority=data.priority.upper(),status="PENDING",details={"service_order_id":o.id},created_by=user.id))
    _event(db,v,"SERVICE_ORDERED",user.id,data.title,{"module":module,"service_order_id":o.id,"invoice_id":o.invoice_id})
    record(db,user,"CREATE","service_order",o.id,{"visit_id":v.id,"module":module})
    db.commit();db.refresh(o);return _order_payload(db,o)


@router.get("/service-orders")
def list_service_orders(module_key:str|None=None,status:str|None=None,user:User=Depends(current_user),db:Session=Depends(get_db)):
    q=db.query(ServiceOrder).filter_by(hospital_id=user.hospital_id)
    if module_key:
        module_key=module_key.lower();_require_enabled(db,user.hospital_id,module_key);ensure_access(user,db,module_key,"VIEW");q=q.filter_by(module_key=module_key)
    else:
        # Only return orders from services the user can view.
        allowed=[m for m in CARE_SERVICE_MODULES if _can(user,db,m,"VIEW")]
        if not allowed: raise HTTPException(403,"No patient-service queue is available for your role")
        q=q.filter(ServiceOrder.module_key.in_(allowed))
    if status: q=q.filter(ServiceOrder.status==status.upper())
    return [_order_payload(db,x) for x in q.order_by(ServiceOrder.ordered_at,ServiceOrder.id).limit(500).all()]


@router.post("/service-orders/{order_id}/start")
def start_service_order(order_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    o=_owned(db,ServiceOrder,order_id,user.hospital_id,"Service order");ensure_access(user,db,o.module_key,"EDIT")
    if o.status in {"COMPLETED","CANCELLED"}: raise HTTPException(400,"Service order is already finished")
    if o.invoice_id and _policy(db,o.hospital_id).require_service_payment:
        v=_visit(db,o.visit_id,o.hospital_id);inv=db.get(Invoice,o.invoice_id)
        if not (v.priority=="EMERGENCY" and _policy(db,o.hospital_id).emergency_bypass_payment) and not visit_payment_sponsored(db,v) and inv and inv.status!="PAID":
            raise HTTPException(400,"Service payment is required before starting this order")
    o.status="IN_PROGRESS";o.started_at=o.started_at or datetime.utcnow();o.assigned_user_id=user.id
    v=_visit(db,o.visit_id,o.hospital_id);_event(db,v,"SERVICE_STARTED",user.id,o.title,{"module":o.module_key,"service_order_id":o.id})
    record(db,user,"EDIT","service_order",o.id,{"status":"IN_PROGRESS"});db.commit();db.refresh(o);return _order_payload(db,o)


@router.post("/service-orders/{order_id}/complete")
def complete_service_order(order_id:int,data:ServiceResultIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    o=_owned(db,ServiceOrder,order_id,user.hospital_id,"Service order");ensure_access(user,db,o.module_key,"EDIT")
    if o.status=="CANCELLED": raise HTTPException(400,"Cancelled service order cannot be completed")
    if not data.result_summary.strip(): raise HTTPException(400,"Result/clinical completion summary is required")
    v=_visit(db,o.visit_id,o.hospital_id)
    verified = _can(user, db, o.module_key, "VERIFY")
    rec=ServiceRecord(hospital_id=o.hospital_id,module_key=o.module_key,patient_id=v.patient_id,title=o.title,status="COMPLETED",
                      details={"visit_id":v.id,"file_no":v.file_no,"service_order_id":o.id,"clinical_question":o.clinical_question,"result":data.result_summary},
                      approved=False,verified=verified,verified_at=datetime.utcnow() if verified else None)
    db.add(rec);db.flush();o.service_record_id=rec.id;o.result_summary=data.result_summary;o.status="COMPLETED";o.completed_at=datetime.utcnow();o.assigned_user_id=o.assigned_user_id or user.id
    # If this order originated from an internal referral, finishing the departmental
    # service also finishes the referral instead of forcing staff to update two screens.
    ref=db.query(ReferralTransfer).filter_by(hospital_id=o.hospital_id,visit_id=o.visit_id,kind="INTERNAL",target_module=o.module_key).filter(ReferralTransfer.status.in_(["REQUESTED","ACCEPTED","IN_PROGRESS"])).order_by(ReferralTransfer.id).first()
    if ref:
        ref.status="COMPLETED";ref.completed_at=datetime.utcnow();ref.accepted_by=ref.accepted_by or user.id
    _event(db,v,"SERVICE_COMPLETED",user.id,data.result_summary,{"module":o.module_key,"service_order_id":o.id,"service_record_id":rec.id,"verified":verified})
    # Return patient to the doctor review queue when not admitted.
    if v.status=="OPEN" and not v.admission_id and v.stage not in {"ADMISSION_PENDING","ADMITTED","DISCHARGE_PENDING"}:
        v.stage="LAB_RESULTS_READY"
    record(db,user,"COMPLETE","service_order",o.id,{"module":o.module_key,"service_record_id":rec.id});db.commit();db.refresh(o);return _order_payload(db,o)


@router.post("/service-orders/{order_id}/cancel")
def cancel_service_order(order_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    o=_owned(db,ServiceOrder,order_id,user.hospital_id,"Service order")
    _require_any(user,db,[("consultation","EDIT"),(o.module_key,"EDIT")])
    if o.status=="COMPLETED": raise HTTPException(400,"Completed service order cannot be cancelled")
    o.status="CANCELLED";v=_visit(db,o.visit_id,o.hospital_id);_event(db,v,"SERVICE_CANCELLED",user.id,o.title,{"module":o.module_key,"service_order_id":o.id})
    db.commit();return _order_payload(db,o)


# ---------------------------------------------------------------------------
# Theatre / surgical pathway
# ---------------------------------------------------------------------------
@router.post("/visits/{visit_id}/surgery")
def request_surgery(visit_id:int,data:SurgeryRequestIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"consultation","EDIT");_require_enabled(db,user.hospital_id,"theatre")
    v=_visit(db,visit_id,user.hospital_id)
    inv=_create_invoice(db,v,f"Theatre / Surgery: {data.procedure_name}",data.amount)
    status="ORDERED"
    pol=_policy(db,v.hospital_id)
    if inv and pol.require_service_payment and not (v.priority=="EMERGENCY" and pol.emergency_bypass_payment) and not visit_payment_sponsored(db,v): status="AWAITING_PAYMENT"
    o=ServiceOrder(hospital_id=v.hospital_id,visit_id=v.id,module_key="theatre",title=data.procedure_name,clinical_question=data.clinical_question,
                   priority=data.urgency.upper(),status=status,amount=data.amount,invoice_id=inv.id if inv else None,requested_by=user.id)
    db.add(o);db.flush()
    db.add(CareTask(hospital_id=v.hospital_id,visit_id=v.id,module_key="theatre",task_type="SURGERY",title=data.procedure_name,
                    priority=data.urgency.upper(),status="PENDING",details={"service_order_id":o.id},created_by=user.id))
    case=SurgicalCase(hospital_id=v.hospital_id,visit_id=v.id,service_order_id=o.id,procedure_name=data.procedure_name,
                      urgency=data.urgency.upper(),status="REQUESTED",created_by=user.id)
    db.add(case);db.flush();_event(db,v,"SURGERY_REQUESTED",user.id,data.procedure_name,{"case_id":case.id,"service_order_id":o.id})
    record(db,user,"CREATE","surgical_case",case.id,{"visit_id":v.id});db.commit();db.refresh(case);return _surgery_payload(db,case)


def _surgery_payload(db:Session,c:SurgicalCase):
    v=db.get(VisitFile,c.visit_id);p=db.get(Patient,v.patient_id) if v else None
    return {"id":c.id,"visit_id":c.visit_id,"file_no":v.file_no if v else None,"patient_no":p.patient_no if p else None,
            "patient_name":f"{p.first_name} {p.last_name}" if p else None,"service_order_id":c.service_order_id,"procedure_name":c.procedure_name,
            "urgency":c.urgency,"status":c.status,"theatre_room":c.theatre_room,"surgeon_id":c.surgeon_id,"anaesthetist_id":c.anaesthetist_id,
            "scheduled_at":c.scheduled_at,"consent_status":c.consent_status,"preop_checklist":c.preop_checklist,
            "anaesthesia_note":c.anaesthesia_note,"operative_note":c.operative_note,"recovery_note":c.recovery_note,
            "created_at":c.created_at,"started_at":c.started_at,"completed_at":c.completed_at}


@router.get("/surgery/queue")
def surgery_queue(user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"theatre","VIEW")
    rows=db.query(SurgicalCase).filter_by(hospital_id=user.hospital_id).filter(SurgicalCase.status!="CANCELLED").order_by(SurgicalCase.id.desc()).limit(300).all()
    return [_surgery_payload(db,x) for x in rows]


@router.patch("/surgery/{case_id}/schedule")
def schedule_surgery(case_id:int,data:SurgeryScheduleIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"theatre","EDIT");c=_owned(db,SurgicalCase,case_id,user.hospital_id,"Surgical case")
    if c.status not in {"REQUESTED","SCHEDULED"}: raise HTTPException(400,"Surgical case cannot be scheduled in its current state")
    for uid,label in [(data.surgeon_id,"Surgeon"),(data.anaesthetist_id,"Anaesthetist")]:
        if uid:
            u=_owned(db,User,uid,user.hospital_id,label)
            if not u.active: raise HTTPException(400,f"{label} account is inactive")
    c.theatre_room=data.theatre_room;c.surgeon_id=data.surgeon_id;c.anaesthetist_id=data.anaesthetist_id;c.scheduled_at=data.scheduled_at;c.status="SCHEDULED"
    o=db.get(ServiceOrder,c.service_order_id);o.status="SCHEDULED"
    v=_visit(db,c.visit_id,c.hospital_id);_event(db,v,"SURGERY_SCHEDULED",user.id,c.procedure_name,{"case_id":c.id,"room":c.theatre_room,"scheduled_at":data.scheduled_at.isoformat()})
    db.commit();return _surgery_payload(db,c)


@router.post("/surgery/{case_id}/consent")
def surgery_consent(case_id:int,data:ConsentIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"theatre","EDIT");c=_owned(db,SurgicalCase,case_id,user.hospital_id,"Surgical case");v=_visit(db,c.visit_id,c.hospital_id)
    row=ConsentRecord(hospital_id=c.hospital_id,visit_id=c.visit_id,consent_type=data.consent_type,status=data.status.upper(),signed_by_name=data.signed_by_name,
                      relationship=data.relationship,witnessed_by=user.id,notes=data.notes,signed_at=datetime.utcnow() if data.status.upper()=="SIGNED" else None)
    db.add(row);db.flush();c.consent_status=row.status;_event(db,v,"CONSENT_RECORDED",user.id,data.consent_type,{"consent_id":row.id,"status":row.status});db.commit();return {"id":row.id,"status":row.status}


@router.post("/surgery/{case_id}/preop")
def surgery_preop(case_id:int,data:PreopIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"theatre","EDIT");c=_owned(db,SurgicalCase,case_id,user.hospital_id,"Surgical case")
    if _policy(db,c.hospital_id).require_surgical_consent and c.consent_status!="SIGNED": raise HTTPException(400,"Signed surgical consent is required")
    c.preop_checklist=data.checklist;c.anaesthesia_note=data.anaesthesia_note;c.status="PREOP_READY"
    v=_visit(db,c.visit_id,c.hospital_id);_event(db,v,"PREOP_COMPLETED",user.id,c.procedure_name,{"case_id":c.id});db.commit();return _surgery_payload(db,c)


@router.post("/surgery/{case_id}/start")
def surgery_start(case_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"theatre","EDIT");c=_owned(db,SurgicalCase,case_id,user.hospital_id,"Surgical case");pol=_policy(db,c.hospital_id)
    if pol.require_surgical_consent and c.consent_status!="SIGNED": raise HTTPException(400,"Signed surgical consent is required")
    if pol.require_preop_checklist and not c.preop_checklist: raise HTTPException(400,"Pre-operative checklist is required")
    if c.status not in {"PREOP_READY","SCHEDULED"}: raise HTTPException(400,"Surgical case is not ready to start")
    c.status="IN_THEATRE";c.started_at=datetime.utcnow();o=db.get(ServiceOrder,c.service_order_id);o.status="IN_PROGRESS";o.started_at=o.started_at or datetime.utcnow();o.assigned_user_id=user.id
    v=_visit(db,c.visit_id,c.hospital_id);_event(db,v,"SURGERY_STARTED",user.id,c.procedure_name,{"case_id":c.id,"room":c.theatre_room});db.commit();return _surgery_payload(db,c)


@router.post("/surgery/{case_id}/complete")
def surgery_complete(case_id:int,data:SurgeryCompleteIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"theatre","EDIT");c=_owned(db,SurgicalCase,case_id,user.hospital_id,"Surgical case")
    if c.status!="IN_THEATRE": raise HTTPException(400,"Surgical case is not currently in theatre")
    c.operative_note=data.operative_note;c.status="RECOVERY";c.completed_at=datetime.utcnow();v=_visit(db,c.visit_id,c.hospital_id)
    _event(db,v,"SURGERY_COMPLETED",user.id,c.procedure_name,{"case_id":c.id});db.commit();return _surgery_payload(db,c)


@router.post("/surgery/{case_id}/recovery")
def surgery_recovery(case_id:int,data:RecoveryIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"theatre","EDIT");c=_owned(db,SurgicalCase,case_id,user.hospital_id,"Surgical case")
    if c.status!="RECOVERY": raise HTTPException(400,"Surgical case is not in recovery")
    dest=data.destination.upper()
    if dest not in {"WARD","ICU","DOCTOR_REVIEW"}: raise HTTPException(400,"destination must be WARD, ICU or DOCTOR_REVIEW")
    if dest=="ICU": _require_enabled(db,c.hospital_id,"icu")
    c.recovery_note=data.recovery_note;c.status="COMPLETED";o=db.get(ServiceOrder,c.service_order_id);o.status="COMPLETED";o.completed_at=datetime.utcnow();o.result_summary=c.operative_note
    v=_visit(db,c.visit_id,c.hospital_id)
    if not o.service_record_id:
        verified=_can(user,db,"theatre","VERIFY")
        rec=ServiceRecord(hospital_id=c.hospital_id,module_key="theatre",patient_id=v.patient_id,title=c.procedure_name,status="COMPLETED",
                          details={"visit_id":v.id,"file_no":v.file_no,"service_order_id":o.id,"operative_note":c.operative_note,"recovery_note":c.recovery_note,"destination":dest},
                          approved=False,verified=verified,verified_at=datetime.utcnow() if verified else None)
        db.add(rec);db.flush();o.service_record_id=rec.id
    _event(db,v,"RECOVERY_COMPLETED",user.id,data.recovery_note,{"case_id":c.id,"destination":dest})
    if dest=="DOCTOR_REVIEW" and not v.admission_id:
        v.stage="LAB_RESULTS_READY"
    elif dest in {"WARD","ICU"} and not v.admission_id:
        _require_enabled(db,c.hospital_id,"wards");_require_enabled(db,c.hospital_id,"beds")
        v.admission_requested=True;v.stage="ADMISSION_PENDING"
        a=_admin_context(db,v);a.department="ICU" if dest=="ICU" else "INPATIENT"
        _event(db,v,"POSTOP_ADMISSION_REQUESTED",user.id,data.recovery_note,{"destination":dest})
    elif dest=="ICU" and v.admission_id:
        a=_admin_context(db,v);a.department="ICU"
    db.commit();return _surgery_payload(db,c)


# ---------------------------------------------------------------------------
# Inpatient nursing, medicines and bed movement
# ---------------------------------------------------------------------------
@router.post("/visits/{visit_id}/medication-administrations")
def administer_medication(visit_id:int,data:MedicationAdminIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    _require_any(user,db,[("nursing","CREATE"),("wards","EDIT")])
    v=_visit(db,visit_id,user.hospital_id)
    if not v.admission_id: raise HTTPException(400,"Patient is not admitted")
    adm=_owned(db,Admission,v.admission_id,user.hospital_id,"Admission")
    if adm.status!="ADMITTED": raise HTTPException(400,"Admission is not active")
    if data.prescription_id:
        rx=_owned(db,Prescription,data.prescription_id,user.hospital_id,"Prescription")
        if rx.encounter_id!=v.encounter_id: raise HTTPException(400,"Prescription belongs to a different visit")
    row=MedicationAdministration(hospital_id=v.hospital_id,visit_id=v.id,admission_id=adm.id,prescription_id=data.prescription_id,
                                 medicine=data.medicine,dose=data.dose,route=data.route.upper(),status=data.status.upper(),administered_by=user.id,notes=data.notes)
    db.add(row);db.flush();_event(db,v,"MEDICATION_ADMINISTERED",user.id,f"{row.medicine} {row.dose}",{"mar_id":row.id,"status":row.status})
    record(db,user,"CREATE","medication_administration",row.id,{"visit_id":v.id});db.commit();db.refresh(row);return {"id":row.id,"medicine":row.medicine,"dose":row.dose,"route":row.route,"status":row.status,"administered_at":row.administered_at}


@router.post("/visits/{visit_id}/bed-transfer")
def transfer_bed(visit_id:int,data:BedTransferIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"wards","EDIT");ensure_access(user,db,"beds","EDIT")
    v=_visit(db,visit_id,user.hospital_id)
    if not v.admission_id: raise HTTPException(400,"Patient is not admitted")
    adm=_owned(db,Admission,v.admission_id,user.hospital_id,"Admission");old_bed=_owned(db,Bed,adm.bed_id,user.hospital_id,"Current bed")
    new_ward=_owned(db,Ward,data.ward_id,user.hospital_id,"Ward");new_bed=_owned(db,Bed,data.bed_id,user.hospital_id,"Bed")
    if new_bed.ward_id!=new_ward.id: raise HTTPException(400,"Bed does not belong to selected ward")
    if new_bed.status!="AVAILABLE": raise HTTPException(400,"Destination bed is not available")
    move=BedMovement(hospital_id=v.hospital_id,visit_id=v.id,admission_id=adm.id,from_ward_id=adm.ward_id,from_bed_id=adm.bed_id,
                     to_ward_id=new_ward.id,to_bed_id=new_bed.id,reason=data.reason,moved_by=user.id)
    old_bed.status="AVAILABLE";new_bed.status="OCCUPIED";adm.ward_id=new_ward.id;adm.bed_id=new_bed.id;db.add(move);db.flush()
    _event(db,v,"BED_TRANSFER",user.id,data.reason,{"from_bed_id":move.from_bed_id,"to_bed_id":move.to_bed_id})
    record(db,user,"TRANSFER","admission",adm.id,{"from_bed_id":move.from_bed_id,"to_bed_id":move.to_bed_id});db.commit();return {"movement_id":move.id,"admission_id":adm.id,"ward_id":adm.ward_id,"bed_id":adm.bed_id}


# ---------------------------------------------------------------------------
# Referrals, consent and discharge planning
# ---------------------------------------------------------------------------
@router.post("/visits/{visit_id}/referrals")
def create_referral(visit_id:int,data:ReferralIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"consultation","EDIT");v=_visit(db,visit_id,user.hospital_id);kind=data.kind.upper()
    if kind not in {"INTERNAL","EXTERNAL","TRANSFER"}: raise HTTPException(400,"kind must be INTERNAL, EXTERNAL or TRANSFER")
    if kind=="INTERNAL":
        if not data.target_module: raise HTTPException(400,"target_module is required for an internal referral")
        module=data.target_module.lower();
        if module not in CARE_SERVICE_MODULES: raise HTTPException(400,"Unsupported internal referral service")
        _require_enabled(db,v.hospital_id,module)
    r=ReferralTransfer(hospital_id=v.hospital_id,visit_id=v.id,kind=kind,target_module=data.target_module.lower() if data.target_module else None,
                       target_facility=data.target_facility,reason=data.reason,status="REQUESTED",requested_by=user.id)
    db.add(r);db.flush()
    if kind=="INTERNAL":
        o=ServiceOrder(hospital_id=v.hospital_id,visit_id=v.id,module_key=r.target_module,title=f"Internal referral: {MODULE_BY_KEY[r.target_module].name}",
                       clinical_question=data.reason,priority=v.priority,status="ORDERED",requested_by=user.id)
        db.add(o);db.flush()
    _event(db,v,"REFERRAL_CREATED",user.id,data.reason,{"referral_id":r.id,"kind":kind,"target_module":r.target_module,"target_facility":r.target_facility})
    record(db,user,"CREATE","referral",r.id,{"visit_id":v.id,"kind":kind});db.commit();return {"id":r.id,"kind":r.kind,"status":r.status}


@router.patch("/referrals/{referral_id}")
def referral_status(referral_id:int,data:ReferralStatusIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    r=_owned(db,ReferralTransfer,referral_id,user.hospital_id,"Referral")
    if r.target_module: ensure_access(user,db,r.target_module,"EDIT")
    else: ensure_access(user,db,"consultation","EDIT")
    status=data.status.upper()
    if status not in {"REQUESTED","ACCEPTED","IN_PROGRESS","COMPLETED","DECLINED","CANCELLED"}: raise HTTPException(400,"Invalid referral status")
    r.status=status;r.accepted_by=user.id if status in {"ACCEPTED","IN_PROGRESS","COMPLETED"} else r.accepted_by;r.completed_at=datetime.utcnow() if status in {"COMPLETED","DECLINED","CANCELLED"} else None
    v=_visit(db,r.visit_id,r.hospital_id);_event(db,v,"REFERRAL_STATUS",user.id,status,{"referral_id":r.id});db.commit();return {"id":r.id,"status":r.status}


@router.post("/visits/{visit_id}/consents")
def create_consent(visit_id:int,data:ConsentIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    _require_any(user,db,[("consultation","EDIT"),("nursing","CREATE"),("theatre","EDIT")]);v=_visit(db,visit_id,user.hospital_id)
    row=ConsentRecord(hospital_id=v.hospital_id,visit_id=v.id,consent_type=data.consent_type,status=data.status.upper(),signed_by_name=data.signed_by_name,
                      relationship=data.relationship,witnessed_by=user.id,notes=data.notes,signed_at=datetime.utcnow() if data.status.upper()=="SIGNED" else None)
    db.add(row);db.flush();_event(db,v,"CONSENT_RECORDED",user.id,data.consent_type,{"consent_id":row.id,"status":row.status});db.commit();return {"id":row.id,"status":row.status}


@router.put("/visits/{visit_id}/discharge-plan")
def save_discharge_plan(visit_id:int,data:DischargePlanIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    _require_any(user,db,[("consultation","EDIT"),("wards","EDIT")]);v=_visit(db,visit_id,user.hospital_id)
    row=db.query(DischargePlan).filter_by(visit_id=v.id).first()
    if not row:
        row=DischargePlan(hospital_id=v.hospital_id,visit_id=v.id,created_by=user.id);db.add(row)
    for k,val in data.model_dump().items(): setattr(row,k,val)
    _event(db,v,"DISCHARGE_PLAN_UPDATED",user.id,data.instructions,{"disposition":data.disposition,"follow_up_at":data.follow_up_at.isoformat() if data.follow_up_at else None})
    db.flush();record(db,user,"EDIT","discharge_plan",row.id,{"visit_id":v.id});db.commit();db.refresh(row)
    p=_patient(db,v)
    if row.follow_up_at and _policy(db,v.hospital_id).auto_followup_sms and p.phone:
        from .notifications import schedule_followup
        schedule_followup(db, visit=v, follow_up_at=row.follow_up_at, department=row.follow_up_department, created_by=user.id)
        db.commit()
    return {"id":row.id,"disposition":row.disposition,"financial_clearance":row.financial_clearance,"follow_up_at":row.follow_up_at}


@router.post("/visits/{visit_id}/financial-clearance")
def financial_clearance(visit_id:int,data:ClearanceIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"billing","EDIT");v=_visit(db,visit_id,user.hospital_id);row=db.query(DischargePlan).filter_by(visit_id=v.id).first()
    if not row:
        row=DischargePlan(hospital_id=v.hospital_id,visit_id=v.id,created_by=user.id);db.add(row);db.flush()
    status=data.status.upper()
    if status not in {"NOT_REQUIRED","PENDING","CLEARED","HOLD"}: raise HTTPException(400,"Invalid clearance status")
    admin=_admin_context(db,v);summary=_financial_summary(db,v)
    sponsored = admin.payer_type == "EXEMPT" or (admin.payer_type in {"INSURANCE","CORPORATE"} and admin.authorization_status in {"APPROVED","AUTHORIZED"})
    if status=="CLEARED" and summary["balance"]>0 and not sponsored:
        raise HTTPException(409,{"code":"OUTSTANDING_BALANCE","balance":summary["balance"]})
    row.financial_clearance=status;_event(db,v,"FINANCIAL_CLEARANCE",user.id,status,{"discharge_plan_id":row.id,"balance":summary["balance"],"payer_type":admin.payer_type});db.commit();return {"visit_id":v.id,"status":row.financial_clearance,"financial":summary}


@router.post("/visits/{visit_id}/terminal-outcome")
def terminal_outcome(visit_id:int,data:DischargePlanIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    ensure_access(user,db,"consultation","EDIT");v=_visit(db,visit_id,user.hospital_id);disp=data.disposition.upper()
    if disp not in {"TRANSFERRED","DECEASED","LEFT_AGAINST_ADVICE"}: raise HTTPException(400,"Unsupported terminal disposition")
    if active_clinical_blockers(db,v.id) and disp!="DECEASED": raise HTTPException(409,{"code":"ACTIVE_CARE_BLOCKERS","items":active_clinical_blockers(db,v.id)})
    row=db.query(DischargePlan).filter_by(visit_id=v.id).first() or DischargePlan(hospital_id=v.hospital_id,visit_id=v.id,created_by=user.id)
    if row.id is None: db.add(row)
    row.disposition=disp;row.final_diagnosis=data.final_diagnosis;row.condition_at_discharge=data.condition_at_discharge;row.instructions=data.instructions
    if v.admission_id:
        adm=_owned(db,Admission,v.admission_id,v.hospital_id,"Admission")
        if adm.status=="ADMITTED":
            bed=_owned(db,Bed,adm.bed_id,v.hospital_id,"Bed");bed.status="AVAILABLE";adm.status="DISCHARGED";adm.discharged_at=datetime.utcnow()
    if disp=="DECEASED" and _module_enabled(db,v.hospital_id,"mortuary"):
        o=ServiceOrder(hospital_id=v.hospital_id,visit_id=v.id,module_key="mortuary",title="Mortuary transfer",clinical_question="Post-death transfer",priority="URGENT",status="ORDERED",requested_by=user.id)
        db.add(o);db.flush()
    _event(db,v,"TERMINAL_OUTCOME",user.id,data.instructions,{"disposition":disp});_finalize_close(db,v,user.id,disp.replace('_',' ').title());db.commit();return _visit_summary(db,v)


# ---------------------------------------------------------------------------
# Department-native queue summaries
# ---------------------------------------------------------------------------
@router.get("/native/{workspace}")
def native_workspace(workspace:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    w=workspace.lower();hid=user.hospital_id
    if w=="reception":
        ensure_access(user,db,"reception","VIEW");rows=db.query(VisitFile).filter_by(hospital_id=hid,status="OPEN").order_by(VisitFile.opened_at).all()
        return {"visits":[_visit_payload(db,x) for x in rows],"doctors":[]}
    if w=="doctor":
        ensure_access(user,db,"consultation","VIEW");rows=db.query(VisitFile).filter_by(hospital_id=hid,status="OPEN").filter(or_(VisitFile.current_doctor_id==user.id,VisitFile.current_doctor_id.is_(None))).order_by(VisitFile.opened_at).all()
        return {"visits":[_visit_payload(db,x) for x in rows if x.stage in {"WAITING_DOCTOR","WITH_DOCTOR","LAB_RESULTS_READY"}],"service_results":[_order_payload(db,o) for o in db.query(ServiceOrder).filter_by(hospital_id=hid,status="COMPLETED").order_by(ServiceOrder.completed_at.desc()).limit(30)]}
    if w=="inpatient":
        ensure_access(user,db,"wards","VIEW");rows=db.query(VisitFile).filter_by(hospital_id=hid,status="OPEN").filter(VisitFile.stage.in_(["ADMISSION_PENDING","ADMITTED","DISCHARGE_PENDING"])).order_by(VisitFile.opened_at).all()
        return {"visits":[_visit_payload(db,x,True) for x in rows]}
    raise HTTPException(404,"Unknown native workspace")
