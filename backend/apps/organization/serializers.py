from rest_framework import serializers

from apps.core.concurrency import VersionedSerializerMixin

from .models import Branch, Discipline, PriceChange, PricingOption, Program, Room


class BranchSerializer(VersionedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            "id",
            "code",
            "name",
            "name_ar",
            "area",
            "area_ar",
            "address",
            "phone",
            "open_days",
            "positioning",
            "is_active",
            "version",
        ]


class DisciplineSerializer(VersionedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Discipline
        fields = ["id", "code", "name", "name_ar", "track", "version"]


class ProgramSerializer(VersionedSerializerMixin, serializers.ModelSerializer):
    disciplines = serializers.SlugRelatedField(slug_field="code", many=True, queryset=Discipline.objects.all())

    class Meta:
        model = Program
        fields = [
            "id",
            "branch",
            "name",
            "name_ar",
            "disciplines",
            "audience",
            "age_min",
            "age_max",
            "description",
            "is_active",
            "version",
        ]


class PricingOptionSerializer(VersionedSerializerMixin, serializers.ModelSerializer):
    counts_as_membership = serializers.BooleanField(read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=3, coerce_to_string=True)

    class Meta:
        model = PricingOption
        fields = [
            "id",
            "branch",
            "name",
            "name_ar",
            "kind",
            "counts_as_membership",
            "programs",
            "price",
            "duration_days",
            "sessions_per_week",
            "total_sessions",
            "package_weeks",
            "all_access",
            "family_discount_allowed",
            "active_from",
            "active_until",
            "is_active",
            "approval",
            "version",
        ]
        read_only_fields = ["approval"]

    def validate(self, attrs):
        # After creation a price changes only through an approved PriceChange (scope M1).
        if self.instance is not None and "price" in attrs and attrs["price"] != self.instance.price:
            raise serializers.ValidationError({"price": "Request a price change; it goes live after approval."})
        return super().validate(attrs)


class PriceChangeSerializer(serializers.ModelSerializer):
    requested_by = serializers.CharField(source="created_by.full_name", read_only=True, default="")
    option_name = serializers.CharField(source="pricing_option.name", read_only=True)

    class Meta:
        model = PriceChange
        fields = [
            "id",
            "pricing_option",
            "option_name",
            "old_price",
            "new_price",
            "effective_from",
            "reason",
            "status",
            "requested_by",
            "decided_at",
            "decision_note",
            "created_at",
        ]
        read_only_fields = ["old_price", "status", "decided_at", "decision_note", "created_at"]


class RoomSerializer(VersionedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "branch", "name", "name_ar", "capacity", "is_active", "version"]
