# Constants for group names
OUVIDORIA_S2 = "S2 - Ouvidoria"
OUVIDORIA_CB = "CB - Ouvidoria"
OUVIDORIA_ADJUNTO = "ADJUNTO - Ouvidoria"
OUVIDORIA_CHEFE = "Chefe - Ouvidoria"
COMANDANTE = "Comandante"

OUVIDORIA_GROUPS = [OUVIDORIA_S2, OUVIDORIA_CB, OUVIDORIA_ADJUNTO, OUVIDORIA_CHEFE]

def is_in_group(user, group_name):
    """
    Checks if a user is in a specific group.
    """
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()

def is_ouvidoria_member(user):
    """
    Checks if the user belongs to any of the 'Ouvidoria' groups or is a superuser.
    This will replace the old `has_ouvidoria_access`.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=OUVIDORIA_GROUPS).exists()

def can_delete_patd(user):
    """
    Checks if the user has permission to delete a PATD.
    (ADJUNTO and Chefe roles)
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=[OUVIDORIA_ADJUNTO, OUVIDORIA_CHEFE]).exists()

def can_edit_apuracao(user):
    """
    Checks if the user has permission to edit the 'Apuração' fields of a PATD.
    (ADJUNTO and Chefe roles)
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=[OUVIDORIA_ADJUNTO, OUVIDORIA_CHEFE]).exists()
    
def can_edit_transgressao(user):
    """
    Checks if the user has permission to edit the 'transgressao' field of a PATD.
    (ADJUNTO and Chefe roles)
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=[OUVIDORIA_ADJUNTO, OUVIDORIA_CHEFE]).exists()

def can_manage_absences(user):
    """
    Checks if the user can manage absences for the Ouvidoria staff.
    (CB, ADJUNTO, and Chefe roles)
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=[OUVIDORIA_CB, OUVIDORIA_ADJUNTO, OUVIDORIA_CHEFE]).exists()

# Redefine has_ouvidoria_access to use the new logic for backward compatibility in the short term.
def has_ouvidoria_access(user):
    """Verifica se o utilizador pertence a algum grupo da 'Ouvidoria' ou é um superutilizador."""
    return is_ouvidoria_member(user)

def has_comandante_access(user):
    """Verifica se o utilizador pertence ao grupo 'Comandante' ou é um superutilizador."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=COMANDANTE).exists() or user.is_superuser
