from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from caixa_entrada.models import Notificacao

class Command(BaseCommand):
    help = 'Exclui permanentemente notificações que estão na lixeira há mais de 30 dias.'

    def handle(self, *args, **options):
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        notificacoes_para_excluir = Notificacao.all_objects.filter(
            deleted=True,
            deleted_at__lt=thirty_days_ago
        )
        
        count = notificacoes_para_excluir.count()
        
        if count > 0:
            self.stdout.write(self.style.WARNING(f'Encontradas {count} notificações para exclusão permanente...'))
            notificacoes_para_excluir.delete()
            self.stdout.write(self.style.SUCCESS(f'Operação concluída. {count} notificações foram excluídas permanentemente.'))
        else:
            self.stdout.write(self.style.SUCCESS('Nenhuma notificação na lixeira para exclusão automática.'))
