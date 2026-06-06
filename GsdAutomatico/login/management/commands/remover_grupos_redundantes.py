from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

# Grupos a remover → grupo canônico para migrar os usuários
# None = sem migração automática (exibe aviso)
MIGRACOES = {
    'S1':                  'Seção de Pessoal (S1)',
    'seção de operação':   'SOP - Operações',
    'Militar da Informática': 'informatica-secao',
    'Ouvidoria':           'S2 - Ouvidoria',
}


class Command(BaseCommand):
    help = 'Remove grupos redundantes do banco, migrando usuários para os grupos canônicos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Mostra o que seria feito sem executar.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        if dry:
            self.stdout.write(self.style.WARNING('--- MODO DRY-RUN (nenhuma alteração será feita) ---\n'))

        for grupo_antigo, grupo_novo in MIGRACOES.items():
            try:
                old_grp = Group.objects.get(name=grupo_antigo)
            except Group.DoesNotExist:
                self.stdout.write(f'[skip] "{grupo_antigo}" não existe no banco.')
                continue

            users = list(old_grp.user_set.all())
            self.stdout.write(f'\n[grupo] "{grupo_antigo}" — {len(users)} usuário(s)')

            if users and grupo_novo:
                new_grp, created = Group.objects.get_or_create(name=grupo_novo)
                for u in users:
                    already = u.groups.filter(name=grupo_novo).exists()
                    action = 'já está em' if already else 'migrado para'
                    self.stdout.write(f'  {u.username}: {action} "{grupo_novo}"')
                    if not dry and not already:
                        u.groups.add(new_grp)
            elif users:
                self.stdout.write(self.style.WARNING(
                    f'  {len(users)} usuário(s) sem destino — remova manualmente.'
                ))

            if not dry:
                old_grp.delete()
                self.stdout.write(self.style.SUCCESS(f'  Grupo "{grupo_antigo}" removido.'))
            else:
                self.stdout.write(f'  [dry-run] removeria "{grupo_antigo}".')

        self.stdout.write('\n' + self.style.SUCCESS('Concluído.'))
