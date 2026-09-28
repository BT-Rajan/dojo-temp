from rest_framework import serializers

from apps.core.concurrency import VersionedSerializerMixin

from .models import Branch, Discipline, PricingOption, Program


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
            "active_from",
            "active_until",
            "is_active",
            "version",
        ]
