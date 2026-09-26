import json
import logging
import uuid
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import re
import psycopg
from psycopg import Connection
import time

HOST = "0.0.0.0"
PORT = 8000

WEB_DIR = Path(__file__).resolve().parent
LOG_DIR = WEB_DIR / "logs"
START_DIR = WEB_DIR / "static"
UPLOAD_DIR = WEB_DIR / "images"
LOG_FILE = LOG_DIR / "app.log"

DB_HOST = "db"
DB_PORT = 5432
DB_SCHEME = "public"
DB_NAME = "images_db"
DB_USER = "root_user"
DB_PASSWORD = "passw123"

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

def create_table(connection: Connection):
    with connection.cursor() as cursor:
        cursor.execute(
        f"""     
        CREATE TABLE IF NOT EXISTS {DB_SCHEME}.images (
          id SERIAL PRIMARY KEY,
          filename TEXT NOT NULL,
          original_name TEXT NOT NULL,
          size INTEGER NOT NULL,
          upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          file_type TEXT NOT NULL
      );
        """
        )
        connection.commit()
    logger.info("Database table is ready!")

def insert_image(connection: Connection, file_name: str, original_name: str, size: int, file_type: str):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO public.images (
                filename,
                original_name,
                size,
                file_type
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (file_name, original_name, size, file_type)
        )
        connection.commit()
        logger.info(f"Insert data {file_name}, {original_name}, {size} , {file_type}")
        return cursor.fetchone()[0]

def get_images(connection: Connection, page: int = 1):
    offset = (page -1 ) * 10
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM public.images OFFSET %s LIMIT 10;",
            (offset, )
        )
        data_all = cursor.fetchall()
        connection.commit()
    logger.info("Select Data ", data_all )
    return data_all

def del_image(connection: Connection, image_id : int):
    with connection.cursor() as cursor:
        if image_id > 0:
            cursor.execute(
                "DELETE  FROM public.images WHERE id = %s;",
                (image_id,)
            )
            connection.commit()
    logger.info(f"Delete image id = %s", image_id)


def _read_body(handler) -> bytes:
    length = int(handler.headers.get("Content-Length", 0))
    return handler.rfile.read(length)

def _extract_boundary(content_type: str) -> bytes:
    match = re.search(r'boundary="?([^";]+)"?', content_type)
    if match:
        return match.group(1).encode()
    logger.warning(f"Could not extract boundary from {content_type}")
    return b""

#    TODO изменить тут все по людски ибо не нравиться но на переиспользование НЕ годиться посмотреть как в нормальных фреймворках делают
def _parse_multipart_body(body: bytes, boundary: bytes) -> list[tuple[str, bytes]]:
    parts = body.split(b"--" + boundary)
    extracted_files = []

    for part in parts:
         # Тупо вырезка пустых данных которые мне мешают... может
        if not part or part == b"--" or part.startswith(b"--\r\n"):
            continue

        header_body_split = part.find(b"\r\n\r\n")
        if header_body_split == -1:
            continue

        headers_raw = part[:header_body_split].decode("utf-8", errors="ignore")
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

def validate_files(self, files:list[tuple[str, bytes]]):
    for file_name, data in files:
        error_message = validate_file(file_name, data)
        file_name = Path(file_name).stem + "_" + uuid.uuid4().hex + Path(file_name).suffix.lower()
        if error_message:
            logger.warning(f"Rejected file '{file_name}': {error_message}")
            json_responce(self,400, error_message, file_name)
            return False
    return True

def validate_file(file_name: str, data: bytes) ->  str | None:
    #TODO вынести все сообщения как исключения. Пока долго заморачиваться
    file_extension = Path(file_name).suffix.lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        return f"IНепідтримуваний формат файлу: {file_extension}. доступны лише: {ALLOWED_EXTENSIONS}"

    if len(data) > MAX_FILE_SIZE:
        return f"File too large. Max size allowed is {MAX_FILE_SIZE // (1024 * 1024)}MB"

    return None

def _generate_unique_filename(file_name: str) -> str:
    safe_name = Path(file_name).name
    ext = Path(file_name).suffix.lower()
    path = Path(safe_name)
    return f"{path.stem}_{uuid.uuid4().hex}{ext}"

def save_file(full_filename, data):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with open(UPLOAD_DIR / full_filename, "wb") as file:
        file.write(data)
    logger.info(f"Saved {full_filename} ")

def json_responce(self, status, message, file_names=None):
    response_data = {
        "status": status,
        "message": message,
        "file": file_names
    }
    self.send_response(status)
    self.send_header("Content-type", "application/json")
    response_body = json.dumps(response_data).encode("utf-8")
    self.send_header("Content-Length", str(len(response_body)))
    self.end_headers()
    self.wfile.write(response_body)



class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # logger.info(f"Welcome => {HOST} : {PORT} /? ars = {args} and kwargs ={kwargs}")
        super().__init__(*args, directory=str(START_DIR),**kwargs)


    def do_POST(self):
        file_names:set = []

        if self.path != "/upload":
            logger.warning(f"Bad route {self.path}")
            self.send_error(404)
            return

        files = extract_file_data(self)
        if not files:
            json_responce(self,500, "No files provided")
            return

        if validate_files(self, files):
            for file_name, data in files:
                logger.info(f"file name = {file_name} --> start downloading")
                file_name_new = _generate_unique_filename(file_name)
                save_file(file_name_new, data)
                file_extension = Path(file_name_new).suffix.lower()
                insert_image(connection, file_name_new, file_name, len(data), file_extension)
                logger.info(f"File {file_name_new}  downloaded!")
                file_names.append(file_name_new)
            json_responce(self, 200, "Файли успішно завантажені", [file_name_new])

connection = None
while not connection:
    try:
        connection = psycopg.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        create_table(connection)
    except psycopg.Error as e:
        logger.warning(f"Could not connect to database: {e}")
        connection = None
        time.sleep(1)

server = ThreadingHTTPServer((HOST, PORT), Handler)
logger.info(f"Python server started on http://localhost:8080/")
server.serve_forever()