from configparser import ConfigParser
from pathlib import Path


def get_database_url() -> str:
    config_path = Path(__file__).resolve().with_name("database.ini")
    config = ConfigParser(interpolation=None)
    with config_path.open(encoding="utf-8") as config_file:
        config.read_file(config_file)
    return config["database"]["url"]

