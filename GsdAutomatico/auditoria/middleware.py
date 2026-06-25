import contextvars

# Sinais (post_save/post_delete) não recebem `request`, então a única forma de saber
# "quem fez essa ação" dentro de um signal é guardar o usuário da requisição atual aqui.
_usuario_atual = contextvars.ContextVar('auditoria_usuario_atual', default=None)


def get_usuario_atual():
    return _usuario_atual.get()


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        token = _usuario_atual.set(user if user and user.is_authenticated else None)
        try:
            return self.get_response(request)
        finally:
            _usuario_atual.reset(token)
