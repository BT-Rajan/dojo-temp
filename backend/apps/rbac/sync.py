from django.db import transaction

from .catalog import PERMISSIONS, ROLES
from .models import Permission, Role


@transaction.atomic
def sync_rbac(reset_role_permissions: bool = True) -> tuple[int, int]:
    """Creates/updates permissions and default roles from the catalogue. Safe to run repeatedly."""
    perms = {}
    for code, description in PERMISSIONS.items():
        perm, _ = Permission.objects.update_or_create(code=code, defaults={"description": description})
        perms[code] = perm
    Permission.objects.exclude(code__in=PERMISSIONS).delete()

    for code, (name, name_ar, description, privileged, role_perms) in ROLES.items():
        role, created = Role.objects.update_or_create(
            code=code,
            defaults={"name": name, "name_ar": name_ar, "description": description, "is_privileged": privileged},
        )
        if created or reset_role_permissions:
            role.permissions.set([perms[p] for p in role_perms])
    return len(PERMISSIONS), len(ROLES)
