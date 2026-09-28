from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.audit.services import record_event
from apps.core.concurrency import OptimisticLockMixin
from apps.rbac.drf import BranchScopedMixin
from apps.rbac.services import branch_scope, has_perm

from .models import EmergencyContact, Guardian, GuardianLink, MediaConsent, Member
from .serializers import EmergencyContactSerializer, GuardianSerializer, MediaConsentSerializer, MemberSerializer


class MemberViewSet(BranchScopedMixin, OptimisticLockMixin, viewsets.ModelViewSet):
    """Members are deactivated, never deleted, so history (payments, attendance, incidents) is kept."""

    queryset = Member.objects.select_related("branch").prefetch_related(
        "guardian_links__guardian", "emergency_contacts", "media_consents"
    )
    serializer_class = MemberSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    required_perms = {
        "list": "members.view",
        "retrieve": "members.view",
        "create": "members.create",
        "update": "members.update",
        "partial_update": "members.update",
        "deactivate": "members.deactivate",
        "consent": "members.manage_consent",
        "add_guardian": "members.update",
        "add_emergency_contact": "members.update",
    }

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("search"):
            term = params["search"].strip()
            qs = qs.filter(
                Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(first_name_ar__icontains=term)
                | Q(last_name_ar__icontains=term)
                | Q(mobile__icontains=term)
            )
        if params.get("branch"):
            qs = qs.filter(branch_id=params["branch"])
        if params.get("active") in ("true", "false"):
            qs = qs.filter(is_active=params["active"] == "true")
        return qs

    def perform_create(self, serializer):
        self.check_branch_write(self._branch_id_from(serializer))
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def _member_for_write(self):
        member = self.get_object()
        self.check_branch_write(member.branch_id)
        return member

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        member = self._member_for_write()
        member.is_active = False
        member.version += 1
        member.updated_by = request.user
        member.save()
        return Response(MemberSerializer(member, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def consent(self, request, pk=None):
        """Record a new media consent (EA-MKT-FRM-01). Unticking everything records a withdrawal."""
        member = self._member_for_write()
        serializer = MediaConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consent = serializer.save(member=member, recorded_by=request.user)
        record_event(
            action="consent_recorded",
            instance=member,
            changes={
                "internal": consent.internal_records,
                "social": consent.social_media,
                "website": consent.website_marketing,
                "signed_by": consent.signed_by_name,
            },
        )
        return Response(MediaConsentSerializer(consent).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="guardians")
    def add_guardian(self, request, pk=None):
        member = self._member_for_write()
        guardian = Guardian.objects.filter(pk=request.data.get("guardian")).first()
        if guardian is None:
            return Response({"guardian": "Guardian not found."}, status=status.HTTP_400_BAD_REQUEST)
        link, _ = GuardianLink.objects.update_or_create(
            guardian=guardian,
            member=member,
            defaults={
                "relationship": request.data.get("relationship", "guardian"),
                "is_primary": bool(request.data.get("is_primary", False)),
            },
        )
        record_event(action="guardian_linked", instance=member, changes={"guardian": guardian.id})
        return Response(status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="emergency-contacts")
    def add_emergency_contact(self, request, pk=None):
        member = self._member_for_write()
        serializer = EmergencyContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(member=member)
        record_event(action="emergency_contact_added", instance=member)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GuardianViewSet(OptimisticLockMixin, viewsets.ModelViewSet):
    """A guardian is visible when at least one of their children is in a branch the user can see."""

    queryset = Guardian.objects.prefetch_related("members")
    serializer_class = GuardianSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    required_perms = {
        "list": "members.view",
        "retrieve": "members.view",
        "create": "members.create",
        "update": "members.update",
        "partial_update": "members.update",
    }

    def get_queryset(self):
        scope = branch_scope(self.request.user, "members.view")
        qs = super().get_queryset()
        if scope is None:
            return qs
        # Newly registered guardians with no children yet stay visible to anyone who may register members.
        return qs.filter(Q(members__branch__in=scope) | Q(members__isnull=True)).distinct()

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            branches = {m.branch_id for m in obj.members.all()}
            if branches and not any(has_perm(request.user, "members.update", b) for b in branches):
                raise PermissionDenied("You cannot change this family's details.")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


__all__ = ["MemberViewSet", "GuardianViewSet", "EmergencyContact", "MediaConsent"]
