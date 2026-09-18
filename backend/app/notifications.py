"""Modular event-driven SMS notification service for NEOVAM HMS.

Clinical/administrative modules emit events into this service.  Provider-specific
SMS transport remains isolated in ``sms_gateway.py`` and the Oracle gateway.
"""
from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, Session

from .database import Base, get_db, SessionLocal
from .models import Hospital, Patient, User, Appointment, Invoice, Payment, Prescription
from .security import current_user, ensure_access
from .audit import record
from .patient_journey import SmsOutbox, VisitFile, _try_send_sms

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class NotificationSetting(Base):
    __tablename__ = "notification_settings"
    __table_args__ = (UniqueConstraint("hospital_id", name="uq_notification_settings_hospital"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    appointment_confirmations: Mapped[bool] = mapped_column(Boolean, default=True)
    appointment_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    lab_results: Mapped[bool] = mapped_column(Boolean, default=True)
    prescription_medication: Mapped[bool] = mapped_column(Boolean, default=True)
    followup_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    health_campaigns: Mapped[bool] = mapped_column(Boolean, default=False)
    hospital_promotions: Mapped[bool] = mapped_column(Boolean, default=False)
    satisfaction_surveys: Mapped[bool] = mapped_column(Boolean, default=True)
    billing_payments: Mapped[bool] = mapped_column(Boolean, default=True)
    emergency_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    staff_communication: Mapped[bool] = mapped_column(Boolean, default=True)
    queue_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    otp_sms: Mapped[bool] = mapped_column(Boolean, default=True)
    appointment_reminder_hours: Mapped[int] = mapped_column(Integer, default=24)
    followup_reminder_hours: Mapped[int] = mapped_column(Integer, default=24)
    medication_reminder_days: Mapped[int] = mapped_column(Integer, default=3)
    satisfaction_delay_hours: Mapped[int] = mapped_column(Integer, default=24)
    queue_notify_threshold: Mapped[int] = mapped_column(Integer, default=3)
    timezone_name: Mapped[str] = mapped_column(String(80), default="Africa/Dar_es_Salaam")
    survey_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationJob(Base):
    __tablename__ = "notification_jobs"
    __table_args__ = (UniqueConstraint("hospital_id", "dedupe_key", name="uq_notification_job_dedupe"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    visit_id: Mapped[int | None] = mapped_column(ForeignKey("visit_files.id", ondelete="SET NULL"), nullable=True, index=True)
    phone: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(180))
    send_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NotificationCampaign(Base):
    __tablename__ = "notification_campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    campaign_type: Mapped[str] = mapped_column(String(40), index=True)
    audience: Mapped[str] = mapped_column(String(30), default="PATIENTS")
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED")
    recipient_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    phone: Mapped[str] = mapped_column(String(50), index=True)
    purpose: Mapped[str] = mapped_column(String(80), default="VERIFICATION")
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


EVENT_FLAG = {
    "APPOINTMENT_CONFIRMATION": "appointment_confirmations",
    "APPOINTMENT_REMINDER": "appointment_reminders",
    "APPOINTMENT_CANCELLED": "appointment_confirmations",
    "LAB_RESULTS_READY": "lab_results",
    "PRESCRIPTION_READY": "prescription_medication",
    "MEDICATION_REMINDER": "prescription_medication",
    "REFILL_REMINDER": "prescription_medication",
    "FOLLOW_UP": "followup_reminders",
    "FOLLOW_UP_CONFIRMATION": "followup_reminders",
    "FOLLOW_UP_REMINDER": "followup_reminders",
    "HEALTH_CAMPAIGN": "health_campaigns",
    "HOSPITAL_PROMOTION": "hospital_promotions",
    "SATISFACTION_SURVEY": "satisfaction_surveys",
    "BILLING_NOTIFICATION": "billing_payments",
    "PAYMENT_CONFIRMATION": "billing_payments",
    "EMERGENCY_NOTIFICATION": "emergency_notifications",
    "STAFF_COMMUNICATION": "staff_communication",
    "QUEUE_NOTIFICATION": "queue_notifications",
    "OTP": "otp_sms",
}


def _settings(db: Session, hospital_id: int) -> NotificationSetting:
    row = db.query(NotificationSetting).filter_by(hospital_id=hospital_id).first()
    if row:
        return row
    row = NotificationSetting(hospital_id=hospital_id)
    db.add(row)
    db.flush()
    return row


def _journey_sms_enabled(db: Session, hospital_id: int) -> bool:
    try:
        from .patient_journey import JourneySetting
        row = db.query(JourneySetting).filter_by(hospital_id=hospital_id).first()
        return bool(row.sms_enabled) if row else True
    except Exception:
        return True


def event_enabled(db: Session, hospital_id: int, event_type: str) -> bool:
    s = _settings(db, hospital_id)
    if not s.enabled or not _journey_sms_enabled(db, hospital_id):
        return False
    flag = EVENT_FLAG.get(event_type)
    return bool(getattr(s, flag, True)) if flag else True


def _hospital_name(db: Session, hospital_id: int) -> str:
    h = db.get(Hospital, hospital_id)
    return (h.name if h else "Hospital").strip() or "Hospital"


def _patient_service_sms_ok(patient: Patient | None) -> bool:
    """Operational SMS is opt-in by default but can be disabled per patient."""
    return bool(patient and patient.phone and getattr(patient, "sms_operational_opt_in", True))


def _local_dt(db: Session, hospital_id: int, value: datetime) -> datetime:
    s = _settings(db, hospital_id)
    try:
        tz = ZoneInfo(s.timezone_name or "Africa/Dar_es_Salaam")
    except Exception:
        tz = ZoneInfo("Africa/Dar_es_Salaam")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tz)


def enqueue_sms(
    db: Session, *, hospital_id: int, phone: str | None, message: str,
    event_type: str, visit_id: int | None = None, dedupe_key: str | None = None,
    force: bool = False,
) -> SmsOutbox | None:
    phone = (phone or "").strip()
    if not phone or not message.strip():
        return None
    if not force and not event_enabled(db, hospital_id, event_type):
        return None
    if dedupe_key:
        existing = db.query(SmsOutbox).filter_by(hospital_id=hospital_id, dedupe_key=dedupe_key).first()
        if existing:
            return existing
    row = SmsOutbox(
        hospital_id=hospital_id, visit_id=visit_id, phone=phone,
        message=message.strip(), event_type=event_type, status="QUEUED",
        dedupe_key=dedupe_key,
    )
    db.add(row)
    db.flush()
    _try_send_sms(row)
    return row


def schedule_sms(
    db: Session, *, hospital_id: int, phone: str | None, message: str,
    event_type: str, send_at: datetime, dedupe_key: str,
    patient_id: int | None = None, user_id: int | None = None,
    visit_id: int | None = None, created_by: int | None = None,
) -> NotificationJob | None:
    phone = (phone or "").strip()
    if not phone or not message.strip() or not event_enabled(db, hospital_id, event_type):
        return None
    existing = db.query(NotificationJob).filter_by(hospital_id=hospital_id, dedupe_key=dedupe_key).first()
    if existing:
        return existing
    if send_at.tzinfo is not None:
        send_at = send_at.astimezone(timezone.utc).replace(tzinfo=None)
    row = NotificationJob(
        hospital_id=hospital_id, patient_id=patient_id, user_id=user_id, visit_id=visit_id,
        phone=phone, message=message.strip(), event_type=event_type,
        dedupe_key=dedupe_key, send_at=send_at, created_by=created_by,
    )
    db.add(row)
    db.flush()
    return row


def process_due_notifications(db: Session, hospital_id: int | None = None, limit: int = 250) -> dict:
    q = db.query(NotificationJob).filter(NotificationJob.status == "SCHEDULED", NotificationJob.send_at <= datetime.utcnow())
    if hospital_id is not None:
        q = q.filter(NotificationJob.hospital_id == hospital_id)
    jobs = q.order_by(NotificationJob.send_at, NotificationJob.id).limit(limit).all()
    sent = queued = failed = skipped = 0
    for job in jobs:
        job.attempts += 1
        try:
            row = enqueue_sms(
                db, hospital_id=job.hospital_id, phone=job.phone, message=job.message,
                event_type=job.event_type, visit_id=job.visit_id, dedupe_key=job.dedupe_key,
            )
            if not row:
                job.status = "SKIPPED"; skipped += 1
            elif row.status == "SENT":
                job.status = "SENT"; sent += 1
            elif row.status == "FAILED":
                job.status = "FAILED"; job.last_error = row.provider_response; failed += 1
            else:
                job.status = "QUEUED"; queued += 1
            job.processed_at = datetime.utcnow()
        except Exception as exc:
            job.status = "FAILED"; job.last_error = str(exc)[:2000]; job.processed_at = datetime.utcnow(); failed += 1
    db.commit()
    return {"processed": len(jobs), "sent": sent, "queued": queued, "failed": failed, "skipped": skipped}


def _worker_once():
    db = SessionLocal()
    try:
        process_due_notifications(db)
    finally:
        db.close()


async def notification_worker(stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(_worker_once)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass


def appointment_created(db: Session, appt: Appointment, created_by: int | None = None):
    p = db.get(Patient, appt.patient_id)
    if not _patient_service_sms_ok(p):
        return
    hospital = _hospital_name(db, appt.hospital_id)
    when = _local_dt(db, appt.hospital_id, appt.scheduled_at)
    clinician = f" with {appt.clinician}" if appt.clinician else ""
    msg = f"{hospital}: Your appointment is confirmed for {when.strftime('%d %b %Y at %H:%M')} in {appt.department}{clinician}."
    enqueue_sms(db, hospital_id=appt.hospital_id, phone=p.phone, message=msg,
                event_type="APPOINTMENT_CONFIRMATION", dedupe_key=f"appointment:{appt.id}:confirmation")
    s = _settings(db, appt.hospital_id)
    send_at = appt.scheduled_at - timedelta(hours=max(1, s.appointment_reminder_hours))
    if send_at <= datetime.utcnow():
        send_at = min(appt.scheduled_at - timedelta(minutes=30), datetime.utcnow() + timedelta(minutes=1))
    if send_at > datetime.utcnow() and send_at < appt.scheduled_at:
        schedule_sms(db, hospital_id=appt.hospital_id, phone=p.phone,
                     message=f"{hospital}: Reminder — your appointment is {when.strftime('%d %b %Y at %H:%M')} in {appt.department}{clinician}.",
                     event_type="APPOINTMENT_REMINDER", send_at=send_at,
                     dedupe_key=f"appointment:{appt.id}:reminder", patient_id=p.id, created_by=created_by)


def appointment_status_changed(db: Session, appt: Appointment):
    # A cancelled/completed/no-show appointment must never fire a stale reminder later.
    if appt.status in {"CANCELLED", "COMPLETED", "NO_SHOW"}:
        job = db.query(NotificationJob).filter_by(hospital_id=appt.hospital_id, dedupe_key=f"appointment:{appt.id}:reminder").first()
        if job and job.status == "SCHEDULED":
            job.status = "CANCELLED"
            job.processed_at = datetime.utcnow()
    if appt.status != "CANCELLED":
        return
    p = db.get(Patient, appt.patient_id)
    if _patient_service_sms_ok(p):
        when = _local_dt(db, appt.hospital_id, appt.scheduled_at)
        enqueue_sms(db, hospital_id=appt.hospital_id, phone=p.phone,
                    message=f"{_hospital_name(db, appt.hospital_id)}: Your appointment for {when.strftime('%d %b %Y at %H:%M')} has been cancelled. Contact the hospital to reschedule.",
                    event_type="APPOINTMENT_CANCELLED", dedupe_key=f"appointment:{appt.id}:cancelled")


def invoice_created(db: Session, invoice: Invoice, visit_id: int | None = None):
    p = db.get(Patient, invoice.patient_id)
    if not _patient_service_sms_ok(p) or invoice.amount <= 0:
        return
    enqueue_sms(db, hospital_id=invoice.hospital_id, phone=p.phone,
                message=f"{_hospital_name(db, invoice.hospital_id)}: Bill INV-{invoice.id:05d} for {invoice.description}: TZS {invoice.amount:,.0f}. Please pay through the hospital cashier/payment channel.",
                event_type="BILLING_NOTIFICATION", visit_id=visit_id,
                dedupe_key=f"invoice:{invoice.id}:created")


def payment_received(db: Session, invoice: Invoice, payment: Payment, visit_id: int | None = None):
    p = db.get(Patient, invoice.patient_id)
    if not _patient_service_sms_ok(p):
        return
    balance = max(0.0, float(invoice.amount or 0) - float(invoice.paid_amount or 0))
    enqueue_sms(db, hospital_id=invoice.hospital_id, phone=p.phone,
                message=f"{_hospital_name(db, invoice.hospital_id)}: Payment received TZS {payment.amount:,.0f} for INV-{invoice.id:05d}. Remaining balance: TZS {balance:,.0f}. Thank you.",
                event_type="PAYMENT_CONFIRMATION", visit_id=visit_id,
                dedupe_key=f"payment:{payment.id}:confirmation")


def medication_plan_completed(db: Session, prescription: Prescription, created_by: int | None = None):
    v = db.query(VisitFile).filter_by(hospital_id=prescription.hospital_id, encounter_id=prescription.encounter_id).first()
    if not v:
        return
    rows = db.query(Prescription).filter_by(hospital_id=v.hospital_id, encounter_id=v.encounter_id).all()
    if any(x.status not in {"DISPENSED", "EXTERNAL"} for x in rows):
        return
    p = db.get(Patient, v.patient_id)
    if not _patient_service_sms_ok(p):
        return
    hospital = _hospital_name(db, v.hospital_id)
    enqueue_sms(db, hospital_id=v.hospital_id, phone=p.phone,
                message=f"{hospital}: Your medication plan is ready. Take medicines exactly as prescribed and keep your prescription/medicine bill for reference.",
                event_type="PRESCRIPTION_READY", visit_id=v.id,
                dedupe_key=f"visit:{v.id}:prescription-ready")
    days = max(0, min(_settings(db, v.hospital_id).medication_reminder_days, 14))
    for day in range(1, days + 1):
        send_at = datetime.utcnow() + timedelta(days=day)
        schedule_sms(db, hospital_id=v.hospital_id, phone=p.phone,
                     message=f"{hospital}: Medication reminder — please take your prescribed medicines according to your clinician's instructions. If you have concerns, contact the hospital.",
                     event_type="MEDICATION_REMINDER", send_at=send_at,
                     dedupe_key=f"visit:{v.id}:medication-reminder:{day}", patient_id=p.id, visit_id=v.id, created_by=created_by)


def schedule_refill_reminder(db: Session, *, hospital_id: int, patient_id: int, visit_id: int | None,
                             send_at: datetime, message: str | None, created_by: int | None):
    p = db.get(Patient, patient_id)
    if not p or p.hospital_id != hospital_id or not _patient_service_sms_ok(p):
        raise HTTPException(404, "Patient/phone not found")
    msg = message or f"{_hospital_name(db, hospital_id)}: Medication refill reminder — please arrange your refill or contact the hospital/pharmacy if you need assistance."
    return schedule_sms(db, hospital_id=hospital_id, phone=p.phone, message=msg,
                        event_type="REFILL_REMINDER", send_at=send_at,
                        dedupe_key=f"refill:{patient_id}:{visit_id or 0}:{int(send_at.timestamp())}",
                        patient_id=patient_id, visit_id=visit_id, created_by=created_by)


def schedule_followup(db: Session, *, visit: VisitFile, follow_up_at: datetime,
                      department: str | None, created_by: int | None = None):
    p = db.get(Patient, visit.patient_id)
    if not _patient_service_sms_ok(p):
        return
    hospital = _hospital_name(db, visit.hospital_id)
    local = _local_dt(db, visit.hospital_id, follow_up_at)
    dept = department or "the hospital"
    enqueue_sms(db, hospital_id=visit.hospital_id, phone=p.phone,
                message=f"{hospital}: Follow-up booked for {local.strftime('%d %b %Y at %H:%M')} at {dept}.",
                event_type="FOLLOW_UP", visit_id=visit.id,
                dedupe_key=f"visit:{visit.id}:followup-confirmation:{int(follow_up_at.timestamp())}")
    lead = max(1, _settings(db, visit.hospital_id).followup_reminder_hours)
    send_at = follow_up_at - timedelta(hours=lead)
    if send_at <= datetime.utcnow():
        send_at = datetime.utcnow() + timedelta(minutes=1)
    if send_at < follow_up_at:
        schedule_sms(db, hospital_id=visit.hospital_id, phone=p.phone,
                     message=f"{hospital}: Reminder — your follow-up is {local.strftime('%d %b %Y at %H:%M')} at {dept}.",
                     event_type="FOLLOW_UP_REMINDER", send_at=send_at,
                     dedupe_key=f"visit:{visit.id}:followup-reminder:{int(follow_up_at.timestamp())}",
                     patient_id=p.id, visit_id=visit.id, created_by=created_by)


def schedule_satisfaction_survey(db: Session, visit: VisitFile):
    p = db.get(Patient, visit.patient_id)
    if not _patient_service_sms_ok(p):
        return
    s = _settings(db, visit.hospital_id)
    hospital = _hospital_name(db, visit.hospital_id)
    suffix = f" Share feedback: {s.survey_url}" if s.survey_url else " We value your feedback about your care."
    schedule_sms(db, hospital_id=visit.hospital_id, phone=p.phone,
                 message=f"{hospital}: Thank you for visiting us.{suffix}",
                 event_type="SATISFACTION_SURVEY",
                 send_at=datetime.utcnow() + timedelta(hours=max(1, s.satisfaction_delay_hours)),
                 dedupe_key=f"visit:{visit.id}:satisfaction", patient_id=p.id, visit_id=visit.id)


def _doctor_queue(db: Session, hospital_id: int, doctor_id: int):
    rows = db.query(VisitFile).filter(
        VisitFile.hospital_id == hospital_id,
        VisitFile.current_doctor_id == doctor_id,
        VisitFile.status == "OPEN",
        VisitFile.stage.in_(["WAITING_DOCTOR", "LAB_RESULTS_READY"]),
    ).order_by(VisitFile.opened_at.asc(), VisitFile.id.asc()).all()
    return rows


def queue_position(db: Session, visit: VisitFile) -> int | None:
    if not visit.current_doctor_id:
        return None
    rows = _doctor_queue(db, visit.hospital_id, visit.current_doctor_id)
    for i, row in enumerate(rows, 1):
        if row.id == visit.id:
            return i
    return None


def notify_lab_results_ready(db: Session, visit: VisitFile):
    p = db.get(Patient, visit.patient_id)
    doctor = db.get(User, visit.current_doctor_id) if visit.current_doctor_id else None
    if not _patient_service_sms_ok(p) or not doctor or not visit.assigned_room:
        return None
    pos = queue_position(db, visit)
    q = f" Your queue position is {pos}." if pos else ""
    return enqueue_sms(db, hospital_id=visit.hospital_id, phone=p.phone,
                       message=f"{_hospital_name(db, visit.hospital_id)}: Your laboratory results are ready. Please proceed to {doctor.full_name}, Room {visit.assigned_room}.{q} Please wait to be called.",
                       event_type="LAB_RESULTS_READY", visit_id=visit.id,
                       dedupe_key=f"visit:{visit.id}:lab-results-ready")


def notify_queue_positions(db: Session, hospital_id: int, doctor_id: int):
    if not event_enabled(db, hospital_id, "QUEUE_NOTIFICATION"):
        return 0
    s = _settings(db, hospital_id)
    threshold = max(1, min(s.queue_notify_threshold, 10))
    rows = _doctor_queue(db, hospital_id, doctor_id)
    doctor = db.get(User, doctor_id)
    count = 0
    for pos, visit in enumerate(rows[:threshold], 1):
        p = db.get(Patient, visit.patient_id)
        if not _patient_service_sms_ok(p):
            continue
        room = visit.assigned_room or "OPD"
        row = enqueue_sms(db, hospital_id=hospital_id, phone=p.phone,
                          message=f"{_hospital_name(db, hospital_id)}: Queue update — you are number {pos} for {doctor.full_name if doctor else 'the doctor'}, Room {room}. Please remain nearby and wait to be called.",
                          event_type="QUEUE_NOTIFICATION", visit_id=visit.id,
                          dedupe_key=f"visit:{visit.id}:queue:{doctor_id}:{pos}")
        if row:
            count += 1
    return count


class SettingsPatch(BaseModel):
    enabled: bool | None = None
    appointment_confirmations: bool | None = None
    appointment_reminders: bool | None = None
    lab_results: bool | None = None
    prescription_medication: bool | None = None
    followup_reminders: bool | None = None
    health_campaigns: bool | None = None
    hospital_promotions: bool | None = None
    satisfaction_surveys: bool | None = None
    billing_payments: bool | None = None
    emergency_notifications: bool | None = None
    staff_communication: bool | None = None
    queue_notifications: bool | None = None
    otp_sms: bool | None = None
    appointment_reminder_hours: int | None = Field(None, ge=1, le=168)
    followup_reminder_hours: int | None = Field(None, ge=1, le=168)
    medication_reminder_days: int | None = Field(None, ge=0, le=14)
    satisfaction_delay_hours: int | None = Field(None, ge=1, le=168)
    queue_notify_threshold: int | None = Field(None, ge=1, le=10)
    timezone_name: str | None = None
    survey_url: str | None = None


class CampaignIn(BaseModel):
    campaign_type: Literal["HEALTH_CAMPAIGN", "HOSPITAL_PROMOTION", "EMERGENCY_NOTIFICATION", "STAFF_COMMUNICATION"]
    audience: Literal["PATIENTS", "STAFF", "BOTH"] = "PATIENTS"
    title: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=2, max_length=700)
    scheduled_at: datetime | None = None


class RefillReminderIn(BaseModel):
    patient_id: int
    visit_id: int | None = None
    send_at: datetime
    message: str | None = Field(None, max_length=700)


class OtpRequestIn(BaseModel):
    phone: str
    purpose: str = "VERIFICATION"


class OtpVerifyIn(BaseModel):
    challenge_id: int
    code: str = Field(min_length=4, max_length=8)


@router.get("/settings")
def get_notification_settings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "VIEW")
    s = _settings(db, user.hospital_id)
    return {c.name: getattr(s, c.name) for c in NotificationSetting.__table__.columns if c.name not in {"id", "hospital_id", "updated_at"}}


@router.patch("/settings")
def patch_notification_settings(data: SettingsPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "EDIT")
    s = _settings(db, user.hospital_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        if k == "timezone_name" and v:
            try: ZoneInfo(v)
            except Exception: raise HTTPException(400, "Invalid timezone")
        setattr(s, k, v)
    record(db, user, "EDIT", "notification_settings", s.id)
    db.commit()
    return get_notification_settings(user, db)


@router.get("/outbox")
def outbox(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "VIEW")
    rows = db.query(SmsOutbox).filter_by(hospital_id=user.hospital_id).order_by(SmsOutbox.id.desc()).limit(250).all()
    return [{"id":x.id,"event_type":x.event_type,"phone":x.phone,"message":x.message,"status":x.status,"created_at":x.created_at,"sent_at":x.sent_at,"visit_id":x.visit_id} for x in rows]


@router.get("/jobs")
def jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "VIEW")
    rows = db.query(NotificationJob).filter_by(hospital_id=user.hospital_id).order_by(NotificationJob.id.desc()).limit(250).all()
    return [{"id":x.id,"event_type":x.event_type,"phone":x.phone,"message":x.message,"send_at":x.send_at,"status":x.status,"attempts":x.attempts,"visit_id":x.visit_id} for x in rows]


@router.post("/process-due")
def process_due(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "EDIT")
    return process_due_notifications(db, user.hospital_id)


@router.post("/refill-reminders")
def create_refill_reminder(data: RefillReminderIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        ensure_access(user, db, "pharmacy", "EDIT")
    except HTTPException:
        ensure_access(user, db, "consultation", "EDIT")
    row = schedule_refill_reminder(db, hospital_id=user.hospital_id, patient_id=data.patient_id, visit_id=data.visit_id,
                                   send_at=data.send_at, message=data.message, created_by=user.id)
    db.commit()
    return {"id": row.id if row else None, "status": row.status if row else "SKIPPED"}


def _campaign_recipients(db: Session, hospital_id: int, kind: str, audience: str):
    recipients: list[tuple[str, str, int | None, int | None]] = []
    if audience in {"PATIENTS", "BOTH"}:
        q = db.query(Patient).filter(Patient.hospital_id == hospital_id, Patient.phone.isnot(None), Patient.phone != "")
        if kind in {"HEALTH_CAMPAIGN", "HOSPITAL_PROMOTION"}:
            q = q.filter(Patient.sms_marketing_opt_in == True)  # noqa: E712
        else:
            q = q.filter(Patient.sms_operational_opt_in == True)  # noqa: E712
        recipients += [(p.phone, f"patient:{p.id}", p.id, None) for p in q.all()]
    if audience in {"STAFF", "BOTH"}:
        q = db.query(User).filter(User.hospital_id == hospital_id, User.active == True, User.phone.isnot(None), User.phone != "")  # noqa: E712
        recipients += [(u.phone, f"staff:{u.id}", None, u.id) for u in q.all()]
    return recipients


@router.post("/campaigns")
def create_campaign(data: CampaignIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "EDIT")
    if not event_enabled(db, user.hospital_id, data.campaign_type):
        raise HTTPException(409, f"{data.campaign_type} SMS is disabled in notification settings")
    if data.campaign_type == "STAFF_COMMUNICATION" and data.audience == "PATIENTS":
        raise HTTPException(400, "Staff communication audience must include staff")
    when = data.scheduled_at or datetime.utcnow()
    row = NotificationCampaign(hospital_id=user.hospital_id, campaign_type=data.campaign_type, audience=data.audience,
                               title=data.title, message=data.message, scheduled_at=when, created_by=user.id)
    db.add(row); db.flush()
    recipients = _campaign_recipients(db, user.hospital_id, data.campaign_type, data.audience)
    row.recipient_count = len(recipients)
    for phone, ref, patient_id, user_id in recipients:
        schedule_sms(db, hospital_id=user.hospital_id, phone=phone,
                     message=f"{_hospital_name(db, user.hospital_id)}: {data.message}",
                     event_type=data.campaign_type, send_at=when,
                     dedupe_key=f"campaign:{row.id}:{ref}", patient_id=patient_id, user_id=user_id,
                     created_by=user.id)
    record(db, user, "CREATE", "notification_campaign", row.id, {"type":data.campaign_type,"recipients":len(recipients)})
    db.commit()
    if when <= datetime.utcnow():
        outcome = process_due_notifications(db, user.hospital_id, limit=max(250, len(recipients)+10))
        if not row.recipient_count:
            row.status = "EMPTY"
        elif outcome.get("failed"):
            row.status = "PARTIAL" if outcome.get("sent") or outcome.get("queued") else "FAILED"
        elif outcome.get("queued"):
            row.status = "QUEUED"
        else:
            row.status = "SENT"
        db.commit()
    return {"id":row.id,"status":row.status,"recipient_count":row.recipient_count}


@router.get("/campaigns")
def list_campaigns(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "VIEW")
    rows = db.query(NotificationCampaign).filter_by(hospital_id=user.hospital_id).order_by(NotificationCampaign.id.desc()).limit(100).all()
    return [{"id":x.id,"campaign_type":x.campaign_type,"audience":x.audience,"title":x.title,"message":x.message,"scheduled_at":x.scheduled_at,"status":x.status,"recipient_count":x.recipient_count} for x in rows]


@router.post("/otp/request")
def request_otp(data: OtpRequestIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_access(user, db, "configuration", "EDIT")
    if not event_enabled(db, user.hospital_id, "OTP"):
        raise HTTPException(409, "OTP SMS is disabled")
    code = f"{secrets.randbelow(1_000_000):06d}"
    row = OtpChallenge(hospital_id=user.hospital_id, phone=data.phone.strip(), purpose=data.purpose.strip().upper()[:80],
                       code_hash=hashlib.sha256(code.encode()).hexdigest(), expires_at=datetime.utcnow()+timedelta(minutes=10), created_by=user.id)
    db.add(row); db.flush()
    enqueue_sms(db, hospital_id=user.hospital_id, phone=row.phone,
                message=f"{_hospital_name(db, user.hospital_id)}: Your verification code is {code}. It expires in 10 minutes. Do not share this code.",
                event_type="OTP", dedupe_key=f"otp:{row.id}")
    db.commit()
    return {"challenge_id":row.id,"expires_at":row.expires_at}


@router.post("/otp/verify")
def verify_otp(data: OtpVerifyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(OtpChallenge, data.challenge_id)
    if not row or row.hospital_id != user.hospital_id:
        raise HTTPException(404, "OTP challenge not found")
    if row.verified_at:
        return {"verified": True}
    if row.expires_at < datetime.utcnow():
        raise HTTPException(400, "OTP expired")
    row.attempts += 1
    if row.attempts > 6:
        db.commit(); raise HTTPException(429, "Too many attempts")
    ok = secrets.compare_digest(row.code_hash, hashlib.sha256(data.code.encode()).hexdigest())
    if ok:
        row.verified_at = datetime.utcnow()
    db.commit()
    if not ok:
        raise HTTPException(400, "Invalid OTP")
    return {"verified": True}
