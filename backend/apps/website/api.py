"""Staff API for website enquiries: trial requests and contact messages (leads.manage, branch-scoped)."""

from rest_framework import mixins, serializers, viewsets

from apps.audit.services import record_event
from apps.rbac.drf import BranchScopedMixin

from .models import ContactMessage, TrialRequest


class TrialRequestSerializer(serializers.ModelSerializer):
    branch_code = serializers.CharField(source="branch.code", read_only=True)
    program_title = serializers.CharField(source="program.title", read_only=True, default="")

    class Meta:
        model = TrialRequest
        fields = [
            "id",
            "name",
            "mobile",
            "branch",
            "branch_code",
            "program",
            "program_title",
            "not_sure",
            "language",
            "source",
            "status",
            "owner",
            "notes",
            "created_at",
        ]
        read_only_fields = [
            "name",
            "mobile",
            "branch",
            "program",
            "not_sure",
            "language",
            "source",
            "owner",
            "created_at",
        ]


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ["id", "name", "mobile", "branch", "message", "language", "handled", "created_at"]
        read_only_fields = ["name", "mobile", "branch", "message", "language", "created_at"]


class TrialRequestViewSet(
    BranchScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = TrialRequest.objects.select_related("branch", "program", "owner")
    serializer_class = TrialRequestSerializer
    http_method_names = ["get", "patch", "head", "options"]
    required_perms = {"list": "leads.manage", "retrieve": "leads.manage", "partial_update": "leads.manage"}

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.query_params.get("status")
        return qs.filter(status=status) if status else qs

    def perform_update(self, serializer):
        item = serializer.instance
        self.check_branch_write(item.branch_id)
        # The first person to work a lead owns it (Customer Management Procedure).
        owner = item.owner or self.request.user
        serializer.save(owner=owner)
        record_event(action="trial_request_updated", instance=item, changes=serializer.validated_data)


class ContactMessageViewSet(
    BranchScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ContactMessage.objects.select_related("branch")
    serializer_class = ContactMessageSerializer
    http_method_names = ["get", "patch", "head", "options"]
    required_perms = {"list": "leads.manage", "retrieve": "leads.manage", "partial_update": "leads.manage"}
