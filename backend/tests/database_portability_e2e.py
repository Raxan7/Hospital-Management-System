import os, sys, tempfile
from pathlib import Path

DB = Path(tempfile.gettempdir()) / 'onehms_database_portability_e2e.db'
try:
    DB.unlink()
except FileNotFoundError:
    pass

os.environ['DATABASE_URL'] = f'sqlite:///{DB}'
os.environ['JWT_SECRET'] = 'database-portability-e2e-secret-12345678901234567890'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text
from app.database import engine, SessionLocal
from app.main import migrate_columns, PATIENT_TZ_COLUMNS, ENCOUNTER_TZ_COLUMNS

checks = []
def ok(name, cond=True):
    if not cond:
        raise AssertionError(name)
    checks.append(name)

# Simulate an older installation before the Tanzania columns existed.
with engine.begin() as conn:
    conn.execute(text('CREATE TABLE patients (id INTEGER PRIMARY KEY)'))
    conn.execute(text('CREATE TABLE encounters (id INTEGER PRIMARY KEY)'))
    conn.execute(text('INSERT INTO patients (id) VALUES (1)'))
    conn.execute(text('INSERT INTO encounters (id) VALUES (1)'))

with SessionLocal() as db:
    migrate_columns(db)
    # Must be safe to run repeatedly at every application startup.
    migrate_columns(db)

inspector = inspect(engine)
patient_cols = {c['name'] for c in inspector.get_columns('patients')}
encounter_cols = {c['name'] for c in inspector.get_columns('encounters')}
ok('patient migration columns added', set(PATIENT_TZ_COLUMNS).issubset(patient_cols))
ok('encounter migration columns added', set(ENCOUNTER_TZ_COLUMNS).issubset(encounter_cols))

with engine.connect() as conn:
    patient_category = conn.execute(text('SELECT patient_category FROM patients WHERE id=1')).scalar_one()
    is_new_case = conn.execute(text('SELECT is_new_case FROM encounters WHERE id=1')).scalar_one()
ok('existing patients receive default patient category', patient_category == 'COST_SHARING')
ok('existing encounters receive boolean default', bool(is_new_case) is True)

source = (Path(__file__).resolve().parents[1] / 'app' / 'main.py').read_text()
ok('startup migration contains no SQLite-only PRAGMA', 'PRAGMA table_info' not in source)
ok('migration uses SQLAlchemy dialect-neutral inspection', 'inspect(db.get_bind())' in source)

print(f'DATABASE PORTABILITY E2E: PASS ({len(checks)}/{len(checks)})')
for i, name in enumerate(checks, 1):
    print(f'{i:02d}. PASS - {name}')
