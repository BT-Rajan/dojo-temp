"""Leads, trials and group sales (M3); campaigns, referrals and broadcasts (M13)."""

import datetime
import io

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from apps.classes.models import ClassSession
from apps.leads import services as ls
from apps.leads.models import Activity, Broadcast, Campaign, GroupDeal, Lead
from apps.organization.models import Branch, Program
from apps.rbac.services import has_perm, users_with_perm

from ..access import L, can, desk, lang
from ..lookup import visible_members
from .ops import _date
from .sales import _money

LEADS = ["leads.manage", "marketing.manage"]


def _due(value):
    """'2026-10-01T16:00' from a datetime-local field → aware datetime."""
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


def _lead(request, pk):
    lead = get_object_or_404(Lead.objects.select_related("branch", "owner", "campaign", "referrer", "program"), pk=pk)
    if not any(has_perm(request.user, p, lead.branch_id) for p in LEADS):
        raise Http404
    return lead


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------
@desk(any_of=LEADS)
def leads(request):
    if request.method == "POST":
        p = request.POST
        lead = ls.intake(
            name=p.get("name", ""),
            mobile=p.get("mobile", ""),
            branch=request.branch,
            source=p.get("source", "walk_in"),
            program=Program.objects.filter(pk=p.get("program") or 0, branch=request.branch).first(),
            interest=p.get("interest", ""),
            language=p.get("language", "ar"),
            campaign=Campaign.objects.filter(pk=p.get("campaign") or 0).first(),
            referrer=ls.referrer_for_code(p.get("referral_code")),
            user=request.user,
            note=p.get("note", ""),
        )
        messages.success(request, L("Lead saved — it's yours.", "تم حفظ العميل المحتمل وهو مسؤوليتك."))
        return redirect("desk:lead", pk=lead.pk)
    show = request.GET.get("show", "open")
    qs = Lead.objects.filter(branch=request.branch).select_related("owner", "campaign")
    if show == "open":
        qs = qs.filter(stage__in=Lead.OPEN)
    elif show == "mine":
        qs = qs.filter(owner=request.user, stage__in=Lead.OPEN)
    elif show == "overdue":
        qs = qs.filter(stage__in=Lead.OPEN, next_due__lt=timezone.now())
    elif show == "unowned":
        qs = qs.filter(stage="new", owner__isnull=True)
    elif show in Lead.Stage.values:
        qs = qs.filter(stage=show)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(mobile__icontains=q))
    qs = qs.order_by("next_due" if show in ("open", "mine", "overdue", "unowned") else "-created_at")
    return render(
        request,
        "desk/leads/list.html",
        {
            "leads": qs[:200],
            "show": show,
            "q": q,
            "sources": Lead.Source.choices,
            "programs": Program.objects.filter(branch=request.branch, is_active=True),
            "campaigns": Campaign.objects.filter(Q(end__isnull=True) | Q(end__gte=timezone.localdate())),
            "can_work": can(request, "leads.manage"),
            "now": timezone.now(),
        },
    )


@desk(any_of=LEADS)
def lead_detail(request, pk):
    lead = _lead(request, pk)
    if request.method == "POST":
        p = request.POST
        action = p.get("action")
        if action == "contact":
            ls.log_contact(
                lead, request.user, p.get("kind"), p.get("text", ""), p.get("next_action", ""), _due(p.get("next_due"))
            )
        elif action == "book":
            session = get_object_or_404(ClassSession, pk=p.get("session"), branch=lead.branch)
            ls.book_trial(lead, session, request.user)
            messages.success(
                request, L("Trial booked; the instructor has the brief.", "تم حجز التجربة وأُرسل الملخص للمدرّب.")
            )
        elif action == "lost":
            ls.mark_lost(lead, request.user, p.get("reason", ""), p.get("note", ""))
        elif action == "reopen":
            ls.reopen(lead, request.user, p.get("next_action", ""), _due(p.get("next_due")))
        elif action == "reassign":
            owner = get_object_or_404(get_user_model(), pk=p.get("owner"), is_active=True)
            ls.reassign(lead, request.user, owner, p.get("reason", ""))
        elif action == "details":
            if not has_perm(request.user, "leads.manage", lead.branch_id):
                raise PermissionDenied
            lead.interest = p.get("interest", "")[:200]
            lead.program = Program.objects.filter(pk=p.get("program") or 0, branch=lead.branch).first()
            lead.campaign = Campaign.objects.filter(pk=p.get("campaign") or 0).first() or lead.campaign
            lead.updated_by = request.user
            lead.save()
        return redirect("desk:lead", pk=pk)
    today = timezone.localdate()
    sessions = ClassSession.objects.filter(
        branch=lead.branch, date__gte=today, date__lte=today + datetime.timedelta(days=14), status="scheduled"
    ).order_by("date", "start")[:60]
    return render(
        request,
        "desk/leads/lead.html",
        {
            "l": lead,
            "activities": lead.activities.select_related("by")[:60],
            "sessions": [s for s in sessions if not s.is_over],
            "kinds": [(k, v) for k, v in Activity.Kind.choices if k in ("call", "whatsapp", "visit", "note")],
            "reasons": Lead.LostReason.choices,
            "can_work": has_perm(request.user, "leads.manage", lead.branch_id),
            "can_reassign": has_perm(request.user, "marketing.approve", lead.branch_id),
            "owners": users_with_perm("leads.manage", lead.branch_id).order_by("full_name"),
            "programs": Program.objects.filter(branch=lead.branch, is_active=True),
            "campaigns": Campaign.objects.all()[:50],
            "tomorrow": (timezone.localtime() + datetime.timedelta(days=1)).replace(minute=0, second=0),
        },
    )


@desk(any_of=["leads.manage", "marketing.manage", "reports.all"])
def lead_report(request):
    days = int(request.GET.get("days") or 30)
    since = timezone.now() - datetime.timedelta(days=days)
    branch_code = request.GET.get("branch", request.branch.code if request.branch else "")
    qs = Lead.objects.filter(created_at__gte=since)
    if branch_code != "all":
        qs = qs.filter(branch__code=branch_code)
    owners = {u.pk: u.full_name for u in get_user_model().objects.filter(owned_leads__in=qs).distinct()}
    campaigns = {c.pk: c.name for c in Campaign.objects.filter(leads__in=qs).distinct()}
    sources = dict(Lead.Source.choices)
    return render(
        request,
        "desk/leads/report.html",
        {
            "days": days,
            "branch_code": branch_code,
            "branches": Branch.objects.filter(is_active=True),
            "total": ls.funnel(qs),
            "by_source": [dict(r, label=sources.get(r["key"], "—")) for r in ls.breakdown(qs, "source")],
            "by_owner": [dict(r, label=owners.get(r["key"], "—")) for r in ls.breakdown(qs, "owner")],
            "by_campaign": [dict(r, label=campaigns.get(r["key"], "—")) for r in ls.breakdown(qs, "campaign")],
            "by_branch": ls.breakdown(qs, "branch__code") if branch_code == "all" else [],
            "lost": qs.filter(stage="lost").values_list("lost_reason", flat=True),
        },
    )


# ---------------------------------------------------------------------------
# Group sales
# ---------------------------------------------------------------------------
@desk(any_of=["leads.manage", "ops.manage"])
def deals(request):
    if request.method == "POST":
        p = request.POST
        deal = ls.create_deal(
            request.user,
            organisation=p.get("organisation", "").strip()[:150],
            kind=p.get("kind", "school"),
            contact_name=p.get("contact_name", "").strip()[:120],
            mobile=p.get("mobile", ""),
            email=p.get("email", "")[:254],
            branch=request.branch,
            details=p.get("details", ""),
        )
        return redirect("desk:deal", pk=deal.pk)
    qs = GroupDeal.objects.filter(branch=request.branch).select_related("owner", "receiving_owner")
    return render(
        request,
        "desk/leads/deals.html",
        {"deals": qs[:100], "kinds": GroupDeal.Kind.choices, "can_create": can(request, "leads.manage")},
    )


@desk(any_of=["leads.manage", "ops.manage"])
def deal_detail(request, pk):
    deal = get_object_or_404(GroupDeal.objects.select_related("branch", "owner", "receiving_owner"), pk=pk)
    if not any(has_perm(request.user, p, deal.branch_id) for p in ("leads.manage", "ops.manage")):
        raise Http404
    if request.method == "POST":
        p = request.POST
        if p.get("action") == "confirm":
            ls.confirm_delivery(deal, request.user)
        elif p.get("action") == "note":
            if not has_perm(request.user, "leads.manage", deal.branch_id):
                raise PermissionDenied
            if p.get("text", "").strip():
                Activity.objects.create(deal=deal, kind=p.get("kind", "note"), text=p["text"].strip(), by=request.user)
        else:
            ls.move_deal(
                deal,
                request.user,
                p.get("stage", ""),
                p.get("note", ""),
                value=_money(p.get("value")) if p.get("value") else None,
                participants=int(p.get("participants") or 0) or None,
                start_date=_date(p.get("start_date")),
                details=p.get("details") or None,
                next_action=p.get("next_action") or None,
                next_due=_date(p.get("next_due")),
            )
        return redirect("desk:deal", pk=pk)
    return render(
        request,
        "desk/leads/deal.html",
        {
            "d": deal,
            "activities": deal.activities.select_related("by")[:60],
            "stages": [(k, v) for k, v in GroupDeal.Stage.choices],
            "can_work": has_perm(request.user, "leads.manage", deal.branch_id),
            "can_confirm": has_perm(request.user, "ops.manage", deal.branch_id)
            and deal.stage == "paid"
            and not deal.confirmed_at,
        },
    )


# ---------------------------------------------------------------------------
# Campaigns and broadcasts
# ---------------------------------------------------------------------------
@desk(any_of=["marketing.manage", "marketing.approve"])
def campaigns(request):
    if request.method == "POST":
        if not can(request, "marketing.manage"):
            raise PermissionDenied
        p = request.POST
        c = Campaign.objects.filter(pk=p.get("campaign") or 0).first() or Campaign(created_by=request.user)
        c.name = p.get("name", "").strip()[:120]
        c.code = p.get("code", "").strip().lower()[:30]
        c.channel = p.get("channel", "other")
        c.branch = Branch.objects.filter(pk=p.get("branch") or 0).first()
        c.start = _date(p.get("start"), timezone.localdate())
        c.end = _date(p.get("end"))
        c.spend = _money(p.get("spend"))
        c.updated_by = request.user
        if not c.name or not c.code:
            messages.error(request, L("Enter the name and a short code.", "أدخل الاسم ورمزاً قصيراً."))
        elif Campaign.objects.filter(code=c.code).exclude(pk=c.pk).exists():
            messages.error(request, L("That code is already used.", "هذا الرمز مستخدم."))
        else:
            c.save()
        return redirect("desk:campaigns")
    rows = [(c, ls.campaign_stats(c)) for c in Campaign.objects.select_related("branch")[:60]]
    return render(
        request,
        "desk/leads/campaigns.html",
        {
            "rows": rows,
            "channels": Campaign.Channel.choices,
            "branches": Branch.objects.filter(is_active=True),
            "today": timezone.localdate(),
            "site": request.build_absolute_uri("/"),
        },
    )


@desk(any_of=["marketing.manage", "marketing.approve"])
def broadcasts(request):
    if request.method == "POST":
        p = request.POST
        action = p.get("action")
        b = Broadcast.objects.filter(pk=p.get("broadcast") or 0).first()
        if action == "send":
            b = ls.send_broadcast(b, request.user)
            messages.success(request, L(f"Sent to {b.recipients} families.", f"أُرسلت إلى {b.recipients} عائلة."))
        elif action == "return":
            ls.return_broadcast(b, request.user, p.get("note", ""))
        else:
            ls.save_broadcast(
                request.user,
                b,
                title=p.get("title", "")[:120],
                message_en=p.get("message_en", ""),
                message_ar=p.get("message_ar", ""),
                branch=Branch.objects.filter(pk=p.get("branch") or 0).first(),
                program=Program.objects.filter(pk=p.get("program") or 0).first(),
                ages=p.get("ages", "all"),
                campaign=Campaign.objects.filter(pk=p.get("campaign") or 0).first(),
            )
            messages.success(request, L("Draft saved for approval.", "حُفظت المسودة للاعتماد."))
        return redirect("desk:broadcasts")
    rows = [
        (b, len(ls.audience(b)) if b.status == "draft" else b.recipients)
        for b in Broadcast.objects.select_related("branch", "program", "created_by")[:40]
    ]
    return render(
        request,
        "desk/leads/broadcasts.html",
        {
            "rows": rows,
            "branches": Branch.objects.filter(is_active=True),
            "programs": Program.objects.filter(is_active=True).select_related("branch"),
            "campaigns": Campaign.objects.all()[:50],
            "ages": Broadcast.Ages.choices,
            "can_draft": can(request, "marketing.manage"),
            "can_send": can(request, "marketing.approve"),
        },
    )


# ---------------------------------------------------------------------------
# Referral card and messaging opt-in (on the member page)
# ---------------------------------------------------------------------------
@desk("members.view")
def referral_card(request, pk):
    import qrcode
    import qrcode.image.svg

    member = get_object_or_404(visible_members(request.user), pk=pk)
    code = ls.referral_code_for(member)
    link = request.build_absolute_uri(f"/{lang()}/?ref={code.code}")
    buf = io.BytesIO()
    qrcode.make(link, image_factory=qrcode.image.svg.SvgPathImage, box_size=8).save(buf)
    svg = mark_safe(buf.getvalue().decode())  # noqa: S308  # nosec B308 B703 - SVG drawn by the qrcode library
    return render(request, "desk/leads/referral_card.html", {"member": member, "code": code, "link": link, "qr": svg})


@require_POST
@desk(any_of=["members.update", "marketing.manage"])
def member_opt_in(request, pk):
    member = get_object_or_404(visible_members(request.user), pk=pk)
    ls.set_opt_in(member, request.user, request.POST.get("opted_in") == "1")
    messages.success(request, L("WhatsApp choice saved.", "تم حفظ اختيار واتساب."))
    return redirect("desk:member", pk=pk)
