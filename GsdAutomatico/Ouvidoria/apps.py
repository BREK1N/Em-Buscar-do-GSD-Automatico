import os
import threading
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


def _auto_delete_worker():
    """Background thread: verifica e exclui PATDs expiradas na lixeira a cada hora."""
    import time
    time.sleep(30)  # aguarda Django terminar de carregar
    while True:
        try:
            from django.utils import timezone
            from datetime import timedelta
            from Ouvidoria.models import PATD, Configuracao
            config = Configuracao.load()
            cutoff = timezone.now() - timedelta(days=config.dias_retencao_lixeira)
            expired = PATD.all_objects.filter(deleted=True, deleted_at__lte=cutoff)
            count = expired.count()
            if count:
                expired.delete()
                logger.info(f'[Lixeira] {count} PATD(s) expirada(s) excluída(s) automaticamente.')
        except Exception as e:
            logger.warning(f'[Lixeira] Erro na limpeza automática: {e}')
        time.sleep(3600)  # a cada 1 hora


class OuvidoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Ouvidoria'

    def ready(self):
        import Ouvidoria.signals  # noqa

        # Inicia worker de limpeza automática.
        # Em dev: RUN_MAIN='true' identifica o processo worker (não o reloader pai).
        # Em produção: RUN_MAIN não está definido — sempre inicia.
        run_main = os.environ.get('RUN_MAIN')
        if run_main == 'true' or run_main is None:
            t = threading.Thread(target=_auto_delete_worker, daemon=True, name='lixeira-auto-delete')
            t.start()
