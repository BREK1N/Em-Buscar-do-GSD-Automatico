from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Exclui PATDs que passaram do prazo de retenção na lixeira.'

    def handle(self, *args, **options):
        from Ouvidoria.models import PATD, Configuracao
        config = Configuracao.load()
        cutoff = timezone.now() - timedelta(days=config.dias_retencao_lixeira)
        expired = PATD.all_objects.filter(deleted=True, deleted_at__lte=cutoff)
        count = expired.count()
        expired.delete()
        self.stdout.write(self.style.SUCCESS(
            f'{count} PATD(s) expirada(s) excluída(s) '
            f'(retenção: {config.dias_retencao_lixeira} dias).'
        ))
