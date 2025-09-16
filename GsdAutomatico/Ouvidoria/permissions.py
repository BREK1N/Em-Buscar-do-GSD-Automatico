def has_ouvidoria_access(user):
    """Verifica se o utilizador pertence ao grupo 'Ouvidoria' ou é um superutilizador."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Ouvidoria').exists() or user.is_superuser

def has_comandante_access(user):
    """Verifica se o utilizador pertence ao grupo 'Comandante' ou é um superutilizador."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='Comandante').exists() or user.is_superuser
