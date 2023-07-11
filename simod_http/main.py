import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from simod_http.app import make_simod_app
from simod_http.configurations import LoggingConfiguration
from simod_http.exceptions import NotFound, BadMultipartRequest, UnsupportedMediaType, InternalServerError, NotSupported
from simod_http.router import router


@asynccontextmanager
async def lifespan(api: FastAPI):
    # Injecting the cust application logic into the FastAPI instance's state.
    # This allows later to inject a mock application instance in tests for handlers.
    app = make_simod_app()
    api.state.app = app

    set_up_logging(app.configuration.logging)

    if app.configuration.debug:
        app.logger.debug("Debug mode is on")
        app.logger.debug(f"Configuration: {app.configuration}")
    else:
        app.logger.info("Debug mode is off")

    # Everything happens here
    yield

    # Closing the application
    app.close()


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


def make_fastapi_app() -> FastAPI:
    api = FastAPI(lifespan=lifespan)

    # Exception handling

    @api.exception_handler(HTTPException)
    async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
        api.state.app.logger.exception(f"HTTP exception occurred: {exc}")
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
    async def not_found_exception_handler(_, exc: NotFound) -> JSONResponse:
        return exc.json_response

    @api.exception_handler(BadMultipartRequest)
    async def bad_multipart_exception_handler(_, exc: BadMultipartRequest) -> JSONResponse:
        api.state.app.logger.exception(f"Bad multipart exception occurred: {exc}")
        return exc.json_response

    @api.exception_handler(UnsupportedMediaType)
    async def bad_multipart_exception_handler(_, exc: UnsupportedMediaType) -> JSONResponse:
        api.state.app.logger.exception(f"Unsupported media type exception occurred: {exc}")
        return exc.json_response

    @api.exception_handler(InternalServerError)
    async def bad_multipart_exception_handler(_, exc: InternalServerError) -> JSONResponse:
        api.state.app.logger.exception(f"Internal server error exception occurred: {exc}")
        return exc.json_response

    @api.exception_handler(NotSupported)
    async def bad_multipart_exception_handler(_, exc: NotSupported) -> JSONResponse:
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

    api.include_router(router, prefix="/v1")

    return api


api = make_fastapi_app()


# Default root handler


@api.get("/")
async def root() -> JSONResponse:
    raise NotFound()
