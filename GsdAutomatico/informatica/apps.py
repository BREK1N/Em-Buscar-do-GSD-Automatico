from django.apps import AppConfig

class InformaticaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'informatica' # ou 'GsdAutomatico.informatica' dependendo da sua estrutura

    def ready(self):
        import informatica.signals # Importa os sinais ao iniciar