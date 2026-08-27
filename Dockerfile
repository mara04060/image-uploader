FROM python:3.12-alpine

ARG UID=1000
ARG GID=1000

RUN addgroup -g ${GID} appuser && \
    adduser -D -u ${UID} -G appuser appuser

WORKDIR /app

COPY .  .

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python3", "-u", "app.py"]
