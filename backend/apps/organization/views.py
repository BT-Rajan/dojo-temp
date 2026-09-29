from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.concurrency import OptimisticLockMixin
from apps.rbac.drf import BranchScopedMixin

from . import services
from .models import Branch, Discipline, PriceChange, PricingOption, Program, Room
from .serializers import (
    BranchSerializer,
    DisciplineSerializer,
    PriceChangeSerializer,
    PricingOptionSerializer,
    ProgramSerializer,
    RoomSerializer,
)


class AuditedWriteMixin(OptimisticLockMixin):
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class BranchViewSet(AuditedWriteMixin, viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]  # branches are deactivated, never deleted
    required_perms = {
        "list": "branches.view",
        "retrieve": "branches.view",
        "create": "branches.manage",
        "update": "branches.manage",
        "partial_update": "branches.manage",
    }
    pagination_class = None

    def get_queryset(self):
        from apps.rbac.services import branch_scope

        scope = branch_scope(self.request.user, "branches.view")
        qs = super().get_queryset()
        return qs if scope is None else qs.filter(id__in=scope)


class DisciplineViewSet(AuditedWriteMixin, viewsets.ModelViewSet):
    queryset = Discipline.objects.all()
    serializer_class = DisciplineSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    required_perms = {
        "list": "programs.view",
        "retrieve": "programs.view",
        "create": "programs.manage",
        "update": "programs.manage",
        "partial_update": "programs.manage",
    }
    pagination_class = None


class ProgramViewSet(BranchScopedMixin, AuditedWriteMixin, viewsets.ModelViewSet):
    queryset = Program.objects.select_related("branch").prefetch_related("disciplines")
    serializer_class = ProgramSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    required_perms = {
        "list": "programs.view",
        "retrieve": "programs.view",
        "create": "programs.manage",
        "update": "programs.manage",
        "partial_update": "programs.manage",
    }


def run_service(fn, *args, **kwargs):
    """Turns service-layer refusals into API errors."""
    try:
        return fn(*args, **kwargs)
    except DjangoPermissionDenied as exc:
        raise PermissionDenied(str(exc)) from exc
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"detail": exc.messages}) from exc


class PricingOptionViewSet(BranchScopedMixin, AuditedWriteMixin, viewsets.ModelViewSet):
    queryset = PricingOption.objects.select_related("branch").prefetch_related("programs")
    serializer_class = PricingOptionSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    required_perms = {
        "list": "programs.view",
        "retrieve": "programs.view",
        "create": "pricing.manage",
        "update": "pricing.manage",
        "partial_update": "pricing.manage",
        "approve": "pricing.approve",
        "reject": "pricing.approve",
    }

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        option = run_service(services.decide_pricing_option, self.get_object(), True, request.user)
        return Response(self.get_serializer(option).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        option = run_service(services.decide_pricing_option, self.get_object(), False, request.user)
        return Response(self.get_serializer(option).data)


class PriceChangeViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    queryset = PriceChange.objects.select_related("pricing_option", "created_by")
    serializer_class = PriceChangeSerializer
    branch_field = "pricing_option__branch"
    required_perms = {
        "list": "programs.view",
        "retrieve": "programs.view",
        "create": "pricing.manage",
        "approve": "pricing.approve",
        "reject": "pricing.approve",
    }

    def get_queryset(self):
        from apps.rbac.services import scope_queryset

        return scope_queryset(super().get_queryset(), self.request.user, "programs.view", "pricing_option__branch")

    def create(self, request, *args, **kwargs):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        change = run_service(
            services.request_price_change,
            v["pricing_option"],
            v["new_price"],
            v["effective_from"],
            v["reason"],
            request.user,
        )
        return Response(self.get_serializer(change).data, status=201)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        change = run_service(
            services.decide_price_change, self.get_object(), True, request.user, request.data.get("note", "")
        )
        return Response(self.get_serializer(change).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        change = run_service(
            services.decide_price_change, self.get_object(), False, request.user, request.data.get("note", "")
        )
        return Response(self.get_serializer(change).data)


class RoomViewSet(BranchScopedMixin, AuditedWriteMixin, viewsets.ModelViewSet):
    queryset = Room.objects.select_related("branch")
    serializer_class = RoomSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    required_perms = {
        "list": "programs.view",
        "retrieve": "programs.view",
        "create": "programs.manage",
        "update": "programs.manage",
        "partial_update": "programs.manage",
    }
