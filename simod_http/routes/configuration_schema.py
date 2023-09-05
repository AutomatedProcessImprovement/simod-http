import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from simod_http.worker import get_schema_json, get_schema_yaml

router = APIRouter(prefix="/configuration-schema")


@router.get("/json")
async def get_configuration_schema_json() -> JSONResponse:
    result = get_schema_json.delay().get()
    return JSONResponse(json.loads(result))


@router.get("/yaml")
async def get_configuration_schema_yaml() -> Response:
    result = get_schema_yaml.delay().get()
    return Response(result, media_type="text/x-yaml")
