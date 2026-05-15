import datetime
from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone

from Secao_operacoes.models import Missao


class Command(BaseCommand):
    help = 'Simula virada de ano: verifica que a numeração de OMIS reseta em 1 no novo ano'

    def handle(self, *args, **options):
        ano_atual = timezone.localdate().year
        ano_anterior = ano_atual - 1

        # Cria missão fictícia no ano anterior com número alto
        ultima = (
            Missao.objects.filter(data_emissao__year=ano_anterior)
            .aggregate(m=models.Max('numero'))['m'] or 0
        )
        missao_teste = Missao.objects.create(
            numero=ultima + 1,
            nome_missao='[TESTE VIRADA ANO]',
            local='Teste',
            objetivo='Missão de teste para verificar reset anual',
            data_emissao=datetime.date(ano_anterior, 12, 31),
            data_missao=datetime.date(ano_anterior, 12, 31),
        )
        self.stdout.write(f"Criada missão de teste no ano {ano_anterior}: OMIS N° {missao_teste.numero}")

        # Calcula próximo número para o ano atual
        proximo_atual = (
            Missao.objects.filter(data_emissao__year=ano_atual)
            .aggregate(m=models.Max('numero'))['m'] or 0
        ) + 1
        self.stdout.write(f"Próximo número para {ano_atual}: {proximo_atual}")

        if proximo_atual == 1:
            self.stdout.write(self.style.SUCCESS("PASS — numeração reseta corretamente para 1 no novo ano"))
        else:
            self.stdout.write(self.style.WARNING(f"FAIL — esperado 1, obtido {proximo_atual}"))

        missao_teste.delete()
        self.stdout.write("Missão de teste removida.")
