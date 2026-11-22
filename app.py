import json
import logging
import os
import re
import time
import uuid
import warnings
from functools import wraps
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs

import psycopg
from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning
from psycopg import Connection

HOST = "0.0.0.0"
APP_PORT = 8000

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

def parse_allowed_extensions(value: str) -> set[str]:
    return {
        extension.strip().lower()
        for extension in value.split(",")
        if extension.strip()
    }


ALLOWED_EXTENSIONS = parse_allowed_extensions(
    os.environ.get("ALLOWED_EXTENSIONS", "jpg,png,gif,jpeg")
)
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_REQUEST_SIZE = MAX_FILE_SIZE * 10
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
    """Bases error aplication."""

class RequestError(AppError):
    """Error HTTP-зrequest."""

class MultipartError(RequestError):
    """помилка розбору multipart/form-data."""

class ImageError(AppError):
    """Bases Error Images."""

class ImageValidationError(ImageError):
    """File not validation and verification."""

class ImageFileWriteError(ImageError):
    """No write file on Disk"""

class ImageFileDeleteError(ImageError):
    """Not delete file on disk"""

class ImageDatabaseInsertError(ImageError):
    """Not inserted info in DB"""

class ImageDatabaseDeleteError(ImageError):
    """No delete info in DB"""

class ImageNotFoundError(ImageError):
    """Image not found"""

class PaginationError(RequestError):
    """Not correct pagination settings"""


class ConfigurationError(AppError):
    """Application configuration is missing or invalid."""


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


def validate_app_config(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global APP_PORT, POSTGRES_PORT, POSTGRES_SCHEME, POSTGRES_DB
        global POSTGRES_USER, POSTGRES_PASSWORD, ALLOWED_EXTENSIONS
        global MAX_FILE_SIZE, MAX_REQUEST_SIZE

        try:
            APP_PORT = validate_positive_integer("APP_PORT", 8000, 65535)
            POSTGRES_PORT = validate_positive_integer("POSTGRES_PORT", 5432, 65535)

            for name in ("POSTGRES_SCHEME", "POSTGRES_DB", "POSTGRES_USER"):
                if not os.environ.get(name, globals()[name]).strip():
                    raise ConfigurationError(f"{name} must not be empty")

            POSTGRES_SCHEME = os.environ.get("POSTGRES_SCHEME", "public").strip()
            POSTGRES_DB = os.environ.get("POSTGRES_DB", "images_db").strip()
            POSTGRES_USER = os.environ.get("POSTGRES_USER", "root_user").strip()
            POSTGRES_PASSWORD = os.environ.get(
                "POSTGRES_PASSWORD", "123"
            )

            ALLOWED_EXTENSIONS = parse_allowed_extensions(
                os.environ.get("ALLOWED_EXTENSIONS", "jpg,png,gif,jpeg")
            )
            if not ALLOWED_EXTENSIONS:
                raise ConfigurationError(
                    "ALLOWED_EXTENSIONS must contain at least one extension"
                )

            max_file_size_mb = validate_positive_integer(
                "MAX_FILE_SIZE", 5
            )
            MAX_FILE_SIZE = max_file_size_mb * 1024 * 1024
            MAX_REQUEST_SIZE = MAX_FILE_SIZE * 10
        except ConfigurationError as error:
            logger.error("Invalid application configuration: %s", error)
            raise

        return func(*args, **kwargs)
    return wrapper


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
        except (psycopg.Error, OSError, ValueError) as e:
            logger.warning("Database initialization failed: %s",e)
        time.sleep(1)


def db_function( connection: Connection, function_name: str, *args):
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
    try:
        result = db_function(connection,f"{POSTGRES_SCHEME}.create_image",file_name, original_name, size, file_type,)
        if result is None:
            logger.error("Database did not return the image ID")
            raise ImageDatabaseInsertError("Database did not return the image ID")
        return result
    except psycopg.Error as e:
        raise ImageDatabaseInsertError("Failed to create image database record") from e

def get_images(connection: Connection, page: int = 1):
    return db_function(connection, f"{POSTGRES_SCHEME}.get_images", page, ITEMS_PER_PAGE)

def get_pagination( connection: Connection, page: int = 1,) -> dict:
    return db_function( connection,f"{POSTGRES_SCHEME}.get_pagination",page, ITEMS_PER_PAGE,)

def delete_image( connection: Connection, image_id: int = 1):
    try:
        return db_function(connection, f"{POSTGRES_SCHEME}.delete_image", image_id)
    except psycopg.Error as e:
        raise ImageDatabaseDeleteError(f"Failed to delete image record: {image_id}") from e


# Request helpers
def _read_body(handler: SimpleHTTPRequestHandler) -> bytes:
    content_length = handler.headers.get("Content-Length")
    if content_length is None:
        raise RequestError("Content-Length header is missing")
    try:
        length = int(content_length)
    except ValueError as e:
        raise RequestError("Invalid Content-Length header") from e

    if length < 0:
        raise RequestError("Invalid Content-Length value")

    if length > MAX_REQUEST_SIZE:
        raise RequestError("Request exceeds the maximum allowed size")

    try:
        body = handler.rfile.read(length)
    except OSError as e:
        raise RequestError("Failed to read request body") from e

    if len(body) != length:
        raise RequestError("Incomplete request body")

    return body


def _extract_boundary(content_type: str) -> bytes:
    if not content_type:
        raise MultipartError("Content-Type header is missing")

    if not content_type.lower().startswith("multipart/form-data"):
        raise MultipartError("Content-Type must be multipart/form-data")

    match = re.search(r'boundary=(?:"([^"]+)"|([^;\s]+))',content_type, re.IGNORECASE)
    if not match:
        raise MultipartError("Multipart boundary was not found")
    boundary = match.group(1) or match.group(2)
    try:
        return boundary.encode("ascii")
    except UnicodeEncodeError as e:
        raise MultipartError("Invalid multipart boundary") from e


# Multipart processing
def _find_multipart_parts(body: bytes, boundary: bytes) -> list[bytes]:
    marker = b"--" + boundary
    parts: list[bytes] = []
    position = 0

    while True:
        boundary_start = body.find(marker, position)
        if boundary_start == -1:
            break

        part_start = boundary_start + len(marker)

        if body[part_start:part_start + 2] == b"--":
            break

        if body[part_start:part_start + 2] != b"\r\n":
            raise MultipartError("Invalid multipart boundary delimiter")
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


def _extract_file_from_part(part: bytes) -> tuple[str, bytes] | None:
    separator = b"\r\n\r\n"
    header_end = part.find(separator)

    if header_end == -1:
        raise MultipartError("Multipart part has invalid headers")

    headers_raw = part[:header_end].decode("utf-8", errors="replace")
    file_body = part[header_end + len(separator):]
    filename_match = re.search(r'filename="([^"]*)"', headers_raw, re.IGNORECASE,)

    if not filename_match:
        return None

    filename = filename_match.group(1).strip()
    if not filename:
        raise MultipartError("Uploaded file has an empty filename")

    if not file_body:
        raise ImageValidationError(f"Uploaded file '{filename}' is empty")
    return filename, file_body


def _parse_multipart_body(body: bytes,boundary: bytes) -> list[tuple[str, bytes]]:
    parts = _find_multipart_parts(body, boundary)
    files: list[tuple[str, bytes]] = []

    for part in parts:
        file_data = _extract_file_from_part(part)
        if file_data is not None:
            files.append(file_data)
    if not files:
        raise MultipartError("No files provided")
    return files


def extract_file_data( handler: SimpleHTTPRequestHandler) -> list[tuple[str, bytes]]:
    content_type = handler.headers.get("Content-Type", "")
    boundary = _extract_boundary(content_type)
    body = _read_body(handler)
    return _parse_multipart_body(body, boundary)


# File validation
def get_file_extension(file_name: str) -> str:
    return Path(file_name).suffix.lower().lstrip(".")


IMAGE_FORMAT_EXTENSIONS = {
    "JPEG": {"jpg", "jpeg"},
    "PNG": {"png"},
    "GIF": {"gif"},
}


def validate_image_content(file_name: str, data: bytes) -> str:
    if not data:
        raise ImageValidationError(f"File '{file_name}' is empty")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in IMAGE_FORMAT_EXTENSIONS:
                    raise ImageValidationError(
                        f"File '{file_name}' has unsupported image content"
                    )

                image.verify()

            with Image.open(BytesIO(data)) as image:
                detected_format = image.format
                width, height = image.size
                frame_count = getattr(image, "n_frames", 1)
                for frame_index in range(frame_count):
                    image.seek(frame_index)
                    image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise ImageValidationError(
            f"File '{file_name}' has invalid or corrupted image content"
        ) from error
    except (DecompressionBombError, DecompressionBombWarning) as error:
        raise ImageValidationError(
            f"File '{file_name}' is too large for safe image decoding"
        ) from error

    if width <= 0 or height <= 0:
        raise ImageValidationError(
            f"File '{file_name}' has invalid image dimensions"
        )

    return detected_format


def validate_file(file_name: str,data: bytes) -> tuple[str, str, int]:
    safe_name = Path(file_name.replace("\\", "/")).name
    extension = get_file_extension(safe_name)
    file_size = len(data)

    if not safe_name or safe_name in {".", ".."}:
        raise ImageValidationError("Invalid filename")

    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ImageValidationError(f"Unsupported file extension: {extension or '<none>'}. Allowed: {allowed}")

    if file_size == 0:
        raise ImageValidationError(f"File '{safe_name}' is empty")

    if file_size > MAX_FILE_SIZE:
        raise ImageValidationError(f"File '{safe_name}' exceeds the maximum size")

    detected_format = validate_image_content(safe_name, data)
    allowed_extensions = IMAGE_FORMAT_EXTENSIONS.get(detected_format, set())
    if extension not in allowed_extensions:
        raise ImageValidationError(
            f"File '{safe_name}' content format '{detected_format}' "
            f"does not match extension '{extension}'"
        )

    return safe_name, extension, file_size


def _generate_unique_filename(file_name: str) -> str:
    extension = get_file_extension(file_name)
    return f"{uuid.uuid4().hex}.{extension}"

def validate_files(files: list[tuple[str, bytes]]) -> list[tuple[str, str, str, int, bytes]]:
    validated_files = []
    for file_name, data in files:
        original_name, extension, file_size = validate_file( file_name, data)
        unique_name = _generate_unique_filename(original_name)
        validated_files.append( (unique_name,original_name,extension,file_size,data) )
    return validated_files

def validate_uploaded_files(func):
    @wraps(func)
    def wrapper(self):
        files = extract_file_data(self)
        validated_files = validate_files(files)
        return func(self, validated_files)
    return wrapper

def get_page(params) :
    page_values = params.get("page", ["1"])

    if len(page_values) != 1:
        raise ValueError("Parameter 'page' must be specified only once")
    try:
        page = int(page_values[0])
    except (ValueError, TypeError):
        raise ValueError("Parameter 'page' must be an integer") from None

    if page < 1:
        raise ValueError("Parameter 'page' must be greater than zero")
    return page

# File saving
def save_file(file_name: str, data: bytes) -> Path:
    safe_name = Path(file_name).name
    file_path = UPLOAD_DIR / safe_name
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        with file_path.open("xb") as file:
            file.write(data)
    except OSError as e:
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to remove partial file '%s'",safe_name)
        raise ImageFileWriteError( f"Failed to save file '{safe_name}'") from e
    logger.info("Saved file '%s'", safe_name)
    return file_path

def get_image_file_name( connection: Connection, image_id: int) -> str:
    file_name = get_image_filename(connection, image_id)
    if not file_name:
        raise ImageNotFoundError(f"Image not found: {image_id}")
    safe_name = Path(file_name).name
    if safe_name != file_name or safe_name in {"", ".", ".."}:
        raise ImageError(f"Invalid filename in database for image {image_id}")
    return safe_name

def delete_file(file_name: str) -> None:
    safe_name = Path(file_name).name
    if safe_name != file_name or safe_name in {"", ".", ".."}:
        logger.error("Invalid filename for deletion")
        raise ImageFileDeleteError("Invalid filename for deletion")
    file_path = UPLOAD_DIR / safe_name
    try:
        file_path.unlink()
    except FileNotFoundError as e:
        logger.warning("File not found on disk: %s",safe_name)
        raise ImageFileDeleteError(f"Image file not found: '{safe_name}'") from e
    except OSError as e:
        logger.exception("Failed to remove file '%s'",safe_name)
        raise ImageFileDeleteError( f"Failed to remove file '{safe_name}'" ) from e
    logger.info("File removed: %s", safe_name)

# JSON
def send_params(handler: SimpleHTTPRequestHandler,status: int,message: str,file_names: Any = None) -> None:
    send_json_dict(
        handler,
        {
            "status": status,
            "message": message,
            "file": file_names,
        },
    )


def send_json_dict(handler: SimpleHTTPRequestHandler,data: dict[str, Any]) -> None:
    status = int(data.get("status", 200))
    if not isinstance(status, int) or not 100 <= status <= 599:
        raise ValueError("Invalid HTTP status code")
    response_body = json.dumps( data, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type","application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin","*")
    handler.send_header("Content-Length", str(len(response_body)) )
    handler.end_headers()
    try:
        handler.wfile.write(response_body)
    except OSError:
        logger.warning("Client disconnected while receiving the response", exc_info=True )
        return
    logger.info("JSON response sent: status=%s", status)


# Upload processing
def handle_upload_errors(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except (RequestError, ImageValidationError) as e:
            logger.warning("Upload request rejected: %s", e)
            send_params(self, 400, str(e))
        except ImageFileWriteError as e:
            logger.error("Upload file operation failed: %s", e)
            send_params(self, 500, "Failed to save uploaded file")
        except ImageDatabaseInsertError as e:
            logger.error("Upload database operation failed: %s", e)
            send_params(self, 500, "Failed to save image metadata")
        except psycopg.Error:
            logger.exception("Database error during upload")
            send_params(self, 500, "Database error")
        except Exception:
            logger.exception("Unexpected error during upload")
            send_params(self, 500, "Internal server error")
    return wrapper

def _save_uploaded_files(files: list[tuple[str, str, str, int, bytes]]) -> list[Path]:
    saved_paths: list[Path] = []
    try:
        for file_name, _, _, _, data in files:
            saved_paths.append(save_file(file_name, data))
    except ImageFileWriteError:
        for file_path in reversed(saved_paths):
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Failed to clean up file '%s'",file_path.name)
        raise
    return saved_paths


def _insert_uploaded_files(connection: Connection, files: list[tuple[str, str, str, int, bytes]]) -> list[str]:
    file_names = []
    for file_name, original_name, extension, file_size, _ in files:
        insert_image( connection, file_name, original_name,file_size, extension )
        file_names.append(file_name)
    return file_names


@handle_upload_errors
@validate_uploaded_files
def upload_files( self, files: list[tuple[str, str, str, int, bytes]]) -> None:
    saved_paths = _save_uploaded_files(files)
    try:
        with get_db_connection() as connection:
            file_names = _insert_uploaded_files( connection, files)
    except Exception:
        for file_path in reversed(saved_paths):
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Failed to clean up file '%s'",file_path.name)
        raise

    logger.info("Successfully uploaded %s file(s)",len(file_names) )
    send_params(self,200,"Файлы успешно загружены", file_names )

def get_page(params: dict[str, list[str]]) -> int:
    page_values = params.get("page", ["1"])
    if len(page_values) != 1:
        raise PaginationError("Parameter 'page' must be specified only once" )
    try:
        page = int(page_values[0])
    except (ValueError, TypeError) as e:
        raise PaginationError("Parameter 'page' must be an integer") from e
    if page < 1:
        raise PaginationError("Parameter 'page' must be greater than zero")
    return page

def get_images_page(page: int) -> dict[str, Any]:
    with get_db_connection() as connection:
        items = get_images(connection, page)
        pagination = get_pagination(connection, page)
    return {
        "status": 200,
        "items": items,
        "pagination": pagination,
    }

def get_files_json(self,parsed) -> None:
    try:
        page = get_page(parse_qs(parsed.query))
        logger.info("Requested images page: %s", page)
        response_data = get_images_page(page)
        send_json_dict(self, response_data)
    except PaginationError as error:
        logger.warning("Invalid pagination parameters: %s", error)
        send_params(self, 400, str(error))
    except psycopg.Error:
        logger.exception("Database error during GET /images-list")
        send_params(self, 500, "Database error")
    except OSError:
        logger.exception("I/O error during GET /images-list" )
        send_params(self, 500, "Internal server error")

def delete_image_transaction(image_id: int) -> str:
    with get_db_connection() as connection:
        file_name = get_image_file_name(connection, image_id)
        logger.info("Starting deletion of image ID=%s, file=%s",image_id, file_name)

        deleted = delete_image(connection, image_id)
        if not deleted:
            connection.rollback()
            raise ImageNotFoundError(f"Image not found: {image_id}")

        try:
            delete_file(file_name)
        except ImageFileDeleteError:
            connection.rollback()
            raise

        try:
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return file_name


def delete_image_file(self,image_id: int) -> None:
    try:
        file_name = delete_image_transaction(image_id)
        send_params(self,200,f"Image deleted: {image_id}", file_name )
    except ImageNotFoundError as error:
        logger.info("Image deletion rejected: %s", error)
        send_params(self, 404, str(error))
    except ImageDatabaseDeleteError:
        logger.exception("Database error during deletion of image ID=%s",image_id )
        send_params(self, 500, "Database error")
    except psycopg.Error:
        logger.exception("Database error during deletion of image ID=%s",image_id )
        send_params(self, 500, "Database error")
    except ImageFileDeleteError:
        logger.exception("File deletion failed for image ID=%s",image_id)
        send_params(self,500,"Failed to remove image file")


# HTTP Handler
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__( *args,directory=str(START_DIR), **kwargs)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/upload":
            logger.warning("POST %s -> 404", parsed.path)
            send_params(self, 404, "Page not found")
            return
        upload_files(self)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/images-list":
            logger.warning("GET %s -> 404", parsed.path)
            send_params(self, 404, "Page not found")
            return
        get_files_json(self, parsed)


    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        match = re.fullmatch(r"/delete/(\d+)", parsed.path)
        if not match:
            logger.warning("DELETE %s -> 404", parsed.path)
            send_params(self, 404, "Image not found")
            return
        image_id = int(match.group(1))
        delete_image_file(self, image_id)


# Server
def create_server() -> ThreadingHTTPServer:
    try:
        return ThreadingHTTPServer((HOST, APP_PORT), Handler )
    except OSError as e:
        logger.exception("Failed to start server on %s:%s",HOST, APP_PORT )
        raise AppError(f"Failed to start server on {HOST}:{APP_PORT}" ) from e


@validate_app_config
def main() -> None:
    wait_for_database()
    server = create_server()
    logger.info("Python server started on http://localhost:%s/",APP_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()