# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG http_proxy
ARG https_proxy

# Aplica no sistema
ENV http_proxy=$http_proxy
ENV https_proxy=$https_proxy

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    postgresql-client \
    netcat-openbsd \
    tesseract-ocr \
    tesseract-ocr-por \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

#RUN pip install --proxy http://19143033776:Recruta24.@10.52.132.240:8080 --upgrade pip && pip install --proxy http://19143033776:Recruta24.@10.52.132.240:8080 -r requirements.txt


COPY . /app/

RUN mkdir -p /app/staticfiles /app/media /app/backups

EXPOSE 8000

# --- SCRIPT DE INICIALIZAÇÃO AUTOMÁTICO ---
RUN echo '#!/bin/sh' > /usr/local/bin/entrypoint.sh && \
    echo 'if [ "$DATABASE" = "postgres" ]; then' >> /usr/local/bin/entrypoint.sh && \
    echo '  echo "Aguardando banco de dados..."' >> /usr/local/bin/entrypoint.sh && \
    echo '  while ! nc -z $HOST $PORT; do sleep 0.1; done' >> /usr/local/bin/entrypoint.sh && \
    echo '  echo "Banco de dados iniciado"' >> /usr/local/bin/entrypoint.sh && \
    echo 'fi' >> /usr/local/bin/entrypoint.sh && \
    \
    echo 'echo "--- 1. Verificando migracoes pendentes ---"' >> /usr/local/bin/entrypoint.sh && \
    echo 'python GsdAutomatico/manage.py makemigrations --check --dry-run' >> /usr/local/bin/entrypoint.sh && \
    echo 'if [ $? -ne 0 ]; then' >> /usr/local/bin/entrypoint.sh && \
    echo '  echo "ERRO: ha mudancas nos models sem migracao gerada/commitada."' >> /usr/local/bin/entrypoint.sh && \
    echo "  echo 'Rode python manage.py makemigrations localmente, revise o arquivo gerado e comite antes de fazer deploy.'" >> /usr/local/bin/entrypoint.sh && \
    echo '  exit 1' >> /usr/local/bin/entrypoint.sh && \
    echo 'fi' >> /usr/local/bin/entrypoint.sh && \
    \
    echo 'echo "--- 2. Backup do banco antes da migracao ---"' >> /usr/local/bin/entrypoint.sh && \
    echo 'mkdir -p /app/backups' >> /usr/local/bin/entrypoint.sh && \
    echo 'BACKUP_FILE="/app/backups/backup_$(date +%Y%m%d_%H%M%S).dump"' >> /usr/local/bin/entrypoint.sh && \
    echo 'if PGPASSWORD="$PASSWORD" pg_dump -h "$HOST" -p "$PORT" -U "$USER" -d "$NAME" -F c -f "$BACKUP_FILE"; then' >> /usr/local/bin/entrypoint.sh && \
    echo '  echo "Backup salvo em $BACKUP_FILE"' >> /usr/local/bin/entrypoint.sh && \
    echo 'else' >> /usr/local/bin/entrypoint.sh && \
    echo '  echo "AVISO: backup do banco falhou. Prosseguindo mesmo assim."' >> /usr/local/bin/entrypoint.sh && \
    echo 'fi' >> /usr/local/bin/entrypoint.sh && \
    echo 'ls -t /app/backups/backup_*.dump 2>/dev/null | tail -n +11 | xargs -r rm --' >> /usr/local/bin/entrypoint.sh && \
    \
    echo 'echo "--- 3. Aplicando Migracoes ---"' >> /usr/local/bin/entrypoint.sh && \
    echo 'python GsdAutomatico/manage.py migrate --noinput' >> /usr/local/bin/entrypoint.sh && \
    \
    echo 'echo "--- 4. Verificando Superusuario ---"' >> /usr/local/bin/entrypoint.sh && \
    echo 'python GsdAutomatico/manage.py createsuperuser --noinput || true' >> /usr/local/bin/entrypoint.sh && \
    \
    echo 'echo "--- 5. Coletando Estaticos ---"' >> /usr/local/bin/entrypoint.sh && \
    echo 'python GsdAutomatico/manage.py collectstatic --noinput' >> /usr/local/bin/entrypoint.sh && \
    \
    echo 'echo "--- 6. Iniciando Servidor ---"' >> /usr/local/bin/entrypoint.sh && \
    echo 'cd GsdAutomatico' >> /usr/local/bin/entrypoint.sh && \
    echo 'exec daphne -b 0.0.0.0 -p 8000 GsdAutomatico.asgi:application' >> /usr/local/bin/entrypoint.sh && \
    chmod +x /usr/local/bin/entrypoint.sh
# ---------------------------------------------------------

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]