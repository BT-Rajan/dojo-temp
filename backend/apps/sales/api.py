"""Read access to sales and memberships; sales themselves are made at the desk (apps.desk)."""

from rest_framework import serializers, viewsets

from apps.rbac.drf import BranchScopedMixin

from .models import Membership, Payment, Sale, SaleLine
from .services import member_status


class LineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleLine
        fields = [
            "description",
            "description_ar",
            "category",
            "quantity",
            "unit_price",
            "discount_amount",
            "line_total",
            "free_issue",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["method", "amount", "reference", "received_at"]


class SaleSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    lines = LineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "reference",
            "branch",
            "kind",
            "member",
            "customer_name",
            "total",
            "discount_total",
            "created_at",
            "lines",
            "payments",
        ]


class MembershipSerializer(serializers.ModelSerializer):
    option = serializers.CharField(source="pricing_option.name", read_only=True)
    kind = serializers.CharField(source="pricing_option.kind", read_only=True)
    sessions_left = serializers.IntegerField(read_only=True)
    member_status = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = [
            "id",
            "member",
            "branch",
            "option",
            "kind",
            "start_date",
            "end_date",
            "sessions_total",
            "sessions_used",
            "sessions_left",
            "status",
            "freeze_used",
            "member_status",
        ]

    def get_member_status(self, obj):
        return member_status(obj.member).code


class SaleViewSet(BranchScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Sale.objects.select_related("branch").prefetch_related("lines", "payments")
    serializer_class = SaleSerializer
    required_perms = {"list": "sales.view", "retrieve": "sales.view"}


class MembershipViewSet(BranchScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Membership.objects.select_related("pricing_option", "member")
    serializer_class = MembershipSerializer
    required_perms = {"list": "sales.view", "retrieve": "sales.view"}

    def get_queryset(self):
        qs = super().get_queryset()
        member = self.request.query_params.get("member")
        return qs.filter(member_id=member) if member else qs
