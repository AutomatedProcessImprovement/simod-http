import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from simod_http.app import make_simod_app
from simod_http.configurations import LoggingConfiguration
from simod_http.exceptions import BadMultipartRequest, InternalServerError, NotFound, NotSupported, UnsupportedMediaType
from simod_http.routes.token import router as auth_router
from simod_http.routes.discoveries import router as discoveries_router
from simod_http.routes.discovery import router as discovery_router


@asynccontextmanager
async def lifespan(api: FastAPI):
    # Request is processed here
    yield

    # Closing the application
    api.state.app.close()


def make_fastapi_app() -> FastAPI:
    global root_path

    api = FastAPI(lifespan=lifespan, root_path="/api/v1")

    # Simod HTTP Application

    # Injecting the custom application logic into the FastAPI instance's state.
    # This allows later to inject a mock application instance in tests for handlers.
    app = make_simod_app()
    api.state.app = app

    set_up_logging(app.configuration.logging)

    if app.configuration.debug:
        app.logger.debug("Debug mode is on")
        app.logger.debug(f"Configuration: {app.configuration}")
    else:
        app.logger.info("Debug mode is off")

    # Exception handling

    @api.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        api.state.app.logger.exception(f"HTTP exception occurred: {exc}, scope={request.scope}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"message": exc.detail},
            },
        )

    @api.exception_handler(RequestValidationError)
    async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
        api.state.app.logger.exception(f"Validation exception occurred: {exc}")
        return JSONResponse(
            status_code=422,
            content={
                "error": {"message": exc.errors()},
            },
        )

    @api.exception_handler(NotFound)
    async def not_found_exception_handler(request: Request, exc: NotFound) -> JSONResponse:
        api.state.app.logger.exception(
            f"Not found exception occurred: {exc}, path={request.url.path}, scope={request.scope}"
        )
        return exc.json_response

    @api.exception_handler(BadMultipartRequest)
    async def bad_multipart_exception_handler(_, exc: BadMultipartRequest) -> JSONResponse:
        api.state.app.logger.exception(f"Bad multipart exception occurred: {exc}")
        return exc.json_response

    @api.exception_handler(UnsupportedMediaType)
    async def unsupported_media_type_exception_handler(_, exc: UnsupportedMediaType) -> JSONResponse:
        api.state.app.logger.exception(f"Unsupported media type exception occurred: {exc}")
        return exc.json_response

    @api.exception_handler(InternalServerError)
    async def internal_server_error_exception_handler(_, exc: InternalServerError) -> JSONResponse:
        api.state.app.logger.exception(f"Internal server error exception occurred: {exc}")
        return exc.json_response

    @api.exception_handler(NotSupported)
    async def not_supported_exception_handler(_, exc: NotSupported) -> JSONResponse:
        api.state.app.logger.exception(f"Not supported exception occurred: {exc}")
        return exc.json_response

    @api.exception_handler(Exception)
    async def exception_handler(_, exc: Exception) -> JSONResponse:
        api.state.app.logger.exception(f"Exception occurred: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": {"message": "Internal Server Error"},
            },
        )

    # Routing

    api.include_router(discoveries_router)
    api.include_router(discovery_router)
    api.include_router(auth_router)

    return api


def set_up_logging(config: LoggingConfiguration):
    logging_handlers = []
    if config.path is not None:
        logging_handlers.append(logging.FileHandler(config.path, mode="w"))

    if len(logging_handlers) > 0:
        logging.basicConfig(
            level=config.level.upper(),
            handlers=logging_handlers,
            format=config.format,
        )
    else:
        logging.basicConfig(
            level=config.level.upper(),
            format=config.format,
        )


api = make_fastapi_app()
