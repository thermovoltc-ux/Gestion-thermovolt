from django.apps import AppConfig


class GestionOtConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestion_mantenimiento.Gestion_ot'
    
    def ready(self):
        # Importar signals cuando la app está lista
        import Gestion_ot.models
