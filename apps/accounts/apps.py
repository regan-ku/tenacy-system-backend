from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = 'Accounts & Identity Management'

    def ready(self):
        # Import signals here if we add any in the future
        # import apps.accounts.signals
        pass