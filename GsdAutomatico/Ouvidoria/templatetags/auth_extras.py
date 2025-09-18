from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.filter(name='has_comandante_access')
def has_comandante_access(user):
    """Verifica se o usuário pertence ao grupo 'Comandante' ou é superuser."""
    return user.groups.filter(name='Comandante').exists() or user.is_superuser
