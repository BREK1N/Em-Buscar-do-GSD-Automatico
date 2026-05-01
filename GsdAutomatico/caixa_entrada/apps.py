from django.apps import AppConfig


class CaixaEntradaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'caixa_entrada'
    verbose_name = 'Caixa de Entrada'

    def ready(self):
        import caixa_entrada.signals  # noqa

        from django.db.models.signals import m2m_changed
        from .models import Mensagem
        from .signals import limpar_notificacao_ao_excluir_permanentemente
        m2m_changed.connect(
            limpar_notificacao_ao_excluir_permanentemente,
            sender=Mensagem.permanentemente_excluida_por.through,
        )
