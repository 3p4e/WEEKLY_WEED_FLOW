import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No ORM/models in this app (raw asyncpg everywhere) — migrations are
# hand-written SQL, so there's no MetaData to diff and autogenerate isn't
# available. Every revision is written with `alembic -n users revision -m
# "..."` and a manual upgrade()/downgrade().
target_metadata = None

# DDL needs a role with schema-change privileges — app_user/app_admin are
# DML-only (see docs/DEPLOY.md's bootstrap grants). Deliberately NOT read
# through app.config: that module raises at import time if SECRET_KEY is
# still the placeholder in production, which has nothing to do with running
# a migration and shouldn't block one.
db_url = os.environ.get("USERS_MIGRATION_DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
