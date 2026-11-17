from configparser import ConfigParser
from pathlib import Path

from sqlalchemy import create_engine, text

from models import Base


def get_database_url() -> str:
    config_path = Path(__file__).resolve().with_name("database.ini")
    config = ConfigParser(interpolation=None)
    with config_path.open(encoding="utf-8") as config_file:
        config.read_file(config_file)
    return config["database"]["url"]


engine = create_engine(get_database_url(),
                       plugins=["geoalchemy2"])


def truncate_all(engine, schema="public", exclude=("alembic_version", "spatial_ref_sys")):
    quote = engine.dialect.identifier_preparer.format_table
    tables = [quote(t) for t in Base.metadata.sorted_tables if t.name not in exclude]
    if not tables:
        return
    stmt = f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"
    with engine.begin() as conn:
        conn.execute(text(stmt))
