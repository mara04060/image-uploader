import json
import logging
import os
import uuid
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import urlparse, parse_qs

import psycopg
from PIL import Image
from psycopg import Connection
import time

# ---------------
# Settings
# ---------------
HOST = "0.0.0.0"
HOST_PORT: int = int(os.environ.get("APP_PORT", 8000))

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
DB_PASSWORD = os.environ.get("DB_PASSWORD", "123")

ALLOWED_EXTENSIONS= os.environ.get("ALLOWED_EXTENSIONS", {"jpg", "png", "gif", "jpeg"})
MAX_FILE_SIZE = 1024 * 1024 * int(os.environ.get("MAX_FILE_SIZE", 5))
ITEMS_PER_PAGE = 10

LOG_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

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

# ---------------
# DB Connection
# ---------------
def get_db_connection() -> Connection:
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def wait_for_database():
    while True:
        try:
            with get_db_connection() as connection:
                create_table(connection)
            logger.info("Database connection established.")
            return
        except psycopg.Error as e:
            logger.warning( f"Could not connect to database: {e}" )
            time.sleep(1)


# ---------------
# CRUD
# ---------------
def create_table(connection: Connection):
    with connection.cursor() as cursor:
        sql_script = f"""
        CREATE TABLE IF NOT EXISTS {DB_SCHEME}.images (
          id SERIAL PRIMARY KEY,
          filename TEXT NOT NULL,
          original_name TEXT NOT NULL,
          size INTEGER NOT NULL,
          upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          file_type TEXT NOT NULL
        );
        """
        cursor.execute(sql_script)
    connection.commit()
    logger.debug("SQL: %s",sql_script )
    logger.info("Database table is ready!")

def insert_image( connection: Connection, file_name: str, original_name: str, size: int, file_type: str):
    try:
        with connection.cursor() as cursor:
            sql_script = f"""
                INSERT INTO {DB_SCHEME}.images (
                    filename,
                    original_name,
                    size,
                    file_type
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """
            cursor.execute( sql_script,
                (file_name, original_name, size, file_type ) )
            result = cursor.fetchone()
        connection.commit()
        logger.info("Insert data %s, %s, %s, %s",file_name, original_name, size, file_type )
        logger.debug("SQL: %s",sql_script )
        return result[0]
    except Exception:
        connection.rollback()
        raise

def get_images( connection: Connection, page: int = 1):
    page = page if page > 0 else 1
    offset = (page - 1) * ITEMS_PER_PAGE
    try:
        with connection.cursor() as cursor:
            sql_script = f"""
                SELECT
                    id, filename, original_name, size, file_type, upload_time
                FROM {DB_SCHEME}.images
                ORDER BY id DESC
                OFFSET %s
                LIMIT {ITEMS_PER_PAGE};
            """

            cursor.execute( sql_script, (offset,) )
            rows = cursor.fetchall()
            logger.debug("SQL: %s",sql_script )
            columns = [ desc[0] for desc in cursor.description ]

            result = [
                {
                    columns[0]: row[0],
                    **dict( zip(columns[1:], row[1:] )  )
                }
                for row in rows ]
            logger.info("Result Data Select: %s",result )
            return result

    except Exception:
        connection.rollback()
        raise


def get_pagination( connection: Connection, page: int = 1):
    try:
        with connection.cursor() as cursor:
            sql_script = f"""
                SELECT jsonb_build_object(
                    'total_items', COUNT(id),
                    'page', {page},
                    'page_size', {ITEMS_PER_PAGE},
                    'total_pages', CEIL(COUNT(id)::numeric / {ITEMS_PER_PAGE}),
                    'has_previous', {page} > 1,
                    'has_next', {page} < CEIL(COUNT(id)::numeric / {ITEMS_PER_PAGE})
                ) AS pagination
                FROM public.images;
            """
            cursor.execute( sql_script )
            result_json = cursor.fetchone()[0]
            logger.debug("SQL: %s",sql_script )
            logger.info("Result JSON: %s",result_json )
            return result_json
    except Exception:
        connection.rollback()
        raise

def get_image_filename( connection: Connection,image_id: int):
    if image_id <= 0:
        return None

    try:
        with connection.cursor() as cursor:
            sql_script = f"""
                SELECT filename
                FROM {DB_SCHEME}.images
                WHERE id = %s;
            """
            cursor.execute(sql_script, (image_id,) )
            result = cursor.fetchone()
        logger.debug("SQL: %s",sql_script )
        if result is None:
            return None

        return result[0]
    except Exception:
        connection.rollback()
        raise

def del_image(connection: Connection, image_id: int):
    try:
        with connection.cursor() as cursor:
            sql_script = None
            if image_id > 0:
                sql_script = f"""
                    DELETE FROM {DB_SCHEME}.images
                    WHERE id = %s;
                """
                cursor.execute( sql_script, (image_id,) )
        connection.commit()
        logger.debug("SQL: %s",sql_script )
        logger.info("SQL: Delete image id = %s",image_id )
        return True
    except Exception:
        connection.rollback()
        raise

# ---------------
# Helpers
# ---------------
def _read_body(handler):
    content_length = handler.headers.get("Content-Length")

    if content_length is None:
        raise ValueError("Content-Length header is required")
    try:
        length = int(content_length)
    except ValueError:
        raise ValueError("Invalid Content-Length")

    if length <= 0:
        raise ValueError("Empty request body")
    # Дозволяю завантажувати до 10 файлыв в одночас по 5 Мб кожен максимум!
    if length > 10 * MAX_FILE_SIZE:
        raise ValueError(
            f"Request too large. Max size allowed is "
            f"{MAX_FILE_SIZE // (1024 * 1024)}MB"
        )
    return handler.rfile.read(length)

def _extract_boundary(content_type: str):
    match = re.search(r'boundary="?([^";]+)"?', content_type )
    if match:
        return match.group(1).encode()
    logger.warning(f"Could not extract boundary from {content_type}" )
    return b""

def _parse_multipart_body( body: bytes,boundary: bytes) -> list[tuple[str, bytes]]:
    parts = body.split(b"--" + boundary )
    extracted_files = []

    for part in parts:
        # Тупо вырезка пустых данных которые мне мешают...
        if ( not part or part == b"--" or part.startswith(b"--\r\n") ):
            continue

        header_body_split = part.find(b"\r\n\r\n" )
        if header_body_split == -1:
            continue

        headers_raw = part[:header_body_split].decode("utf-8", errors="ignore" )
        data = part[header_body_split + 4:].rstrip(b"\r\n")

        # Это спасибо Макс подсказал.. реально работает...
        filename_match = re.search(r'filename="([^"]+)"',headers_raw )
        if filename_match and data:
            filename = filename_match.group(1)
            extracted_files.append( (filename, data ) )
    return extracted_files

def extract_file_data(handler) -> list[tuple[str, bytes]]:
    content_type = handler.headers.get( "Content-Type", "")
    boundary = _extract_boundary(content_type )
    if not boundary:
        logger.warning("No body in boundary" )
        return []
    body = _read_body(handler)
    return _parse_multipart_body( body, boundary )

def validate_files(self, files: list[tuple[str, bytes]]):
    for file_name, data in files:
        error_message = validate_file( file_name, data )
        if error_message:
            logger.warning( f"Rejected file '{file_name}': {error_message}" )
            send_params(self,400,error_message,file_name)
            return False
    return True

def validate_file(file_name: str,data: bytes):
    # TODO вынести все сообщения как исключения.
    # Пока долго заморачиваться
    file_extension = get_file_ext(file_name)
    if file_extension not in ALLOWED_EXTENSIONS:
        return (f"Непідтримуваний формат файлу: {file_extension}. доступны лише: {ALLOWED_EXTENSIONS}" )

    # Якщо робити таку перевірку то повинні бути справжні MIME code JPEG GIF PNG
    if not is_real_image(file_extension, data):
        return (f"Image is not correct File. mime code is not Image!")

    if len(data) > MAX_FILE_SIZE:
        return ( f"File too large. Max size allowed is {MAX_FILE_SIZE // (1024 * 1024)}MB" )

    return None

# Перевіряє імідж з внутрішнього боку
def is_real_image(ext: str, data: bytes):
    try:
        with Image.open(BytesIO(data)) as img:
            fmt = img.format
            img.verify()
            logger.info(f"Image is mime code {fmt} == {ALLOWED_EXTENSIONS}")
            if fmt.lower() in ALLOWED_EXTENSIONS:
                return fmt
    except Exception:
        logger.warning(f"Could not determine mime code for {ext}" )
        return False

def get_file_ext(file_name: str):
    logger.info("Extended = %s", Path(file_name).suffix.lower().strip(".") )
    return Path(file_name).suffix.lower().strip(".")

def _generate_unique_filename( file_name: str):
    ext = get_file_ext(file_name)
    return (f"{uuid.uuid4().hex}{ext}")

def download_file(full_filename,data):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with open(UPLOAD_DIR / full_filename, "wb") as file:
        file.write(data)
    logger.info(f"Saved {full_filename}" )

def row_to_dict(rows):
    return [dict(row) for row in rows]

def send_json_in_list(self,data: dict, status: int):
    self.send_response( status )
    send_json( self,  data )
    return None

def send_json_dict(self,data: dict):
    status = int( data.get("status",200) )
    self.send_response( status )
    send_json( self, data )
    return None

def send_json(self, data):
    self.send_header("Content-type","application/json")
    self.send_header("Access-Control-Allow-Origin", "*")
    response_body = json.dumps( data, ensure_ascii=False, default=str).encode("utf-8")
    self.send_header("Content-Length", str(len(response_body)) )
    self.end_headers()
    self.wfile.write( response_body )
    logger.info(f"Send JSON {data}")

def send_params( self,status,message,file_names=None):
    send_json_dict( self,
    {"status": status,
            "message": message,
            "file": file_names
        }
    )


def delete_file(file_name: str):
    logger.info(f"Deleting {file_name}")
    if ( not isinstance(file_name, str) or not file_name.strip() ):
        logger.error(f"File is Not Delete")
        raise ValueError( "Bad file name." )

    # Неможливо змынити директорію з якої видаляємо
    # ../file, /tmp/file, subdir/file и т.п.
    filename_path = Path(file_name)
    if (filename_path.name != file_name or file_name in {".", ".."}):
        raise ValueError( "WARNING: Only file name can be specified." )

    # Шлях в межах лише UPLOAD_DIR
    upload_dir = UPLOAD_DIR.resolve()
    file_path = (upload_dir / file_name).resolve()

    # Ще один додатковий захист
    try:
        file_path.relative_to(upload_dir)
    except ValueError:
        raise ValueError("Invalid file path")

    # перевірка існування файлу
    # Якщо вже не існує - то хоча б з БД видаляємо далі
    if not file_path.exists():
        return False

    # Якщо це директорія
    if file_path.is_dir():
        raise IsADirectoryError( f"This is a directory, not a file.: {file_name}" )
    file_path.unlink()
    return True


# ---------------
# Func Business Logic
# ---------------
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__( *args, directory=str(START_DIR), **kwargs )

    # ---------------
    # Upload POST
    # ---------------
    def do_POST(self):
        file_names: set = []
        if self.path != "/upload":
            logger.warning(f"Bad route {self.path}" )
            # принципово сторінку а не JSON
            self.send_error( 404 )
            return None

        files = extract_file_data(self)
        if not files:
            send_params(self,500,"No files provided")
            return None

        if not validate_files( self, files):
            return None
        for file_name, data in files:
            logger.info(f"file name = {file_name} --> start downloading")
            file_name_new = ( _generate_unique_filename( file_name ) )
            download_file( file_name_new, data )
            try:
                with get_db_connection() as connection:
                    insert_image(connection, file_name_new, file_name, len(data), get_file_ext(file_name_new))
            except psycopg.Error as e:
                logger.error("DB error, rollback file %s: %s",file_name,  e )
                delete_file(file_name_new)
                send_params( self,500,"Database error File Not Save" )
                return None
            logger.info( f"File {file_name_new} downloaded!" )
            file_names.append(file_name_new )
        send_params(self,200,"Файли успішно завантажені",file_names)

    # ---------------
    # Get Images
    # ---------------
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/images-list":
            logger.warning(f"GET {parsed.path} --> 404")
            # Принципово сторінку 404 помилки замість JSON
            self.send_error(404)
            return None

        params = parse_qs( parsed.query)
        try:
            page = int( params.get("page",["1"] )[0] )
        except ValueError as e:
            self.send_error(400,"Invalid page" )
            logger.warning( f"Page not found: {e}" )
            return None
        logger.info( f"Page found: {page}")
        try:
            with get_db_connection() as connection:
                json_obj = {
                    "items": get_images( connection, page),
                    "pagination": get_pagination( connection, page)
                }
            logger.info(f"JSON obj: {json_obj}" )
            send_json_in_list(self, json_obj,200 )
        except psycopg.Error as e:
            logger.exception("Database error during GET /images-list" )
            send_params(self,500,"Database error" )
        return None

    # ---------------
    # DELETE image
    # ---------------
    def do_DELETE(self):
        parsed = urlparse(self.path)
        match = re.fullmatch(r"/delete/(\d+)", parsed.path )
        if not match:
            logger.warning( f"DELETE {parsed.path} --> 404" )
            send_params( self,404,"Invalid delete route" )
            return None

        image_id = int( match.group(1) )
        try:
            with get_db_connection() as connection:
                delete_file_name = (get_image_filename(connection,image_id) )
                if not delete_file_name:
                    send_params(self,404,f"Image not found ID:{image_id}" )
                    return None
                logger.info( f"DELETE file: {delete_file_name}" )
                delete_file(delete_file_name )
                logger.info( f"Remove file: {delete_file_name}" )
                logger.info("DELETE image id={image_id}" )
                del_image( connection, image_id)
        except ValueError as e:
            logger.warning(e)
            send_params( self,404, str(e) )
            return None
        except psycopg.Error as e:
            logger.exception(f"Database error during DELETE: {e}" )
            send_params( self,500,"Database error" )
            return None
        send_params( self,200,f"Image deleted ID: {image_id}" )

# ---------------
# Start Server
# ---------------
def main():
    # Wait for PostgreSQL
    wait_for_database()
    server = ThreadingHTTPServer((HOST, HOST_PORT), Handler )
    logger.info( f"Python server started on http://localhost:{HOST_PORT}/" )
    server.serve_forever()


if __name__ == "__main__":
    main()