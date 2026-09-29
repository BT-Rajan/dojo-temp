"""Front-desk check-in: search or scan the member card, pick the class, check in."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.classes import services as classes
from apps.classes.models import Attendance, ClassSession
from apps.sales.services import member_status

from ..access import L, desk
from ..lookup import search_members, visible_members

WARNINGS = {
    "no_membership": (
        "No membership on file — checked in. Offer a membership or trial pass.",
        "لا يوجد اشتراك — تم تسجيل الحضور. اعرض اشتراكاً أو حصة تجريبية.",
    ),
    "expired": (
        "Membership expired — checked in and added to the renewals list.",
        "الاشتراك منتهٍ — تم تسجيل الحضور وأُضيف إلى قائمة التجديد.",
    ),
    "frozen": ("Membership is frozen today — checked in.", "الاشتراك مجمّد اليوم — تم تسجيل الحضور."),
    "no_sessions": (
        "No sessions left in the package — checked in. Offer a renewal.",
        "لا توجد حصص متبقية في الباقة — تم تسجيل الحضور. اعرض التجديد.",
    ),
    "other_program": (
        "The membership doesn't cover this class — checked in.",
        "الاشتراك لا يشمل هذه الحصة — تم تسجيل الحضور.",
    ),
}


def warning_text(code):
    en, ar = WARNINGS[code]
    return L(en, ar)


@desk("classes.checkin")
def checkin(request):
    q = request.GET.get("q", "").strip()
    results = list(search_members(request.user, q)) if q else []
    member = None
    member_id = request.GET.get("member")
    if member_id:
        member = get_object_or_404(visible_members(request.user), pk=member_id)
    elif len(results) == 1 and results[0].qr_token == q:
        member = results[0]  # scanned card
    ctx = {"q": q, "results": results, "member": member}
    if member is not None and request.branch is not None:
        ranked, mine, booked = classes.sessions_for_check_in(member, request.branch)
        ctx.update(
            status=member_status(member),
            ranked=ranked,
            mine=mine,
            booked=booked,
            done={a.session_id for a in Attendance.objects.filter(member=member, session__date=timezone.localdate())},
            all_today=ClassSession.objects.filter(
                branch=request.branch, date=timezone.localdate(), status="scheduled"
            ).order_by("start"),
        )
        # A scanned card with exactly one class right now checks straight in.
        if q and q == member.qr_token and len(ranked) == 1 and (ranked[0].slot_id in mine or ranked[0].pk in booked):
            return _do_check_in(request, member, ranked[0], Attendance.Method.QR)
    return render(request, "desk/checkin.html", ctx)


def _do_check_in(request, member, session, method):
    attendance, created, warning = classes.check_in(member, session, request.user, method)
    name = str(member)
    if not created:
        messages.info(
            request,
            L(
                f"{name} is already checked in to {session.title_en}.",
                f"{name} مسجّل حضوره مسبقاً في {session.title_ar or session.title_en}.",
            ),
        )
    elif warning:
        messages.warning(request, f"{name}: {warning_text(warning)}")
    else:
        messages.success(
            request,
            L(
                f"{name} checked in to {session.title_en} {session.start:%H:%M}.",
                f"تم تسجيل حضور {name} في {session.title_ar or session.title_en} {session.start:%H:%M}.",
            ),
        )
    return redirect(reverse("desk:checkin"))


@require_POST
@desk("classes.checkin")
def checkin_do(request):
    member = get_object_or_404(visible_members(request.user), pk=request.POST.get("member"))
    session = get_object_or_404(ClassSession, pk=request.POST.get("session"), branch=request.branch)
    return _do_check_in(request, member, session, request.POST.get("method") or Attendance.Method.DESK)
