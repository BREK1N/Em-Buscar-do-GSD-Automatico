"""
Simula uma virada de ano no sistema para testar o reset de numeração.

Modos:
  --aplicar   Move missões e PATDs do ano atual para o ano anterior (simula que já passou o ano)
  --reverter  Desfaz a simulação, restaurando os dados para o ano original

Uso:
  python manage.py simular_virada_ano --aplicar
  python manage.py simular_virada_ano --reverter
"""
import json
import os
import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction

BACKUP_PATH = '/tmp/simular_virada_ano_backup.json'


class Command(BaseCommand):
    help = 'Simula passagem de ano para testar reset de numeração de OMIS e PATD'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--aplicar', action='store_true', help='Simula virada: move dados do ano atual para o ano anterior')
        group.add_argument('--reverter', action='store_true', help='Desfaz a simulação e restaura os dados originais')

    def handle(self, *args, **options):
        if options['aplicar']:
            self._aplicar()
        else:
            self._reverter()

    def _aplicar(self):
        if os.path.exists(BACKUP_PATH):
            raise CommandError(
                f'Já existe um backup em {BACKUP_PATH}. '
                'Execute --reverter antes de aplicar novamente.'
            )

        from Secao_operacoes.models import Missao
        from Ouvidoria.models import PATD

        ano_atual = timezone.localdate().year
        ano_anterior = ano_atual - 1
        delta_ano = datetime.timedelta(days=365)

        missoes = list(Missao.objects.filter(data_emissao__year=ano_atual).values('pk', 'data_emissao', 'data_missao'))
        patds = list(PATD.objects.filter(data_inicio__year=ano_atual).values('pk', 'data_inicio'))

        if not missoes and not patds:
            self.stdout.write(self.style.WARNING('Nenhuma missão ou PATD encontrada no ano atual. Nada a fazer.'))
            return

        backup = {'missoes': [], 'patds': [], 'ano_original': ano_atual}

        with transaction.atomic():
            for m in missoes:
                missao = Missao.objects.get(pk=m['pk'])
                backup['missoes'].append({
                    'pk': missao.pk,
                    'data_emissao': missao.data_emissao.isoformat(),
                    'data_missao': missao.data_missao.isoformat(),
                })
                missao.data_emissao = missao.data_emissao - delta_ano
                missao.data_missao = missao.data_missao - delta_ano
                missao.save(update_fields=['data_emissao', 'data_missao'])

            for p in patds:
                patd = PATD.objects.get(pk=p['pk'])
                backup['patds'].append({
                    'pk': patd.pk,
                    'data_inicio': patd.data_inicio.isoformat(),
                })
                patd.data_inicio = patd.data_inicio - delta_ano
                patd.save(update_fields=['data_inicio'])

        with open(BACKUP_PATH, 'w') as f:
            json.dump(backup, f)

        self.stdout.write(self.style.SUCCESS(
            f'\nSimulação aplicada com sucesso!'
            f'\n  {len(missoes)} missão(ões) movidas de {ano_atual} → {ano_anterior}'
            f'\n  {len(patds)} PATD(s) movidas de {ano_atual} → {ano_anterior}'
            f'\n  Backup salvo em {BACKUP_PATH}'
            f'\n\nAgora crie uma nova OMIS e uma nova PATD e verifique se o número começa em 1.'
            f'\nQuando terminar, execute: python manage.py simular_virada_ano --reverter'
        ))

    def _reverter(self):
        if not os.path.exists(BACKUP_PATH):
            raise CommandError(f'Nenhum backup encontrado em {BACKUP_PATH}. Execute --aplicar primeiro.')

        with open(BACKUP_PATH) as f:
            backup = json.load(f)

        from Secao_operacoes.models import Missao
        from Ouvidoria.models import PATD

        with transaction.atomic():
            for m in backup['missoes']:
                try:
                    missao = Missao.objects.get(pk=m['pk'])
                    missao.data_emissao = datetime.date.fromisoformat(m['data_emissao'])
                    missao.data_missao = datetime.date.fromisoformat(m['data_missao'])
                    missao.save(update_fields=['data_emissao', 'data_missao'])
                except Missao.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'  Missão pk={m["pk"]} não encontrada (pode ter sido deletada durante o teste)'))

            for p in backup['patds']:
                try:
                    patd = PATD.objects.get(pk=p['pk'])
                    patd.data_inicio = datetime.datetime.fromisoformat(p['data_inicio'])
                    patd.save(update_fields=['data_inicio'])
                except PATD.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'  PATD pk={p["pk"]} não encontrada (pode ter sido deletada durante o teste)'))

        os.remove(BACKUP_PATH)

        ano_original = backup['ano_original']
        self.stdout.write(self.style.SUCCESS(
            f'\nSimulação revertida com sucesso!'
            f'\n  {len(backup["missoes"])} missão(ões) restauradas para {ano_original}'
            f'\n  {len(backup["patds"])} PATD(s) restauradas para {ano_original}'
            f'\n  Backup removido.'
            f'\n\nLembre-se de deletar as OMIS e PATD de teste criadas durante a simulação.'
        ))
