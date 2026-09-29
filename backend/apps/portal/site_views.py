"""
Portal pages on the website (/en/my/…, /ar/my/…): one page per child or adult member, the account page and the
online renewal round-trip. Everything is reached through the signed-in family (apps.portal.services.family).
"""

import datetime
from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language
from django.views.decorators.http import require_POST

from apps.classes.models import Booking, ClassSession
from apps.rbac.services import has_perm
from apps.shop.payments import get_gateway
from apps.training import services as tr

from . import services as ps
from .models import RenewalPayment


def _lang():
    return "ar" if get_language() == "ar" else "en"


def T(en, ar):
    return ar if _lang() == "ar" else en


def portal_url():
    from apps.website.models import PortalPage

    page = PortalPage.objects.live().first()
    return page.url if page else f"/{_lang()}/"


def family_only(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not has_perm(request.user, "portal.own_family"):
            return HttpResponseRedirect(portal_url())
        try:
            return view(request, *args, **kwargs)
        except (ValidationError, PermissionDenied) as exc:
            if request.method != "POST":
                raise
            for msg in getattr(exc, "messages", [str(exc)]):
                messages.error(request, msg)
            return HttpResponseRedirect(request.get_full_path())

    return wrapper


def _page(request, template, ctx):
    ctx.setdefault("portal_home", portal_url())
    ctx.setdefault("lang", _lang())
    return TemplateResponse(request, template, ctx)


def _progress(member):
    out = []
    for art in tr.arts_for(member):
        mr = tr.member_rank(member, art, create=False)
        if mr is None:
            continue
        e = tr.eligibility(member, art)
        p = tr.skill_progress(member, mr.rank)
        tests = member.tests.filter(
            test_day__date__gte=timezone.localdate(), test_day__status="planned"
        ).select_related("test_day")
        out.append(
            {
                "art": art,
                "mr": mr,
                "e": e,
                "done": p["count"],
                "total": p["total"],
                "tests": tests,
                "evaluations": member.evaluations.filter(art=art).exclude(notes="").select_related("instructor")[:3],
                "notes": member.progress_notes.filter(art=art, status="sent")[:3],
                "seminars": tr.seminar_points(member, art),
            }
        )
    return out


@family_only
def member_page(request, pk):
    member = ps.member_for(request.user, pk)
    if request.method == "POST":
        p = request.POST
        action = p.get("action")
        if action == "book":
            session = get_object_or_404(ClassSession, pk=p.get("session"))
            b = ps.book(request.user, member, session)
            messages.success(
                request,
                T("On the waiting list — we'll message you.", "في قائمة الانتظار — سنراسلك.")
                if b.status == "waitlisted"
                else T("Booked.", "تم الحجز."),
            )
        elif action == "cancel":
            booking = get_object_or_404(Booking, pk=p.get("booking"), member=member)
            b = ps.cancel(request.user, booking)
            messages.success(
                request,
                T("Cancelled (less than 2 hours' notice is noted).", "تم الإلغاء (يُسجَّل الإلغاء قبل أقل من ساعتين).")
                if b.late_cancellation
                else T("Cancelled.", "تم الإلغاء."),
            )
        elif action == "freeze":
            try:
                start = datetime.date.fromisoformat(p.get("start", ""))
            except ValueError as exc:
                raise ValidationError(T("Choose the start date.", "اختر تاريخ البداية.")) from exc
            ps.request_freeze(request.user, member, start, int(p.get("weeks") or 0), p.get("reason", ""))
            messages.success(request, T("Freeze request sent to the branch.", "أُرسل طلب التجميد للفرع."))
        elif action == "consent":
            ps.set_consent(
                request.user, member, p.get("internal") == "1", p.get("social") == "1", p.get("website") == "1"
            )
            messages.success(request, T("Photo choices saved.", "تم حفظ اختيارات الصور."))
        elif action == "rules":
            ps.sign_rules(request.user, member, p.get("name", ""), p.get("agree") == "1")
            messages.success(request, T("Thank you — rules signed.", "شكراً — تم توقيع القواعد."))
        return HttpResponseRedirect(request.path)
    membership = ps.current_membership(member)
    from apps.sales.services import member_status

    return _page(
        request,
        "website/portal/member.html",
        {
            "member": member,
            "status": member_status(member, timezone.localdate()),
            "membership": membership,
            "renewal": ps.renewal_option(member),
            "classes": ps.upcoming(member),
            "attendance": ps.attendance(member, 10),
            "progress": _progress(member),
            "receipts": ps.receipts(member, 10),
            "consent": member.media_consents.first(),
            "rules_signed": ps.rules_signed(member),
            "signer": ps.signer_name(request.user),
            "pending_freeze": membership.requests.filter(status="pending", kind="freeze").first()
            if membership
            else None,
            "today": timezone.localdate(),
        },
    )


@family_only
def account(request):
    if request.method == "POST":
        p = request.POST
        ps.update_email(request.user, p.get("email", ""))
        ps.set_messages(request.user, p.get("service") == "1", p.get("broadcasts") == "1")
        messages.success(request, T("Saved.", "تم الحفظ."))
        return HttpResponseRedirect(request.path)
    from apps.leads.services import opted_in
    from apps.notifications.services import service_messages_on

    fam = list(ps.family(request.user))
    profile = getattr(request.user, "guardian_profile", None) or getattr(request.user, "member_profile", None)
    return _page(
        request,
        "website/portal/account.html",
        {
            "family": fam,
            "email": profile.email if profile else "",
            "mobile": ps.family_mobile(request.user),
            "service_on": service_messages_on(ps.family_mobile(request.user)),
            "broadcasts_on": any(opted_in(m) for m in fam),
            "recent": ps.recent_messages(request.user),
        },
    )


@require_POST
@family_only
def renew(request, pk):
    member = ps.member_for(request.user, pk)
    with transaction.atomic():
        payment = ps.start_renewal(request.user, member, request.POST.get("method", "knet"))
    request.session["orders"] = [*request.session.get("orders", []), payment.reference][-10:]
    return_url = request.build_absolute_uri(reverse("portal-renew-return", args=[payment.reference]))
    return HttpResponseRedirect(get_gateway().start(payment, return_url))


@family_only
def renew_return(request, reference):
    payment = RenewalPayment.objects.filter(reference=reference, user=request.user).first()
    if payment is None:
        raise Http404
    paid, gateway_ref = get_gateway().verify(payment, request)
    payment = ps.complete_renewal(payment, paid, gateway_ref)
    if payment.status == RenewalPayment.Status.PAID:
        messages.success(request, T("Payment received — the membership is renewed.", "تم الدفع — تم تجديد الاشتراك."))
    else:
        messages.error(
            request, T("The payment didn't go through. Nothing was charged.", "لم تتم عملية الدفع. لم يُخصم أي مبلغ.")
        )
    return HttpResponseRedirect(reverse("portal-member", args=[payment.member_id]))
