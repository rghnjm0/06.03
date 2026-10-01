"""Alembic environment for the project's SQLite database."""
from logging.config import fileConfig
import os
from alembic import context
from sqlalchemy import create_engine, pool

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.environ.get('UYUT_DB_PATH', os.path.join(base_dir, 'hotel_management.db'))
config.set_main_option('sqlalchemy.url', 'sqlite:///' + db_path.replace('\\', '/'))


def run_migrations_offline():
    context.configure(url=config.get_main_option('sqlalchemy.url'),
                      literal_binds=True, dialect_opts={'paramstyle': 'named'},
                      render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = create_engine(config.get_main_option('sqlalchemy.url'),
                                poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
