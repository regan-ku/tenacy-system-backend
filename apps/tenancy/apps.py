from django.apps import AppConfig

class TenancyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenancy'
    verbose_name = 'Tenancy & Occupancy Management'

    def ready(self):
        # Import signals here when we add them (e.g., auto-syncing marketplace on tenancy creation)
        # import apps.tenancy.signals
        pass