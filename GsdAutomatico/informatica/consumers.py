"""
WebSocket consumer para o terminal SSH interativo do servidor de backup.

A sessão roda dentro de um `tmux` no servidor remoto (uma sessão fixa por
usuário: gsd-web-<username>). Isso faz o terminal sobreviver a reload de
página, queda de WiFi, etc. — ao reconectar, o consumer só re-anexa
(`tmux new-session -A -s ...`) na mesma sessão em vez de abrir um shell novo.

paramiko é bloqueante (sync), então a leitura contínua do shell remoto roda
numa thread separada que empurra cada chunk de volta pro browser via
self.send(). Fechar a aba NÃO mata a sessão tmux — ela continua rodando no
servidor até alguém encerrá-la explicitamente (Ctrl+B, ou `tmux kill-session`).
"""
import re
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
            # Sessão tmux fixa por usuário: -A (re)anexa se já existir, cria se não existir.
            sessao = re.sub(r'[^a-zA-Z0-9_-]', '_', user.username) or 'anon'
            self.channel_ssh = self.ssh.get_transport().open_session()
            self.channel_ssh.get_pty(term='xterm-256color', width=120, height=32)
            self.channel_ssh.invoke_shell()
            self.channel_ssh.send(f"tmux new-session -A -s gsd-web-{sessao}\n")
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
        if not ch or text_data is None:
            return
        try:
            # Mensagens de resize chegam como JSON: {"resize":[cols,rows]}
            if text_data.startswith('{"resize"'):
                import json
                cols, rows = json.loads(text_data)['resize']
                ch.resize_pty(width=int(cols), height=int(rows))
                return
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
