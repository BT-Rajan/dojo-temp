from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _sync_after_migrate(sender, **kwargs):
    from .sync import sync_rbac

    # Adds new permissions/roles; keeps any role changes Systems & IT made since.
    sync_rbac(reset_role_permissions=False)


class RbacConfig(AppConfig):
    name = "apps.rbac"
    label = "rbac"

    def ready(self):
        post_migrate.connect(_sync_after_migrate, sender=self, dispatch_uid="rbac_sync_after_migrate")
