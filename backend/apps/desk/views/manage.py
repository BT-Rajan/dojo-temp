"""Approvals (OM / Training Lead), cash-up, renewals, pricing, reports and trial requests."""

import datetime
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.classes import services as classes
from apps.classes.models import Attendance, Booking, ClassChange, ClassSession
from apps.core.validators import day_range
from apps.members.services import contact_mobile
from apps.organization import services as org
from apps.organization.models import PriceChange, PricingOption, Program
from apps.rbac.services import scope_queryset
from apps.renewals import services as renewals
from apps.renewals.models import FollowUp, InstructorHandoff
from apps.sales import services as sales
from apps.sales.models import AccountRequest, CashUp, Discount, SaleLine

from ..access import L, can, desk, lang, safe_next
from .sales import _money


# ---------------------------------------------------------------------------
# Approvals inbox
# ---------------------------------------------------------------------------
@desk(any_of=["sales.approve_refund", "pricing.approve", "classes.change_approve", "reports.verify", "finance.manage"])
def approvals(request):
    ctx = {}
    if can(request, "sales.approve_refund"):
        ctx["requests"] = AccountRequest.objects.filter(status="pending").select_related(
            "membership__member", "membership__pricing_option", "sale", "branch", "created_by"
        )
    if can(request, "pricing.approve"):
        ctx["price_changes"] = PriceChange.objects.filter(status="pending").select_related(
            "pricing_option", "created_by"
        )
        ctx["new_options"] = PricingOption.objects.filter(approval="pending").select_related("branch", "created_by")
    if can(request, "classes.change_approve"):
        ctx["class_changes"] = (
            ClassChange.objects.filter(status="pending")
            .select_related("session", "created_by")
            .prefetch_related("new_instructors")
        )
    if can(request, "reports.verify") or can(request, "finance.manage"):
        ctx["cash_ups"] = CashUp.objects.filter(status="submitted").select_related("branch", "submitted_by")
    return render(request, "desk/manage/approvals.html", ctx)


@require_POST
@desk("sales.approve_refund")
def request_decide(request, pk):
    req = get_object_or_404(AccountRequest, pk=pk)
    approve = request.POST.get("decision") == "approve"
    sales.decide_request(req, approve, request.user, request.POST.get("note", ""))
    messages.success(request, L("Decision saved.", "تم حفظ القرار."))
    return redirect(safe_next(request, "desk:approvals"))


@require_POST
@desk("pricing.approve")
def price_decide(request, pk):
    approve = request.POST.get("decision") == "approve"
    if request.POST.get("what") == "option":
        org.decide_pricing_option(get_object_or_404(PricingOption, pk=pk), approve, request.user)
    else:
        org.decide_price_change(
            get_object_or_404(PriceChange, pk=pk), approve, request.user, request.POST.get("note", "")
        )
    messages.success(request, L("Decision saved.", "تم حفظ القرار."))
    return redirect(safe_next(request, "desk:approvals"))


# ---------------------------------------------------------------------------
# Cash-up
# ---------------------------------------------------------------------------
@desk("sales.cashup")
def cash_up(request):
    day = request.GET.get("date")
    day = datetime.date.fromisoformat(day) if day else timezone.localdate()
    record = sales.open_cash_up(request.branch, day, request.user)
    if request.method == "POST":
        p = request.POST
        sales.submit_cash_up(
            record,
            request.user,
            counted_cash=_money(p.get("counted_cash")),
            terminal_knet=_money(p.get("terminal_knet")),
            terminal_card=_money(p.get("terminal_card")),
            reason=p.get("reason", ""),
        )
        messages.success(
            request,
            L(
                "Cash-up submitted to the Operations Manager and the Accountant.",
                "تم إرسال الإغلاق اليومي إلى مدير العمليات والمحاسب.",
            ),
        )
        return redirect(f"{request.path}?date={day}")
    history = CashUp.objects.filter(branch=request.branch).select_related("submitted_by", "verified_by")[:30]
    return render(
        request,
        "desk/manage/cashup.html",
        {"record": record, "day": day, "history": history, "threshold": CashUp.REASON_THRESHOLD},
    )


@require_POST
@desk(any_of=["reports.verify", "finance.manage"])
def cash_up_verify(request, pk):
    sales.verify_cash_up(get_object_or_404(CashUp, pk=pk), request.user)
    messages.success(request, L("Cash-up verified.", "تم التحقق من الإغلاق اليومي."))
    return redirect(safe_next(request, "desk:approvals"))


# ---------------------------------------------------------------------------
# Renewals
# ---------------------------------------------------------------------------
def whatsapp_link(member, membership):
    mobile = "".join(ch for ch in contact_mobile(member) if ch.isdigit())
    if not mobile:
        return ""
    from urllib.parse import quote

    text = renewals.reminder_text(
        membership, "ar" if lang() == "ar" else "en", max((membership.end_date - timezone.localdate()).days, 0)
    )
    return f"https://wa.me/{mobile}?text={quote(text)}"


@desk("renewals.follow_up")
def renewals_list(request):
    tab = request.GET.get("tab", "list")
    ctx = {
        "tab": tab,
        "outcomes": FollowUp.Outcome.choices,
        "channels": FollowUp.Channel.choices,
        "today": timezone.localdate(),
    }
    if tab == "at_risk":
        ctx["at_risk"] = renewals.at_risk(request.branch)
    elif tab == "handoffs":
        ctx["handoffs"] = InstructorHandoff.objects.filter(membership__branch=request.branch).select_related(
            "member", "instructor", "membership"
        )[:100]
    else:
        rows = renewals.follow_up_list(request.branch)
        ctx["rows"] = [(r, whatsapp_link(r.member, r.membership)) for r in rows]
    return render(request, "desk/manage/renewals.html", ctx)


@require_POST
@desk("renewals.follow_up")
def renewal_record(request, pk):
    from apps.sales.models import Membership

    membership = get_object_or_404(scope_queryset(Membership.objects.all(), request.user, "renewals.follow_up"), pk=pk)
    p = request.POST
    fu = renewals.record_follow_up(
        membership,
        request.user,
        outcome=p.get("outcome", ""),
        channel=p.get("channel") or "whatsapp",
        will_renew_on=datetime.date.fromisoformat(p["will_renew_on"]) if p.get("will_renew_on") else None,
        leaving_reason=p.get("leaving_reason", ""),
        note=p.get("note", ""),
    )
    if fu.outcome == FollowUp.Outcome.FREEZE:
        messages.info(request, L("Log the freeze request now.", "سجّل طلب التجميد الآن."))
        return redirect(f"{reverse('desk:request_new')}?membership={membership.pk}&kind=freeze")
    if fu.outcome == FollowUp.Outcome.RENEWED:
        return redirect(f"{reverse('desk:sell')}?member={membership.member_id}")
    if fu.outcome == FollowUp.Outcome.NO_ANSWER and fu.attempt >= renewals.NO_ANSWER_LIMIT:
        messages.warning(
            request,
            L(
                "Third unanswered attempt: passed to the member's instructor.",
                "المحاولة الثالثة دون رد: تم تحويله إلى مدرّب العضو.",
            ),
        )
    else:
        messages.success(request, L("Saved.", "تم الحفظ."))
    return redirect(safe_next(request, "desk:renewals"))


@require_POST
@desk("classes.view")
def handoff_done(request, pk):
    renewals.complete_handoff(get_object_or_404(InstructorHandoff, pk=pk), request.user, request.POST.get("note", ""))
    messages.success(request, L("Thanks — noted.", "شكراً — تم التسجيل."))
    return redirect(safe_next(request, "desk:my_classes"))


# ---------------------------------------------------------------------------
# Pricing and discounts
# ---------------------------------------------------------------------------
class OptionForm(forms.ModelForm):
    class Meta:
        model = PricingOption
        fields = [
            "name",
            "name_ar",
            "kind",
            "programs",
            "price",
            "duration_days",
            "total_sessions",
            "package_weeks",
            "sessions_per_week",
            "all_access",
            "family_discount_allowed",
            "active_from",
            "active_until",
        ]
        widgets = {
            "programs": forms.CheckboxSelectMultiple,
            "active_from": forms.DateInput(attrs={"type": "date"}),
            "active_until": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, branch, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["programs"].queryset = Program.objects.filter(branch=branch)


class DiscountForm(forms.ModelForm):
    class Meta:
        model = Discount
        fields = ["name", "name_ar", "kind", "branch", "percent", "amount", "active_from", "active_until", "is_enabled"]
        widgets = {
            "active_from": forms.DateInput(attrs={"type": "date"}),
            "active_until": forms.DateInput(attrs={"type": "date"}),
        }


@desk("programs.view")
def pricing(request):
    options = (
        PricingOption.objects.filter(branch=request.branch)
        .prefetch_related("programs")
        .order_by("-is_active", "kind", "name")
    )
    form = OptionForm(request.branch, request.POST or None) if can(request, "pricing.manage") else None
    if request.method == "POST" and request.POST.get("form") == "option" and form is not None and form.is_valid():
        option = form.save(commit=False)
        option.branch, option.created_by, option.updated_by = request.branch, request.user, request.user
        option.approval = PricingOption.Approval.PENDING
        option.save()
        form.save_m2m()
        messages.success(
            request,
            L(
                "Saved. It can be sold once the Operations Manager approves it.",
                "تم الحفظ. يمكن بيعه بعد اعتماد مدير العمليات.",
            ),
        )
        return redirect("desk:pricing")
    if request.method == "POST" and request.POST.get("form") == "change":
        option = get_object_or_404(PricingOption, pk=request.POST.get("option"), branch=request.branch)
        org.request_price_change(
            option,
            _money(request.POST.get("new_price")),
            datetime.date.fromisoformat(request.POST.get("effective_from")),
            request.POST.get("reason", ""),
            request.user,
        )
        messages.success(request, L("Price change requested.", "تم طلب تغيير السعر."))
        return redirect("desk:pricing")
    discount_form = DiscountForm(request.POST or None) if can(request, "pricing.approve") else None
    if (
        request.method == "POST"
        and request.POST.get("form") == "discount"
        and discount_form
        and discount_form.is_valid()
    ):
        d = discount_form.save(commit=False)
        d.created_by = d.updated_by = request.user
        d.applies_to_kinds = request.POST.getlist("applies_to_kinds")
        d.save()
        return redirect("desk:pricing")
    return render(
        request,
        "desk/manage/pricing.html",
        {
            "options": options,
            "form": form,
            "discount_form": discount_form,
            "discounts": Discount.objects.all(),
            "changes": PriceChange.objects.filter(pricing_option__branch=request.branch).select_related(
                "pricing_option"
            )[:20],
            "today": timezone.localdate(),
            "kinds": PricingOption.Kind.choices,
        },
    )


@require_POST
@desk("pricing.approve")
def discount_toggle(request, pk):
    d = get_object_or_404(Discount, pk=pk)
    d.is_enabled = not d.is_enabled
    d.updated_by = request.user
    d.save(update_fields=["is_enabled", "updated_by", "updated_at"])
    return redirect("desk:pricing")


# ---------------------------------------------------------------------------
# Reports: class utilisation, visits, no-shows, sales by category
# ---------------------------------------------------------------------------
@desk(any_of=["reports.branch", "reports.all"])
def reports(request):
    end = timezone.localdate()
    start = end - datetime.timedelta(days=27)
    branch = request.branch
    visits = (
        Attendance.objects.filter(session__branch=branch, session__date__range=(start, end))
        .values("session__date")
        .annotate(n=Count("id"))
        .order_by("session__date")
    )
    visit_map = {v["session__date"]: v["n"] for v in visits}
    trend = [
        (start + datetime.timedelta(days=i), visit_map.get(start + datetime.timedelta(days=i), 0)) for i in range(28)
    ]
    peak = max([n for _, n in trend] + [1])
    no_shows = Booking.objects.filter(
        session__branch=branch, session__date__range=(start, end), status="no_show"
    ).count()
    late = Booking.objects.filter(
        session__branch=branch, session__date__range=(start, end), late_cancellation=True
    ).count()
    s0, _ = day_range(start)
    _, e1 = day_range(end)
    by_category = (
        SaleLine.objects.filter(sale__branch=branch, sale__created_at__gte=s0, sale__created_at__lt=e1)
        .values("category")
        .annotate(total=Sum("line_total"), n=Count("id"))
        .order_by("category")
    )
    return render(
        request,
        "desk/manage/reports.html",
        {
            "start": start,
            "end": end,
            "utilisation": classes.utilisation(branch, start, end),
            "trend": trend,
            "peak": peak,
            "no_shows": no_shows,
            "late": late,
            "by_category": by_category,
            "sessions_held": ClassSession.objects.filter(
                branch=branch, date__range=(start, end), status="scheduled"
            ).count(),
            "total_sales": sum((r["total"] or Decimal("0")) for r in by_category),
        },
    )


# ---------------------------------------------------------------------------
# Website trial requests → book into a class
# ---------------------------------------------------------------------------
@desk("leads.manage")
def trial_requests(request):
    """Website trial requests are leads since Phase 5 (decision P5-1)."""
    return redirect("desk:leads")
