from datetime import datetime, date
from typing import Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class LoginIn(BaseModel):
    email: EmailStr
    password: str
class UserOut(ORM):
    id:int; full_name:str; email:str; role_id:int; active:bool=True
class LoginOut(BaseModel):
    access_token:str; token_type:str='bearer'; user:UserOut

class PatientIn(BaseModel):
    first_name:str; last_name:str; sex:str='Unknown'; date_of_birth:date|None=None; phone:str|None=None; address:str|None=None; blood_group:str|None=None; allergies:str|None=None; next_of_kin:str|None=None
class PatientUpdate(BaseModel):
    first_name:str|None=None; last_name:str|None=None; sex:str|None=None; date_of_birth:date|None=None; phone:str|None=None; address:str|None=None; blood_group:str|None=None; allergies:str|None=None; next_of_kin:str|None=None
class PatientOut(ORM):
    id:int; patient_no:str; first_name:str; last_name:str; sex:str; date_of_birth:date|None=None; phone:str|None=None; address:str|None=None; blood_group:str|None=None; allergies:str|None=None; next_of_kin:str|None=None; created_at:datetime

class AppointmentIn(BaseModel):
    patient_id:int; scheduled_at:datetime; department:str='OPD'; clinician:str|None=None; reason:str|None=None
class StatusIn(BaseModel): status:str
class AppointmentOut(ORM):
    id:int; patient_id:int; scheduled_at:datetime; department:str; clinician:str|None=None; reason:str|None=None; status:str

class EncounterIn(BaseModel):
    patient_id:int; appointment_id:int|None=None; encounter_type:str='OPD'; chief_complaint:str|None=None
class EncounterOut(ORM):
    id:int; patient_id:int; appointment_id:int|None=None; encounter_type:str; status:str; chief_complaint:str|None=None; clinical_notes:str|None=None; diagnosis:str|None=None; created_at:datetime
class ConsultationUpdate(BaseModel):
    clinical_notes:str; diagnosis:str; status:str='OPEN'

class VitalIn(BaseModel):
    encounter_id:int; temperature_c:float|None=None; pulse:int|None=None; systolic:int|None=None; diastolic:int|None=None; spo2:int|None=Field(None,ge=0,le=100); weight_kg:float|None=None; height_cm:float|None=None
class VitalOut(ORM):
    id:int; encounter_id:int; temperature_c:float|None=None; pulse:int|None=None; systolic:int|None=None; diastolic:int|None=None; spo2:int|None=None; weight_kg:float|None=None; height_cm:float|None=None; created_at:datetime

class PrescriptionIn(BaseModel):
    encounter_id:int; inventory_item_id:int|None=None; medicine:str; dose:str; frequency:str; duration:str; quantity:int=Field(1,ge=1); instructions:str|None=None
class PrescriptionOut(ORM):
    id:int; encounter_id:int; inventory_item_id:int|None=None; medicine:str; dose:str; frequency:str; duration:str; quantity:int; instructions:str|None=None; status:str; dispensed_at:datetime|None=None

class LabOrderIn(BaseModel): encounter_id:int; test_name:str
class LabOrderOut(ORM):
    id:int; encounter_id:int; test_name:str; status:str; result:str|None=None; verified:bool; approved:bool=False; approved_at:datetime|None=None; created_at:datetime
class LabResultIn(BaseModel): result:str; verified:bool=False

class InvoiceIn(BaseModel): patient_id:int; amount:float=Field(gt=0); description:str='Clinical services'
class InvoiceOut(ORM):
    id:int; patient_id:int; amount:float; paid_amount:float; description:str; status:str; created_at:datetime
class PaymentIn(BaseModel): amount:float=Field(gt=0); method:str='CASH'; reference:str|None=None
class PaymentOut(ORM):
    id:int; invoice_id:int; amount:float; method:str; reference:str|None=None; created_at:datetime

class InventoryIn(BaseModel):
    sku:str; name:str; category:str='General'; quantity:int=Field(0,ge=0); reorder_level:int=Field(10,ge=0); unit_price:float=Field(0,ge=0)
class InventoryOut(ORM):
    id:int; sku:str; name:str; category:str; quantity:int; reorder_level:int; unit_price:float
class StockAdjustIn(BaseModel): delta:int; reason:str

class ModuleToggle(BaseModel): enabled:bool
class ModuleOut(BaseModel): key:str; name:str; group:str; core:bool; enabled:bool
class FacilityUpdate(BaseModel): name:str|None=None; facility_type:str|None=None; address:str|None=None; phone:str|None=None; apply_preset:bool=False

class RoleIn(BaseModel): name:str; permissions:dict[str,list[str]]=Field(default_factory=dict)
class RoleUpdate(BaseModel): name:str|None=None; permissions:dict[str,list[str]]|None=None
class RoleOut(ORM): id:int; name:str; permissions:dict[str,list[str]]
class RoleTemplateOut(BaseModel): name:str; category:str; description:str; permissions:dict[str,list[str]]
class UserIn(BaseModel): full_name:str; email:EmailStr; password:str=Field(min_length=6); role_id:int
class UserUpdate(BaseModel): full_name:str|None=None; role_id:int|None=None; active:bool|None=None; password:str|None=Field(None,min_length=6)
class UserAdminOut(ORM): id:int; full_name:str; email:str; role_id:int; active:bool

class WardIn(BaseModel): name:str; ward_type:str='GENERAL'
class WardOut(ORM): id:int; name:str; ward_type:str; active:bool
class BedIn(BaseModel): ward_id:int; code:str
class BedOut(ORM): id:int; ward_id:int; code:str; status:str
class AdmissionIn(BaseModel): patient_id:int; encounter_id:int|None=None; ward_id:int; bed_id:int; diagnosis:str|None=None
class AdmissionOut(ORM):
    id:int; patient_id:int; encounter_id:int|None=None; ward_id:int; bed_id:int; diagnosis:str|None=None; status:str; admitted_at:datetime; discharged_at:datetime|None=None

class ServiceRecordIn(BaseModel): patient_id:int|None=None; title:str; status:str='OPEN'; details:dict[str,Any]=Field(default_factory=dict)
class ServiceRecordUpdate(BaseModel): title:str|None=None; status:str|None=None; details:dict[str,Any]|None=None
class ServiceRecordOut(ORM):
    id:int; module_key:str; patient_id:int|None=None; title:str; status:str; details:dict[str,Any]; approved:bool=False; verified:bool=False; approved_at:datetime|None=None; verified_at:datetime|None=None; created_at:datetime; updated_at:datetime
