# GsdAutomatico/login/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from .models import UserProfile
from Ouvidoria.models import Configuracao

@receiver(post_save, sender=UserProfile)
def on_user_profile_save(sender, instance, **kwargs):
    """
    Quando um perfil é salvo e o militar associado é o comandante configurado,
    garante que o usuário esteja no grupo 'Comandante'.
    A remoção do grupo é gerenciada exclusivamente por on_commander_change
    (via post_save de ConfiguracaoComandantes) para evitar que salvamentos
    rotineiros do perfil (ex: update_last_login no login) retirem o grupo
    de usuários legitimamente adicionados.
    """
    try:
        config = Configuracao.load()
        is_commander = instance.militar and (instance.militar == config.comandante_gsd)

        if is_commander:
            comandante_group, _ = Group.objects.get_or_create(name='Comandante')
            if not instance.user.groups.filter(name='Comandante').exists():
                instance.user.groups.add(comandante_group)

    except Exception:
        pass
