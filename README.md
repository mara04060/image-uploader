# Image Uploader

Невеликий вебсервіс для завантаження, перегляду та видалення зображень з автоматичним резервним копіюванням бази даних. Бекенд написано на чистому Python (без фреймворків), метадані зберігаються в PostgreSQL, статичні файли та зображення віддає Nginx. Весь проєкт запускається через Docker Compose.

## Можливості

- Завантаження одного або кількох зображень (`.jpg`, `.png`, `.gif`) через `multipart/form-data`.
- Перевірка формату та розміру файлу (за замовчуванням до 5 МБ).
- Генерація унікального імені файлу (UUID), щоб уникнути колізій і небезпечних імен.
- Збереження метаданих у PostgreSQL: оригінальна назва, нове ім'я, розмір, тип, час завантаження.
- Список зображень з пагінацією (10 елементів на сторінку, нові — першими).
- Видалення зображення: файл з диска та запис у базі.
- Захист від path traversal при видаленні файлів.
- Автоматичні резервні копії бази (`pg_dump`) за розкладом.
- Логування у файли та в консоль.

## Архітектура

| Сервіс | Опис |
|---|---|
| `db` | PostgreSQL 18, дані зберігаються в томі `postgres-data`. Має healthcheck (`pg_isready`). |
| `app` | Python-бекенд (`app.py`) на порту `8000`, `ThreadingHTTPServer`. |
| `backup_scheduler` | Скрипт `backup_scheduler.py`, який через задані інтервали робить `pg_dump`. |
| `nginx` | Reverse proxy, віддає статику (`static/`) та зображення (`/app/images`, лише читання). Публікується на `${HOST_PORT}`. |

Усі сервіси працюють в одній внутрішній мережі `app-network`. Сервіси `app` і `backup_scheduler` стартують лише після того, як база пройшла healthcheck.

Dockerfile багатоетапний: цілі (`target`) `app` (Python 3.12 Alpine, з `postgresql-client` для `pg_dump`) та `nginx` (Nginx Alpine з `nginx.conf` і `static/`). Застосунок запускається від непривілейованого користувача `appuser` з UID/GID, які можна передати через змінні `UID` та `GID`.

## Структура проєкту

```
.
├── app.py                 # HTTP-бекенд
├── backup_scheduler.py    # Планувальник резервних копій
├── Dockerfile             # Цілі: app, nginx
├── docker-compose.yml
├── nginx.conf
├── requirements.txt
├── static/                # Фронтенд (віддається Nginx)
├── images/                # Завантажені зображення (том)
├── logs/                  # app.log, backup.log (том)
└── backups/               # Резервні копії (за BACKUP_DIR)
```

## Запуск
0. Створити директорії в межах склонованого проекту: (Linux* - обовёязково)
```cmd
mkdir -p images logs backups
sudo chown -R 1000:1000 images logs backups
chmod 755 images logs backups
```
1. Створіть файл `.env` поруч із `docker-compose.yml`:

```env
HOST_NGINX=localhost
HOST_PORT=8080
APP_PORT=8000

POSTGRES_PORT=5432
POSTGRES_SCHEME=public
POSTGRES_DB=images_db
POSTGRES_USER=user
POSTGRES_PASSWORD=passw

ALLOWED_EXTENSIONS=jpg,png,gif,jpeg
MAX_FILE_SIZE=5

BACKUP_DIR=backups
BACKUP_INTERVAL_MINUTES=5

# Необов'язково (значення за замовчуванням 1000)
UID=1000
GID=1000
```

2. Створіть каталоги для томів і переконайтеся, що вони доступні користувачу з UID/GID:

```bash
mkdir -p images logs backups
```

3. Запустіть проєкт:

```bash
docker compose up -d --build
```

4. Відкрийте `http://localhost:8080` (або порт зі змінної `HOST_PORT`).

Зупинка: `docker compose down` (додайте `-v`, щоб видалити також том з базою).
```bash
docker compose down -v --rmi local
```

## Змінні оточення

| Змінна                    | За замовчуванням | Опис |
|---------------------------|---|---|
| `HOST_PORT`               | — | Порт Nginx на хості. |
| `POSTGRES_DB`             | `images_db` | Назва бази даних. |
| `POSTGRES_USER`           | `root_user` | Користувач бази. |
| `POSTGRES_PASSWORD`       | `123` (у `app.py`) | Пароль бази. |
| `DB_SCHEME`               | `public` | Схема, у якій створюється таблиця `images`. |
| `DB_PORT`                 | `5432` | Порт PostgreSQL. |
| `MAX_FILE_SIZE`           | `5` | Максимальний розмір файлу в МБ. |
| `BACKUP_DIR`              | `/backups` | Каталог для резервних копій усередині контейнера (і на хості відносно проєкту). |
| `BACKUP_INTERVAL_MINUTES` | `2` | Інтервал між резервними копіями, хв. |

Хост бази даних зафіксовано як `db` (ім'я сервісу в Compose).

## API

### `POST /upload`

Завантаження файлів. Тіло запиту — `multipart/form-data`, можна передати кілька файлів.

Приклад:

```bash
curl -F "file=@photo.jpg" -F "file=@logo.png" http://localhost:8080/upload
```

Успішна відповідь:

```json
{
  "status": 200,
  "message": "Файли успішно завантажені",
  "file": ["3f2a...c1.jpg", "9b7d...e4.png"]
}
```

Помилки: `400` — непідтримуваний формат або завеликий файл; `500` — файли не передано.

### `GET /images-list?page=1`

Повертає сторінку зі списком зображень та інформацію про пагінацію.

```json
{
  "items": [
    {
      "id": 12,
      "filename": "3f2a...c1.jpg",
      "original_name": "photo.jpg",
      "size": 204800,
      "file_type": "jpeg",
      "upload_time": "2026-10-03 12:00:00"
    }
  ],
  "pagination": {
    "total_items": 25,
    "page": 1,
    "page_size": 10,
    "total_pages": 3,
    "has_previous": false,
    "has_next": true
  }
}
```

Якщо `page` не є числом — відповідь `400 Invalid page`.

### `DELETE /delete/{id}`

Видаляє зображення за його `id` (файл і запис у базі).

```bash
curl -X DELETE http://localhost:8080/delete/12
```

Відповіді: `200` — видалено; `404` — зображення не знайдено або маршрут некоректний.
приклад:
```json
{
    "status": 200,
    "message": "Image deleted ID: 2",
    "file": "photo_2026-08-25_14-32-10.jpg"
}
```

## Модель даних

Таблиця `images` створюється автоматично під час старту застосунку:

| Поле | Тип | Опис |
|---|---|---|
| `id` | `SERIAL PRIMARY KEY` | Ідентифікатор. |
| `filename` | `TEXT` | Унікальне ім'я файлу на диску. |
| `original_name` | `TEXT` | Оригінальна назва файлу. |
| `size` | `INTEGER` | Розмір у байтах. |
| `upload_time` | `TIMESTAMP` | Час завантаження (`CURRENT_TIMESTAMP`). |
| `file_type` | `TEXT` | Розширення файлу. |

## Резервне копіювання

Сервіс `backup_scheduler` у нескінченному циклі:

1. викликає `pg_dump` для бази `POSTGRES_NAME`;
2. зберігає дамп у `BACKUP_DIR` з іменем `backup_YYYY-MM-DD_HHMMSS.sql`;
3. у разі помилки видаляє неповний файл і пише причину в лог;
4. чекає `BACKUP_INTERVAL_MINUTES` хвилин і повторює.

Логи пишуться в `logs/backup.log`. 

За необхіднстю зробити BackUp:
```bash
docker compose exec -T postgres pg_dump -U $DB_USER $DB_NAME > backups/backup_$(date +%F_%H%M%S).sql
```
Відновлення з копії:

```bash
docker compose exec -T postgres psql -U $DB_USER -d $DB_NAME < backups/backup_2026-10-03_120000.sql
```

## Логи

- `logs/app.log` — робота бекенду (запити, завантаження, видалення, помилки).
- `logs/backup.log` — робота планувальника резервних копій.
- Логи Nginx зберігаються в `logs/` (змонтовано як `/logs`).

## Безпека та валідація

- Дозволені лише розширення `jpg`, `png`, `gif`.
- Обмеження розміру файлу (`MAX_FILE_SIZE`).
- Файли зберігаються під випадковими UUID-іменами, оригінальне ім'я лише в базі.
- Під час видалення перевіряється, що ім'я файлу не містить шляху (`../`, `/`, піддиректорій), а фінальний шлях лежить у межах `images/`.
- Усі SQL-запити з користувацькими значеннями параметризовані.

## Відомі обмеження та план покращень

- Розширення перевіряється лише за назвою файлу, вміст (MIME/сигнатура) не перевіряється.
- Файл читається в пам'ять повністю, а власний multipart-парсер не підходить для великих навантажень; варто перейти на бібліотеку або фреймворк.
- Резервні копії не ротуються — старі файли потрібно очищати вручну.
- Для CORS встановлено `Access-Control-Allow-Origin: *`.
- Автентифікація відсутня: будь-хто може завантажувати та видаляти зображення.