import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from simod_http.app import make_app
from simod_http.configurations import LoggingConfiguration
from simod_http.exceptions import NotFound, BadMultipartRequest, UnsupportedMediaType, InternalServerError, NotSupported
from simod_http.router import router

app = make_app()


@asynccontextmanager
async def lifespan(_api: FastAPI):
    set_up_logging(app.configuration.logging)

    if app.configuration.debug:
        app.logger.debug("Debug mode is on")
        app.logger.debug(f"Configuration: {app.configuration}")
    else:
        app.logger.info("Debug mode is off")

    yield
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


api = FastAPI(lifespan=lifespan)
# Injecting the application instance into the FastAPI instance
# allows to inject a mock application instance in tests for handlers
api.state.app = app
api.include_router(router, prefix="/v1")


# Default root handler


@api.get("/")
async def root() -> JSONResponse:
    raise NotFound()


# Exception handling


@api.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
    app.logger.exception(f"HTTP exception occurred: {exc}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
        },
    )


@api.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    app.logger.exception(f"Validation exception occurred: {exc}")
    return JSONResponse(
        status_code=422,
        content={
            "error": exc.errors(),
        },
    )


@api.exception_handler(NotFound)
async def not_found_exception_handler(_, exc: NotFound) -> JSONResponse:
    return exc.json_response


@api.exception_handler(BadMultipartRequest)
async def bad_multipart_exception_handler(_, exc: BadMultipartRequest) -> JSONResponse:
    app.logger.exception(f"Bad multipart exception occurred: {exc}")
    return exc.json_response


@api.exception_handler(UnsupportedMediaType)
async def bad_multipart_exception_handler(_, exc: UnsupportedMediaType) -> JSONResponse:
    app.logger.exception(f"Unsupported media type exception occurred: {exc}")
    return exc.json_response


@api.exception_handler(InternalServerError)
async def bad_multipart_exception_handler(_, exc: InternalServerError) -> JSONResponse:
    app.logger.exception(f"Internal server error exception occurred: {exc}")
    return exc.json_response


@api.exception_handler(NotSupported)
async def bad_multipart_exception_handler(_, exc: NotSupported) -> JSONResponse:
    app.logger.exception(f"Not supported exception occurred: {exc}")
    return exc.json_response


@api.exception_handler(Exception)
async def exception_handler(_, exc: Exception) -> JSONResponse:
    app.logger.exception(f"Exception occurred: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {"message": "Internal Server Error"},
        },
    )