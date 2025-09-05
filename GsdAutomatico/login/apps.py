from django.apps import AppConfig


class LoginConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'login'

    def ready(self):
        """
        Importa os sinais quando a aplicação estiver pronta,
        garantindo que eles sejam registrados e funcionem.
        """
        import login.signals
