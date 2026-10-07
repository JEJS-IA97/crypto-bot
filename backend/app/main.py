import asyncio
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import bot, candidates, health, observability, signals, simulation
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services import bot_loop
from app.services.keepalive_service import keepalive_loop, should_keepalive
from app.services.observability_service import purge_old_events
from app.services.phase_service import get_phase
from app.services.structured_log import configure_logging, emit

logger = logging.getLogger(__name__)


def _as_origin(value: str) -> str:
    """Normaliza a origen CORS (scheme://host[:port]).

    El navegador sólo envía `Origin: scheme://host` (nunca la ruta), así
    que una entrada con path (`https://x/crypto-bot/`) se reduce a su
    origen real (RF-8).
    """
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return value
    return f"{parts.scheme}://{parts.netloc}"


def _cors_kwargs(origins_csv: str) -> dict[str, object]:
    """Opciones de CORSMiddleware a partir del CSV `CORS_ORIGINS` (RF-8)."""
    return {
        "allow_origins": [
            _as_origin(origin.strip())
            for origin in origins_csv.split(",")
            if origin.strip()
        ],
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(
        bind=engine
    )

    # Spec 005, RF-1/RF-8: log JSON + purga inicial de eventos viejos.
    log_handler = configure_logging()
    with SessionLocal() as db:
        try:
            purge_old_events(db)
        except Exception:
            logger.exception("could not purge old events on startup")
        try:
            mode = get_phase(db).phase.value
        except Exception:
            logger.exception("could not resolve current phase")
            mode = "unknown"
        emit(
            service="main",
            event="system.started",
            result="ok",
            mode=mode,
            db=db,
        )

    stop_event = asyncio.Event()
    bot_task = None
    keepalive_task = None

    if settings.simulation_bot_enabled:
        bot_task = asyncio.create_task(
            bot_loop.run(stop_event=stop_event)
        )

    if should_keepalive(settings.keepalive_url):
        keepalive_task = asyncio.create_task(
            keepalive_loop(
                stop_event,
                url=settings.keepalive_url,
            )
        )

    yield

    stop_event.set()
    if bot_task is not None:
        bot_loop.controller.notify()
        await bot_task
    if keepalive_task is not None:
        await keepalive_task

    try:
        with SessionLocal() as db:
            emit(service="main", event="system.stopped", result="ok", db=db)
    except Exception:
        logger.exception("could not record system.stopped")
    if log_handler is not None:
        logging.getLogger().removeHandler(log_handler)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Private cryptocurrency trading "
        "bot backend"
    ),
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    **_cors_kwargs(settings.cors_origins),
)


app.include_router(
    bot.router
)

app.include_router(
    observability.router
)

app.include_router(
    candidates.router
)

app.include_router(
    signals.router
)

app.include_router(
    health.router
)

app.include_router(
    simulation.router
)