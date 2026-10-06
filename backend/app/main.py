import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import bot, health, signals, simulation
from app.config import settings
from app.database import Base, engine
from app.services import bot_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(
        bind=engine
    )

    stop_event = asyncio.Event()
    bot_task = None

    if settings.simulation_bot_enabled:
        bot_task = asyncio.create_task(
            bot_loop.run(stop_event=stop_event)
        )

    yield

    if bot_task is not None:
        stop_event.set()
        bot_loop.controller.notify()
        await bot_task


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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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