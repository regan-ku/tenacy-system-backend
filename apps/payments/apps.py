from django.apps import AppConfig

class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"  # <-- CHANGE THIS LINE
    verbose_name = "Payments & Financial Operations Engine"

    def ready(self):
        # import apps.payments.signals
        pass