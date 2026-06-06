from django.apps import AppConfig


class SecaoPessoalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Secao_pessoal'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_criar_grupos_s1, sender=self)


def _criar_grupos_s1(sender, **kwargs):
    from django.contrib.auth.models import Group
    Group.objects.get_or_create(name='Seção de Pessoal (S1)')
