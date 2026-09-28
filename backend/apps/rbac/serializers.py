from rest_framework import serializers

from .models import Permission, Role, RoleAssignment


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["code", "description"]


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(slug_field="code", many=True, read_only=True)

    class Meta:
        model = Role
        fields = ["id", "code", "name", "name_ar", "description", "is_privileged", "permissions"]


class RoleAssignmentSerializer(serializers.ModelSerializer):
    role = serializers.SlugRelatedField(slug_field="code", queryset=Role.objects.all())
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    branch_code = serializers.CharField(source="branch.code", read_only=True, default=None)
    granted_by_name = serializers.CharField(source="granted_by.full_name", read_only=True, default=None)

    class Meta:
        model = RoleAssignment
        fields = [
            "id",
            "user",
            "user_name",
            "role",
            "branch",
            "branch_code",
            "starts_on",
            "ends_on",
            "granted_by_name",
            "reason",
            "created_at",
        ]
        read_only_fields = ["ends_on", "created_at"]

    def validate(self, attrs):
        request = self.context["request"]
        if attrs["user"] == request.user:
            raise serializers.ValidationError("You cannot change your own access. Ask another administrator.")
        if not attrs.get("reason"):
            raise serializers.ValidationError({"reason": "Give a reason for granting this access."})
        return attrs
