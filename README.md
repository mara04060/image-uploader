# Image Manager — Python + PostgreSQL + NGINX + Docker Compose

## Швидкий запуск проєкту

### 1\. Підготовка каталогів

Після клонування проєкту перейдіть до його кореневого каталогу.

Для Linux створіть каталоги для зображень, логів і резервних копій та налаштуйте права доступу:

```
mkdir -p images logs backups
sudo chown -R 1000:1000 images logs backups
chmod 755 images logs backups
```

> **Примітка:** UID/GID `1000:1000` використовуються за замовчуванням. Якщо у `.env` задані інші значення `UID` і `GID`, необхідно відповідно змінити власника каталогів.

### 2\. Налаштування `.env`

Створіть файл `.env` у кореневому каталозі проєкту, поруч із `docker-compose.yml`:

```
# Application
HOST_NGINX=localhost
HOST_PORT=8080
APP_PORT=8000

# PostgreSQL
POSTGRES_PORT=5432
POSTGRES_SCHEME=public
POSTGRES_DB=images_db
POSTGRES_USER=root_user
POSTGRES_PASSWORD=passw123

# File upload
ALLOWED_EXTENSIONS=jpg,png,gif,jpeg
MAX_FILE_SIZE=5

# Backup
BACKUP_DIR=backups
BACKUP_INTERVAL_MINUTES=5

# Application user (optional)
UID=1000
GID=1000
```

**Основні налаштування:**

- `HOST_PORT` — порт NGINX, доступний на host-системі.
- `POSTGRES_DB` — назва бази даних.
- `POSTGRES_USER` і `POSTGRES_PASSWORD` — облікові дані PostgreSQL.
- `ALLOWED_EXTENSIONS` — дозволені розширення файлів.
- `MAX_FILE_SIZE` — максимальний розмір одного файлу в МБ.
- `BACKUP_INTERVAL_MINUTES` — інтервал автоматичного резервного копіювання в хвилинах.

### 3\. Збірка та запуск

Виконайте команду в кореневому каталозі проєкту:

```
docker compose up -d --build
```

Команда збере необхідні образи та запустить контейнери:

- `nginx` — вебсервер;
- `app` — Python API;
- `postgres` — база даних PostgreSQL;
- `backup_scheduler` — автоматичне резервне копіювання.

Перевірте стан контейнерів:

```
docker compose ps
```

Перегляньте логи запуску:

```
docker compose logs -f
```

Після успішного запуску відкрийте frontend у браузері:

```
http://localhost:8080
```

Якщо в `.env` задано інше значення `HOST_PORT`, використовуйте відповідний порт.

### 4\. Перевірка роботи API

**Завантаження зображення:**

```
curl -X POST \
  -F "file=@sample.jpg" \
  http://localhost:8080/upload
```

**Отримання списку зображень:**

```
curl http://localhost:8080/images-list
```

**Отримання другої сторінки:**

```
curl "http://localhost:8080/images-list?page=2"
```

**Перегляд завантаженого зображення:**

```
http://localhost:8080/images/<filename>
```

Замість `<filename>` вкажіть ім'я файлу, отримане у відповіді `POST /upload`.

**Видалення зображення за ID:**

```
curl -X DELETE http://localhost:8080/delete/1
```

Замість `1` вкажіть ID зображення в базі даних.

### 5\. Зупинка проєкту

Зупинити контейнери, зберігши дані:

```
docker compose down
```

Повторний запуск:

```
docker compose up -d
```

**Повне видалення контейнерів, локальних образів проєкту та даних PostgreSQL:**

```
docker compose down -v --rmi local
```

> **Увага!** Параметр `-v` видаляє іменований Docker volume `postgres-data`, у якому зберігається база даних. Дані PostgreSQL буде втрачено, якщо попередньо не створено резервну копію. Каталоги `images/`, `logs/` і `backups/`, підключені як bind volumes, цією командою не видаляються.

### 6\. Перегляд резервних копій і логів

Резервні копії PostgreSQL зберігаються в каталозі:

```
backups/
```

Інтервал їх створення задається параметром `BACKUP_INTERVAL_MINUTES`.

Основні файли логів:

```
logs/
├── app.log
└── backup.log
```

Перегляд логів Python API:

```
docker compose logs -f app
```

Перегляд логів резервного копіювання:

```
docker compose logs -f backup_scheduler
```

Перегляд логів PostgreSQL:

```
docker compose logs -f postgres
```

Перегляд логів NGINX:

```
docker compose logs -f nginx
```

---

## Змінні оточення

| Змінна | Значення за замовчуванням у `.env` | Опис |
| --- | --- | --- |
| `HOST_NGINX` | `localhost` | Ім'я хоста для доступу до вебінтерфейсу. |
| `HOST_PORT` | `8080` | Порт NGINX на host-системі. |
| `APP_PORT` | `8000` | Порт Python API всередині контейнера. |
| `POSTGRES_PORT` | `5432` | Порт PostgreSQL усередині Docker-мережі. |
| `POSTGRES_SCHEME` | `public` | Схема PostgreSQL для функцій роботи із зображеннями. |
| `POSTGRES_DB` | `images_db` | Назва бази даних. |
| `POSTGRES_USER` | `root_user` | Користувач PostgreSQL. |
| `POSTGRES_PASSWORD` | `passw123` | Пароль PostgreSQL. |
| `ALLOWED_EXTENSIONS` | `jpg,png,gif,jpeg` | Дозволені розширення файлів. |
| `MAX_FILE_SIZE` | `5` | Максимальний розмір одного файлу в МБ. |
| `BACKUP_DIR` | `backups` | Каталог для резервних копій усередині контейнера. |
| `BACKUP_INTERVAL_MINUTES` | `5` | Інтервал між резервними копіями в хвилинах. |
| `UID` | `1000` | UID користувача Python-застосунку. |
| `GID` | `1000` | GID групи Python-застосунку. |

**Важливо:** ім'я хоста PostgreSQL у коді зафіксовано як `postgres` — це ім'я сервісу в `docker-compose.yml`. Порт Python API `8000` не публікується безпосередньо на host-систему: доступ до API здійснюється через NGINX.

Для робочого середовища рекомендується встановити власний надійний пароль PostgreSQL у `.env` і не додавати цей файл до системи контролю версій.

## 1\. Призначення

Проєкт демонструє роботу вебзастосунку для завантаження, зберігання, перегляду та видалення зображень із використанням Python, PostgreSQL, NGINX і Docker Compose.

Основні функції:

- NGINX обслуговує статичний frontend;
- Python реалізує API для керування зображеннями;
- завантажені файли перевіряються та отримують унікальні імена;
- PostgreSQL зберігає метадані зображень;
- NGINX віддає зображення через `/images/`;
- API підтримує перегляд списку зображень із пагінацією;
- реалізовано видалення зображень із файлової системи та бази даних;
- автоматично створюються резервні копії PostgreSQL;
- логи застосунку та резервного копіювання зберігаються у `logs/`.

Зовнішня адреса:

```
http://localhost:8080
```

Порт `8080` використовується як приклад. Фактичний порт визначається змінною `HOST_PORT` у `.env`.

---

## 2\. Структура проєкту

```
project/
├── static/
│   ├── index.html
│   └── ...
├── images/
├── logs/
├── backups/
├── app.py
├── backup_scheduler.py
├── install.sql
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── .env
└── .dockerignore
```

Призначення основних компонентів:

- `app.py` — Python API, робота із файлами та PostgreSQL.
- `backup_scheduler.py` — автоматичне резервне копіювання бази даних.
- `install.sql` — створення необхідних таблиць і функцій PostgreSQL.
- `static/` — файли frontend.
- `images/` — завантажені зображення.
- `logs/` — журнали роботи застосунку та резервного копіювання.
- `backups/` — резервні копії бази даних у форматі SQL.
- `nginx.conf` — конфігурація вебсервера та проксі.
- `Dockerfile` — складання образів Python і NGINX.
- `docker-compose.yml` — конфігурація контейнерів і мережі.
- `.env` — змінні середовища.

---

## 3\. Архітектура

```
                  Client / Browser
                         |
                         v
                    NGINX :80
                         |
             +-----------+-----------+
             |           |           |
             v           v           v
          Frontend    /upload    /images-list
          /images/       |           |
                         v           |
                     Python :8000 <-+
                         |
                 +-------+-------+
                 |               |
                 v               v
             PostgreSQL      images/
                 ^
                 |
          backup_scheduler
                 |
                 v
              backups/
```

Система складається з чотирьох компонентів:

1. **Python API**
   - Обробляє HTTP-запити.
   - Перевіряє завантажені файли.
   - Генерує унікальні імена.
   - Зберігає файли та метадані.
   - Реалізує пагінацію й видалення зображень.

2. **PostgreSQL**
   - Зберігає інформацію про зображення.
   - Виконує операції через SQL-функції.
   - Ініціалізує структуру бази даних під час запуску застосунку.

3. **NGINX**
   - Обслуговує статичний frontend.
   - Віддає файли з каталогу `images/`.
   - Передає API-запити Python-застосунку.

4. **Backup Scheduler**
   - Періодично створює резервні копії PostgreSQL за допомогою `pg_dump`.
   - Зберігає SQL-файли у `backups/`.
   - Записує інформацію про виконання операцій у логи.

Усі контейнери взаємодіють через внутрішню Docker-мережу `app-network`. Порт Python `8000` і порт PostgreSQL `5432` не публікуються безпосередньо на host-систему.

---

## 4\. API

Усі запити виконуються через NGINX.

### POST /upload

Завантаження одного або декількох зображень.

```
POST http://localhost:8080/upload
```

Тип запиту:

```
multipart/form-data
```

Назва поля з файлом — `file`.

Приклад:

```
curl -X POST \
  -F "file=@sample.jpg" \
  http://localhost:8080/upload
```

Успішна відповідь:

```
{
  "status": 200,
  "message": "Файлы успешно загружены",
  "file": [
    "d177807bc3c04b47ba442bc50afe33dd.jpg"
  ]
}
```

Основні особливості:

- підтримується завантаження декількох файлів;
- дозволені розширення визначаються змінною `ALLOWED_EXTENSIONS`;
- максимальний розмір одного файлу визначається `MAX_FILE_SIZE`;
- кожен файл отримує унікальне ім'я;
- метадані зберігаються в PostgreSQL.

Якщо один із файлів не проходить перевірку, запит відхиляється з HTTP `400`.

### GET /images-list

Отримання списку зображень із пагінацією.

```
GET http://localhost:8080/images-list
```

Отримання другої сторінки:

```
GET http://localhost:8080/images-list?page=2
```

За замовчуванням повертається перша сторінка, яка містить до 10 записів.

Відповідь містить:

- `status` — HTTP-статус;
- `items` — список зображень;
- `pagination` — інформацію про пагінацію.

Некоректний параметр `page` призводить до відповіді HTTP `400`.

### GET /images/\<filename\>

Отримання завантаженого зображення.

```
GET http://localhost:8080/images/d177807bc3c04b47ba442bc50afe33dd.jpg
```

Файл віддається безпосередньо NGINX із каталогу `images/`.

### DELETE /delete/\<id\>

Видалення зображення за його ID у базі даних.

```
DELETE http://localhost:8080/delete/1
```

Застосунок:

1. Отримує ім'я файлу з PostgreSQL.
2. Видаляє файл із файлової системи.
3. Видаляє запис із бази даних.
4. Повертає JSON із результатом операції.

Якщо зображення не знайдено, повертається HTTP `404`.

---

## 5\. Docker

### Збірка

```
docker compose build
```

Повна перебудова образів:

```
docker compose build --no-cache
```

### Запуск

```
docker compose up -d
```

Перевірка стану контейнерів:

```
docker compose ps
```

Перегляд логів:

```
docker compose logs -f
```

Після запуску frontend доступний за адресою:

```
http://localhost:8080
```

Фактична адреса залежить від значення `HOST_PORT` у `.env`.

### Зупинка

Зупинити контейнери:

```
docker compose stop
```

Зупинити та видалити контейнери:

```
docker compose down
```

Дані в `images/`, `logs/`, `backups/` і PostgreSQL зберігаються окремо від контейнерів. База даних використовує іменований Docker volume `postgres-data`.

---

## 6\. Резервне копіювання

Для автоматичного резервного копіювання використовується окремий контейнер `backup_scheduler`.

Резервні копії створюються за допомогою `pg_dump` і зберігаються у форматі SQL.

Приклад структури:

```
backups/
├── backup_2026-10-11_120000.sql
├── backup_2026-10-11_120200.sql
└── ...
```

Інтервал між копіюваннями задається змінною:

```
BACKUP_INTERVAL_MINUTES=2
```

Значення `2` означає створення нової резервної копії кожні дві хвилини.

Каталог резервних копій задається змінною:

```
BACKUP_DIR=backups
```

Логи резервного копіювання:

```
logs/backup.log
```

У разі невдалого створення копії помилковий SQL-файл видаляється, а інформація про помилку записується в лог.

**Примітка:** резервні копії містять дані PostgreSQL. Зображення зберігаються окремо в `images/`, тому для повного відновлення системи необхідно зберігати і базу даних, і відповідні файли.

---

## 7\. Логування

Застосунок записує логи у файли та виводить їх у консоль.

Основні файли:

```
logs/
├── app.log
└── backup.log
```

Перегляд логів усіх контейнерів:

```
docker compose logs -f
```

Логи Python API:

```
docker compose logs -f app
```

Логи резервного копіювання:

```
docker compose logs -f backup_scheduler
```

Логи PostgreSQL:

```
docker compose logs -f postgres
```

Логи NGINX:

```
docker compose logs -f nginx
```

---

## 8\. Користувач Python

Python-застосунок запускається від непривілейованого користувача:

```
appuser
```

UID і GID задаються через змінні середовища:

```
UID=1000
GID=1000
```

Це дозволяє запускати застосунок без використання `root` та працювати з каталогами, підключеними через Docker volumes.

---

## 9\. Основні команди

```
# Збірка образів
docker compose build

# Запуск
docker compose up -d

# Перевірка контейнерів
docker compose ps

# Перегляд логів
docker compose logs -f

# Логи Python
docker compose logs -f app

# Логи резервного копіювання
docker compose logs -f backup_scheduler

# Зупинка
docker compose stop

# Зупинка та видалення контейнерів
docker compose down
```

Повне оновлення образів:

```
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## 10\. Підсумок

У проєкті реалізовано:

- статичний frontend через NGINX;
- Python API для завантаження та видалення зображень;
- перевірку розширень і розмірів файлів;
- генерацію унікальних імен;
- зберігання метаданих у PostgreSQL;
- отримання списку зображень із пагінацією;
- роздачу зображень через NGINX;
- автоматичне резервне копіювання PostgreSQL;
- логування роботи API та системи резервного копіювання;
- запуск Python від непривілейованого користувача;
- ізоляцію компонентів у внутрішній Docker-мережі;
- збереження файлів, логів, резервних копій і даних PostgreSQL поза життєвим циклом контейнерів.