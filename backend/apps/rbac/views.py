from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.audit.services import record_event

from .models import Permission, Role, RoleAssignment
from .serializers import PermissionSerializer, RoleAssignmentSerializer, RoleSerializer
from .services import effective_access, has_perm


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    required_perms = {"list": "rbac.view", "retrieve": "rbac.view"}
    pagination_class = None


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Role.objects.prefetch_related("permissions")
    serializer_class = RoleSerializer
    required_perms = {"list": "rbac.view", "retrieve": "rbac.view"}
    pagination_class = None


class RoleAssignmentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """Grant and end roles. Assignments are never edited or deleted — only ended — so history is kept."""

    queryset = RoleAssignment.objects.select_related("user", "role", "branch", "granted_by")
    serializer_class = RoleAssignmentSerializer
    required_perms = {"list": "rbac.view", "retrieve": "rbac.view", "create": "rbac.assign", "end": "rbac.assign"}

    def get_queryset(self):
        qs = super().get_queryset()
        user_id = self.request.query_params.get("user")
        if user_id:
            qs = qs.filter(user_id=user_id)
        if self.request.query_params.get("current") == "true":
            qs = qs.current()
        return qs

    def perform_create(self, serializer):
        role = serializer.validated_data["role"]
        branch = serializer.validated_data.get("branch")
        granter = self.request.user
        # No privilege escalation: you can only hand out powers you hold yourself, in your own branches.
        mine = effective_access(granter).permissions
        missing = {p.code for p in role.permissions.all()} - mine
        if missing and not has_perm(granter, "rbac.manage_roles"):
            raise PermissionDenied("You cannot grant a role with permissions you don't have yourself.")
        if not has_perm(granter, "rbac.assign", branch.id if branch else None) or (
            branch is None and not self._has_all_branch_assign(granter)
        ):
            raise PermissionDenied("You cannot grant access for this branch.")
        assignment = serializer.save(granted_by=granter)
        record_event(
            action="role_granted",
            instance=assignment,
            changes={
                "user": assignment.user_id,
                "role": role.code,
                "branch": branch.code if branch else "all",
                "reason": assignment.reason,
            },
        )

    @staticmethod
    def _has_all_branch_assign(user):
        from .services import branch_scope

        return branch_scope(user, "rbac.assign") is None

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        assignment = self.get_object()
        if assignment.user_id == request.user.id:
            raise PermissionDenied("You cannot change your own access.")
        if assignment.ends_on is not None and assignment.ends_on <= timezone.localdate():
            raise ValidationError("This access has already ended.")
        assignment.ends_on = timezone.localdate()
        assignment.save(update_fields=["ends_on"])
        assignment.user.revoke_all_sessions()  # the change takes effect immediately
        record_event(
            action="role_ended", instance=assignment, changes={"user": assignment.user_id, "role": assignment.role.code}
        )
        return Response(
            RoleAssignmentSerializer(assignment, context={"request": request}).data, status=status.HTTP_200_OK
        )
