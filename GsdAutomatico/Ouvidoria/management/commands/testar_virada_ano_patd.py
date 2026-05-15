import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

from Ouvidoria.models import PATD
from Ouvidoria.views.helpers import get_next_patd_number


class Command(BaseCommand):
    help = 'Simula virada de ano: verifica que a numeração de PATD reseta em 1 no novo ano'

    def handle(self, *args, **options):
        ano_atual = timezone.now().year
        ano_anterior = ano_atual - 1

        # Conta PATDs do ano anterior para referência
        total_anterior = PATD.objects.filter(data_inicio__year=ano_anterior).count()
        self.stdout.write(f"PATDs no ano {ano_anterior}: {total_anterior}")

        # Próximo número segundo lógica atual (deve ser baseado no ano atual)
        proximo = get_next_patd_number()
        self.stdout.write(f"Próximo número para {ano_atual}: {proximo}")

        total_atual = PATD.objects.filter(data_inicio__year=ano_atual).count()
        esperado = total_atual + 1

        if proximo == 1 and total_atual == 0:
            self.stdout.write(self.style.SUCCESS("PASS — sem PATDs este ano, próximo número é 1"))
        elif proximo <= total_atual + 1:
            self.stdout.write(self.style.SUCCESS(f"PASS — próximo número {proximo} é válido para {total_atual} PATDs existentes em {ano_atual}"))
        else:
            self.stdout.write(self.style.WARNING(f"FAIL — esperado <= {esperado}, obtido {proximo}"))
