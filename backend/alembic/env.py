import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.db import models  # noqa: F401  (registers tables on Base.metadata)
from app.db.base import Base

config = context.config
# Tests pass their own database URL and keep their logging setup.
database_url: str | None = config.attributes.get("database_url")
if database_url is None:
    if config.config_file_name is not None:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    database_url = get_settings().database_url

# "%" is legal in URL-encoded passwords but special in the ini parser.
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


asyncio.run(run_migrations())
