"""
API for classes, bookings and check-in (for the member portal and apps in later phases).
Every endpoint goes through the same services as the desk, so the rules are identical.
"""

import datetime

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.members.models import Member
from apps.rbac.drf import BranchScopedMixin
from apps.rbac.services import scope_queryset

from . import services
from .models import Attendance, Booking, ClassSession


def run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DjangoPermissionDenied as exc:
        raise PermissionDenied(str(exc)) from exc
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"detail": exc.messages}) from exc


class SessionSerializer(serializers.ModelSerializer):
    instructors = serializers.SlugRelatedField(slug_field="full_name", many=True, read_only=True)
    places_taken = serializers.SerializerMethodField()

    class Meta:
        model = ClassSession
        fields = [
            "id",
            "branch",
            "kind",
            "title_en",
            "title_ar",
            "date",
            "start",
            "end",
            "capacity",
            "places_taken",
            "status",
            "instructors",
            "program",
            "room",
            "seminar_points",
        ]

    def get_places_taken(self, obj):
        return services.places_taken(obj)


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            "id",
            "session",
            "member",
            "guest_name",
            "guest_mobile",
            "status",
            "source",
            "is_trial",
            "late_cancellation",
            "created_at",
        ]
        read_only_fields = ["status", "is_trial", "late_cancellation", "created_at"]


class SessionViewSet(BranchScopedMixin, viewsets.ReadOnlyModelViewSet):
    """GET ?date=YYYY-MM-DD&branch=<id>. `roster` lists regulars, bookings, trials and walk-ins."""

    queryset = ClassSession.objects.select_related("branch").prefetch_related("instructors")
    serializer_class = SessionSerializer
    required_perms = {"list": "classes.view", "retrieve": "classes.view", "roster": "classes.view"}

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get("date"):
            qs = qs.filter(date=datetime.date.fromisoformat(p["date"]))
        if p.get("branch"):
            qs = qs.filter(branch_id=p["branch"])
        return qs.order_by("date", "start")

    @action(detail=True)
    def roster(self, request, pk=None):
        session = self.get_object()
        rows = services.roster(session)
        return Response(
            [
                {
                    "member": r.member.pk if r.member else None,
                    "name": r.name,
                    "kind": r.kind,
                    "booking": r.booking.pk if r.booking else None,
                    "checked_in_at": r.attendance.checked_in_at if r.attendance else None,
                }
                for r in rows
            ]
        )


class BookingViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Booking.objects.select_related("session", "member")
    serializer_class = BookingSerializer
    required_perms = {"list": "classes.view", "create": "classes.book", "cancel": "classes.book"}

    def get_queryset(self):
        return scope_queryset(super().get_queryset(), self.request.user, "classes.view", "session__branch")

    def create(self, request, *args, **kwargs):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        member = v.get("member")
        if member is not None:
            member = get_object_or_404(scope_queryset(Member.objects.all(), request.user, "members.view"), pk=member.pk)
        booking = run(
            services.book,
            v["session"],
            request.user,
            member=member,
            guest_name=v.get("guest_name", ""),
            guest_mobile=v.get("guest_mobile", ""),
            source=v.get("source") or "desk",
        )
        return Response(self.get_serializer(booking).data, status=201)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = run(services.cancel_booking, self.get_object(), request.user)
        return Response(self.get_serializer(booking).data)


class CheckInSerializer(serializers.Serializer):
    member = serializers.PrimaryKeyRelatedField(queryset=Member.objects.all())
    session = serializers.PrimaryKeyRelatedField(queryset=ClassSession.objects.all())
    method = serializers.ChoiceField(choices=Attendance.Method.choices, default=Attendance.Method.DESK)


class CheckInViewSet(viewsets.GenericViewSet):
    """POST {member, session, method}. Warnings never block (decision of 29 Sep 2026); they are returned."""

    serializer_class = CheckInSerializer
    required_perms = {"create": "classes.checkin"}

    def create(self, request):
        data = self.get_serializer(data=request.data)
        data.is_valid(raise_exception=True)
        member = get_object_or_404(
            scope_queryset(Member.objects.all(), request.user, "members.view"), pk=data.validated_data["member"].pk
        )
        attendance, created, warning = run(
            services.check_in, member, data.validated_data["session"], request.user, data.validated_data["method"]
        )
        return Response(
            {"attendance": attendance.pk, "created": created, "warning": warning, "walk_in": attendance.walk_in},
            status=201 if created else 200,
        )
