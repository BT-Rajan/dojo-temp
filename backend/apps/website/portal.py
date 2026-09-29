"""
Member portal sign-in: mobile number + 4-digit code sent by WhatsApp; no passwords.

Security (ISO 27001 A.8.5):
- the same neutral answer whether or not the number is registered (no account discovery);
- codes are stored only as keyed hashes, expire after 5 minutes and allow 5 attempts;
- at most 3 codes per number per 15 minutes and 10 per address per hour;
- a signed-in parent sees only their own family (reached through their own profile).
"""

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.translation import get_language

from apps.audit.services import record_event
from apps.core.messaging import last_message_to, send_message
from apps.core.middleware import client_ip
from apps.core.validators import normalize_kuwait_mobile
from apps.members.models import Guardian, Member
from apps.rbac.models import Role, RoleAssignment
from apps.rbac.services import has_perm

from .models import MemberProgress, PortalCode

TEXT = {
    "bad_number": ("Please enter an 8-digit Kuwaiti number.", "يرجى إدخال رقم كويتي من 8 أرقام."),
    "bad_code": (
        "That code doesn't match. Check the latest message and try again.",
        "الرمز غير صحيح. تحقق من آخر رسالة وحاول مجدداً.",
    ),
    "expired": ("That code has expired. We've sent you a new one.", "انتهت صلاحية الرمز. أرسلنا لك رمزاً جديداً."),
    "too_many": (
        "Too many attempts. Please wait 15 minutes, or WhatsApp your branch.",
        "محاولات كثيرة. يرجى الانتظار 15 دقيقة أو مراسلة الفرع عبر واتساب.",
    ),
    "sms": (
        "Your Elite Academy sign-in code is {code}. It expires in 5 minutes.",
        "رمز الدخول إلى أكاديمية إيليت هو {code}. صالح لمدة 5 دقائق.",
    ),
}


def tr(key, lang, **kw):
    en, ar = TEXT[key]
    return (ar if lang == "ar" else en).format(**kw)


def _limit(key, limit, window):
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, window)
    return False


def _find_account(mobile):
    guardian = Guardian.objects.filter(mobile=mobile).first()
    if guardian:
        return guardian, "guardian"
    member = Member.objects.filter(mobile=mobile, is_active=True).first()
    if member and not member.is_minor:
        return member, "member"
    return None, None


@transaction.atomic
def _portal_user(profile, kind):
    User = get_user_model()
    user = profile.user
    if user is None:
        name = profile.full_name if kind == "guardian" else f"{profile.first_name} {profile.last_name}"
        mobile = profile.mobile if not User.objects.filter(mobile=profile.mobile).exists() else None
        user = User.objects.create_user(
            email=f"portal-{kind}-{profile.pk}@members.elite.local", password=None, full_name=name, mobile=mobile
        )
        profile.user = user
        profile.save(update_fields=["user"])
    role = Role.objects.get(code="guardian")
    if not RoleAssignment.objects.current().filter(user=user, role=role).exists():
        RoleAssignment.objects.create(user=user, role=role, reason="Portal sign-in by verified mobile")
    return user


def _family(user):
    """Each child's belt (MemberProgress until the curriculum module), plus live membership and next class."""
    from apps.classes.models import ClassSession
    from apps.sales.services import member_status

    members = Member.objects.none()
    guardian = getattr(user, "guardian_profile", None)
    if guardian is not None:
        members = guardian.members.all()
    own = getattr(user, "member_profile", None)
    if own is not None:
        members = members | Member.objects.filter(pk=own.pk)
    members = members.filter(is_active=True).select_related("branch").distinct()
    progress = {p.member_id: p for p in MemberProgress.objects.filter(member__in=members)}
    today = timezone.localdate()
    rows = []
    for m in members:
        status = member_status(m, today)
        slot_ids = m.enrollments.filter(end_date__isnull=True).values_list("slot_id", flat=True)
        next_class = (
            ClassSession.objects.filter(date__gte=today, status="scheduled")
            .filter(
                models.Q(slot_id__in=list(slot_ids))
                | models.Q(bookings__member=m, bookings__status__in=["booked", "waitlisted"])
            )
            .exclude(date=today, end__lt=timezone.localtime().time())
            .order_by("date", "start")
            .first()
        )
        membership = status.membership
        rows.append(
            {
                "member": m,
                "progress": progress.get(m.pk),
                "key": "promenade" if m.branch.code == "PRM" else "bedaya",
                "status": status,
                "membership": membership,
                "next_class": next_class,
                "expiring": status.code in ("expiring", "expired"),
            }
        )
    return rows


def serve_portal(page, request):
    lang = "ar" if get_language() == "ar" else "en"
    context = page.get_context(request)
    user = request.user

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "logout":
            record_event(action="portal_logout", object_type="User", object_id=str(user.pk))
            logout(request)
            return HttpResponseRedirect(page.url)
        if action in ("send", "resend"):
            return _send_code(page, request, context, lang)
        if action == "verify":
            return _verify_code(page, request, context, lang)

    if user.is_authenticated and has_perm(user, "portal.own_family"):
        context.update(step="family", family=_family(user))
        return TemplateResponse(request, page.get_template(request), context)

    step = "code" if request.GET.get("step") == "code" and request.session.get("portal_mobile") else "phone"
    context.update(step=step, mobile=request.session.get("portal_mobile", ""))
    _add_test_code(context, request)
    return TemplateResponse(request, page.get_template(request), context)


def _add_test_code(context, request):
    """Development only: show the code the console messaging backend 'sent'."""
    if settings.MESSAGING_BACKEND == "console" and getattr(settings, "ENVIRONMENT", "") != "production":
        message = last_message_to(request.session.get("portal_mobile", ""))
        if message:
            context["test_message"] = message["text"]


def _send_code(page, request, context, lang):
    raw = request.POST.get("mobile", "") or request.session.get("portal_mobile", "")
    try:
        mobile = normalize_kuwait_mobile(raw)
    except ValidationError:
        context.update(step="phone", mobile=raw, error=tr("bad_number", lang))
        return TemplateResponse(request, page.get_template(request), context)

    if _limit(f"portal:ip:{client_ip(request)}", 10, 3600) or _limit(f"portal:num:{mobile}", 3, 900):
        context.update(step="phone", mobile=mobile, error=tr("too_many", lang))
        return TemplateResponse(request, page.get_template(request), context)

    request.session["portal_mobile"] = mobile
    profile, _ = _find_account(mobile)
    if profile is not None:
        _, code = PortalCode.issue(mobile)
        send_message(mobile, tr("sms", lang, code=code))
    record_event(action="portal_code_requested", object_type="Mobile", object_id=mobile[-4:])
    return HttpResponseRedirect(f"{page.url}?step=code")


def _verify_code(page, request, context, lang):
    mobile = request.session.get("portal_mobile")
    code = "".join(request.POST.get(f"d{i}", "") for i in range(4)) or request.POST.get("code", "")
    code = code.strip()
    context.update(step="code", mobile=mobile or "")
    record = PortalCode.objects.filter(mobile=mobile, used_at__isnull=True).first() if mobile else None
    if record is None or record.attempts >= settings.PORTAL_OTP_MAX_ATTEMPTS:
        context["error"] = tr("too_many" if record else "bad_code", lang)
        return TemplateResponse(request, page.get_template(request), context)
    if record.expired:
        record.used_at = timezone.now()
        record.save(update_fields=["used_at"])
        context["error"] = tr("expired", lang)
        return _send_code(page, request, context, lang)
    if not record.matches(code):
        record.attempts += 1
        record.save(update_fields=["attempts"])
        record_event(action="portal_code_failed", object_type="Mobile", object_id=mobile[-4:])
        context["error"] = tr("bad_code", lang)
        _add_test_code(context, request)
        return TemplateResponse(request, page.get_template(request), context)

    record.used_at = timezone.now()
    record.save(update_fields=["used_at"])
    profile, kind = _find_account(mobile)
    if profile is None:
        context["error"] = tr("bad_code", lang)
        return TemplateResponse(request, page.get_template(request), context)
    user = _portal_user(profile, kind)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.pop("portal_mobile", None)
    record_event(action="portal_login", object_type="User", object_id=str(user.pk), actor=user)
    return HttpResponseRedirect(page.url)
