from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .chain import seal_pending, verify_chain
from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "occurred_at",
            "actor",
            "actor_label",
            "action",
            "object_type",
            "object_id",
            "branch_id",
            "changes",
            "ip_address",
            "request_id",
            "seal_seq",
            "hash",
        ]


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditEvent.objects.all()
    serializer_class = AuditEventSerializer
    required_perms = {"list": "audit.view", "retrieve": "audit.view", "verify": "audit.view"}

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for field in ("action", "object_type", "object_id", "actor"):
            if params.get(field):
                qs = qs.filter(**{field: params[field]})
        if params.get("since"):
            qs = qs.filter(occurred_at__gte=params["since"])
        if params.get("until"):
            qs = qs.filter(occurred_at__lte=params["until"])
        return qs

    @action(detail=False, methods=["get"])
    def verify(self, request):
        seal_pending()
        return Response(verify_chain())
