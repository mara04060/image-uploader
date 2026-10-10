import json
import logging
import os
import re
import time
import uuid
from functools import wraps
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

import psycopg
from psycopg import Connection

HOST = "0.0.0.0"
APP_PORT= 8000

WEB_DIR = Path(__file__).resolve().parent
LOG_DIR = WEB_DIR / "logs"
START_DIR = WEB_DIR / "static"
UPLOAD_DIR = WEB_DIR / "images"
LOG_FILE = LOG_DIR / "app.log"

POSTGRES_HOST = "postgres"
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", 5432))
POSTGRES_SCHEME = os.environ.get("POSTGRES_SCHEME", "public")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "images_db")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "root_user")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "123")

ALLOWED_EXTENSIONS = set(os.environ.get("ALLOWED_EXTENSIONS", "jpg, png, gif").lower().strip().split(","))
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", 5)) * 1024 * 1024
ITEMS_PER_PAGE = 10

LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("AppLogger")

# Custom exceptions
class AppError(Exception):
    pass


class RequestError(AppError):
    pass


class MultipartError(RequestError):
    pass


class FileValidationError(AppError):
    pass


class FileSaveError(AppError):
    pass



class ImageError(Exception):
    """Базовая ошибка обработки изображения."""


class ImageValidationError(ImageError):
    """Файл не прошёл валидацию."""


class ImageFileWriteError(ImageError):
    """Не удалось записать файл на диск."""


class ImageFileDeleteError(ImageError):
    """Не удалось удалить файл с диска."""


class ImageDatabaseInsertError(ImageError):
    """Не удалось создать запись в БД."""


class ImageDatabaseDeleteError(ImageError):
    """Не удалось удалить запись из БД."""


class ImageDatabaseUpdateError(ImageError):
    """Не удалось обновить запись в БД."""


# DB Connection
def get_db_connection() -> Connection:
    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )

def wait_for_database():
    while True:
        try:
            with get_db_connection() as connection:
                execute_sql_file(connection, 'install.sql')
            logger.info("Database connection established.")
            return None
        except psycopg.Error as e:
            logger.warning( f"Could not connect to database: {e}" )
            time.sleep(1)


def db_function( connection: Connection, function_name: str, *args: Any,) -> Any:
    placeholders = ", ".join(["%s"] * len(args))
    sql = f"SELECT {function_name}({placeholders})"
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, args)
            row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        connection.rollback()
        raise
# execute only start. create function and Create table
def execute_sql_file( connection: Connection, sql_file='install.sql') -> None:
    file_path = Path(sql_file)
    if not file_path.is_file():
        raise FileNotFoundError(f"SQL-файл не знайдено: {file_path}")
    sql_script = file_path.read_text(encoding="utf-8")
    if not sql_script.strip():
        logger.warning("SQL-файл пустий: %s", file_path)
        raise ValueError(f"SQL-файл пустой: {file_path}")
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql_script)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    logger.info( "SQL-файл побудовано: %s",file_path, )


def get_image_filename(connection: Connection, image_id: int,) -> str | None:
    return db_function( connection,f"{POSTGRES_SCHEME}.get_image_filename",image_id,)

def insert_image(connection: Connection, file_name: str, original_name: str, size: int, file_type: str,) -> int:
    result = db_function(
        connection,f"{POSTGRES_SCHEME}.create_image",file_name, original_name, size, file_type,)
    connection.commit()
    return result

def get_pagination( connection: Connection, page: int = 1,) -> dict:
    return db_function( connection,f"{POSTGRES_SCHEME}.get_pagination",page, ITEMS_PER_PAGE,)

# Request helpers
def _read_body(handler):
    content_length = handler.headers.get("Content-Length")
    if content_length is None:
        raise RequestError("Content-Length header is missing")

    try:
        length = int(content_length)
    except ValueError as e:
        raise RequestError("Invalid Content-Length header") from e

    if length < 0:
        raise RequestError("Invalid Content-Length value")

    if length > MAX_FILE_SIZE:
        raise RequestError(f"Request is too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB")

    try:
        return handler.rfile.read(length)
    except OSError as e:
        raise RequestError("Failed to read request body") from e


def _extract_boundary(content_type: str) -> bytes:
    if not content_type:
        raise MultipartError("Content-Type header is missing")

    match = re.search(r'boundary="?([^";]+)"?', content_type, re.IGNORECASE,)

    if not match:
        raise MultipartError("Multipart boundary was not found" )
    return match.group(1).encode("utf-8")


# Multipart processing
def _find_multipart_parts( body: bytes, boundary: bytes,):
    marker = b"--" + boundary
    parts: list[bytes] = []
    position = 0

    while True:
        boundary_start = body.find(marker, position)
        if boundary_start == -1:
            break

        part_start = boundary_start + len(marker)

        # Final boundary: --boundary--
        if body[part_start:part_start + 2] == b"--":
            break

        # Normal boundary must be followed by CRLF.(to be continue...
        if body[part_start:part_start + 2] == b"\r\n":
            part_start += 2

        next_boundary = body.find(marker, part_start)
        if next_boundary == -1:
            raise MultipartError("Multipart body has an incomplete boundary")
        part = body[part_start:next_boundary]

        if part.endswith(b"\r\n"):
            part = part[:-2]

        if part:
            parts.append(part)
        position = next_boundary

    if not parts:
        raise MultipartError("No multipart parts found")
    return parts


def _extract_file_from_part(part: bytes,):
    separator = b"\r\n\r\n"
    header_end = part.find(separator)

    if header_end == -1:
        raise MultipartError("Multipart part has invalid headers")

    headers_raw = part[:header_end].decode("utf-8", errors="replace",)
    file_body = part[header_end + len(separator):]
    filename_match = re.search(r'filename="([^"]*)"', headers_raw, re.IGNORECASE,)

    if not filename_match:
        return None

    filename = filename_match.group(1).strip()
    if not filename:
        raise MultipartError("Uploaded file has an empty filename")

    if not file_body:
        raise FileValidationError(f"Uploaded file '{filename}' is empty")
    return filename, file_body


def _parse_multipart_body(body: bytes,boundary: bytes,):
    parts = _find_multipart_parts(body, boundary)
    files: list[tuple[str, bytes]] = []

    for part in parts:
        file_data = _extract_file_from_part(part)

        if file_data is not None:
            files.append(file_data)

    if not files:
        raise RequestError("No files provided")
    return files


def extract_file_data(handler) -> list[tuple[str, bytes]]:
    content_type = handler.headers.get("Content-Type", "")
    boundary = _extract_boundary(content_type)
    body = _read_body(handler)
    return _parse_multipart_body(body, boundary)


# File validation
def validate_file(file_name: str,data: bytes,):
    safe_name = Path(file_name).name
    extension = get_file_extension(safe_name)
    file_size = len(data)

    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise FileValidationError(f"Непідтримуваний формат файлу: {extension or '<none>'}. Доступні: {allowed}" )

    if file_size > MAX_FILE_SIZE:
        raise FileValidationError(f"File '{safe_name}' is too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB" )
    return (safe_name, extension, file_size)

def get_file_extension(file_name):
    return Path(file_name).suffix.lower().strip(".")

def _generate_unique_filename(file_name: str) -> str:
    safe_name = Path(file_name).name
    return (f"{uuid.uuid4().hex}.{get_file_extension(safe_name)}")


def validate_files( files,):
    validated_files = []
    for file_name, data in files:
        original_name, ext_file, file_size = validate_file(file_name, data)
        unique_name = _generate_unique_filename(file_name)
        validated_files.append((unique_name, original_name, ext_file, file_size, data))
    return validated_files

def validate_uploaded_files(func):
    @wraps(func)
    def wrapper(handler):
        files = extract_file_data(handler)
        return func(handler, validate_files(files))
    return wrapper


def handle_upload_errors(func):
    @wraps(func)
    def wrapper(handler):
        try:
            return func(handler)

        except FileValidationError as e:
            logger.warning("File validation failed: %s",e,)
            json_response(handler,400,str(e),)

        except MultipartError as e:
            logger.warning("Multipart processing failed: %s",e, )
            json_response(handler,400,str(e),)

        except RequestError as e:
            logger.warning("Request error: %s",e,)
            json_response(handler,400,str(e),)

        except FileSaveError as e:
            logger.error("File save error: %s",e,)
            json_response(handler,500,str(e),)

        except Exception:
            logger.exception("Unexpected server error")
            json_response(handler,500,"Internal server error",)
    return wrapper


# File saving
def save_file(file_name: str,data: bytes,):
    try:
        UPLOAD_DIR.mkdir(parents=True,exist_ok=True,)
        file_path = UPLOAD_DIR / Path(file_name).name
        with file_path.open("wb") as file:
            file.write(data)

    except OSError as e:
        logger.exception("Failed to save file '%s'",file_name,)
        raise FileSaveError(f"Failed to save file '{file_name}'") from e

    logger.info("Saved file '%s'",file_name,)


# HTTP response
def json_response(handler,status: int,message: str,file_names=None):
    response_data = {"status": status,"message": message,"file": file_names,}
    try:
        response_body = json.dumps(response_data,ensure_ascii=False,).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type","application/json; charset=utf-8",)
        handler.send_header("Content-Length",str(len(response_body)),)
        handler.end_headers()
        handler.wfile.write(response_body)

    except OSError:
        logger.exception("Failed to send HTTP response")


# Upload processing
@handle_upload_errors
@validate_uploaded_files
def upload_files(handler, files,):
    file_names: list[str] = []
    for file_name, original_name, ext_file, file_size, data in files:
        logger.info("Starting upload of '%s'",file_name,)
        save_file(file_name, data)
        logger.info(f"Insert in DB: {file_name}, {original_name}, {file_size}, {ext_file} ", )
        insert_image(get_db_connection(), file_name, original_name, file_size, ext_file )
        file_names.append(file_name)
        logger.info("File '%s' uploaded successfully",file_name,)

    json_response(handler,200,"Файли успішно завантажені", file_names,)


# HTTP Handler
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__( *args, directory=str(START_DIR),**kwargs,)

    def do_POST(self):
        if (self.path != "/upload"):
            logger.warning("Unknown route: %s",self.path,)
            self.send_error(404)
            return
        upload_files(self)


# Server
def create_server() -> ThreadingHTTPServer:
    try:
        return ThreadingHTTPServer((HOST, APP_PORT), Handler, )
    except OSError as e:
        logger.exception("Failed to start server on %s:%s", HOST, APP_PORT, )
        raise AppError(f"Failed to start server on {HOST}:{APP_PORT}") from e

def main():
    wait_for_database()
    server = create_server()
    logger.info("Python server started on http://localhost:%s/", APP_PORT, )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()