import logging
import os
import subprocess
import time
from datetime import datetime
from functools import wraps
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent
LOG_DIR = WEB_DIR / "logs"
LOG_FILE = LOG_DIR / "backup.log"

POSTGRES_HOST = "postgres"
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", 5432))
POSTGRES_SCHEME = os.environ.get("POSTGRES_SCHEME", "public")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "images_db")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "root_user")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "backups"))
BACKUP_INTERVAL_MINUTES = int(os.environ.get("BACKUP_INTERVAL_MINUTES", 2))

BACKUP_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BackUpSystem")


class ConfigurationError(Exception):
    """Backup scheduler configuration is missing or invalid."""


def validate_positive_integer(name: str, default: int, maximum: int | None = None) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    if parsed <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    if maximum is not None and parsed > maximum:
        raise ConfigurationError(f"{name} must not exceed {maximum}")
    return parsed


def validate_backup_config(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global POSTGRES_PORT, POSTGRES_SCHEME, POSTGRES_DB
        global POSTGRES_USER, POSTGRES_PASSWORD, BACKUP_DIR
        global BACKUP_INTERVAL_MINUTES

        try:
            POSTGRES_PORT = validate_positive_integer(
                "POSTGRES_PORT", 5432, 65535
            )
            BACKUP_INTERVAL_MINUTES = validate_positive_integer(
                "BACKUP_INTERVAL_MINUTES", 5
            )

            POSTGRES_SCHEME = os.environ.get(
                "POSTGRES_SCHEME", "public"
            ).strip()
            POSTGRES_DB = os.environ.get(
                "POSTGRES_DB", "images_db"
            ).strip()
            POSTGRES_USER = os.environ.get(
                "POSTGRES_USER", "root_user"
            ).strip()
            POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")

            if not POSTGRES_SCHEME:
                raise ConfigurationError("POSTGRES_SCHEME must not be empty")
            if not POSTGRES_DB:
                raise ConfigurationError("POSTGRES_DB must not be empty")
            if not POSTGRES_USER:
                raise ConfigurationError("POSTGRES_USER must not be empty")
            if not POSTGRES_PASSWORD:
                raise ConfigurationError("POSTGRES_PASSWORD must not be empty")

            backup_dir = os.environ.get("BACKUP_DIR", "backups").strip()
            if not backup_dir:
                raise ConfigurationError("BACKUP_DIR must not be empty")
            BACKUP_DIR = Path(backup_dir)
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        except ConfigurationError as error:
            logger.error("Invalid backup scheduler configuration: %s", error)
            raise

        return func(*args, **kwargs)
    return wrapper


@validate_backup_config
def create_backup():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = ( BACKUP_DIR / f"backup_{timestamp}.sql" )
    env = os.environ.copy()
    env["PGPASSWORD"] = POSTGRES_PASSWORD or ""
    command =[ "pg_dump", "-h", POSTGRES_HOST, "-p", str(POSTGRES_PORT), "-U", POSTGRES_USER, "-d", POSTGRES_DB, ]
    logger.info( f"Creating backup: {backup_file}" )
    try:
        with backup_file.open("w", encoding="utf-8") as file:
            result = subprocess.run(
                command,
                env=env,
                stdout=file,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

        if result.returncode != 0:
            logger.error( "Backup failed:" )
            logger.error(result.stderr)
            backup_file.unlink(missing_ok=True)
            return False

        logger.info(f"Backup successfully created: {backup_file}" )
        return True
    except Exception as e:
        logger.error( f"Unexpected backup error: {e}" )
        backup_file.unlink( missing_ok=True )
        return False


@validate_backup_config
def main():
    while True:
        create_backup()
        logger.info(f"Next backup in {BACKUP_INTERVAL_MINUTES} minutes" )
        time.sleep( BACKUP_INTERVAL_MINUTES * 60 )



if __name__ == "__main__":
    main()