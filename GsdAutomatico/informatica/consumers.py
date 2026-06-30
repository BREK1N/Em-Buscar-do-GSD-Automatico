"""
WebSocket consumer para o terminal SSH interativo do servidor de backup.

paramiko é bloqueante (sync), então a leitura contínua do shell remoto roda
numa thread separada que empurra cada chunk de volta pro browser via
async_to_sync(self.send). O fechamento da conexão (WS ou SSH) encerra a
thread e libera o canal SSH.
"""
import threading

import paramiko
from channels.generic.websocket import WebsocketConsumer


class BackupTerminalConsumer(WebsocketConsumer):
    """Consumer síncrono: paramiko é bloqueante, então usamos o WebsocketConsumer
    síncrono do Channels (que já roda numa thread própria do worker)."""

    def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated or not self._is_informatica_admin(user):
            self.close()
            return

        from .models import BackupDestino
        destino = BackupDestino.get_instance()
        if not destino.host or not destino.usuario:
            self.accept()
            self.send(text_data='\r\n\x1b[31mServidor de backup não configurado (host/usuário ausentes).\x1b[0m\r\n')
            self.close()
            return

        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(
                hostname=destino.host, port=destino.porta, username=destino.usuario,
                password=destino.get_senha(), timeout=15,
            )
            self.channel_ssh = self.ssh.invoke_shell(term='xterm-256color', width=120, height=32)
        except Exception as exc:
            self.accept()
            self.send(text_data=f'\r\n\x1b[31mFalha ao conectar: {exc}\x1b[0m\r\n')
            self.close()
            return

        self.accept()
        self._running = True
        self._reader_thread = threading.Thread(target=self._ler_ssh, daemon=True)
        self._reader_thread.start()

    def disconnect(self, close_code):
        self._running = False
        ssh = getattr(self, 'ssh', None)
        if ssh:
            try:
                ssh.close()
            except Exception:
                pass

    def receive(self, text_data=None, bytes_data=None):
        ch = getattr(self, 'channel_ssh', None)
        if not ch:
            return
        try:
            if text_data is not None:
                ch.send(text_data)
        except Exception:
            self.close()

    def _ler_ssh(self):
        ch = self.channel_ssh
        while self._running:
            try:
                if ch.recv_ready():
                    data = ch.recv(4096)
                    if not data:
                        break
                    self.send(text_data=data.decode('utf-8', errors='replace'))
                elif ch.exit_status_ready():
                    break
                else:
                    import time
                    time.sleep(0.03)
            except Exception:
                break
        try:
            self.close()
        except Exception:
            pass

    @staticmethod
    def _is_informatica_admin(user):
        return user.is_superuser or user.groups.filter(name='informatica-admin').exists()
