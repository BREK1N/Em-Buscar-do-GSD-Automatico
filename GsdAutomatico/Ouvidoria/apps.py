from django.apps import AppConfig

class OuvidoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Ouvidoria'

    def ready(self):
        # Importa os sinais quando a app estiver pronta
        import Ouvidoria.signals