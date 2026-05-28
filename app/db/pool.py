from app.core.config import settings
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def _configure_connection(conn) -> None:
    register_vector(conn)


def init_pool() -> ConnectionPool:
    global _pool
    if _pool is not None:
        return _pool

    if not settings.database_url:
        msg = "DATABASE_URL is not configured"
        raise RuntimeError(msg)

    _pool = ConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=10,
        kwargs={"autocommit": True},
        configure=_configure_connection,
    )

    with _pool.connection() as conn:
        register_vector(conn)

    return _pool


def get_pool() -> ConnectionPool:
    if _pool is None:
        return init_pool()
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
