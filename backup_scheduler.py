import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent
LOG_DIR = WEB_DIR / "logs"
LOG_FILE = LOG_DIR / "backup.log"

POSTGRES_HOST = "postgres"
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", 5432))
POSTGRES_SCHEME = os.environ.get("POSTGRES_SCHEME", "public")
POSTGRES_NAME = os.environ.get("POSTGRES_NAME", "images_db")
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


def create_backup():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = ( BACKUP_DIR / f"backup_{timestamp}.sql" )
    env = os.environ.copy()
    env["PGPASSWORD"] = POSTGRES_PASSWORD or ""
    command =[ "pg_dump", "-h", POSTGRES_HOST, "-p", str(POSTGRES_PORT), "-U", POSTGRES_USER, "-d", POSTGRES_NAME, ]
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


def main():
    while True:
        create_backup()
        logger.info(f"Next backup in {BACKUP_INTERVAL_MINUTES} minutes" )
        time.sleep( BACKUP_INTERVAL_MINUTES * 60 )



if __name__ == "__main__":
    main()
