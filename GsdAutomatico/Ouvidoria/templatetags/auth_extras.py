from django import template
from Ouvidoria import permissions

register = template.Library()

@register.filter(name='has_comandante_access')
def has_comandante_access_filter(user):
    """Verifica se o usuário pertence ao grupo 'Comandante' ou é superuser."""
    return permissions.has_comandante_access(user)

@register.filter(name='has_ouvidoria_access')
def has_ouvidoria_access_filter(user):
    """Verifica se o usuário pertence a algum dos grupos da Ouvidoria ou é superuser."""
    return permissions.is_ouvidoria_member(user)

@register.filter(name='can_delete_patd')
def can_delete_patd_filter(user):
    """Verifica se o usuário pode excluir uma PATD."""
    return permissions.can_delete_patd(user)

@register.filter(name='can_edit_apuracao')
def can_edit_apuracao_filter(user):
    """Verifica se o usuário pode editar a apuração de uma PATD."""
    return permissions.can_edit_apuracao(user)
    
@register.filter(name='can_edit_transgressao')
def can_edit_transgressao_filter(user):
    """Verifica se o usuário pode editar a transgressão de uma PATD."""
    return permissions.can_edit_transgressao(user)
