from django import template

register = template.Library()


@register.filter
def is_sop_operacoes(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name='SOP - Operações').exists()


@register.filter
def is_sop_escalas(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name='SOP- Escalas').exists()


@register.filter
def can_see_missoes(user):
    """Pode ver Missões: staff/superuser ou grupo SOP - Operações (não apenas SOP- Escalas)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name='SOP - Operações').exists()


@register.filter
def can_see_escalas(user):
    """Pode ver Escalas: staff/superuser ou grupo SOP- Escalas (não apenas SOP - Operações)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name='SOP- Escalas').exists()


@register.filter
def omis_numero(value):
    """Formata número de OMIS: OMIS N° 42/SOPBINFAEGL/BINFAE GL"""
    return f"OMIS N° {value}/SOPBINFAEGL/BINFAE GL"


@register.filter
def filter_slot(qs, key):
    """Filtra ItemHorario extras pelo slot_key."""
    return qs.filter(slot_key=key).order_by('ordem')


@register.filter
def join_horarios(qs):
    """Concatena horários de um queryset com '/'."""
    return '/'.join(h.horario.strftime('%H:%M') for h in qs if h.horario)
