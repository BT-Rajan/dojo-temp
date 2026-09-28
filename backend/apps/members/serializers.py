from rest_framework import serializers

from apps.core.concurrency import VersionedSerializerMixin
from apps.core.crypto import mask
from apps.core.validators import normalize_kuwait_mobile, validate_civil_id
from apps.rbac.services import has_perm

from .models import EmergencyContact, Guardian, GuardianLink, MediaConsent, Member


def _kuwait_mobile(value):
    if not value:
        return value
    try:
        return normalize_kuwait_mobile(value)
    except Exception as exc:  # django ValidationError -> DRF error
        raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc


def _civil_id(value):
    if not value:
        return value
    try:
        validate_civil_id(value)
    except Exception as exc:
        raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc
    return value


class GuardianLinkSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="guardian.full_name", read_only=True)
    mobile = serializers.CharField(source="guardian.mobile", read_only=True)

    class Meta:
        model = GuardianLink
        fields = ["guardian", "full_name", "mobile", "relationship", "is_primary"]


class EmergencyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyContact
        fields = ["id", "name", "relationship", "mobile"]

    def validate_mobile(self, value):
        return _kuwait_mobile(value)


class MediaConsentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source="recorded_by.full_name", read_only=True, default=None)

    class Meta:
        model = MediaConsent
        fields = [
            "id",
            "internal_records",
            "social_media",
            "website_marketing",
            "signed_by_name",
            "signed_at",
            "recorded_by_name",
            "notes",
            "is_withdrawn",
        ]
        read_only_fields = ["signed_at", "is_withdrawn"]


class MemberSerializer(VersionedSerializerMixin, serializers.ModelSerializer):
    guardians = GuardianLinkSerializer(source="guardian_links", many=True, read_only=True)
    emergency_contacts = EmergencyContactSerializer(many=True, read_only=True)
    current_consent = serializers.SerializerMethodField()
    age = serializers.IntegerField(read_only=True)
    civil_id = serializers.CharField(required=False, allow_blank=True, validators=[_civil_id])

    class Meta:
        model = Member
        fields = [
            "id",
            "branch",
            "first_name",
            "last_name",
            "first_name_ar",
            "last_name_ar",
            "date_of_birth",
            "age",
            "gender",
            "nationality",
            "civil_id",
            "mobile",
            "email",
            "area",
            "source",
            "medical_notes",
            "allergies",
            "joined_on",
            "is_active",
            "guardians",
            "emergency_contacts",
            "current_consent",
            "version",
        ]

    def validate_mobile(self, value):
        return _kuwait_mobile(value)

    def get_current_consent(self, obj):
        # Uses the prefetched list (newest first) instead of one extra query per member.
        consents = list(obj.media_consents.all())
        consent = consents[0] if consents else None
        return MediaConsentSerializer(consent).data if consent else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = request.user if request else None
        # Need-to-know: full Civil ID and medical details only for roles that need them, per branch.
        if not has_perm(user, "members.view_sensitive", instance.branch_id):
            data["civil_id"] = mask(instance.civil_id)
        if not has_perm(user, "members.view_medical", instance.branch_id):
            data.pop("medical_notes", None)
            data.pop("allergies", None)
        return data


class GuardianSerializer(VersionedSerializerMixin, serializers.ModelSerializer):
    civil_id = serializers.CharField(required=False, allow_blank=True, validators=[_civil_id])
    children = serializers.SerializerMethodField()

    class Meta:
        model = Guardian
        fields = ["id", "full_name", "full_name_ar", "mobile", "email", "civil_id", "children", "version"]

    def validate_mobile(self, value):
        return _kuwait_mobile(value)

    def get_children(self, obj):
        return [{"id": m.id, "name": str(m), "branch": m.branch_id} for m in obj.members.all()]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if not (request and has_perm(request.user, "members.view_sensitive")):
            data["civil_id"] = mask(instance.civil_id)
        return data
