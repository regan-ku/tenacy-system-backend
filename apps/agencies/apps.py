from django.apps import AppConfig

class AgenciesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.agencies'
    verbose_name = 'Agencies & Delegation Management'

    def ready(self):
        """
        Import signals here if we add any in the future.
        For now, the app relies on explicit service calls for state changes.
        """
        # import apps.agencies.signals
        pass