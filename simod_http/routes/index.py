from fastapi import APIRouter

from simod_http.exceptions import NotFound

router = APIRouter(prefix="/discoveries")


@router.get("/")
async def root():
    raise NotFound()
