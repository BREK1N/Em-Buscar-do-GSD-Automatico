from django.apps import AppConfig


class SecaoOperacoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Secao_operacoes'

    def ready(self):
        import Secao_operacoes.signals
