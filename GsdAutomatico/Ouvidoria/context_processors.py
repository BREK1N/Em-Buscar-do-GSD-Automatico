from .permissions import has_comandante_access


def ouvidoria_context(request):
    if request.user.is_authenticated:
        return {'is_comandante': has_comandante_access(request.user)}
    return {'is_comandante': False}
