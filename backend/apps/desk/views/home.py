"""Desk home: today at this branch, and what is waiting for me."""

from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.classes.models import Booking, ClassChange, ClassSession
from apps.core.validators import day_range
from apps.organization.models import PriceChange, PricingOption
from apps.renewals.models import InstructorHandoff
from apps.renewals.services import at_risk, follow_up_list
from apps.sales.models import AccountRequest, CashUp, Sale
from apps.website.models import TrialRequest

from ..access import can, desk


def waiting_counts(request):
    """Counts for the sidebar and the home page. Only what this user may act on."""
    branch = request.branch
    out = {}
    if can(request, "sales.approve_refund"):
        out["requests"] = AccountRequest.objects.filter(status="pending").count()
    if can(request, "pricing.approve"):
        out["prices"] = (
            PriceChange.objects.filter(status="pending").count()
            + PricingOption.objects.filter(approval="pending").count()
        )
    if can(request, "classes.change_approve"):
        out["changes"] = ClassChange.objects.filter(status="pending").count()
    if can(request, "reports.verify") or can(request, "finance.manage"):
        out["cashups"] = CashUp.objects.filter(status="submitted").count()
    if branch is not None and can(request, "leads.manage"):
        out["trials"] = TrialRequest.objects.filter(branch=branch, status="new").count()
    out["approvals"] = sum(out.get(k, 0) for k in ("requests", "prices", "changes", "cashups"))
    return out


@desk()
def home(request):
    today = timezone.localdate()
    branch = request.branch
    ctx = {"today": today, "counts": waiting_counts(request)}
    if branch is not None and can(request, "classes.view"):
        ctx["sessions"] = (
            ClassSession.objects.filter(branch=branch, date=today)
            .annotate(
                visits=Count("attendance", distinct=True),
                booked=Count(
                    "bookings",
                    filter=Q(bookings__status__in=[Booking.Status.BOOKED, Booking.Status.ATTENDED]),
                    distinct=True,
                ),
            )
            .order_by("start")
        )
    ctx["my_sessions"] = ClassSession.objects.filter(instructors=request.user, date=today).order_by("start")
    ctx["my_handoffs"] = InstructorHandoff.objects.filter(instructor=request.user, done_at__isnull=True).select_related(
        "member"
    )
    if branch is not None and can(request, "renewals.follow_up"):
        ctx["renewals"] = len(follow_up_list(branch, today))
        ctx["at_risk"] = len(at_risk(branch, today))
    if branch is not None and can(request, "sales.sell"):
        start, end = day_range(today)
        sales = Sale.objects.filter(branch=branch, created_at__gte=start, created_at__lt=end)
        ctx["sales_today"] = sales.count()
        ctx["sales_total"] = sum((s.total for s in sales), 0)
        ctx["cash_up"] = CashUp.objects.filter(branch=branch, date=today).first()
    from ..tasks import my_tasks

    ctx["tasks"] = my_tasks(request)[:6]
    ctx["shift_needed"] = any(t["url"].endswith("/shift/") for t in ctx["tasks"])
    return render(request, "desk/home.html", ctx)
