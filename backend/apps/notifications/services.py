"""
Templates and preferences for outgoing messages. Sending itself stays in apps.core.messaging.send_message,
which logs every message here and skips service messages a family has turned off.
"""

from string import Formatter

from django.core.exceptions import PermissionDenied, ValidationError

from apps.rbac.services import has_perm

from .models import FamilyPreference, MessageTemplate

# One Voice wording (P6-9). {placeholders} are filled when sent; overrides must keep the same ones.
DEFAULTS = {
    "trial_confirmed": (
        "Hi {name}! Your trial class at {branch} is booked: {when} · {cls}. Please arrive 10 minutes early in "
        "comfortable sports clothes. See you on the mat! — Elite Academy",
        "أهلاً {name}! تم حجز حصتك التجريبية في {branch}: {when} · {cls}. نرجو الحضور قبل 10 دقائق بملابس رياضية "
        "مريحة. نراك على البساط! — أكاديمية إيليت",
    ),
    "test_day_invite": (
        "{member} is invited to the {art} test day at {branch} on {date}. Good luck! — Elite Academy",
        "{member} مدعو ليوم اختبار {art} في {branch} بتاريخ {date}. بالتوفيق! — أكاديمية إيليت",
    ),
    "order_ready": (
        "Your order {reference} is ready for pick-up at {branch}. Please bring this message. — Elite Academy",
        "طلبك {reference} جاهز للاستلام في {branch}. يرجى إحضار هذه الرسالة. — أكاديمية إيليت",
    ),
    "order_sent": (
        "Your order {reference} is on its way to you. — Elite Academy",
        "طلبك {reference} في الطريق إليك. — أكاديمية إيليت",
    ),
    "renewal_paid": (
        "Thank you! {member}'s membership is renewed until {end}. Receipt {receipt}. — Elite Academy",
        "شكراً لك! تم تجديد اشتراك {member} حتى {end}. الإيصال {receipt}. — أكاديمية إيليت",
    ),
    "booking_confirmed": (
        "{member} is booked for {cls} on {when}. — Elite Academy",
        "تم حجز {member} في {cls} بتاريخ {when}. — أكاديمية إيليت",
    ),
    "waitlisted": (
        "{cls} on {when} is full: {member} is on the waiting list and we'll message you if a place opens. "
        "— Elite Academy",
        "حصة {cls} بتاريخ {when} ممتلئة: {member} في قائمة الانتظار وسنراسلك إن توفر مكان. — أكاديمية إيليت",
    ),
}
LABELS = {
    "trial_confirmed": "Trial booked (to the visitor)",
    "test_day_invite": "Test day invitation",
    "order_ready": "Online order ready for pick-up",
    "order_sent": "Online order sent out",
    "renewal_paid": "Online renewal paid",
    "booking_confirmed": "Class booked from the portal",
    "waitlisted": "Put on a waiting list",
}


def _fields(text):
    return {f for _, f, _, _ in Formatter().parse(text) if f}


def render(key, lang="ar", **values) -> str:
    en, ar = DEFAULTS[key]
    override = MessageTemplate.objects.filter(key=key).first()
    if override is not None:
        en, ar = override.text_en, override.text_ar
    return (ar if lang == "ar" else en).format(**values)


def save_template(user, key, text_en, text_ar) -> MessageTemplate:
    if not has_perm(user, "marketing.approve"):
        raise PermissionDenied("Only the Marketing Lead changes message wording.")
    if key not in DEFAULTS:
        raise ValidationError("Unknown message.")
    needed = _fields(DEFAULTS[key][0])
    for text in (text_en, text_ar):
        if not text.strip():
            raise ValidationError("Write the message in English and Arabic.")
        if _fields(text) != needed:
            raise ValidationError("Keep the same {placeholders}: " + ", ".join(sorted(needed)))
    obj, _ = MessageTemplate.objects.update_or_create(
        key=key, defaults={"text_en": text_en.strip(), "text_ar": text_ar.strip(), "updated_by": user}
    )
    return obj


def reset_template(user, key):
    if not has_perm(user, "marketing.approve"):
        raise PermissionDenied("Only the Marketing Lead changes message wording.")
    MessageTemplate.objects.filter(key=key).delete()


def service_messages_on(mobile) -> bool:
    pref = FamilyPreference.objects.filter(mobile=mobile).first()
    return pref is None or pref.service_messages


def set_service_messages(mobile, on: bool, user=None) -> FamilyPreference:
    pref, _ = FamilyPreference.objects.update_or_create(
        mobile=mobile, defaults={"service_messages": bool(on), "updated_by": user}
    )
    return pref
