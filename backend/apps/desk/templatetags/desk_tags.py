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
