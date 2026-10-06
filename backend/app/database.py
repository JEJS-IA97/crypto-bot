from collections.abc import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.config import settings

class Base(DeclarativeBase):
    pass


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Activa PRAGMA foreign_keys en cada conexión SQLite (spec 001, RF-4/RF-10)."""
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def _engine_options(database_url: str) -> dict[str, object]:
    """Opciones del engine según dialecto (spec 002, RF-2).

    SQLite (suite local) necesita `check_same_thread`; Postgres (Neon,
    despliegue) no y activa `pool_pre_ping` para tolerar las pausas del
    tier gratuito de Neon sin errores transitorios.
    """
    if database_url.startswith("sqlite"):
        return {
            "connect_args": {"check_same_thread": False},
            "pool_pre_ping": False,
        }
    return {
        "connect_args": {},
        "pool_pre_ping": True,
    }


engine = create_engine(
    settings.database_url,
    **_engine_options(settings.database_url),
)

_enable_sqlite_foreign_keys(engine)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()