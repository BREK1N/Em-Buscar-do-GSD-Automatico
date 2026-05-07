def can_manage_home_content(user):
    """Apenas administradores (staff/superuser) podem criar/editar tutoriais e carrossel."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff
