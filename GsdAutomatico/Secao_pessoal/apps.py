import os
import threading
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


def _auto_delete_worker():
    """Background thread: verifica e exclui militares expirados na lixeira a cada hora."""
    import time
    time.sleep(30)  # aguarda Django terminar de carregar
    while True:
        try:
            from django.utils import timezone
            from datetime import timedelta
            from Secao_pessoal.models import Efetivo, DIAS_RETENCAO_LIXEIRA_EFETIVO
            cutoff = timezone.now() - timedelta(days=DIAS_RETENCAO_LIXEIRA_EFETIVO)
            expired = Efetivo.all_objects.filter(deleted=True, deleted_at__lte=cutoff)
            count = expired.count()
            if count:
                expired.delete()
                logger.info(f'[Lixeira Efetivo] {count} militar(es) expirado(s) excluído(s) automaticamente.')
        except Exception as e:
            logger.warning(f'[Lixeira Efetivo] Erro na limpeza automática: {e}')
        time.sleep(3600)  # a cada 1 hora


class SecaoPessoalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Secao_pessoal'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_criar_grupos_s1, sender=self)

        # Inicia worker de limpeza automática.
        # Em dev: RUN_MAIN='true' identifica o processo worker (não o reloader pai).
        # Em produção: RUN_MAIN não está definido — sempre inicia.
        run_main = os.environ.get('RUN_MAIN')
        if run_main == 'true' or run_main is None:
            t = threading.Thread(target=_auto_delete_worker, daemon=True, name='lixeira-efetivo-auto-delete')
            t.start()


def _criar_grupos_s1(sender, **kwargs):
    from django.contrib.auth.models import Group
    Group.objects.get_or_create(name='Seção de Pessoal (S1)')
