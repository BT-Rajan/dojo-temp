"""
Coaches (for the CEO and the Operations Manager): everyone who teaches, their weekly classes, what they taught this
month, evaluations, pay arrangement and anything needing attention. Built from the timetable, sessions, training and
payroll records; nothing is entered here.
"""

import calendar
import datetime
from decimal import Decimal

from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.classes.models import Attendance, ClassSession, ClassSlot
from apps.organization.models import Branch
from apps.payroll.models import PayComponent
from apps.payroll.services import session_hours
from apps.rbac.models import RoleAssignment
from apps.rbac.services import has_perm
from apps.staff.models import StaffProfile
from apps.training.models import Evaluation, ProgressNote, Promotion

from ..access import desk, lang

PAY_AR = {
    "salary": "راتب شهري",
    "allowance": "بدل شهري",
    "hourly": "بالساعة",
    "per_class": "لكل حصة",
    "commission": "عمولة",
}
COACH_ROLES = ("instructor", "track_lead", "training_lead")


def coach_users():
    """People with a teaching role (the CEO's all-access role doesn't make them a coach)."""
    from django.contrib.auth import get_user_model

    ids = RoleAssignment.objects.current().filter(role__code__in=COACH_ROLES).values_list("user_id")
    return get_user_model().objects.filter(pk__in=ids, is_active=True).order_by("full_name")


TYPE_AR = {"full_time": "دوام كامل", "part_time": "دوام جزئي", "hourly": "بالساعة", "freelance": "متعاقد حر"}


def _month(request):
    raw = request.GET.get("month", "")
    try:
        month = datetime.date.fromisoformat(raw + "-01") if len(raw) == 7 else timezone.localdate()
    except ValueError:
        month = timezone.localdate()
    first = month.replace(day=1)
    return first, first.replace(day=calendar.monthrange(first.year, first.month)[1])


def _pay_summary(profile, on):
    pay = getattr(profile, "pay", None)
    if pay is None:
        return []
    out = []
    for c in (
        PayComponent.objects.filter(profile=pay, valid_from__lte=on).exclude(valid_to__lt=on).select_related("program")
    ):
        name = PAY_AR.get(c.kind, c.kind) if lang() == "ar" else c.get_kind_display()
        value = f"{c.percent}%" if c.kind == "commission" else f"{c.amount:.3f} {'د.ك' if lang() == 'ar' else 'KD'}"
        if c.program_id:
            name += f" · {c.program.name}"
        out.append(f"{name}: {value}")
    return out


def _sessions(user, start, end, branch=None):
    today = timezone.localdate()
    qs = ClassSession.objects.filter(
        instructors=user, date__range=(start, min(end, today)), status=ClassSession.Status.SCHEDULED
    )
    if branch is not None:
        qs = qs.filter(branch=branch)
    return qs


def coach_rows(start, end, branch=None):
    today = timezone.localdate()
    horizon = today + datetime.timedelta(days=30)
    coaches = list(coach_users().select_related("staff_profile__primary_branch", "staff_profile__pay"))
    roles = {}
    for a in RoleAssignment.objects.current().filter(user__in=coaches).select_related("role", "branch"):
        roles.setdefault(a.user_id, []).append(a.role.name + (f" ({a.branch.code})" if a.branch_id else ""))
    rows = []
    for u in coaches:
        profile = getattr(u, "staff_profile", None)
        slots = ClassSlot.objects.filter(instructors=u, is_active=True)
        if branch is not None:
            slots = slots.filter(branch=branch)
            if not slots.exists() and (profile is None or profile.primary_branch_id != branch.pk):
                continue
        sessions = list(_sessions(u, start, end, branch))
        hours = sum((session_hours(s) for s in sessions), Decimal(0))
        visits = Attendance.objects.filter(session__in=sessions).count()
        alerts = []
        if profile is None:
            alerts.append(("No staff record", "لا يوجد سجل موظف"))
        else:
            if not _pay_summary(profile, today):
                alerts.append(("Pay not set up", "لم يُحدد الأجر"))
            if profile.documents.filter(expires_on__lte=horizon).exists():
                alerts.append(("Document expiring", "مستند ينتهي قريباً"))
        if not slots.exists():
            alerts.append(("No weekly classes", "لا حصص أسبوعية"))
        rows.append(
            {
                "user": u,
                "profile": profile,
                "roles": roles.get(u.pk, []),
                "weekly": slots.count(),
                "taught": len(sessions),
                "hours": hours.quantize(Decimal("0.1")),
                "visits": visits,
                "evaluations": Evaluation.objects.filter(instructor=u, date__range=(start, end)).count(),
                "pay": _pay_summary(profile, today) if profile else [],
                "alerts": alerts,
            }
        )
    return rows


@desk("staff.manage")
def coaches(request):
    start, end = _month(request)
    branch = Branch.objects.filter(code=request.GET.get("branch", "")).first()
    rows = coach_rows(start, end, branch)
    return render(
        request,
        "desk/coaches/list.html",
        {
            "rows": rows,
            "start": start,
            "end": end,
            "branch": branch,
            "branches": Branch.objects.filter(is_active=True).order_by("-code"),
            "sees_pay": has_perm(request.user, "payroll.view") or has_perm(request.user, "payroll.prepare"),
            "totals": {
                "coaches": len(rows),
                "taught": sum(r["taught"] for r in rows),
                "hours": sum((r["hours"] for r in rows), Decimal(0)),
                "alerts": sum(1 for r in rows if r["alerts"]),
            },
            "type_ar": TYPE_AR,
        },
    )


@desk("staff.manage")
def coach(request, pk):
    user = get_object_or_404(coach_users(), pk=pk)
    profile = StaffProfile.objects.filter(user=user).select_related("primary_branch", "reports_to__user").first()
    start, end = _month(request)
    sessions = (
        _sessions(user, start, end)
        .select_related("branch")
        .annotate(visits=Count("attendance", distinct=True))
        .order_by("-date", "-start")
    )
    return render(
        request,
        "desk/coaches/detail.html",
        {
            "coach": user,
            "profile": profile,
            "start": start,
            "end": end,
            "row": next((r for r in coach_rows(start, end) if r["user"].pk == user.pk), None),
            "slots": ClassSlot.objects.filter(instructors=user, is_active=True).select_related("branch", "room"),
            "sessions": sessions[:60],
            "evaluations": Evaluation.objects.filter(instructor=user)
            .select_related("member", "art")
            .order_by("-date")[:15],
            "promotions": Promotion.objects.filter(date__range=(start, end), created_by=user).count(),
            "notes_sent": ProgressNote.objects.filter(instructor=user, month=start, status="sent").count(),
            "notes_draft": ProgressNote.objects.filter(instructor=user, status="draft").count(),
            "sees_pay": has_perm(request.user, "payroll.view") or has_perm(request.user, "payroll.prepare"),
            "type_ar": TYPE_AR,
        },
    )
