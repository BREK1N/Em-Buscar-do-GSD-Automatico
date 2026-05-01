"""
ASGI config — suporta HTTP (Django) e WebSockets (Django Channels).
Daphne usa este arquivo como entry-point no lugar do wsgi.py.

Para executar em desenvolvimento:
    daphne -b 0.0.0.0 -p 8000 GsdAutomatico.asgi:application

Para produção Docker (docker-compose):
    command: daphne -b 0.0.0.0 -p 8000 GsdAutomatico.asgi:application
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GsdAutomatico.settings')

# Inicializa o Django antes de qualquer import de apps
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack            # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
import chamados.routing                                   # noqa: E402

application = ProtocolTypeRouter({
    # Requisições HTTP normais continuam sendo tratadas pelo Django
    "http": django_asgi_app,

    # WebSockets — sessão Django injetada automaticamente por AuthMiddlewareStack
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(chamados.routing.websocket_urlpatterns)
        )
    ),
})
