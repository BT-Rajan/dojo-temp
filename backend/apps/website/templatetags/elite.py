"""
Template helpers for the Elite Academy website (ported from the design system's reference build).

    {% t "Book a trial" "احجز حصة تجريبية" %}   pick by the page language
    {% f page "promise" %}                       page.promise_ar in Arabic (falls back to English)
    {% kd price %}                               85.000 KD / 85.000 د.ك (three decimals, LTR digits)
    {% icon "chev" "ea-flip" %}  {% belt "yellow" %}  {% illo %}
    {% photo image "Caption" "4/3" %}            real image, or the design's placeholder with a caption
"""

from decimal import ROUND_HALF_UP, Decimal

from django import template
from django.urls import translate_url
from django.utils.html import format_html, mark_safe

from apps.website.belts import BELTS, belt_css_var

register = template.Library()

ICONS = {
    "chev": '<path d="M9 6l6 6-6 6"/>',
    "chevl": '<path d="M15 6l-6 6 6 6"/>',
    "chevd": '<path d="M6 9l6 6 6-6"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "cal": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "phone": '<path d="M5 4h4l1.5 4.5-2.3 1.4a11 11 0 0 0 5.9 5.9l1.4-2.3L20 15v4a1.5 1.5 0 0 1-1.6 1.5A16.5 16.5 0 0 1 3.5 5.6 1.5 1.5 0 0 1 5 4z"/>',  # noqa: E501
    "wa": '<path d="M4 20l1.2-4A8.5 8.5 0 1 1 8.3 19z"/><path d="M9 8.5c0 3.5 2.8 6.5 6.5 6.5l1-1.6-2-1-1 .9a4.6 4.6 0 0 1-2.4-2.4l.9-1-1-2z"/>',  # noqa: E501
    "ig": '<rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.3" cy="6.7" r=".6"/>',  # noqa: E501
    "check": '<path d="M5 12.5l4.2 4.2L19 7"/>',
    "alert": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v5.5M12 16.2v.3"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "chat": '<path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9a1.5 1.5 0 0 1-1.5 1.5H10l-4.5 4V16h0A1.5 1.5 0 0 1 4 14.5z"/><path d="M8.5 9.5h7M8.5 12.5h4"/>',  # noqa: E501
    "send": '<path d="M4 12l16-8-6 16-2.5-6.5z"/>',
    "play": '<path d="M8 5.5v13l11-6.5z"/>',
    "globe": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 2.5 14.4 0 17M12 3.5c-2.5 2.6-2.5 14.4 0 17"/>',  # noqa: E501
    "user": '<circle cx="12" cy="8.5" r="3.5"/><path d="M5 20a7 7 0 0 1 14 0"/>',
    "shield": '<path d="M12 3.5l7 2.5v5.5c0 4.4-3 7.9-7 9-4-1.1-7-4.6-7-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "photo": '<rect x="3.5" y="5" width="17" height="14" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="M20.5 16l-5-5-8 8"/>',  # noqa: E501
    "bag": '<path d="M5 8h14l-1 12H6z"/><path d="M9 8V6.5a3 3 0 0 1 6 0V8"/>',
    "car": '<path d="M5 16V11l2-4.5h10L19 11v5M5 16h14M5 16v2M19 16v2"/><circle cx="8" cy="13" r=".6"/><circle cx="16" cy="13" r=".6"/>',  # noqa: E501
}

ILLO = (
    '<svg class="ea-illo {cls}" viewBox="0 0 160 120" fill="none" stroke="currentColor" stroke-width="2.2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 46c22-6 44-8 68-8s46 2 68 8"/><path d="M12 60c22-6 44-8 68-8s46 2 68 8"/>'
    '<path d="M68 40l-4 22h32l-4-22z"/><path d="M72 62l-16 46M88 62l14 44"/><path d="M64 62l-20 42M96 62l20 40"/>'
    '<path d="M44 104l12 4M116 102l-14 4"/></svg>'
)

AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _lang(context):
    return context.get("lang", "en")


def pick(obj, field, lang):
    """Arabic value when the page is Arabic and one exists, otherwise English."""

    def get(name):
        if obj is None:
            return ""
        if not hasattr(obj, "_meta") and hasattr(obj, "get"):  # StructValue / dict
            return obj.get(name) or ""
        return getattr(obj, name, "") or ""

    if lang == "ar":
        value = get(f"{field}_ar")
        if value:
            return value
    return get(f"{field}_en") or get(field)


@register.simple_tag(takes_context=True)
def t(context, en, ar):
    return ar if _lang(context) == "ar" else en


@register.simple_tag(takes_context=True)
def f(context, obj, field):
    return pick(obj, field, _lang(context))


def format_kd(amount, lang="en"):
    value = Decimal(str(amount or 0)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return format_html('<span class="ea-num" dir="ltr">{}</span> {}', f"{value:.3f}", "د.ك" if lang == "ar" else "KD")


@register.simple_tag(takes_context=True)
def kd(context, amount):
    return format_kd(amount, _lang(context))


@register.filter
def kd_plain(amount):
    value = Decimal(str(amount or 0)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return f"{value:.3f}"


@register.simple_tag
def icon(name, cls=""):
    return mark_safe(  # noqa: S308 - static SVG paths from this module only
        f'<svg class="ea-ico {cls}" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'
    )


@register.simple_tag
def belt(key, style=""):
    key = key if key in BELTS else "black"
    extra = f";{style}" if style else ""
    return format_html(
        '<span class="ea-belt" data-belt="{}" style="{}{}" aria-hidden="true"></span>', key, belt_css_var(key), extra
    )


@register.simple_tag
def belt_var(key):
    return belt_css_var(key if key in BELTS else "black")


@register.simple_tag(takes_context=True)
def belt_name(context, key):
    names = BELTS.get(key, ("", ""))
    return names[1] if _lang(context) == "ar" else names[0]


@register.simple_tag
def illo(cls=""):
    return mark_safe(ILLO.format(cls=cls))  # noqa: S308 - static SVG


RATIO_SPECS = {
    "16/9": "fill-1280x720",
    "4/3": "fill-800x600",
    "4/5": "fill-640x800",
    "1/1": "fill-800x800",
    "3/2": "max-1600x1100",
}


@register.inclusion_tag("website/partials/photo.html", takes_context=True)
def photo(context, image=None, caption="", ratio="4/3", cls="", spec=""):
    """A fixed-ratio photo slot: the CMS image (WebP rendition, lazy) or the design's captioned placeholder."""
    rendition = None
    if image:
        rendition = image.get_rendition((spec or RATIO_SPECS.get(ratio, "fill-800x600")) + "|format-webp")
    return {
        "rendition": rendition,
        "caption": caption,
        "ratio": ratio,
        "cls": cls,
        "lang": _lang(context),
        "alt": caption or getattr(image, "title", ""),
    }


@register.simple_tag(takes_context=True)
def switch_lang_url(context, target):
    request = context.get("request")
    path = request.get_full_path() if request else "/"
    return translate_url(path, target)


@register.filter
def split_lines(value):
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


@register.filter
def western_digits(value):
    return str(value).translate(AR_DIGITS)


@register.filter
def in_section(page, item):
    """True when `page` is `item` or sits under it in the page tree (menu highlighting)."""
    path = getattr(page, "path", "")
    return bool(path and item is not None and path.startswith(item.path))


@register.filter
def split_words(value):
    return (value or "").split()


@register.filter
def get_item(mapping, key):
    try:
        return mapping[key]
    except (KeyError, TypeError, IndexError):
        return None


@register.simple_tag(takes_context=True)
def trial_url(context, obj=None, source="", branch=""):
    """Link to Book a trial, pre-filling branch and program from a page, program or timetable entry."""
    from urllib.parse import urlencode

    from apps.classes.models import ClassSlot
    from apps.website.models import ProgramPage

    try:
        trial = context["key"].get("trial_page")
    except (KeyError, AttributeError):
        trial = None
    if trial is None:
        return ""
    params = {}
    branch_obj = getattr(obj, "branch", None) if obj is not None and getattr(obj, "branch_id", None) else None
    if branch or branch_obj is not None:
        params["branch"] = branch or branch_obj.code
    if isinstance(obj, ProgramPage):
        params["program"] = obj.pk
    elif isinstance(obj, ClassSlot):
        cache = context.render_context.setdefault("slot_program_pages", {})  # one lookup per program per page
        if obj.program_id not in cache:
            page = ProgramPage.objects.live().filter(system_programs=obj.program_id).order_by("path").first()
            cache[obj.program_id] = page.pk if page else None
        if cache[obj.program_id]:
            params["program"] = cache[obj.program_id]
    if source:
        params["source"] = source
    url = trial.get_url(context.get("request"))
    return f"{url}?{urlencode(params)}#trial" if params else f"{url}#trial"


@register.simple_tag(takes_context=True)
def step_name(context, key):
    from apps.website.belts import STEP_NAMES

    names = STEP_NAMES.get(key, ("", ""))
    return names[1] if _lang(context) == "ar" else names[0]


@register.simple_tag(takes_context=True)
def clock(context, value):
    """4:30 PM / 4:30 م — Western digits, kept left-to-right."""
    if not value:
        return ""
    suffix = ("م" if value.hour >= 12 else "ص") if _lang(context) == "ar" else ("PM" if value.hour >= 12 else "AM")
    hour = value.hour % 12 or 12
    return format_html('<time dir="ltr">{} <small>{}</small></time>', f"{hour}:{value.minute:02d}", suffix)


MONTHS_AR = [
    "يناير",
    "فبراير",
    "مارس",
    "أبريل",
    "مايو",
    "يونيو",
    "يوليو",
    "أغسطس",
    "سبتمبر",
    "أكتوبر",
    "نوفمبر",
    "ديسمبر",
]


@register.simple_tag
def month_ar(value):
    return MONTHS_AR[value.month - 1] if value else ""


@register.filter
def approved(items):
    """Only real quotes published with the parent's permission (brand book; handoff rule 9)."""
    return [item for item in (items or []) if item.get("approved")]


@register.filter
def branch_facts(page, lang):
    """The fact strip under a branch page band: membership, trial, opening days, ages."""
    from apps.website.models import SiteSettings

    ar = lang == "ar"
    rows = []
    for row in page.prices[:2]:
        note = row["note_ar"] if ar and row["note_ar"] else row["note_en"]
        rows.append(("الاشتراك" if ar else "Membership", format_html("{} {}", format_kd(row["amount"], lang), note)))
    rows.append(
        (
            "الحصة التجريبية" if ar else "Trial class",
            format_html(
                "{} {}",
                format_kd(SiteSettings.load().trial_price, lang),
                "تُدفع في الفرع" if ar else "paid at the branch",
            ),
        )
    )
    rows.append(("مفتوح" if ar else "Open", pick(page, "open_days", lang)))
    return rows


@register.filter
def program_facts(page, lang):
    from apps.website.models import SiteSettings

    ar = lang == "ar"
    return [
        ("العمر" if ar else "Ages", pick(page, "ages", lang)),
        ("الأيام" if ar else "Days", pick(page, "days", lang)),
        ("السعر" if ar else "Price", format_html("{} {}", format_kd(page.price, lang), "شهرياً" if ar else "/ month")),
        ("التجربة" if ar else "Trial", format_kd(SiteSettings.load().trial_price, lang)),
    ]


@register.simple_tag
def type_ar(code):
    from apps.website.models import EventPage

    return EventPage.TYPE_AR.get(code, code)


@register.simple_tag
def category_ar(code):
    from apps.shop.models import CATEGORY_AR

    return CATEGORY_AR.get(code, code)


@register.filter
def stripe_range(value):
    try:
        return range(max(0, min(int(value), 12)))
    except (TypeError, ValueError):
        return range(0)
