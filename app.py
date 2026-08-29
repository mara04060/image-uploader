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
MAX_FILE_SIZE = 1024 * 1024 * 5

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


def _read_body(handler) -> bytes:
    length = int(handler.headers.get("Content-Length", 0))
    return handler.rfile.read(length)

def _extract_boundary(content_type: str) -> bytes:
    match = re.search(r'boundary="?([^";]+)"?', content_type)
    if match:
        return match.group(1).encode()
    logger.warning(f"Could not extract boundary from {content_type}")
    return b""

def _parse_multipart_body(body: bytes, boundary: bytes) -> list[tuple[str, bytes]]:
    parts = body.split(b"--" + boundary)
    extracted_files = []

    for part in parts:
        # TODO изменить тут все по людски ибо не нравиться но на переиспользование НЕ годиться посмотреть как в нормальных фреймворках делают
        # Тупо вырезка пустых данных которые мне мешают... может
        if not part or part == b"--" or part.startswith(b"--\r\n"):
            continue

        # Вконце потока идет двойной перевод строки, воспользуюсь этим
        header_body_split = part.find(b"\r\n\r\n")
        if header_body_split == -1:
            continue

        headers_raw = part[:header_body_split].decode("utf-8", errors="ignore")
        # адаляю излишние переносытела файла (\r\n)
        data = part[header_body_split + 4:].rstrip(b"\r\n")

        # Это спасибо Макс подсказал.. реально работает...
        filename_match = re.search(r'filename="([^"]+)"', headers_raw)
        if filename_match and data:
            filename = filename_match.group(1)
            extracted_files.append((filename, data))

    return extracted_files

def extract_file_data(handler) -> list[tuple[str, bytes]]:
    content_type = handler.headers.get("Content-Type", "")
    boundary = _extract_boundary(content_type)
    if not boundary:
        logger.warning("No body in boundary")
        return []

    body = _read_body(handler)
    return _parse_multipart_body(body, boundary)

def save_file(full_filename, data):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with open(UPLOAD_DIR / full_filename, "wb") as file:
        file.write(data)
    logger.info(f"Saved {full_filename} ")

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # logger.info(f"Welcome => {HOST} : {PORT} /? ars = {args} and kwargs ={kwargs}")
        super().__init__(*args, directory=str(START_DIR),**kwargs)

    def do_POST(self):
        if self.path != "/upload":
            logger.warning(f"Bad route {self.path}")
            self.send_error(404)
            return

        files = extract_file_data(self)
        if not files:
            self.send_error(400, "No files provided")
            return

        for file_name, data in files:
            file_extension = Path(file_name).suffix
            if file_extension in ALLOWED_EXTENSIONS:
                logger.info(f"file name = {file_name} --> start downloading")
                save_file(file_name, data)
                logger.info(f"")
            else:
                logger.warning(f"Invalid file = {file_name} extension. Not in {ALLOWED_EXTENSIONS}")


server = ThreadingHTTPServer((HOST, PORT), Handler)
print(f"Python server started on http://localhost:{PORT}", flush=True)
server.serve_forever()