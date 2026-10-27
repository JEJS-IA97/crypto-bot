import asyncio
import logging
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, inspect, text

from app.api.routes import (
    ai,
    bot,
    candidates,
    decisions,
    health,
    lab,
    learning,
    observability,
    risk,
    signals,
    simulation,
)
from app.brain.analyst import brain_loop
from app.signals.telegram import telegram_loop
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.lab import live as lab_live
from app.lab import models as lab_models  # noqa: F401 — registra las tablas del laboratorio
from app.bets import engine as bets_engine  # noqa: F401 — registra la tabla de apuestas
from app.services import bot_loop
from app.services.ai_daily_analysis import daily_loop
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


def add_missing_columns(bind: Engine) -> None:
    """Sincroniza columnas del modelo con las tablas existentes.

    `create_all` solo crea tablas ausentes: si el modelo gana una columna
    (p.ej. `simulation_trades.decision_id`), la BD vieja sigue sin ella y
    cada INSERT/SELECT del ORM revienta (bug del 10/10: sin fill de orden).
    """
    inspector = inspect(bind)
    preparer = bind.dialect.identifier_preparer
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                # shortcut: solo la columna (sin índices/unique); migrar con
                # Alembic cuando haga falta replicar constraints.
                conn.execute(
                    text(
                        f"ALTER TABLE {preparer.quote(table.name)}"
                        f" ADD COLUMN {preparer.quote(column.name)}"
                        f" {column.type.compile(bind.dialect)}"
                    )
                )
                logger.warning(
                    "schema drift fixed: added %s.%s",
                    table.name,
                    column.name,
                )


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(
        bind=engine
    )
    add_missing_columns(engine)

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
    ai_task = None

    # Núcleo de tendencia diaria (SMA50 y SMA200, BTC+ETH) sobre la cuenta principal de 40 USD.
    if settings.simulation_bot_enabled:
        bot_task = asyncio.create_task(
            bot_loop.run(stop_event=stop_event)
        )

    lab_task = None
    if settings.lab_enabled:
        lab_live.runner = lab_live.LabRunner()
        lab_task = asyncio.create_task(lab_live.runner.run(stop_event))
    brain_task = (
        asyncio.create_task(brain_loop(stop_event)) if settings.brain_enabled else None
    )
    telegram_task = asyncio.create_task(telegram_loop(stop_event))
    from app.signals.okx_watch import okx_loop

    from app.lab.context import context_loop

    okx_task = asyncio.create_task(okx_loop(stop_event)) if settings.lab_enabled else None
    context_task = asyncio.create_task(context_loop(stop_event)) if settings.lab_enabled else None
    from app.bets.engine import bets_loop

    bets_task = asyncio.create_task(bets_loop(stop_event)) if settings.bets_enabled else None

    if settings.gemini_auto_analysis and settings.gemini_api_key.strip():
        ai_task = asyncio.create_task(
            daily_loop(stop_event=stop_event)
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
    if lab_task is not None:
        await lab_task
    if brain_task is not None:
        await brain_task
    await telegram_task
    if okx_task is not None:
        await okx_task
    if context_task is not None:
        await context_task
    if bets_task is not None:
        await bets_task
    if ai_task is not None:
        await ai_task

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
    risk.router
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

app.include_router(
    ai.router
)

app.include_router(
    decisions.router
)

app.include_router(
    learning.router
)
app.include_router(
    lab.router
)

# Panel: si existe el build del frontend (npm run build), se sirve en
# http://127.0.0.1:8000/ y no hace falta Vite ni Render.
_PANEL = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _PANEL.is_dir():
    app.mount("/", StaticFiles(directory=_PANEL, html=True), name="panel")
