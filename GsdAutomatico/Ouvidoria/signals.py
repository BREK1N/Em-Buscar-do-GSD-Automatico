# GsdAutomatico/Ouvidoria/signals.py
import logging

from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group
from .models import Configuracao
from .permissions import OUVIDORIA_GROUPS, COMANDANTE
from informatica.models import ConfiguracaoComandantes

logger = logging.getLogger(__name__)

@receiver(post_migrate)
def create_default_groups(sender, **kwargs):
    """
    Cria automaticamente os grupos de permissões da Ouvidoria e do Comandante
    após a execução das migrações do banco de dados.
    """
    # Verifica se o sender é a aplicação atual para evitar execução duplicada
    # Ajuste 'Ouvidoria' se o nome da tua AppConfig for diferente
    if sender.name == 'Ouvidoria':
        # 1. Cria grupos da Ouvidoria (S2, CB, ADJUNTO, CHEFE, APURADOR)
        for group_name in OUVIDORIA_GROUPS:
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                logger.info("Grupo criado automaticamente: %s", group_name)

        # 2. Garante que o grupo Comandante existe
        group, created = Group.objects.get_or_create(name=COMANDANTE)
        if created:
            logger.info("Grupo criado automaticamente: %s", COMANDANTE)

@receiver(post_save, sender=ConfiguracaoComandantes)
def on_commander_change(sender, instance, **kwargs):
    """
    Quando a configuração de comandantes é salva, garante que apenas
    o usuário do comandante atual tenha a permissão 'Comandante'.
    """
    try:
        from login.models import UserProfile
    except ImportError:
        pass

    try:
        comandante_group, created = Group.objects.get_or_create(name=COMANDANTE)

        new_commander_militar = instance.comandante_gsd
        new_commander_user = None

        # Tenta encontrar o usuário associado ao novo comandante
        if new_commander_militar:
            try:
                new_commander_user = UserProfile.objects.get(militar=new_commander_militar).user
            except Exception:
                # O comandante definido ainda não tem um usuário associado.
                pass
        
        # Remove a permissão de 'Comandante' de todos os usuários, EXCETO o novo comandante.
        comandante_group.user_set.exclude(pk=getattr(new_commander_user, 'pk', None)).clear()
        
        # Se o novo usuário comandante existe e ainda não está no grupo, adiciona-o.
        if new_commander_user and not new_commander_user.groups.filter(name=COMANDANTE).exists():
            new_commander_user.groups.add(comandante_group)

    except Exception as e:
        logger.error("Erro no signal on_commander_change: %s", e)