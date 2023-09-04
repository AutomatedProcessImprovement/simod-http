import datetime
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Union, Annotated

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from starlette import status

# We use a single admin user for Simod.
# Credentials are set via environment variables.
username = os.environ.get("SIMOD_ADMIN_USERNAME")
password = os.environ.get("SIMOD_ADMIN_PASSWORD")  # encrypted with bcrypt
secret_key = os.environ.get("SIMOD_SECRET_KEY")
algorithm = os.environ.get("SIMOD_SECURITY_ALGORITHM", "HS256")
expires_in = datetime.timedelta(seconds=int(os.environ.get("SIMOD_SECURITY_EXPIRES_IN", 3600)))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@dataclass
class Token:
    access_token: str
    token_type: str


@dataclass
class TokenData:
    username: Union[str, None] = None


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> Union[str, None]:
    """
    Gets the username from the JWT token. It is used to authenticate the admin user by FastAPI routes.
    """
    global secret_key, algorithm

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    return username


def authenticate_user(username_: str, password_: str) -> bool:
    """
    Verifies the username and password correspond to the admin user.
    """
    global username, password

    print(f"username_={username_}, username={username}, password_={password_}, password={password}")
    return username_ == username and _verify_password(password_, password)


def create_access_token(data: dict, expires_delta: timedelta = expires_in) -> str:
    """
    Create a JWT token given a payload.
    """
    global secret_key, algorithm

    token_data = data.copy()

    expires_at = datetime.datetime.utcnow() + expires_delta
    token_data.update({"exp": expires_at})

    encoded_jwt = jwt.encode(token_data, secret_key, algorithm=algorithm)

    return encoded_jwt


def _verify_password(plain_password: Union[str, bytes], hashed_password: Union[str, bytes]) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _get_password_hash(password: Union[str, bytes]) -> str:
    return pwd_context.hash(password)


if __name__ == "__main__":
    print(_get_password_hash("admin"))
