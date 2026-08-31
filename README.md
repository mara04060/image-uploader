# image-uploader - Python + NGINX + Docker Compose

## 1. Призначення

Проєкт демонструє роботу Python-застосунку та NGINX у Docker-контейнерах.

Основні функції:

* NGINX обслуговує статичний frontend;
* `POST /upload` передає завантаження Python-застосунку;
* Python зберігає файли та формує нове ім'я;
* NGINX віддає завантажені файли через `/images/`;
* логи Python та NGINX зберігаються у `logs/`.

Зовнішня адреса:

```text
http://localhost:8080
```

---

## 2. Структура проєкту

Структура відповідає технічному завданню:

```text
project/
├── static/
│   ├── index.html
│   └── ...
├── images/
├── logs/
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── Image Upload API.postman_collection.json (--Тестування та перевырка АПІ)
└── .dockerignore
```

`static/` та `nginx.conf` під час збірки потрапляють безпосередньо до Docker-образу NGINX.

`images/` та `logs/` використовуються як bind volumes.

---

## 3. Архітектура

```text
Client
   │
   ▼
NGINX :8080
   │
   ├── GET /
   │      └── static/
   │
   ├── GET /images/*
   │      └── images/
   │
   └── POST /upload
          │
          ▼
       Python :8000
          │
          ▼
       images/
```
Система складається з двох основних компонентів:
1. **Python-бекенд:**
- Відповідає за обробку HTTP-запитів, завантаження зображень, валідацію даних та логування.
- Виконує бізнес-логіку додатку, пов'язану з керуванням завантаженими файлами.
- Працює всередині Docker-контейнера, слухаючи запити на порту `8000`.
2. **Nginx-сервер:**
- Роздає статичні файли та завантажені зображення за маршрутом `/images/`.
- Проксує запити на Python-бекенд для інших маршрутів.
- Працює в окремому Docker-контейнері, слухаючи запити на порту `80`.

Компоненти взаємодіють через локальну мережу, створену за допомогою Docker Compose.
Порт Python `8000` не відкривається безпосередньо для host-системи. Доступ до нього здійснюється через NGINX.

---

# 4. API

## GET /

Отримання головної сторінки frontend.

```http
GET http://localhost:8080/
```

NGINX повертає:

```text
static/index.html
```

---

## POST /upload

Завантаження файлу на сервер.

```http
POST http://localhost:8080/upload
```

Тип запиту:

```text
multipart/form-data
```

У Postman файл передається через поле:

```text
file
```

Приклад через `curl`:

```bash
curl -X POST \
  -F "file=@sample.jpg" \
  http://localhost:8080/upload
```

При успішному завантаженні сервер повертає JSON:

```json
{
    "status": 200,
    "message": "Files is downloaded",
    "file": [
        "sample-birch-400x300_d177807bc3c04b47ba442bc50afe33dd.jpg"
    ]
}
```

У полі `file` знаходиться ім'я збереженого файлу. (Яке повертаэться у фронт)

Як варіант  -можливо завантажити де-кілька файлів дозволених форматов та розміру.
(Примітка: Якщо 1 файл з завантажуємих не відповідає вимогам - ресурс видає 400 помилку.)
Приклад:
```json
{
    "status": 200,
    "message": "Files is downloaded",
    "file": [
        "sample-birch-400x300_06eba2c3c90f4ea9a11932ab2ac7242a.jpg",
        "Снимок экрана_20260827_212751_28d46e4b952941f380c5a47ad3cefda8.png"
    ]
}
```

---

## GET /images/

Отримання конкретного завантаженого файлу.

```http
GET http://localhost:8080/images/<filename>
```

Наприклад:

```http
GET http://localhost:8080/images/sample-birch-400x300_d177807bc3c04b47ba442bc50afe33dd.jpg
```

Файл віддається безпосередньо NGINX із каталогу `images/`.

---

# 5. Docker

## Збірка

Для першого запуску або після зміни Dockerfile:

```bash
docker compose build
```

Для повної пересборки:

```bash
docker compose build --no-cache
```

## Запуск

```bash
docker compose up -d
```

Перевірка стану:

```bash
docker compose ps
```

Після успішного запуску проєкт доступний за адресою:

```text
http://localhost:8080
```

---

## Зупинка

Зупинити контейнери:

```bash
docker compose stop
```

Повністю зупинити та видалити контейнери:

```bash
docker compose down
```

Каталоги `images/` та `logs/` при цьому залишаються на host-системі.

---

# 6. Перегляд логів

Усі логи:

```bash
docker compose logs
```

У режимі реального часу:

```bash
docker compose logs -f
```

Тільки Python:

```bash
docker compose logs -f app
```

Тільки NGINX:

```bash
docker compose logs -f nginx
```

Логи NGINX також зберігаються у:

```text
logs/
├── nginx_access.log
└── nginx_error.log
```

---

# 7. Користувач Python

Python-застосунок запускається не від `root`, а від користувача:

```text
appuser
```

За замовчуванням:

```text
UID=1000
GID=1000
```

Це дозволяє застосунку працювати з каталогами:

```text
/app/images
/app/logs
```

без запуску самого Python від імені `root`.

---

# 8. Postman

Для тестування API використовується колекція Postman.

Рекомендований порядок:

1. Імпортувати колекцію в Postman.
2. Виконати `POST /upload`.
3. Вибрати файл(и) для завантаження.(Завантажуэться на Body / form-data поле file )
4. Після успішного запиту ім'я файлу автоматично зберігається у змінну:

   ```text
   filename
   ```
5. Виконати:

   ```http
   GET {{baseUrl}}/images/{{filename}}
   ```

Змінна:

```text
baseUrl = http://localhost:8080
```

---

## 9. Автоматичне збереження імені файлу

У `POST /upload` використовується Post-response script:

```javascript
const response = pm.response.json();

if (Array.isArray(response.file) && response.file.length > 0) {
    pm.variables.set("uploadedFile", response.file[0]);

    console.log("Uploaded file:", response.file[0]);
}
```

Після виконання POST змінна:

```text
filename
```

містить, наприклад:

```text
sample-birch-400x300_d177807bc3c04b47ba442bc50afe33dd.jpg
```
назву самого файлу.

Наступний GET:

```http
GET {{baseUrl}}/images/{{filename}}
```

автоматично сформує URL:

```text
http://localhost:8080/images/sample-birch-400x300_d177807bc3c04b47ba442bc50afe33dd.jpg
```

---

# 10. Основні команди

```bash
# Збірка
docker compose build

# Запуск
docker compose up -d

# Перевірка
docker compose ps

# Логи
docker compose logs -f

# Зупинка
docker compose stop

# Зупинка та видалення контейнерів
docker compose down
```

Для повного оновлення образів:

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

## Підсумок

У проєкті реалізовано:

* статичний frontend через NGINX;
* API `POST /upload` для завантаження файлів;
* автоматичне перейменування файлів Python-застосунком;
* отримання файлів через `GET /images/<filename>`;
* збереження `images/` та `logs/` через volumes;
* запуск Python від непривілейованого користувача;
* автоматичне отримання імені завантаженого файлу в Postman або фронтЕнд.
* взаємодію Python та NGINX через внутрішню Docker-мережу.
