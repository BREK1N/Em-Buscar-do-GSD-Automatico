import logging

from .middleware import get_usuario_atual

logger = logging.getLogger(__name__)


def _nome_guerra(user) -> str:
    try:
        militar = user.profile.militar
    except Exception:
        return ''
    return militar.nome_guerra if militar else ''


def resolver_label(user, mapeamento: dict) -> str:
    """Percorre os grupos do usuário e devolve o primeiro label mapeado (ex.: 'Sop- Missões')."""
    if user is None:
        return '—'
    if user.is_superuser:
        return 'Superusuário'
    nomes_grupos = set(user.groups.values_list('name', flat=True))
    for nome_grupo, label in mapeamento.items():
        if nome_grupo in nomes_grupos:
            return label
    return '—'


def registrar(user, secao, permissao, acao, descricao, objeto_tipo='', objeto_id=''):
    """
    Registra uma ação de auditoria de forma assíncrona (Celery).
    `user` pode ser omitido (None) — nesse caso usa o usuário da requisição atual,
    capturado pela CurrentUserMiddleware (útil dentro de signals post_save/post_delete).
    """
    from .tasks import registrar_log_task

    if user is None:
        user = get_usuario_atual()
    if user is None or not getattr(user, 'is_authenticated', False):
        return

    try:
        registrar_log_task.delay(
            usuario_id=user.id,
            username=user.username,
            nome_guerra=_nome_guerra(user),
            permissao=permissao or '—',
            secao=secao or '',
            acao=acao or '',
            objeto_tipo=objeto_tipo or '',
            objeto_id=objeto_id,
            descricao=descricao,
        )
    except Exception:
        logger.exception("registrar: falha ao despachar log de auditoria (%s / %s)", secao, descricao)
