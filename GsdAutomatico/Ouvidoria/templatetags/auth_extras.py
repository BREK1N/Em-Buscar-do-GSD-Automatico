from django import template
from Ouvidoria import permissions

register = template.Library()


@register.filter(name='is_informatica_admin')
def is_informatica_admin_filter(user):
    return user.is_staff or user.groups.filter(name='informatica-admin').exists()


@register.filter(name='is_informatica_secao')
def is_informatica_secao_filter(user):
    return user.is_staff or user.groups.filter(name__in=['informatica-admin', 'informatica-secao']).exists()


@register.filter(name='user_foto_url')
def user_foto_url(user):
    """Retorna a URL da foto do perfil do usuário, ou string vazia."""
    try:
        if user.userprofile.foto:
            return user.userprofile.foto.url
    except Exception:
        pass
    return ''

@register.filter(name='has_comandante_access')
def has_comandante_access_filter(user):
    """Verifica se o usuário pertence ao grupo 'Comandante' ou é superuser."""
    return permissions.has_comandante_access(user)

@register.filter(name='has_ouvidoria_access')
def has_ouvidoria_access_filter(user):
    """Verifica se o usuário pertence a algum dos grupos da Ouvidoria ou é superuser."""
    return permissions.is_ouvidoria_member(user)

@register.filter(name='can_edit_patd')
def can_edit_patd_filter(user):
    """Verifica se o usuário pode editar uma PATD."""
    return permissions.can_edit_patd(user)

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

@register.filter(name='can_change_patd_date')
def can_change_patd_date_filter(user):
    """Verifica se o usuário pode alterar a data da PATD."""
    return permissions.can_change_patd_date(user)

@register.filter(name='can_finalizar_ouvidoria')
def can_finalizar_ouvidoria_filter(user):
    """Verifica se o usuário pode usar o botão Finalizar(Ouvidoria) — apenas ADJUNTO e Chefe."""
    return permissions.can_finalizar_ouvidoria(user)

@register.filter(name='abs_value')
def abs_value(value):
    """Retorna o valor absoluto de um número."""
    return abs(value)