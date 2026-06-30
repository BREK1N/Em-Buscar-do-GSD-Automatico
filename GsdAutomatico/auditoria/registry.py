"""
Auto-instrumentação genérica de auditoria via post_save/post_delete.

Registrar um modelo aqui cobre TODA criação/edição/exclusão dele — não importa
se aconteceu numa view normal, no admin do Django ou numa ação em lote — sem
precisar tocar em cada view que salva esse modelo.
"""
import logging

from django.db.models.signals import pre_save, post_save, post_delete

from .middleware import get_usuario_atual
from .utils import registrar

logger = logging.getLogger(__name__)

_SNAPSHOT_ATTR = '_auditoria_snapshot_anterior'


def registrar_modelo(model, *, secao, objeto_tipo, permissao_resolver, campo_id,
                      campos_monitorados=None, label=None):
    """
    secao: chave curta da seção (ex. 'operacoes').
    objeto_tipo: nome legível do objeto (ex. 'Missão/OMIS').
    permissao_resolver: callable(user) -> str, ex. via utils.resolver_label(user, {...}).
    campo_id: callable(instance) -> valor mostrado na descrição (ex. lambda m: m.numero).
    campos_monitorados: lista de nomes de campos que entram no diff de "editou".
    label: nome usado na frase ("criou {label} {id}"); por padrão usa objeto_tipo.
    """
    campos_monitorados = campos_monitorados or []
    label = label or objeto_tipo

    logger.info("[AUDITORIA] registrar_modelo: %s (secao=%s objeto_tipo=%s campos=%s)",
                model.__name__, secao, objeto_tipo, campos_monitorados)

    def _pre_save(sender, instance, **kwargs):
        logger.debug("[AUDITORIA] pre_save: %s pk=%s", sender.__name__, instance.pk)
        if instance.pk and campos_monitorados:
            anterior = sender.objects.filter(pk=instance.pk).values(*campos_monitorados).first()
            logger.debug("[AUDITORIA] pre_save snapshot: %s", anterior)
        else:
            anterior = None
        setattr(instance, _SNAPSHOT_ATTR, anterior)

    def _post_save(sender, instance, created, **kwargs):
        logger.debug("[AUDITORIA] post_save: %s pk=%s created=%s", sender.__name__, instance.pk, created)
        try:
            user = get_usuario_atual()
            if user is None:
                logger.debug("[AUDITORIA] post_save: sem usuário no contexto (task/migração) — skip")
                return
            logger.debug("[AUDITORIA] post_save: user=%s", user.username)
            permissao = permissao_resolver(user)
            obj_id = campo_id(instance)

            if created:
                acao = 'criou'
                descricao = f"criou {label} {obj_id}"
            else:
                acao = 'editou'
                anterior = getattr(instance, _SNAPSHOT_ATTR, None)
                alteracoes = []
                if anterior:
                    for campo in campos_monitorados:
                        velho = anterior.get(campo)
                        novo = getattr(instance, campo)
                        if str(velho) != str(novo):
                            alteracoes.append(f"{campo}: {velho} → {novo}")
                # Se há campos monitorados mas nenhum mudou, skip para evitar entradas vazias
                # (ex: save(update_fields=['assinatura_oficial']) não altera campos monitorados)
                if not alteracoes and campos_monitorados:
                    logger.debug("[AUDITORIA] post_save: nenhuma alteração em campos monitorados — skip")
                    return
                if alteracoes:
                    descricao = f"editou {label} {obj_id} (alterou: {'; '.join(alteracoes)})"
                else:
                    descricao = f"editou {label} {obj_id}"

            logger.debug("[AUDITORIA] post_save: registrando acao='%s' descricao='%s'", acao, descricao)
            registrar(user, secao=secao, permissao=permissao, acao=acao,
                      descricao=descricao, objeto_tipo=objeto_tipo, objeto_id=obj_id)
        except Exception:
            logger.exception("registry.post_save: falha ao auditar %s", sender)

    def _post_delete(sender, instance, **kwargs):
        logger.debug("[AUDITORIA] post_delete: %s pk=%s", sender.__name__, instance.pk)
        try:
            user = get_usuario_atual()
            if user is None:
                logger.debug("[AUDITORIA] post_delete: sem usuário no contexto — skip")
                return
            permissao = permissao_resolver(user)
            obj_id = campo_id(instance)
            logger.debug("[AUDITORIA] post_delete: registrando user=%s obj=%s/%s", user.username, objeto_tipo, obj_id)
            registrar(user, secao=secao, permissao=permissao, acao='excluiu',
                      descricao=f"excluiu {label} {obj_id}", objeto_tipo=objeto_tipo, objeto_id=obj_id)
        except Exception:
            logger.exception("registry.post_delete: falha ao auditar %s", sender)

    # weak=False: os receivers são closures locais — sem isso o garbage collector
    # os coletaria e o signal pararia de disparar silenciosamente.
    pre_save.connect(_pre_save, sender=model, weak=False)
    post_save.connect(_post_save, sender=model, weak=False)
    post_delete.connect(_post_delete, sender=model, weak=False)
    logger.info("[AUDITORIA] sinais conectados para %s", model.__name__)
