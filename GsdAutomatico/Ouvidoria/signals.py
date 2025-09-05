# GsdAutomatico/Ouvidoria/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from .models import Configuracao

@receiver(post_save, sender=Configuracao)
def on_commander_change(sender, instance, **kwargs):
    """
    Quando a configuração é salva (ex: comandante é definido),
    esta função garante que apenas o usuário do comandante atual
    tenha a permissão 'Comandante'.
    """
    # Importa localmente para evitar problemas de dependência circular
    from login.models import UserProfile 

    try:
        comandante_group, created = Group.objects.get_or_create(name='Comandante')
        
        new_commander_militar = instance.comandante_gsd
        new_commander_user = None

        # Tenta encontrar o usuário associado ao novo comandante
        if new_commander_militar:
            try:
                new_commander_user = UserProfile.objects.get(militar=new_commander_militar).user
            except UserProfile.DoesNotExist:
                # O comandante definido ainda não tem um usuário associado.
                # A permissão será atribuída quando o usuário for criado/associado.
                pass
        
        # Remove a permissão de 'Comandante' de todos os usuários, EXCETO o novo comandante.
        # Se o novo comandante não tiver usuário, remove de todos.
        comandante_group.user_set.exclude(pk=getattr(new_commander_user, 'pk', None)).clear()
        
        # Se o novo usuário comandante existe e ainda não está no grupo, adiciona-o.
        if new_commander_user and not new_commander_user.groups.filter(name='Comandante').exists():
            new_commander_user.groups.add(comandante_group)

    except Exception:
        # Em caso de qualquer erro (ex: BD não pronto na migração inicial), ignora para não quebrar o sistema.
        pass
