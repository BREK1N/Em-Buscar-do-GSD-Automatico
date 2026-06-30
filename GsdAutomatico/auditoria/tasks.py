import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def registrar_log_task(usuario_id, username, nome_guerra, permissao, secao, acao,
                        objeto_tipo, objeto_id, descricao):
    """Grava o LogAuditoria em background — a auditoria nunca pode atrasar/derrubar a ação principal."""
    from .models import LogAuditoria

    logger.info("[AUDITORIA] registrar_log_task: user=%s secao=%s acao=%s objeto=%s/%s",
                username, secao, acao, objeto_tipo, objeto_id)
    try:
        log = LogAuditoria.objects.create(
            usuario_id=usuario_id,
            username=username,
            nome_guerra=nome_guerra,
            permissao=permissao,
            secao=secao,
            acao=acao,
            objeto_tipo=objeto_tipo,
            objeto_id=str(objeto_id) if objeto_id is not None else '',
            descricao=descricao,
        )
        logger.info("[AUDITORIA] log gravado: id=%s", log.pk)
    except Exception:
        logger.exception("registrar_log_task: falha ao gravar log de auditoria (%s / %s)", secao, descricao)
