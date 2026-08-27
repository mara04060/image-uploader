from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import re


HOST = "0.0.0.0"
PORT = 8000

WEB_DIR = Path(__file__).resolve().parent
START_DIR = WEB_DIR / "static"
UPLOAD_DIR = WEB_DIR / "images"


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

        content_type = self.headers.get("Content-Type", "")
        boundary = re.search(
            r'boundary="?([^";]+)"?',
            content_type
        )

        if not boundary:
            self.send_error(400, "No boundary")
            return

        boundary = boundary.group(1).encode()
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length)
        parts = body.split(b"--" + boundary)
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

            data = data.rstrip(b"\r\n")
            filename = Path(filename).name

            with open(UPLOAD_DIR / filename, "wb") as file:
                file.write(data)


        self.send_response(200)
        self.end_headers()


server = ThreadingHTTPServer(
    (HOST, PORT),
    Handler
)

print(
    f"Python server started on http://localhost:{PORT}",
    flush=True
)

server.serve_forever()