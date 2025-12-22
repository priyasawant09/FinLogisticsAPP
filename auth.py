# auth.py
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User
from schemas import TokenData

# === CONFIG ===
SECRET_KEY = "replace-with-a-long-random-secret-string"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
EMAIL_TOKEN_EXPIRE_MINUTES = 30  # verification link validity

# Use pbkdf2_sha256 to avoid 72-byte bcrypt limit issues
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")
# add near ACCESS_TOKEN_EXPIRE_MINUTES
PASSWORD_RESET_EXPIRE_MINUTES = 30  # reset link validity

# ----- DB dependency -----

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----- Password helpers -----

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ----- User helpers -----

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(db, username)
    if not user:
        user = get_user_by_email(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ----- JWT helpers -----

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_email_verification_token(email: str) -> str:
    """Token used in email verification link."""
    to_encode = {
        "sub": email,
        "type": "verify_email",
        "exp": datetime.utcnow() + timedelta(minutes=EMAIL_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_email_verification_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "verify_email":
            return None
        return payload.get("sub")
    except JWTError:
        return None

#password reset ( forgot password )helpers
def create_password_reset_token(email: str) -> str:
    """Token used in password reset link."""
    to_encode = {
        "sub": email,
        "type": "reset_password",
        "exp": datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES),
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_password_reset_token(token: str) -> Optional[str]:
    """Return email if token is valid reset token, else None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "reset_password":
            return None
        return payload.get("sub")
    except JWTError:
        return None

# ----- Current user dependencies -----

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials (token).",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = get_user_by_username(db, token_data.username)  # type: ignore[arg-type]
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    if not current_user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Email not verified. Please check your inbox."
        )
    return current_user
