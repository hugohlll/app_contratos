from django.apps import AppConfig


class ContratosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'contratos'

    def ready(self):
        from contratos import signals  # noqa: F401  (registra os receivers dos alertas da ACI)
