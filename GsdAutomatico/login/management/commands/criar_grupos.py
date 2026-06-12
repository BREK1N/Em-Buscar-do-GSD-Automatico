from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

TODOS_OS_GRUPOS = [
    # Acesso geral / chefia
    'Comandante',

    # ESI
    'ESI',
    'ESI-Missões',

    # EPA
    'EPA - Missões',

    # Seção de Operações
    'SOP - Operações',
    'SOP- Escalas',

    # Informática
    'informatica-admin',
    'informatica-secao',

    # Seção de Pessoal
    'Seção de Pessoal (S1)',

    # Ouvidoria (cada papel dá acesso direto — sem grupo genérico)
    'S2 - Ouvidoria',
    'CB - Ouvidoria',
    'ADJUNTO - Ouvidoria',
    'Chefe - Ouvidoria',
    'Apurador - Ouvidoria',
]


class Command(BaseCommand):
    help = 'Cria todos os grupos do sistema (idempotente — seguro de rodar múltiplas vezes)'

    def handle(self, *args, **options):
        criados = []
        ja_existiam = []

        for nome in TODOS_OS_GRUPOS:
            _, created = Group.objects.get_or_create(name=nome)
            if created:
                criados.append(nome)
            else:
                ja_existiam.append(nome)

        if criados:
            self.stdout.write(self.style.SUCCESS(f'Criados ({len(criados)}):'))
            for nome in criados:
                self.stdout.write(f'  + {nome}')

        if ja_existiam:
            self.stdout.write(f'Já existiam ({len(ja_existiam)}):')
            for nome in ja_existiam:
                self.stdout.write(f'  = {nome}')

        self.stdout.write(self.style.SUCCESS('\nTodos os grupos estão presentes.'))
