from django.apps import AppConfig

class MarketplaceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.marketplace'
    verbose_name = 'Public Marketplace & Discovery'

    def ready(self):
        # import apps.marketplace.signals
        pass