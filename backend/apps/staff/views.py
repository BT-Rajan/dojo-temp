from rest_framework import serializers, viewsets

from apps.core.concurrency import OptimisticLockMixin, VersionedSerializerMixin
from apps.core.crypto import mask
from apps.rbac.services import has_perm

from .models import StaffProfile


class StaffProfileSerializer(VersionedSerializerMixin, serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    disciplines = serializers.SlugRelatedField(slug_field="code", many=True, read_only=True)

    class Meta:
        model = StaffProfile
        fields = [
            "id",
            "user",
            "full_name",
            "email",
            "is_active",
            "job_title",
            "job_title_ar",
            "employment_type",
            "primary_branch",
            "reports_to",
            "nationality",
            "civil_id",
            "start_date",
            "end_date",
            "disciplines",
            "bio",
            "version",
        ]
        extra_kwargs = {"civil_id": {"write_only": False}}

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        # HR identifiers are visible in full only to people who manage staff (ISO 27001 A.8.11).
        if not (request and has_perm(request.user, "staff.manage")):
            data["civil_id"] = mask(instance.civil_id)
            data.pop("nationality", None)
        return data


class StaffProfileViewSet(OptimisticLockMixin, viewsets.ModelViewSet):
    queryset = StaffProfile.objects.select_related("user", "primary_branch").prefetch_related("disciplines")
    serializer_class = StaffProfileSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    required_perms = {
        "list": "staff.view",
        "retrieve": "staff.view",
        "create": "staff.manage",
        "update": "staff.manage",
        "partial_update": "staff.manage",
    }

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
