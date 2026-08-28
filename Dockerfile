FROM python:3.12-alpine
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG UID=1000
ARG GID=1000

RUN addgroup -g ${GID} appuser && \
    adduser -D -u ${UID} -G appuser appuser

COPY . .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python3", "-u", "app.py"]