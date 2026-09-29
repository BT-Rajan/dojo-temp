from django import template

register = template.Library()

CATEGORY_AR = {
    "new": "جديد",
    "renew": "تجديد",
    "trial": "تذكرة تجربة",
    "day_pass": "تذكرة يوم",  # nosec B105 - a sale category label, not a password
    "equipment": "معدات",
    "other": "جلسات وفعاليات",
}


@register.simple_tag(takes_context=True)
def category_label(context, code):
    from apps.sales.models import SaleLine

    if context.get("lang") == "ar":
        return CATEGORY_AR.get(code, code)
    return dict(SaleLine.Category.choices).get(code, code)


@register.simple_tag(takes_context=True)
def weekday_name(context, day):
    from apps.classes.models import WEEKDAYS, WEEKDAYS_AR

    return WEEKDAYS_AR[day] if context.get("lang") == "ar" else dict(WEEKDAYS)[day]


@register.simple_tag(takes_context=True)
def name(context, member):
    """The member's name in the page language (Arabic when recorded), falling back to English."""
    from apps.members.services import display_name

    if member is None:
        return ""
    return display_name(member, context.get("lang", "en"))


@register.filter
def dmy(value):
    """'2026-09-19' (as stored in a frozen report) or a date → 19/09/2026."""
    import datetime

    if isinstance(value, str) and len(value) == 10:
        try:
            value = datetime.date.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime("%d/%m/%Y") if hasattr(value, "strftime") else value


METHODS_AR = {"KNET": "كي نت", "Visa / Mastercard": "فيزا / ماستركارد", "Cash": "نقداً"}


@register.simple_tag(takes_context=True)
def methods(context, value):
    """'KNET + Cash' in the page language."""
    if context.get("lang") != "ar" or not value:
        return value
    return " + ".join(METHODS_AR.get(part, part) for part in value.split(" + "))
