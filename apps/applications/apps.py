from django.apps import AppConfig

class ApplicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.applications'
    verbose_name = 'Rental & Transfer Applications'

    def ready(self):
        # import apps.applications.signals
        pass