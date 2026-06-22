from django.apps import AppConfig

class IntegrationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.integrations'  # <-- THIS MUST MATCH INSTALLED_APPS EXACTLY
    verbose_name = 'Third-Party Integrations & Communications'

    def ready(self):
        # Import signals here if you have any
        # import apps.integrations.signals
        pass