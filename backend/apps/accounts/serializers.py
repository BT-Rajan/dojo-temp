from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)
    otp_token = serializers.CharField(required=False, allow_blank=True, max_length=10)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "Current password is not correct."})  # nosec B105
        password_validation.validate_password(attrs["new_password"], user)
        return attrs


class MfaConfirmSerializer(serializers.Serializer):
    otp_token = serializers.CharField(max_length=10)


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "mobile", "full_name", "full_name_ar", "preferred_language", "must_change_password"]
