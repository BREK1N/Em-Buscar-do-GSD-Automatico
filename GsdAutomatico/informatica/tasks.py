import datetime
import logging
from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

IGNORED_LOG_TERMS = [
    '/static/', '/media/', '/favicon.ico', '/api/logs/',
    'POST /jsi18n/', 'Auto-reloading', 'Watching for file changes', '/admin/login/',
]


@shared_task
def fetch_docker_logs_task():
    """
    Coleta logs dos containers Docker e armazena em cache Redis.
    Executada periodicamente pelo Celery Beat (a cada 30s).
    Serve tanto o endpoint system_logs_api (dict) quanto o dashboard (strings).
    """
    import docker

    logs_api: list[dict] = []
    logs_terminal: list[str] = []

    try:
        client = docker.from_env()
        containers = client.containers.list()
        logs_terminal.append(
            f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Conectado ao Daemon do Docker."
        )

        for container in containers:
            name = container.name.lower()

            # system_logs_api: web e nginx apenas
            if not ('db' in name or 'postgres' in name):
                if 'web' in name or 'nginx' in name:
                    log_output = container.logs(tail=100, timestamps=True).decode('utf-8', errors='replace')
                    for entry in log_output.split('\n'):
                        if not entry.strip():
                            continue
                        if any(t in entry for t in IGNORED_LOG_TERMS):
                            continue
                        display = entry[31:] if len(entry) > 31 and entry[4] == '-' and entry[19] == 'T' else entry
                        logs_api.append({'container': container.name, 'text': display[:300]})

            # dashboard terminal: todos os containers, tail=5
            tail_logs = container.logs(tail=5, timestamps=True).decode('utf-8', errors='replace')
            for entry in tail_logs.split('\n'):
                if entry.strip():
                    clean = entry[:150] + '...' if len(entry) > 150 else entry
                    logs_terminal.append(f"[{container.name}] {clean}")

    except Exception as exc:
        logger.warning("fetch_docker_logs_task: erro ao ler Docker: %s", exc)
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        logs_api.append({'container': 'system', 'text': f"Erro: {exc}"})
        logs_terminal.append(f"[{ts}] ERRO: Não foi possível ler logs do Docker. Detalhe: {exc}")

    if not logs_terminal:
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        logs_terminal.append(f"[{ts}] Nenhum container ativo ou logs vazios.")

    cache.set('docker_logs_api', logs_api, timeout=60)
    cache.set('docker_terminal_logs', logs_terminal, timeout=60)
    logger.debug("fetch_docker_logs_task: %d entradas api, %d terminal", len(logs_api), len(logs_terminal))
    return len(logs_api)


@shared_task(bind=True, max_retries=1, default_retry_delay=5)
def fetch_monitor_task(self):
    """Coleta dados do servidor de backup/monitoramento e armazena em cache."""
    import os
    import requests as req_lib

    url = os.getenv('URL_MONITOR', 'http://10.52.18.29:5000')
    try:
        response = req_lib.get(url, timeout=5)
        if response.status_code == 200:
            data = {'online': True, 'dados': response.json()}
        else:
            data = {'online': False, 'erro': f'Erro HTTP: {response.status_code}'}
    except Exception as exc:
        data = {'online': False, 'erro': str(exc)}
    cache.set('monitor_data', data, timeout=120)
    return data['online']
