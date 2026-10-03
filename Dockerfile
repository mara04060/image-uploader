# Python
FROM python:3.12-alpine AS app

WORKDIR /app
# Install dependencies as root
RUN apk add --no-cache postgresql-client
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application user
ARG UID=1000
ARG GID=1000

RUN addgroup -g ${GID} appuser && \
    adduser -D -u ${UID} -G appuser appuser

# Application
COPY app.py /app/app.py
COPY backup_scheduler.py /app/backup_scheduler.py

RUN mkdir -p /app/images /app/logs /app/backup && \
    chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
CMD ["python3", "-u", "app.py"]

# NGINX
FROM nginx:alpine AS nginx
COPY nginx.conf /etc/nginx/nginx.conf
COPY static/ /app/static/
RUN mkdir -p /app/images /logs