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


@shared_task(bind=True, max_retries=1, default_retry_delay=30)
def executar_backup_task(self):
    """
    Checagem periódica (a cada 30 min, via Celery Beat): só executa o backup
    de fato quando o relógio estiver dentro da janela configurada em
    BackupDestino.horario_execucao e ainda não tiver rodado com sucesso hoje.
    """
    from django.utils import timezone

    from .models import BackupDestino, BackupExecucao

    destino_check = BackupDestino.get_instance()
    agora = timezone.localtime()
    horario = destino_check.horario_execucao
    dentro_da_janela = (
        agora.hour == horario.hour
        and abs(agora.minute - horario.minute) <= 15
    )
    ja_rodou_hoje = BackupExecucao.objects.filter(
        iniciado_em__date=agora.date(),
        status__in=['sucesso_local', 'sucesso_remoto'],
    ).exists()
    if not dentro_da_janela or ja_rodou_hoje:
        return None

    return _executar_backup()


@shared_task(bind=True, max_retries=1, default_retry_delay=30)
def executar_backup_manual_task(self):
    """Backup disparado manualmente por um admin da Informática, sem checar a janela de horário."""
    return _executar_backup()


def _executar_backup():
    """
    Backup diário (banco via pg_dump -F c + mídia via tar.gz) salvo em /app/backups,
    com envio opcional via SFTP para o servidor reserva configurado em BackupDestino.
    """
    import os
    import subprocess
    import tarfile

    from django.conf import settings
    from django.utils import timezone

    from .models import BackupDestino, BackupExecucao

    backups_dir = os.path.join(settings.BASE_DIR.parent, 'backups')
    os.makedirs(backups_dir, exist_ok=True)

    ts = timezone.now().strftime('%Y%m%d_%H%M%S')
    db_conf = settings.DATABASES['default']

    execucao = BackupExecucao.objects.create()

    arquivo_db = os.path.join(backups_dir, f'backup_db_{ts}.dump')
    arquivo_media = os.path.join(backups_dir, f'backup_media_{ts}.tar.gz')

    try:
        env = os.environ.copy()
        env['PGPASSWORD'] = db_conf['PASSWORD'] or ''
        subprocess.run(
            [
                'pg_dump', '-h', db_conf['HOST'], '-p', str(db_conf['PORT']),
                '-U', db_conf['USER'], '-d', db_conf['NAME'], '-F', 'c', '-f', arquivo_db,
            ],
            env=env, check=True, capture_output=True, text=True, timeout=270,
        )

        media_root = settings.MEDIA_ROOT
        if os.path.isdir(media_root):
            with tarfile.open(arquivo_media, 'w:gz') as tar:
                tar.add(media_root, arcname='media')
        else:
            arquivo_media = ''

        execucao.arquivo_db = arquivo_db
        execucao.arquivo_media = arquivo_media
        execucao.tamanho_db_bytes = os.path.getsize(arquivo_db)
        execucao.tamanho_media_bytes = os.path.getsize(arquivo_media) if arquivo_media else 0
        execucao.status = 'sucesso_local'
    except subprocess.CalledProcessError as exc:
        execucao.status = 'erro'
        execucao.erro_detalhe = exc.stderr or str(exc)
        execucao.finalizado_em = timezone.now()
        execucao.save()
        logger.error("executar_backup_task: pg_dump falhou: %s", execucao.erro_detalhe)
        raise
    except Exception as exc:
        execucao.status = 'erro'
        execucao.erro_detalhe = str(exc)
        execucao.finalizado_em = timezone.now()
        execucao.save()
        logger.error("executar_backup_task: erro inesperado: %s", exc)
        raise

    # O backup local já está garantido a partir daqui — uma falha no envio remoto
    # (rede, credencial errada etc.) não pode apagar o sucesso do backup local.
    destino = BackupDestino.get_instance()
    if destino.ativo and destino.host:
        try:
            _enviar_sftp(destino, [arquivo_db] + ([arquivo_media] if arquivo_media else []))
            execucao.enviado_remoto = True
            execucao.status = 'sucesso_remoto'
        except Exception as exc:
            execucao.erro_detalhe = f'Backup local ok, mas envio remoto falhou: {exc}'
            logger.error("executar_backup_task: envio SFTP falhou: %s", exc)

    execucao.finalizado_em = timezone.now()
    execucao.save()

    _limpar_backups_antigos(backups_dir, destino.dias_retencao_local)
    return execucao.id


def _enviar_sftp(destino, arquivos_locais):
    """
    Envia os arquivos via SFTP. A chave do host é fixada na primeira conexão
    (modelo "trust on first use", como o known_hosts do SSH) e validada nas
    conexões seguintes — sem isso, paramiko aceitaria qualquer chave e o
    envio (incluindo a senha) ficaria vulnerável a man-in-the-middle.
    """
    import paramiko

    transport = paramiko.Transport((destino.host, destino.porta))
    try:
        transport.connect(username=destino.usuario, password=destino.get_senha())

        host_key = transport.get_remote_server_key()
        fingerprint = f"{host_key.get_name()}:{host_key.get_fingerprint().hex()}"
        if destino.host_key_fingerprint:
            if fingerprint != destino.host_key_fingerprint:
                raise ValueError(
                    "A chave SSH do servidor reserva mudou desde a última conexão "
                    "(possível troca de servidor ou ataque man-in-the-middle). "
                    "Envio cancelado. Se a troca foi esperada, limpe "
                    "BackupDestino.host_key_fingerprint para confiar na nova chave."
                )
        else:
            destino.host_key_fingerprint = fingerprint
            destino.save(update_fields=['host_key_fingerprint'])

        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            _sftp_mkdir_p(sftp, destino.diretorio_destino)
            for caminho_local in arquivos_locais:
                nome = caminho_local.replace('\\', '/').rsplit('/', 1)[-1]
                destino_remoto = f"{destino.diretorio_destino.rstrip('/')}/{nome}"
                sftp.put(caminho_local, destino_remoto)
        finally:
            sftp.close()
    finally:
        transport.close()


def _sftp_mkdir_p(sftp, remote_dir):
    partes = [p for p in remote_dir.split('/') if p]
    caminho = ''
    for parte in partes:
        caminho += f'/{parte}'
        try:
            sftp.stat(caminho)
        except FileNotFoundError:
            sftp.mkdir(caminho)


def _limpar_backups_antigos(backups_dir, dias_retencao):
    import os
    import time

    cutoff = time.time() - dias_retencao * 86400
    for nome in os.listdir(backups_dir):
        caminho = os.path.join(backups_dir, nome)
        if os.path.isfile(caminho) and os.path.getmtime(caminho) < cutoff:
            os.remove(caminho)
