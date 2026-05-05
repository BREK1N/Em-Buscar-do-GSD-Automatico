from django.apps import AppConfig


class NotificacoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notificacoes'
    verbose_name = 'Notificações'

    def ready(self):
        import notificacoes.signals  # noqa: F401 — registra os receivers

        # Conecta o signal M2M de Mensagem.destinatarios
        try:
            from caixa_entrada.models import Mensagem
            from django.db.models.signals import m2m_changed
            from notificacoes.signals import _notificar_mensagem

            def _handler(sender, instance, action, pk_set, **kwargs):
                if action == 'post_add' and pk_set:
                    _notificar_mensagem(instance, pk_set)

            m2m_changed.connect(_handler, sender=Mensagem.destinatarios.through)
        except Exception:
            pass
