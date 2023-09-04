from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from simod_http.auth import Token, authenticate_user, create_access_token

router = APIRouter()


@router.post("/token", response_model=Token)
async def login(request: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    Get a JWT token to access the API.
    """

    logger = request.app.state.app.logger

    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(
            f"Invalid login attempt for user {form_data.username}, "
            f"password: {form_data.password}, "
            f"IP: {request.client.host}, "
            f"UA: {request.headers.get('user-agent')} "
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    access_token = create_access_token(data={"sub": form_data.username})

    return {"access_token": access_token, "token_type": "bearer"}
