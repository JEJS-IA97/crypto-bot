import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import bot, health, signals, simulation
from app.config import settings
from app.database import Base, engine
from app.services import bot_loop
from app.services.keepalive_service import keepalive_loop, should_keepalive


def _cors_kwargs(origins_csv: str) -> dict[str, object]:
    """Opciones de CORSMiddleware a partir del CSV `CORS_ORIGINS` (RF-8)."""
    return {
        "allow_origins": [
            origin.strip()
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
    signals.router
)

app.include_router(
    health.router
)

app.include_router(
    simulation.router
)