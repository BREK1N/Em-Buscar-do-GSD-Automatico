"""URL routing para WebSockets do módulo de chamados."""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ws://host/ws/chamados/<pk>/
    re_path(r"^ws/chamados/(?P<chamado_pk>\d+)/$", consumers.ChamadoConsumer.as_asgi()),
]
