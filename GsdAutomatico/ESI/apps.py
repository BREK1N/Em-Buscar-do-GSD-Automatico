from django.apps import AppConfig


class EsiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ESI'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_criar_grupo_esi, sender=self)


def _criar_grupo_esi(sender, **kwargs):
    from django.contrib.auth.models import Group
    Group.objects.get_or_create(name='ESI')
