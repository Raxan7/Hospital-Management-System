from datetime import datetime, date
from sqlalchemy import String, Integer, Boolean, DateTime, Date, ForeignKey, Text, Float, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Hospital(Base):
    __tablename__ = 'hospitals'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    facility_type: Mapped[str] = mapped_column(String(20), default='SMALL')
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class HospitalModule(Base):
    __tablename__ = 'hospital_modules'
    __table_args__ = (UniqueConstraint('hospital_id','module_key'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    module_key: Mapped[str] = mapped_column(String(80), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)

class Role(Base):
    __tablename__ = 'roles'
    __table_args__ = (UniqueConstraint('hospital_id','name'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(80))
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey('roles.id'))
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[Role] = relationship()

class Patient(Base):
    __tablename__ = 'patients'
    __table_args__ = (UniqueConstraint('hospital_id','patient_no'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    patient_no: Mapped[str] = mapped_column(String(40), index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    sex: Mapped[str] = mapped_column(String(20), default='Unknown')
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_of_kin: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Appointment(Base):
    __tablename__ = 'appointments'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    department: Mapped[str] = mapped_column(String(100), default='OPD')
    clinician: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='BOOKED')

class Encounter(Base):
    __tablename__ = 'encounters'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'))
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey('appointments.id'), nullable=True)
    encounter_type: Mapped[str] = mapped_column(String(30), default='OPD')
    status: Mapped[str] = mapped_column(String(30), default='OPEN')
    chief_complaint: Mapped[str | None] = mapped_column(Text, nullable=True)
    clinical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Vital(Base):
    __tablename__ = 'vitals'
    id: Mapped[int] = mapped_column(primary_key=True)
    encounter_id: Mapped[int] = mapped_column(ForeignKey('encounters.id', ondelete='CASCADE'), index=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    pulse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    systolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diastolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spo2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Prescription(Base):
    __tablename__ = 'prescriptions'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    encounter_id: Mapped[int] = mapped_column(ForeignKey('encounters.id'))
    inventory_item_id: Mapped[int | None] = mapped_column(ForeignKey('inventory_items.id'), nullable=True)
    medicine: Mapped[str] = mapped_column(String(160))
    dose: Mapped[str] = mapped_column(String(100))
    frequency: Mapped[str] = mapped_column(String(100))
    duration: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='PENDING')
    dispensed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class LabOrder(Base):
    __tablename__ = 'lab_orders'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    encounter_id: Mapped[int] = mapped_column(ForeignKey('encounters.id'))
    test_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default='ORDERED')
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Invoice(Base):
    __tablename__ = 'invoices'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'))
    amount: Mapped[float] = mapped_column(Float, default=0)
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    description: Mapped[str] = mapped_column(String(255), default='Clinical services')
    status: Mapped[str] = mapped_column(String(30), default='UNPAID')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey('invoices.id', ondelete='CASCADE'), index=True)
    amount: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(40), default='CASH')
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    received_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class InventoryItem(Base):
    __tablename__ = 'inventory_items'
    __table_args__ = (UniqueConstraint('hospital_id','sku'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    sku: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(100), default='General')
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=10)
    unit_price: Mapped[float] = mapped_column(Float, default=0)

class StockTransaction(Base):
    __tablename__ = 'stock_transactions'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('inventory_items.id', ondelete='CASCADE'), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(160))
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Ward(Base):
    __tablename__ = 'wards'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    ward_type: Mapped[str] = mapped_column(String(80), default='GENERAL')
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Bed(Base):
    __tablename__ = 'beds'
    __table_args__ = (UniqueConstraint('hospital_id','code'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    ward_id: Mapped[int] = mapped_column(ForeignKey('wards.id'))
    code: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default='AVAILABLE')

class Admission(Base):
    __tablename__ = 'admissions'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey('patients.id'))
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey('encounters.id'), nullable=True)
    ward_id: Mapped[int] = mapped_column(ForeignKey('wards.id'))
    bed_id: Mapped[int] = mapped_column(ForeignKey('beds.id'))
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='ADMITTED')
    admitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class ServiceRecord(Base):
    __tablename__ = 'service_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    module_key: Mapped[str] = mapped_column(String(80), index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey('patients.id'), nullable=True)
    title: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(40), default='OPEN')
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey('hospitals.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
