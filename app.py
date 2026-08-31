import json
import logging
import uuid
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import re


HOST = "0.0.0.0"
PORT = 8000

WEB_DIR = Path(__file__).resolve().parent
LOG_DIR = WEB_DIR / "logs"
START_DIR = WEB_DIR / "static"
UPLOAD_DIR = WEB_DIR / "images"
LOG_FILE = LOG_DIR / "app.log"

ALLOWED_EXTENSIONS = {".jpg", ".png", ".gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024

# Вдруг директорию забіли создать
LOG_DIR.mkdir(parents=True, exist_ok=True)

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



# Exceptions
class UploadError(Exception):
    def __init__(
        self,
        message: str,
        file_name: str | None = None,
        status_code: int = 400
    ):
        super().__init__(message)

        self.message = message
        self.file_name = file_name
        self.status_code = status_code

# Files not found
class NoFilesError(UploadError):
    pass

# Not in ALLOWED_EXTENSIONS
class InvalidFileTypeError(UploadError):
    pass

# Limit max size
class FileTooLargeError(UploadError):
    pass

# Error save file
class FileSaveError(UploadError):
    def __init__(self, message: str, file_name: str):
        super().__init__(
            message=message,
            file_name=file_name,
            status_code=500
        )

# Error parsing multi-form
class MultipartError(UploadError):
    pass



def _read_body(handler) -> bytes:
    length = int(handler.headers.get("Content-Length", 0))
    return handler.rfile.read(length)


def _extract_boundary(content_type: str) -> bytes:
    match = re.search(
        r'boundary="?([^";]+)"?',
        content_type
    )

    if not match:
        raise MultipartError("Could not extract multipart boundary")
    return match.group(1).encode()


def _parse_multipart_body( body: bytes, boundary: bytes) -> list[tuple[str, bytes]]:
    parts = body.split(b"--" + boundary)
    extracted_files = []

    for part in parts:
        if not part or part == b"--"  or part.startswith(b"--\r\n"):
            continue

        header_body_split = part.find(b"\r\n\r\n")
        if header_body_split == -1:
            continue

        headers_raw = part[:header_body_split].decode("utf-8",errors="ignore" )
        data = part[ header_body_split + 4:].rstrip(b"\r\n")
        filename_match = re.search( r'filename="([^"]+)"', headers_raw )

        if filename_match and data:
            filename = filename_match.group(1)
            extracted_files.append((filename, data) )
    return extracted_files

def extract_file_data(handler) -> list[tuple[str, bytes]]:
    content_type = handler.headers.get("Content-Type","" )
    files = _parse_multipart_body( _read_body(handler), _extract_boundary(content_type) )
    if not files:
        raise NoFilesError("No files provided")
    return files

def validate_file(file_name: str, data: bytes) -> None:
    file_extension = Path(file_name).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise InvalidFileTypeError(
            f"Непідтримуваний формат файлу: {file_extension}. Доступні лише: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            file_name=file_name
            )

    if len(data) > MAX_FILE_SIZE:
        raise FileTooLargeError( ( "File too large. Max size allowed is {MAX_FILE_SIZE // (1024 * 1024)}MB" ),
                                 file_name=file_name )

def validate_files(files):
    try:
        for file_name, data in files:
            logger.info(f"Validating file '{file_name}'")
            validate_file(file_name, data)
    except (InvalidFileTypeError) as e:
        logger.warning(f"")

def generate_filename(  original_name: str) -> str:
    path = Path(original_name)
    return (f"{path.stem} {uuid.uuid4().hex} {path.suffix.lower()}" )


def save_file( file_name: str, data: bytes) -> None:
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True )
        file_path = UPLOAD_DIR / file_name
        with open(file_path, "wb") as file:
            file.write(data)
    except OSError as error:
        raise FileSaveError(f"Could not save file: {error}",file_name=file_name ) from error
    logger.info(
        f"File '{file_name}' successfully saved"
    )

def json_response(handler, status: int, message: str, file_names=None) -> None:
    response_data = {
        "status": status,
        "message": message,
        "file": file_names
    }

    response_body = json.dumps( response_data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type","application/json; charset=utf-8" )
    handler.send_header("Content-Length",str(len(response_body)))
    handler.end_headers()
    handler.wfile.write(response_body)

class Handler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__( *args,directory=str(START_DIR),**kwargs)

    def do_POST(self):

        if self.path != "/upload":
            logger.warning( f"Bad route {self.path}")
            self.send_error(404)
            return

        try:
            files = extract_file_data(self)

            uploaded_files = []

            for file_name, data in files:
                new_file_name = generate_filename(file_name )
                logger.info(f"Starting upload: '{file_name}' -> '{new_file_name}'")
                save_file(new_file_name,data)
                uploaded_files.append(new_file_name)
            json_response(self,200,"Файли успішно завантажені",uploaded_files)

        except UploadError as error:
            logger.warning(
                f"Upload error"
                f"{f' for {error.file_name}' if error.file_name else ''}: "
                f"{error.message}"
            )

            json_response(self,error.status_code,error.message,error.file_name)

        except Exception:
            logger.exception("Unexpected server error")

            json_response(self,500,"Internal server error")


server = ThreadingHTTPServer((HOST, PORT), Handler)
logger.info(f"Python server started on http://localhost:8080/")
server.serve_forever()