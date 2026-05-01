from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = 'Cria os grupos informatica-admin e informatica-secao'

    def handle(self, *args, **options):
        admin_group, created = Group.objects.get_or_create(name='informatica-admin')
        self.stdout.write(f'{"Criado" if created else "Já existe"}: informatica-admin')

        secao_group, created = Group.objects.get_or_create(name='informatica-secao')
        self.stdout.write(f'{"Criado" if created else "Já existe"}: informatica-secao')

        self.stdout.write(self.style.SUCCESS('Grupos criados com sucesso.'))
