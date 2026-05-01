"""
WebSocket consumer para o chat em tempo real dos chamados de suporte.

Cada chamado tem seu próprio "group" no channel layer:
    chamado_{pk}

Eventos suportados:
    chat_message  — nova mensagem enviada por um participante
    typing        — indicador "está digitando..."
    status_change — mudança de status (broadcast para todos os participantes)
"""
import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChamadoConsumer(AsyncWebsocketConsumer):

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def connect(self):
        self.chamado_pk = self.scope["url_route"]["kwargs"]["chamado_pk"]
        self.group_name = f"chamado_{self.chamado_pk}"
        user = self.scope["user"]

        # Rejeita conexões não autenticadas
        if not user.is_authenticated:
            await self.close()
            return

        # Verifica se o usuário tem acesso ao chamado
        if not await self._tem_acesso(user, self.chamado_pk):
            await self.close()
            return

        # Entra no group do chamado
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ── Recebe mensagem do browser ────────────────────────────────────────────

    async def receive(self, text_data):
        data = json.loads(text_data)
        tipo = data.get("tipo")
        user = self.scope["user"]

        if tipo == "chat_message":
            texto = data.get("texto", "").strip()
            if not texto and not data.get("tem_anexo"):
                return

            # Persiste no banco de dados
            msg = await self._salvar_mensagem(user, texto)

            # Monta payload para broadcast
            payload = {
                "tipo": "chat_message",
                "id": msg.id,
                "autor_id": user.id,
                "autor_nome": user.get_full_name() or user.username,
                "autor_foto": await self._foto_url(user),
                "texto": texto,
                "timestamp": msg.created_at.strftime("%d/%m/%Y %H:%M"),
                "eh_ti": await self._is_informatica(user),
            }
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "broadcast_message", "payload": payload},
            )

        elif tipo == "typing":
            # Propaga o evento "está digitando" para os outros (não para quem enviou)
            payload = {
                "tipo": "typing",
                "autor_id": user.id,
                "autor_nome": user.get_full_name() or user.username,
                "digitando": data.get("digitando", False),
            }
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "broadcast_typing", "payload": payload},
            )

    # ── Handlers de eventos do group ─────────────────────────────────────────

    async def broadcast_message(self, event):
        """Recebe mensagem do group e envia para este WebSocket."""
        await self.send(text_data=json.dumps(event["payload"]))

    async def broadcast_typing(self, event):
        """Envia evento de 'digitando' para este WebSocket (exceto o próprio autor)."""
        user = self.scope["user"]
        if event["payload"]["autor_id"] != user.id:
            await self.send(text_data=json.dumps(event["payload"]))

    async def broadcast_status(self, event):
        """Broadcast de mudança de status — disparado pela view update_status_view."""
        await self.send(text_data=json.dumps(event["payload"]))

    # ── Helpers de banco de dados (sync → async) ──────────────────────────────

    @database_sync_to_async
    def _tem_acesso(self, user, chamado_pk):
        from .models import Chamado
        try:
            c = Chamado.objects.get(pk=chamado_pk)
        except Chamado.DoesNotExist:
            return False
        return (
            user.is_superuser
            or user.groups.filter(name="Militar da Informática").exists()
            or c.solicitante_id == user.id
        )

    @database_sync_to_async
    def _salvar_mensagem(self, user, texto):
        from .models import MensagemChamado, Chamado
        chamado = Chamado.objects.get(pk=self.chamado_pk)
        return MensagemChamado.objects.create(
            chamado=chamado,
            autor=user,
            texto=texto,
        )

    @database_sync_to_async
    def _is_informatica(self, user):
        return (
            user.is_superuser
            or user.groups.filter(name="Militar da Informática").exists()
        )

    @database_sync_to_async
    def _foto_url(self, user):
        try:
            if hasattr(user, "profile") and user.profile.foto:
                return user.profile.foto.url
        except Exception:
            pass
        return None
