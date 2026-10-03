import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent
LOG_DIR = WEB_DIR / "logs"
START_DIR = WEB_DIR / "static"
UPLOAD_DIR = WEB_DIR / "images"
LOG_FILE = LOG_DIR / "app.log"

DB_HOST = "db"
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_SCHEME = os.environ.get("DB_SCHEME", "public")
DB_NAME = os.environ.get("DB_NAME", "images_db")
DB_USER = os.environ.get("DB_USER", "root_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/backup"))
BACKUP_INTERVAL_MINUTES = int(os.environ.get("BACKUP_INTERVAL_MINUTES", 2))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AppLogger")


def create_backup():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = ( BACKUP_DIR / f"backup_{timestamp}.sql" )
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASSWORD or ""
    command =[ "pg_dump", "-h", DB_HOST, "-p", str(DB_PORT), "-U", DB_USER, "-d", DB_NAME,]
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
            logger.info( "Backup failed:" )
            logger.info(result.stderr)
            backup_file.unlink(missing_ok=True)
            return False

        logger.info(f"Backup successfully created: {backup_file}" )
        return True
    except Exception as e:
        logger.info( f"Unexpected backup error: {e}" )
        backup_file.unlink( missing_ok=True )
        return False


def main():
    while True:
        create_backup()
        logger.info(f"Next backup in {BACKUP_INTERVAL_MINUTES} minutes" )
        time.sleep( BACKUP_INTERVAL_MINUTES * 60 )



if __name__ == "__main__":
    main()
