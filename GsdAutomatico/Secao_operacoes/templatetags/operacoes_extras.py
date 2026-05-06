from django import template

register = template.Library()


@register.filter
def is_sop_operacoes(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name='SOP - Operações').exists()
