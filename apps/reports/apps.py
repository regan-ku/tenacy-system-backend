from django.apps import AppConfig

class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reports'
    verbose_name = 'Reports, Analytics & Dashboards'

    def ready(self):
        # ONLY import signals here if you create them later.
        # NEVER import models at the top level of apps.py
        # import apps.reports.signals
        pass