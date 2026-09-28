from rest_framework import viewsets

from apps.core.concurrency import OptimisticLockMixin
from apps.rbac.drf import BranchScopedMixin

from .models import Branch, Discipline, PricingOption, Program
from .serializers import BranchSerializer, DisciplineSerializer, PricingOptionSerializer, ProgramSerializer


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
    }
