"""Timetable, sessions, the coach's class list, bookings and class changes."""

import datetime

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.classes import services as classes
from apps.classes.models import WEEKDAYS, Attendance, Booking, ClassChange, ClassSession, ClassSlot
from apps.organization.models import PricingOption, Program, Room
from apps.rbac.services import has_perm, scope_queryset
from apps.website.models import TrialRequest

from ..access import L, can, desk, safe_next
from ..lookup import search_members, visible_members


def staff_users():
    """Everyone who holds a teaching role (for instructor pickers)."""
    from apps.rbac.models import RoleAssignment

    ids = RoleAssignment.objects.current().filter(role__permissions__code="training.teach").values_list("user_id")
    return get_user_model().objects.filter(pk__in=ids, is_active=True).order_by("full_name")


# ---------------------------------------------------------------------------
# Weekly timetable
# ---------------------------------------------------------------------------
class SlotForm(forms.ModelForm):
    class Meta:
        model = ClassSlot
        fields = [
            "program",
            "room",
            "title_en",
            "title_ar",
            "ages_en",
            "ages_ar",
            "age_group",
            "focus",
            "weekday",
            "start",
            "end",
            "capacity",
            "instructors",
            "valid_from",
            "valid_until",
            "is_public",
            "is_sample",
            "is_active",
        ]
        widgets = {
            "start": forms.TimeInput(attrs={"type": "time"}),
            "end": forms.TimeInput(attrs={"type": "time"}),
            "valid_from": forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "instructors": forms.CheckboxSelectMultiple,
        }

    def __init__(self, branch, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.branch = branch
        self.fields["program"].queryset = Program.objects.filter(branch=branch, is_active=True)
        self.fields["room"].queryset = Room.objects.filter(branch=branch, is_active=True)
        self.fields["instructors"].queryset = staff_users()


@desk("classes.view")
def timetable(request):
    slots = (
        ClassSlot.objects.filter(branch=request.branch, is_active=True)
        .select_related("room", "program")
        .prefetch_related("instructors")
        .annotate(regulars=Count("enrollments", filter=Q(enrollments__end_date__isnull=True)))
    )
    open_days = request.branch.open_days or list(range(6)) if request.branch else []
    days = [(d, name) for d, name in WEEKDAYS if d in open_days]
    by_day = {d: [s for s in slots if s.weekday == d] for d, _ in days}
    return render(
        request,
        "desk/classes/timetable.html",
        {"days": days, "by_day": by_day, "can_manage": can(request, "classes.manage")},
    )


@desk("classes.manage")
def slot_edit(request, pk=None):
    slot = get_object_or_404(ClassSlot, pk=pk, branch=request.branch) if pk else None
    form = SlotForm(request.branch, request.POST or None, instance=slot)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.branch = request.branch
        obj.updated_by = request.user
        if slot is None:
            obj.created_by = request.user
        else:
            obj.version += 1
        obj.save()
        form.save_m2m()
        # Future sessions follow the timetable: create new ones; update untouched ones.
        today = timezone.localdate()
        future = ClassSession.objects.filter(slot=obj, date__gte=today, status="scheduled")
        for session in future:
            if not session.changes.filter(status="approved").exists():
                if not obj.runs_on(session.date):
                    if not session.bookings.exclude(status="cancelled").exists():
                        session.delete()
                    continue
                session.title_en, session.title_ar, session.start, session.end = (
                    obj.title_en,
                    obj.title_ar,
                    obj.start,
                    obj.end,
                )
                session.capacity, session.room, session.program = obj.capacity, obj.room, obj.program
                session.save()
                session.instructors.set(obj.instructors.all())
        classes.generate_sessions(slots=ClassSlot.objects.filter(pk=obj.pk))
        messages.success(
            request,
            L(
                "Timetable saved. The website and SAQR show it straight away.",
                "تم حفظ الجدول. يظهر على الموقع وفي صقر فوراً.",
            ),
        )
        return redirect("desk:timetable")
    return render(request, "desk/classes/slot_form.html", {"form": form, "slot": slot})


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["name", "name_ar", "capacity", "is_active"]


@desk("classes.manage")
def rooms(request):
    form = RoomForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        room = form.save(commit=False)
        room.branch, room.created_by, room.updated_by = request.branch, request.user, request.user
        room.save()
        return redirect("desk:rooms")
    return render(
        request, "desk/classes/rooms.html", {"form": form, "rooms": Room.objects.filter(branch=request.branch)}
    )


# ---------------------------------------------------------------------------
# Sessions and the class list
# ---------------------------------------------------------------------------
@desk("classes.view")
def sessions(request):
    day = request.GET.get("date")
    day = datetime.date.fromisoformat(day) if day else timezone.localdate()
    qs = (
        ClassSession.objects.filter(branch=request.branch, date=day)
        .select_related("room")
        .prefetch_related("instructors")
        .annotate(
            visits=Count("attendance", distinct=True),
            booked=Count("bookings", filter=Q(bookings__status__in=["booked", "attended"]), distinct=True),
            waiting=Count("bookings", filter=Q(bookings__status="waitlisted"), distinct=True),
        )
        .order_by("start")
    )
    rows = [(s, classes.places_taken(s)) for s in qs]
    return render(
        request,
        "desk/classes/sessions.html",
        {
            "day": day,
            "rows": rows,
            "prev": day - datetime.timedelta(days=1),
            "next": day + datetime.timedelta(days=1),
            "can_manage": can(request, "classes.manage"),
        },
    )


@desk("classes.view")
def my_classes(request):
    today = timezone.localdate()
    mine = (
        ClassSession.objects.filter(
            instructors=request.user, date__gte=today, date__lte=today + datetime.timedelta(days=6)
        )
        .select_related("branch")
        .order_by("date", "start")
    )
    from apps.renewals.models import InstructorHandoff

    handoffs = InstructorHandoff.objects.filter(instructor=request.user, done_at__isnull=True).select_related(
        "member", "membership"
    )
    return render(request, "desk/classes/my_classes.html", {"sessions": mine, "handoffs": handoffs})


@desk("classes.view")
def session_detail(request, pk):
    session = get_object_or_404(ClassSession.objects.select_related("branch", "room", "program", "slot"), pk=pk)
    if not has_perm(request.user, "classes.view", session.branch_id):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    rows = classes.roster(session)
    show_medical = has_perm(request.user, "members.view_medical", session.branch_id)
    q = request.GET.get("q", "").strip()
    return render(
        request,
        "desk/classes/session.html",
        {
            "session": session,
            "rows": rows,
            "show_medical": show_medical,
            "taken": classes.places_taken(session),
            "q": q,
            "found": search_members(request.user, q) if q else [],
            "can_book": has_perm(request.user, "classes.book", session.branch_id),
            "can_checkin": has_perm(request.user, "classes.checkin", session.branch_id),
            "can_change": has_perm(request.user, "classes.change_request", session.branch_id),
            "changes": session.changes.select_related("created_by", "decided_by"),
            "trials": TrialRequest.objects.filter(branch=session.branch, status__in=["new", "contacted"])[:20],
            "instructors": staff_users(),
        },
    )


@require_POST
@desk("classes.checkin")
def session_checkin(request, pk):
    session = get_object_or_404(ClassSession, pk=pk)
    if request.POST.get("booking"):
        booking = get_object_or_404(Booking, pk=request.POST["booking"], session=session)
        classes.check_in_guest(booking, request.user)
        messages.success(request, L(f"{booking.display_name} is here.", f"وصل {booking.display_name}."))
    else:
        member = get_object_or_404(visible_members(request.user), pk=request.POST.get("member"))
        _, created, warning = classes.check_in(member, session, request.user, Attendance.Method.COACH)
        if warning:
            from .checkin import warning_text

            messages.warning(request, f"{member}: {warning_text(warning)}")
        elif created:
            messages.success(request, L(f"{member} checked in.", f"تم تسجيل حضور {member}."))
    return redirect("desk:session", pk=pk)


@require_POST
@desk("classes.checkin")
def session_undo(request, pk, attendance_id):
    attendance = get_object_or_404(Attendance, pk=attendance_id, session_id=pk)
    classes.undo_check_in(attendance, request.user)
    messages.info(request, L("Check-in removed.", "تم حذف تسجيل الحضور."))
    return redirect("desk:session", pk=pk)


@require_POST
@desk("classes.book")
def session_book(request, pk):
    session = get_object_or_404(ClassSession, pk=pk)
    p = request.POST
    if p.get("member"):
        member = get_object_or_404(visible_members(request.user), pk=p["member"])
        booking = classes.book(session, request.user, member=member, source="desk")
    else:
        trial = TrialRequest.objects.filter(pk=p.get("trial_request") or 0).first()
        booking = classes.book(
            session,
            request.user,
            guest_name=p.get("guest_name") or (trial.name if trial else ""),
            guest_mobile=p.get("guest_mobile") or (trial.mobile if trial else ""),
            trial_request=trial,
            source="trial" if trial else "desk",
            is_trial=True,
        )
        if trial is not None:
            trial.status = TrialRequest.Status.BOOKED
            trial.owner = trial.owner or request.user  # first contact owns the lead
            trial.save(update_fields=["status", "owner"])
    if booking.status == Booking.Status.WAITLISTED:
        messages.warning(
            request, L("The class is full: added to the waiting list.", "الحصة ممتلئة: أُضيف إلى قائمة الانتظار.")
        )
    else:
        messages.success(request, L(f"{booking.display_name} booked.", f"تم حجز {booking.display_name}."))
    return redirect("desk:session", pk=pk)


@require_POST
@desk("classes.book")
def booking_cancel(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    classes.cancel_booking(booking, request.user)
    messages.info(request, L("Booking cancelled.", "تم إلغاء الحجز."))
    return redirect("desk:session", pk=booking.session_id)


class OneOffForm(forms.ModelForm):
    class Meta:
        model = ClassSession
        fields = [
            "kind",
            "program",
            "room",
            "title_en",
            "title_ar",
            "date",
            "start",
            "end",
            "capacity",
            "instructors",
            "pricing_option",
            "seminar_points",
            "note",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start": forms.TimeInput(attrs={"type": "time"}),
            "end": forms.TimeInput(attrs={"type": "time"}),
            "instructors": forms.CheckboxSelectMultiple,
        }

    def __init__(self, branch, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].choices = [c for c in ClassSession.Kind.choices if c[0] != "class"]
        self.fields["program"].queryset = Program.objects.filter(branch=branch)
        self.fields["room"].queryset = Room.objects.filter(branch=branch)
        self.fields["pricing_option"].queryset = PricingOption.objects.filter(branch=branch, approval="approved")
        self.fields["instructors"].queryset = staff_users()


@desk("classes.manage")
def session_new(request):
    """Seminars, camps, events and private sessions (scope M4)."""
    form = OneOffForm(request.branch, request.POST or None)
    if request.method == "POST" and form.is_valid():
        session = form.save(commit=False)
        session.branch, session.created_by, session.updated_by = request.branch, request.user, request.user
        session.save()
        form.save_m2m()
        return redirect("desk:session", pk=session.pk)
    return render(request, "desk/classes/session_new.html", {"form": form})


@require_POST
@desk("classes.change_request")
def change_request(request, pk):
    session = get_object_or_404(ClassSession, pk=pk)
    p = request.POST
    classes.request_change(
        session,
        request.user,
        kind=p.get("kind"),
        reason=p.get("reason", ""),
        new_date=datetime.date.fromisoformat(p["new_date"]) if p.get("new_date") else None,
        new_start=datetime.time.fromisoformat(p["new_start"]) if p.get("new_start") else None,
        new_end=datetime.time.fromisoformat(p["new_end"]) if p.get("new_end") else None,
        new_instructors=staff_users().filter(pk__in=p.getlist("new_instructors")),
    )
    messages.success(
        request,
        L(
            "Change requested. The Training Lead or OM will approve it.",
            "تم طلب التغيير. سيعتمده مسؤول التدريب أو مدير العمليات.",
        ),
    )
    return redirect("desk:session", pk=pk)


@desk(any_of=["classes.change_request", "classes.change_approve"])
def change_log(request):
    """The digital EA-OPS-FRM-04 Class Change Notice Log."""
    qs = (
        scope_queryset(ClassChange.objects.all(), request.user, "classes.view", "session__branch")
        .select_related("session", "created_by", "decided_by")
        .prefetch_related("new_instructors")[:200]
    )
    return render(
        request, "desk/classes/changes.html", {"changes": qs, "can_approve": can(request, "classes.change_approve")}
    )


@require_POST
@desk("classes.change_approve")
def change_decide(request, pk):
    change = get_object_or_404(ClassChange, pk=pk)
    approve = request.POST.get("decision") == "approve"
    change = classes.decide_change(change, approve, request.user, request.POST.get("note", ""))
    if approve:
        messages.success(
            request,
            L(
                f"Approved. {change.notified_count} families told on WhatsApp.",
                f"تم الاعتماد. أُبلغت {change.notified_count} عائلة عبر واتساب.",
            ),
        )
    else:
        messages.info(request, L("Rejected.", "تم الرفض."))
    return redirect(safe_next(request, "desk:changes"))
