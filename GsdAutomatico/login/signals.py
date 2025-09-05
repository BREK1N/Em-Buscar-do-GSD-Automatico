# GsdAutomatico/login/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from .models import UserProfile
from Ouvidoria.models import Configuracao

@receiver(post_save, sender=UserProfile)
def on_user_profile_save(sender, instance, **kwargs):
    """
    Quando um perfil de usuário é salvo (criado ou atualizado),
    verifica se o militar associado é o comandante atual e, em caso afirmativo,
    concede a permissão 'Comandante'. Também remove a permissão se o militar
    deixa de ser o comandante.
    """
    try:
        config = Configuracao.load()
        comandante_group, _ = Group.objects.get_or_create(name='Comandante')

        # Verifica se o militar associado a este perfil é o comandante definido nas configurações
        is_commander = instance.militar and (instance.militar == config.comandante_gsd)
        
        # Verifica se este usuário já está no grupo de comandantes
        is_in_group = instance.user.groups.filter(name='Comandante').exists()

        if is_commander and not is_in_group:
            # Se ele É o comandante mas NÃO está no grupo, adiciona.
            instance.user.groups.add(comandante_group)
        elif not is_commander and is_in_group:
            # Se ele NÃO é o comandante mas ESTÁ no grupo, remove.
            instance.user.groups.remove(comandante_group)

    except Exception:
        # Em caso de qualquer erro (ex: BD não pronto na migração inicial), ignora.
        pass
