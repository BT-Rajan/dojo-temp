from django.core.management.base import BaseCommand

from apps.rbac.sync import sync_rbac


class Command(BaseCommand):
    help = "Create or update permissions and default roles from apps/rbac/catalog.py."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-role-permissions",
            action="store_true",
            help="Only add missing roles; don't overwrite permissions of existing roles.",
        )

    def handle(self, *args, **opts):
        n_perms, n_roles = sync_rbac(reset_role_permissions=not opts["keep_role_permissions"])
        self.stdout.write(self.style.SUCCESS(f"RBAC synced: {n_perms} permissions, {n_roles} roles."))
