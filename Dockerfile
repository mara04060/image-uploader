# Python
FROM python:3.12-alpine AS app

WORKDIR /app
#Именно от рута копируем и віполняем инсталляцию
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

#Теперь пользователь внутри контейнера принципиально НЕ рут
ARG UID=1000
ARG GID=1000

#Все что ниже запускается именно от него
RUN addgroup -g ${GID} appuser && \
    adduser -D -u ${UID} -G appuser appuser

COPY app.py /app/app.py

RUN mkdir -p /app/images /app/logs && \
    chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
CMD ["python3", "-u", "app.py"]


# NGINX
FROM nginx:alpine AS nginx

#Замена конфиг файла, у провайдеров все-таки волюм пробрасівают!
COPY nginx.conf /etc/nginx/nginx.conf

#Так можно, а почему бі и нет. Иначе Волюм что тоже не плохо
COPY static/ /app/static/
RUN mkdir -p /app/images /logs