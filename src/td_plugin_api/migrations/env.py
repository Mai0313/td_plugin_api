"""Run migrations on the server's connection, or on `TD_PLUGIN_API_DATABASE_URL` from the `alembic` command."""

from alembic import context
from sqlalchemy import Connection, create_engine

from td_plugin_api.db import Base, database_url


def _run(connection: Connection) -> None:
    # SQLite cannot alter most of a table in place, so its changes rebuild the table.
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is None:
    with create_engine(database_url()).connect() as opened:
        _run(opened)
else:
    _run(connection)
