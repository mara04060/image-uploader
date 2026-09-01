import json
import logging
import re
import uuid
from functools import wraps
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

HOST = "0.0.0.0"
PORT = 8000

WEB_DIR = Path(__file__).resolve().parent
LOG_DIR = WEB_DIR / "logs"
START_DIR = WEB_DIR / "static"
UPLOAD_DIR = WEB_DIR / "images"
LOG_FILE = LOG_DIR / "app.log"

ALLOWED_EXTENSIONS = {".jpg", ".png", ".gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024

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
    # Content - Type: multipart / form - data;
    # boundary = ----WebKitFormBoundaryABC123

    #Парсинг условно на части
    # boundary = b"----WebKitFormBoundaryABC123"
    # marker = b"--" + boundary

    # ------WebKitFormBoundaryABC123\r\n
    # Content - Disposition: form - data;
    # name = "file";
    # filename = "photo.jpg"\r\n
    # Content - Type: image / jpeg\r\n
    # \r\n
    # [БАЙТЫ JPEG - ФАЙЛА]
    # \r\n
    # ------WebKitFormBoundaryABC123\r\n
    # Content - Disposition: form - data;
    # name = "file";
    # filename = "image.png"\r\n
    # Content - Type: image / png\r\n
    # \r\n
    # [БАЙТЫ PNG - ФАЙЛА]
    # \r\n
    # ------WebKitFormBoundaryABC123 - -\r\n(Запрос закончился)

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
def validate_file(file_name: str,data: bytes,) -> None:
    safe_name = Path(file_name).name
    extension = Path(safe_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise FileValidationError(f"Непідтримуваний формат файлу: {extension or '<none>'}. Доступні: {allowed}" )

    if len(data) > MAX_FILE_SIZE:
        raise FileValidationError(f"File '{safe_name}' is too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB" )


def _generate_unique_filename(file_name: str) -> str:
    safe_name = Path(file_name).name
    path = Path(safe_name)
    return (f"{path.stem}_{uuid.uuid4().hex}{path.suffix.lower()}" )


def validate_files( files,):
    validated_files = []
    for file_name, data in files:
        validate_file(file_name, data)
        unique_name = _generate_unique_filename(file_name)
        validated_files.append((unique_name, data))
    return validated_files

def validate_uploaded_files(func):
    @wraps(func)
    def wrapper(handler):
        files = extract_file_data(handler)
        validated_files = validate_files(files)
        return func(handler, validated_files)
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
def json_response(handler,status: int,message: str,file_names,):
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

    for file_name, data in files:
        logger.info("Starting upload of '%s'",file_name,)
        save_file(file_name, data)
        file_names.append(file_name)
        logger.info("File '%s' uploaded successfully",file_name,)

    json_response(handler,200,"Файли успішно завантажені", file_names,)


# HTTP Handler
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__( *args, directory=str(START_DIR),**kwargs,)

    def do_POST(self):
        if self.path != "/upload":
            logger.warning("Unknown route: %s",self.path,)
            self.send_error(404)
            return
        upload_files(self)


# Server
def create_server() -> ThreadingHTTPServer:
    try:
        return ThreadingHTTPServer((HOST, PORT), Handler,)
    except OSError as e:
        logger.exception("Failed to start server on %s:%s",HOST, PORT,)
        raise AppError(f"Failed to start server on {HOST}:{PORT}") from e

def main():
    server = create_server()
    logger.info("Python server started on http://localhost:%s/",PORT,)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()