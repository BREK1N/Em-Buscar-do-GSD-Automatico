from django import template

register = template.Library()

@register.filter(name='is_in_group')
def is_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()

@register.filter(name='is_informatica_admin')
def is_informatica_admin_filter(user):
    return user.is_staff or user.groups.filter(name='informatica-admin').exists()

@register.filter(name='is_informatica_secao')
def is_informatica_secao_filter(user):
    return user.is_staff or user.groups.filter(name__in=['informatica-admin', 'informatica-secao']).exists()
