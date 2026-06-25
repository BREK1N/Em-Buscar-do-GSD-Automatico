from django.apps import AppConfig


class EpaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'EPA'

    def ready(self):
        import EPA.signals  # noqa

        from django.db.models.signals import post_migrate
        post_migrate.connect(_criar_grupo_epa, sender=self)


def _criar_grupo_epa(sender, **kwargs):
    from django.contrib.auth.models import Group
    Group.objects.get_or_create(name='EPA - Missões')
