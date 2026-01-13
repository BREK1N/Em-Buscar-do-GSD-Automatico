# GsdAutomatico/Ouvidoria/signals.py

from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group
from .models import Configuracao
from .permissions import OUVIDORIA_GROUPS, COMANDANTE

@receiver(post_migrate)
def create_default_groups(sender, **kwargs):
    """
    Cria automaticamente os grupos de permissões da Ouvidoria e do Comandante
    após a execução das migrações do banco de dados.
    """
    # Verifica se o sender é a aplicação atual para evitar execução duplicada
    # Ajuste 'Ouvidoria' se o nome da tua AppConfig for diferente
    if sender.name == 'Ouvidoria':
        # 1. Cria grupos da Ouvidoria (S2, CB, ADJUNTO, CHEFE)
        for group_name in OUVIDORIA_GROUPS:
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                print(f"--- [SISTEMA] Grupo criado automaticamente: {group_name}")

        # 2. Garante que o grupo Comandante existe
        group, created = Group.objects.get_or_create(name=COMANDANTE)
        if created:
            print(f"--- [SISTEMA] Grupo criado automaticamente: {COMANDANTE}")

@receiver(post_save, sender=Configuracao)
def on_commander_change(sender, instance, **kwargs):
    """
    Quando a configuração é salva (ex: comandante é definido),
    esta função garante que apenas o usuário do comandante atual
    tenha a permissão 'Comandante'.
    """
    # Importa localmente para evitar problemas de dependência circular
    # Tenta importar de login.models ou onde quer que UserProfile esteja
    try:
        from login.models import UserProfile 
    except ImportError:
        # Fallback caso a estrutura de pastas seja diferente
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
        # Em caso de qualquer erro (ex: BD não pronto na migração inicial), ignora.
        print(f"Erro no signal on_commander_change: {e}")
        pass