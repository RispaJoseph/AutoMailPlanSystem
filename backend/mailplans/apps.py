from django.apps import AppConfig


class MailplansConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mailplans'

    def ready(self):
        import mailplans.signals
