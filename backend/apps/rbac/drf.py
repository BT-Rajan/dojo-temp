"""
Connects RBAC to the REST API.

Every view must say what it needs, otherwise access is refused:
- `public = True`                 anyone, logged in or not (login, health)
- `allow_any_authenticated = True` any logged-in user (my profile, logout)
- `required_perms = {action: "perm.code"}` for viewsets, or a single `required_perm` for simple views.
"""

from django.conf import settings
from rest_framework.permissions import BasePermission

from .services import has_perm, is_mfa_verified, is_privileged


class RBACPermission(BasePermission):
    message = "You do not have permission to do this."

    def has_permission(self, request, view):
        if getattr(view, "public", False):
            return True
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False

        # Privileged roles must have completed two-factor login before doing anything else.
        if (
            settings.ENFORCE_PRIVILEGED_MFA
            and not getattr(view, "allow_without_mfa", False)
            and is_privileged(user)
            and not is_mfa_verified(user)
        ):
            self.message = "Set up two-factor login to continue."
            return False

        if getattr(view, "allow_any_authenticated", False):
            return True

        code = self.required_code(view)
        if code is None:
            return False  # a view that declares nothing is closed
        return has_perm(user, code)

    def has_object_permission(self, request, view, obj):
        if getattr(view, "public", False) or getattr(view, "allow_any_authenticated", False):
            return True
        code = self.required_code(view)
        branch_id = getattr(obj, getattr(view, "branch_field", "branch") + "_id", None)
        return code is not None and has_perm(request.user, code, branch_id)

    @staticmethod
    def required_code(view):
        perms = getattr(view, "required_perms", None)
        if perms is not None:
            action = getattr(view, "action", None) or request_method_action(view)
            return perms.get(action)
        return getattr(view, "required_perm", None)


def request_method_action(view):
    method = view.request.method.lower() if getattr(view, "request", None) else ""
    return {"get": "list", "post": "create", "put": "update", "patch": "partial_update", "delete": "destroy"}.get(
        method
    )


class BranchScopedMixin:
    """
    For viewsets over branch-owned data: lists show only branches the user may see,
    and new records can only be created in branches the user may act on.
    """

    branch_field = "branch"

    def scope_permission(self):
        perms = getattr(self, "required_perms", {})
        return perms.get("list") or perms.get("retrieve")

    def get_queryset(self):
        from .services import scope_queryset

        return scope_queryset(super().get_queryset(), self.request.user, self.scope_permission(), self.branch_field)

    def _branch_id_from(self, serializer):
        value = serializer.validated_data.get(self.branch_field)
        return getattr(value, "pk", value)

    def perform_create(self, serializer):
        self.check_branch_write(self._branch_id_from(serializer))
        super().perform_create(serializer)

    def perform_update(self, serializer):
        # Moving a record to another branch needs rights in the destination branch too.
        if self.branch_field in serializer.validated_data:
            self.check_branch_write(self._branch_id_from(serializer))
        super().perform_update(serializer)

    def check_branch_write(self, branch_id):
        from rest_framework.exceptions import PermissionDenied

        code = RBACPermission.required_code(self)
        if not has_perm(self.request.user, code, branch_id):
            raise PermissionDenied("You cannot make changes for this branch.")
