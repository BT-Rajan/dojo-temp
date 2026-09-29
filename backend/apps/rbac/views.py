from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit.services import record_event

from .models import Permission, Role, RoleAssignment
from .serializers import PermissionSerializer, RoleAssignmentSerializer, RoleSerializer
from .services import check_can_grant, end_role


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
        check_can_grant(granter, role, branch)  # no privilege escalation, own branches only
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

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        assignment = self.get_object()
        try:
            end_role(request.user, assignment)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(
            RoleAssignmentSerializer(assignment, context={"request": request}).data, status=status.HTTP_200_OK
        )
