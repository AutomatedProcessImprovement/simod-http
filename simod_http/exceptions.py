from typing import Union

from starlette.responses import JSONResponse

from simod_http.discoveries import DiscoveryStatus
from simod_http.responses import Response


class BaseRequestException(Exception):
    _status_code = 500

    discovery_id = None
    discovery_status = None
    archive_url = None
    message = "Internal server error"

    def __init__(
        self,
        discovery_id: Union[str, None] = None,
        message: Union[str, None] = None,
        discovery_status: Union[DiscoveryStatus, None] = None,
        archive_url: Union[str, None] = None,
    ):
        if discovery_id is not None:
            self.discovery_id = discovery_id
        if message is not None:
            self.message = message
        if discovery_status is not None:
            self.discovery_status = discovery_status
        if archive_url is not None:
            self.archive_url = archive_url

    @property
    def status_code(self) -> int:
        return self._status_code

    def make_response(self) -> Response:
        return Response(
            discovery_id=self.discovery_id,
            discovery_status=self.discovery_status,
            archive_url=self.archive_url,
            error=self.message,
        )

    def json_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content=self.make_response().dict(exclude_none=True),
        )


class NotFound(BaseRequestException):
    _status_code = 404
    message = "Not Found"


class BadMultipartRequest(BaseRequestException):
    _status_code = 400
    message = "Bad Multipart Request"


class UnsupportedMediaType(BaseRequestException):
    _status_code = 415
    message = "Unsupported Media Type"


class InternalServerError(BaseRequestException):
    _status_code = 500
    message = "Internal Server Error"


class NotSupported(BaseRequestException):
    _status_code = 501
    message = "Not Supported"
