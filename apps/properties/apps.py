from django.apps import AppConfig

class PropertiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.properties'

    def ready(self):
        # ✅ Import the signals module to ensure the receivers are registered
        import apps.properties.signals 