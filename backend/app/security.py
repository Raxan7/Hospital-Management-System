from datetime import datetime, timedelta, timezone
import hashlib, hmac, secrets
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User, HospitalModule
from .modules import MODULE_BY_KEY

bearer = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 200_000).hex()
    return f'pbkdf2_sha256${salt}${digest}'

def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, salt, expected = password_hash.split('$', 2)
        if scheme != 'pbkdf2_sha256': return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 200_000).hex()
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {'sub': str(user.id), 'hospital_id': user.hospital_id, 'iat': now, 'exp': now + timedelta(minutes=settings.access_token_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials: raise HTTPException(status_code=401, detail='Missing bearer token')
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload['sub'])
    except Exception:
        raise HTTPException(status_code=401, detail='Invalid token')
    user = db.get(User, user_id)
    if not user or not user.active: raise HTTPException(status_code=401, detail='Inactive or missing user')
    return user

def ensure_access(user: User, db: Session, module_key: str, permission: str):
    module = MODULE_BY_KEY.get(module_key)
    if not module: raise HTTPException(status_code=404, detail='Unknown module')
    row = db.query(HospitalModule).filter_by(hospital_id=user.hospital_id, module_key=module_key).first()
    enabled = module.core if row is None else row.enabled
    if not enabled: raise HTTPException(status_code=403, detail={'code':'MODULE_DISABLED','module':module_key})
    allowed = (user.role.permissions or {}).get(module_key, [])
    if '*' not in allowed and permission not in allowed:
        raise HTTPException(status_code=403, detail={'code':'PERMISSION_DENIED','module':module_key,'permission':permission})

def require(module_key: str, permission: str):
    def dependency(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
        ensure_access(user, db, module_key, permission); return user
    return dependency
