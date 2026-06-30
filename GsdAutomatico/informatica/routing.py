"""URL routing para WebSockets do módulo de Informática."""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ws://host/ws/informatica/backup-terminal/
    re_path(r"^ws/informatica/backup-terminal/$", consumers.BackupTerminalConsumer.as_asgi()),
]
