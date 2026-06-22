from django.apps import AppConfig

class CommunicationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.communications"  # <-- CHANGE THIS LINE
    verbose_name = "Communication & Notification Engine"

    def ready(self):
        # import apps.communications.signals
        pass