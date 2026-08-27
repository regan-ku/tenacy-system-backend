from django.apps import AppConfig


class MarketplaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.marketplace"  # keep whatever you currently have here

    def ready(self):
        import apps.marketplace.signals  # noqa: F401  ✅ REQUIRED to load the signals