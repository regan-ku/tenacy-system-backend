from django.apps import AppConfig

class PropertiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.properties'
    verbose_name = 'Properties & Real Estate'

    def ready(self):
        # Import signals here if we add any in the future
        # import apps.properties.signals
        pass