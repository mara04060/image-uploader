import logging
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


def get_boundary(content_type):
    match = re.search(r'boundary="?([^";]+)"?', content_type)

    if not match:
        raise ValueError("No boundary")

    return b"--" + match.group(1).encode()


def get_filename(headers):
    match = re.search(rb'filename="([^"]*)"', headers)

    if not match:
        return None

    return Path(
        match.group(1).decode("utf-8", errors="replace")
    ).name


def validate_file(filename, data):
    if not filename:
        raise ValueError("No filename")

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Invalid file extension. Allowed: {ALLOWED_EXTENSIONS}"
        )

    if len(data) > MAX_FILE_SIZE:
        raise ValueError(
            "File is too large. Maximum size is 5 MiB."
        )


def save_file(filename, data):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with open(UPLOAD_DIR / filename, "wb") as file:
        file.write(data)


def multy_parts(self, body, boundary):
    for part in body.split(boundary):
        if b'filename="' not in part:
            continue

        headers, data = part.split(b"\r\n\r\n", 1)
        filename = self.get_filename(headers)

        if not filename:
            continue

        data = data.rstrip(b"\r\n")

        self.validate_file(filename, data)
        self.save_file(filename, data)

        logger.info(f"File uploaded successfully: {filename}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"File uploaded successfully")
        return

class Handler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            directory=str(START_DIR),
            **kwargs
        )

    def do_POST(self):
        if self.path != "/upload":
            self.send_error(404)
            return

        try:
            boundary = get_boundary( self.headers.get("Content-Type", "") )
            length = int(self.headers["Content-Length"])
            multy_parts(self, self.rfile.read(length), boundary)
            self.send_error(400, "No file found in request")

        except ValueError as error:
            logger.warning(str(error))
            self.send_error(400, str(error))


server = ThreadingHTTPServer(
    (HOST, PORT),
    Handler
)

print(
    f"Python server started on http://localhost:{PORT}",
    flush=True
)

server.serve_forever()