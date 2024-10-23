import os
from logging.config import fileConfig
from logging import getLogger
from pathlib import Path
import pkgutil
import importlib

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
if config is None or config.config_file_name is None:
    raise Exception("No config found")

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

from app.core.config import settings # noqa

def import_all_models(package_name: str, ignore: list[str] = []):
    print("Discovered models:")
    print("==============================")
    # Import the package itself
    package = importlib.import_module(package_name)

    # Check if the package has a __path__ attribute
    if not hasattr(package, '__path__'):
        raise ImportError(f"{package_name} is not a package")

    package_path = package.__path__

    # Iterate through all modules in the package
    for _, module_name, is_pkg in pkgutil.walk_packages(package_path, package_name + '.'):
        if any([module_name.startswith(i) for i in ignore]) or is_pkg:
            continue
        if module_name.endswith('.models'):
            importlib.import_module(module_name)
            print(f"{module_name}")
    print("==============================")

from sqlmodel import SQLModel
import_all_models('app') # all tables contained in modules under app.models should inherit from SQLModel, populating SQLModel.metadata as they are imported

target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    return str(settings.SQLALCHEMY_DATABASE_URI)


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        raise Exception("No config section found")
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True
        )

        with context.begin_transaction() as transaction:
            context.run_migrations()
            if 'dry-run' in context.get_x_argument():
                print('Dry-run succeeded; now rolling back transaction...')
                transaction.rollback()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
