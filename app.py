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

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}


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

class Handler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            directory=str(START_DIR),
            **kwargs
        )

    def do_POST(self):
        if self.path != "/upload":
            logger.warning(f"Route not found: {self.path}")
            self.send_error(404)
            return

        content_type = self.headers.get("Content-Type", "")
        boundary = re.search(
            r'boundary="?([^";]+)"?',
            content_type
        )

        if not boundary:
            logger.error("Error uploading? not boundary in Content-Type")
            self.send_error(400, "No boundary")
            return

        boundary = boundary.group(1).encode()
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length)
        parts = body.split(b"--" + boundary)

        file_saved = False
        for part in parts:
            if b'filename="' not in part:
                continue

            headers, data = part.split(b"\r\n\r\n", 1)
            match = re.search(
                rb'filename="([^"]*)"',
                headers
            )

            if not match:
                continue

            filename = match.group(1).decode(
                "utf-8",
                errors="replace"
            )

            data = data.rstrip(b"\r\n--")  # Корректная очистка хвоста multipart
            filename = Path(filename).name

            if filename:
                file_ext = Path(filename).suffix.lower()
                if file_ext not in ALLOWED_EXTENSIONS:
                    logger.warning(f"Your file '{filename}':  ({file_ext}) is not allowed")
                    self.send_error(400, f"Invalid file extension. Only {ALLOWED_EXTENSIONS} are allowed.")
                    return

                UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
                with open(UPLOAD_DIR / filename, "wb") as file:
                    file.write(data)
                logger.info(f"File uploadind {filename}. Upload sucessfull !")
                file_saved = True

        if file_saved:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"File uploaded successfully")
        else:
            logger.warning("Not file in uploading")
            self.send_error(400, "No file found in request")


server = ThreadingHTTPServer(
    (HOST, PORT),
    Handler
)

print(
    f"Python server started on http://localhost:{PORT}",
    flush=True
)

server.serve_forever()