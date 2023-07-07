from typing import Union

from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from simod_http.discoveries import DiscoveryStatus


class Response(BaseModel):
    request_id: Union[str, None]
    request_status: Union[DiscoveryStatus, None]
    error: Union[str, None]
    archive_url: Union[str, None]

    def json_response(self, status_code: int) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content=self.dict(exclude_none=True),
        )

    @staticmethod
    def from_http_exception(exc: HTTPException) -> "Response":
        return Response(
            error=exc.detail,
        )
