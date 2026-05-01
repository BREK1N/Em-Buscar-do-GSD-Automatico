INFORMATICA_GROUP = 'Informatica'


def can_manage_home_content(user):
    """Apenas Informática e superuser podem criar/editar carrossel e tutoriais."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=INFORMATICA_GROUP).exists()
