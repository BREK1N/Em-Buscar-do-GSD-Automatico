"""
Cria 20 usuários de teste para load testing. Remove-os ao final.
Uso:
  python manage.py criar_usuarios_teste --criar
  python manage.py criar_usuarios_teste --remover
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

PREFIX = "loadtest_"
SENHA  = "LoadTest@2024!"
NOMES  = [f"user{i:02d}" for i in range(1, 21)]   # loadtest_user01 … loadtest_user20


class Command(BaseCommand):
    help = "Gerencia usuários de load testing"

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--criar",   action="store_true")
        group.add_argument("--remover", action="store_true")

    def handle(self, *args, **options):
        if options["criar"]:
            self._criar()
        else:
            self._remover()

    def _criar(self):
        criados = 0
        for nome in NOMES:
            username = PREFIX + nome
            if not User.objects.filter(username=username).exists():
                User.objects.create_user(
                    username=username,
                    password=SENHA,
                    email=f"{username}@loadtest.local",
                    is_active=True,
                )
                criados += 1
        self.stdout.write(self.style.SUCCESS(
            f"{criados} usuário(s) criado(s). Senha: {SENHA}"
        ))

    def _remover(self):
        qs = User.objects.filter(username__startswith=PREFIX)
        n = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"{n} usuário(s) removido(s)."))
