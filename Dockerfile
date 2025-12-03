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
    netcat-openbsd \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --proxy http://19143033776:Recruta24.@10.52.132.240:8080 --upgrade pip && pip install --proxy http://19143033776:Recruta24.@10.52.132.240:8080 -r requirements.txt


COPY . /app/

RUN mkdir -p /app/staticfiles /app/media

EXPOSE 8000

# --- SCRIPT DE INICIALIZAÇÃO AUTOMÁTICO ---
RUN echo '#!/bin/sh' > /usr/local/bin/entrypoint.sh && \
    echo 'if [ "$DATABASE" = "postgres" ]; then' >> /usr/local/bin/entrypoint.sh && \
    echo '  echo "Aguardando banco de dados..."' >> /usr/local/bin/entrypoint.sh && \
    echo '  while ! nc -z $HOST $PORT; do sleep 0.1; done' >> /usr/local/bin/entrypoint.sh && \
    echo '  echo "Banco de dados iniciado"' >> /usr/local/bin/entrypoint.sh && \
    echo 'fi' >> /usr/local/bin/entrypoint.sh && \
    \
    echo 'echo "--- 1. Criando Migracoes Automaticas ---"' >> /usr/local/bin/entrypoint.sh && \
    echo 'python GsdAutomatico/manage.py makemigrations --noinput' >> /usr/local/bin/entrypoint.sh && \
    \
    echo 'echo "--- 2. Aplicando Migracoes ---"' >> /usr/local/bin/entrypoint.sh && \
    echo 'python GsdAutomatico/manage.py migrate --noinput' >> /usr/local/bin/entrypoint.sh && \
    \
    echo 'echo "--- 3. Verificando Superusuario ---"' >> /usr/local/bin/entrypoint.sh && \
    echo 'python GsdAutomatico/manage.py createsuperuser --noinput || true' >> /usr/local/bin/entrypoint.sh && \
    \
    echo 'echo "--- 4. Coletando Estaticos ---"' >> /usr/local/bin/entrypoint.sh && \
    echo 'python GsdAutomatico/manage.py collectstatic --noinput' >> /usr/local/bin/entrypoint.sh && \
    \
    echo 'echo "--- 5. Iniciando Servidor ---"' >> /usr/local/bin/entrypoint.sh && \
    echo 'cd GsdAutomatico' >> /usr/local/bin/entrypoint.sh && \
    echo 'exec waitress-serve --listen=*:8000 GsdAutomatico.wsgi:application' >> /usr/local/bin/entrypoint.sh && \
    chmod +x /usr/local/bin/entrypoint.sh
# ---------------------------------------------------------

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]