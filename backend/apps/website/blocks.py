"""
CMS block types — one per block in the Elite Academy design system (handoff rule 5).

Every text field comes as an English + Arabic pair. English is required; an empty
Arabic field falls back to English so a page never shows blanks. Blocks that show
live data (programs, timetable, events, albums, instructors, branches) read it from
the database, so staff never type the same thing in two places.

Inside a home-page PathSection, blocks render "inner" (without their own section band).
"""

import datetime
import secrets

from django.utils import timezone
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

from .belts import BELT_CHOICES, KAJUKENBO_PATH

RICH_FEATURES = ["bold", "italic", "link", "ol", "ul", "h3"]


def bi(label, required=True, kind="char", help_text=""):
    """An English + Arabic pair of fields."""

    def make(lang_label, req):
        common = {"label": f"{label} ({lang_label})", "required": req, "help_text": help_text}
        if kind == "text":
            return blocks.TextBlock(**common)
        if kind == "rich":
            return blocks.RichTextBlock(features=RICH_FEATURES, **common)
        return blocks.CharBlock(**common)

    return make("English", required), make("Arabic", False)


TONE_CHOICES = [("", "Page ground"), ("white", "White"), ("sunken", "Sunken"), ("deep", "Night blue (last step only)")]


# ---------------------------------------------------------------------------
# Content blocks
# ---------------------------------------------------------------------------
class RichTextBlock(blocks.StructBlock):
    text_en, text_ar = bi("Text", kind="rich")

    class Meta:
        template = "website/blocks/rich_text.html"
        icon = "doc-full"
        label = "Text"


class HeadingBlock(blocks.StructBlock):
    eyebrow_en, eyebrow_ar = bi("Eyebrow", required=False)
    title_en, title_ar = bi("Title")
    lead_en, lead_ar = bi("Lead line", required=False, kind="text")

    class Meta:
        template = "website/blocks/heading.html"
        icon = "title"
        label = "Section heading"


class TrialStepsBlock(blocks.StructBlock):
    class Meta:
        template = "website/blocks/trial_steps.html"
        icon = "list-ol"
        label = "Trial steps (Book · Try · We place your child)"


class PrincipleItem(blocks.StructBlock):
    title_en, title_ar = bi("Principle")
    line_en, line_ar = bi("Line", kind="text")


class PrinciplesBlock(blocks.StructBlock):
    eyebrow_en, eyebrow_ar = bi("Eyebrow", required=False)
    title_en, title_ar = bi("Title")
    lead_en, lead_ar = bi("Lead", required=False, kind="text")
    illustration = ImageChooserBlock(required=False, help_text="Playbook line figure (single ink). Optional.")
    style = blocks.ChoiceBlock(choices=[("light", "Light"), ("deep", "Night blue")], default="light")
    principles = blocks.ListBlock(PrincipleItem(), min_num=1, max_num=5)

    class Meta:
        template = "website/blocks/principles.html"
        icon = "pick"
        label = "Five principles"


class ReasonItem(blocks.StructBlock):
    title_en, title_ar = bi("Title")
    line_en, line_ar = bi("Line", kind="text")


class ChipItem(blocks.StructBlock):
    label_en, label_ar = bi("Chip")


class WhyStayBlock(blocks.StructBlock):
    """Home · yellow belt: vision photo, principle chips and four reasons."""

    image = ImageChooserBlock(required=False)
    image_caption_en, image_caption_ar = bi("Photo caption", required=False)
    lead_en, lead_ar = bi("Lead", required=False, kind="text")
    chips = blocks.ListBlock(ChipItem(), required=False)
    reasons = blocks.ListBlock(ReasonItem(), max_num=4)

    class Meta:
        template = "website/blocks/why_stay.html"
        icon = "pick"
        label = "Why families stay"


class FAQItem(blocks.StructBlock):
    question_en, question_ar = bi("Question")
    answer_en, answer_ar = bi("Answer", kind="text")


class FAQBlock(blocks.StructBlock):
    title_en, title_ar = bi("Title")
    items = blocks.ListBlock(FAQItem())
    first_open = blocks.BooleanBlock(required=False, default=True, label="Open the first question")

    class Meta:
        template = "website/blocks/faq.html"
        icon = "help"
        label = "FAQ"


class CTAStripBlock(blocks.StructBlock):
    headline_en, headline_ar = bi("Headline")
    line_en, line_ar = bi("Line", kind="text")
    button_en, button_ar = bi("Button label", required=False)
    button_page = blocks.PageChooserBlock(required=False, help_text="Defaults to Book a trial.")
    show_whatsapp = blocks.BooleanBlock(required=False, default=True)

    class Meta:
        template = "website/blocks/cta_strip.html"
        icon = "pick"
        label = "Call-to-action strip"


class PromoBannerBlock(blocks.StructBlock):
    title_en, title_ar = bi("Title")
    line_en, line_ar = bi("Line", kind="text", required=False)
    ended_line_en, ended_line_ar = bi("Line after it ends", kind="text", required=False)
    end_date = blocks.DateBlock(help_text="Required. After this date the banner shows its ended state.")
    button_en, button_ar = bi("Button label", required=False)
    button_page = blocks.PageChooserBlock(required=False)

    class Meta:
        template = "website/blocks/promo_banner.html"
        icon = "date"
        label = "Promo banner"

    def get_context(self, value, parent_context=None):
        ctx = super().get_context(value, parent_context)
        today = timezone.localdate()
        ctx["ended"] = value["end_date"] < today
        ctx["days_left"] = max((value["end_date"] - today).days, 0)
        return ctx


class TestimonialItem(blocks.StructBlock):
    quote_en, quote_ar = bi("Quote", kind="text")
    name_en, name_ar = bi("Parent's first name")
    relation_en, relation_ar = bi("Relation", help_text="e.g. Parent of a Kajukenbo student")
    branch = blocks.ChoiceBlock(choices=[("promenade", "Promenade"), ("bedaya", "Bedaya")], required=False)
    approved = blocks.BooleanBlock(
        required=False, help_text="Tick only for a real quote published with the parent's permission."
    )


class TestimonialsBlock(blocks.StructBlock):
    eyebrow_en, eyebrow_ar = bi("Eyebrow", required=False)
    title_en, title_ar = bi("Title", required=False)
    items = blocks.ListBlock(TestimonialItem(), max_num=3)

    class Meta:
        template = "website/blocks/testimonials.html"
        icon = "openquote"
        label = "Parent quotes"


class StoryRow(blocks.StructBlock):
    year = blocks.CharBlock(max_length=10)
    title_en, title_ar = bi("Title")
    line_en, line_ar = bi("Line", kind="text", required=False)


class StoryBlock(blocks.StructBlock):
    eyebrow_en, eyebrow_ar = bi("Eyebrow", required=False)
    title_en, title_ar = bi("Title")
    intro_en, intro_ar = bi("Intro", kind="text", required=False)
    rows = blocks.ListBlock(StoryRow())

    class Meta:
        template = "website/blocks/story.html"
        icon = "history"
        label = "Story timeline"


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    caption_en, caption_ar = bi("Caption", required=False)

    class Meta:
        template = "website/blocks/image.html"
        icon = "image"
        label = "Photo"


class PortalPreviewBlock(blocks.StructBlock):
    """Home · green belt: what parents see in the member portal."""

    lead_en, lead_ar = bi("Lead", kind="text")

    class Meta:
        template = "website/blocks/portal_preview.html"
        icon = "user"
        label = "Portal preview"


# ---------------------------------------------------------------------------
# Data-driven blocks
# ---------------------------------------------------------------------------
class ProgramGridBlock(blocks.StructBlock):
    eyebrow_en, eyebrow_ar = bi("Eyebrow", required=False)
    title_en, title_ar = bi("Title", required=False)
    programs = blocks.ListBlock(
        blocks.PageChooserBlock(page_type="website.ProgramPage"),
        required=False,
        help_text="Leave empty to show every published program.",
    )
    show_filters = blocks.BooleanBlock(required=False, default=True)
    compact = blocks.BooleanBlock(required=False, help_text="List rows instead of cards (home page on phones).")

    class Meta:
        template = "website/blocks/program_grid.html"
        icon = "list-ul"
        label = "Programs"

    def get_context(self, value, parent_context=None):
        from .models import ProgramPage

        ctx = super().get_context(value, parent_context)
        chosen = [p.specific for p in value["programs"] if p and p.live]
        ctx["programs"] = chosen or list(ProgramPage.objects.live().public().order_by("path"))
        return ctx


class BranchComparisonBlock(blocks.StructBlock):
    eyebrow_en, eyebrow_ar = bi("Eyebrow", required=False)
    title_en, title_ar = bi("Title", required=False)
    lead_en, lead_ar = bi("Lead", required=False, kind="text")

    class Meta:
        template = "website/blocks/branch_comparison.html"
        icon = "site"
        label = "Branch comparison"

    def get_context(self, value, parent_context=None):
        from .models import BranchPage

        ctx = super().get_context(value, parent_context)
        # Promenade first in both languages (it reads first in either direction).
        ctx["branches"] = sorted(
            BranchPage.objects.live().public().select_related("branch"),
            key=lambda b: 0 if b.branch.code == "PRM" else 1,
        )
        return ctx


class ScheduleBlock(blocks.StructBlock):
    title_en, title_ar = bi("Title", required=False)
    note_en, note_ar = bi("Note", required=False, kind="text")
    branch = blocks.ChoiceBlock(
        choices=[("", "All branches"), ("PRM", "Promenade"), ("BED", "Bedaya")],
        required=False,
        help_text="Pre-select a branch (branch pages).",
    )
    program = blocks.PageChooserBlock(
        page_type="website.ProgramPage", required=False, help_text="Show only this program's classes (program pages)."
    )

    class Meta:
        template = "website/blocks/schedule.html"
        icon = "time"
        label = "Class schedule"

    def get_context(self, value, parent_context=None):
        from apps.classes.models import ClassSlot

        from .models import BranchPage

        ctx = super().get_context(value, parent_context)
        # The one timetable (scope rule 18): the classes the desk manages, shown live.
        today = timezone.localdate()
        entries = (
            ClassSlot.objects.filter(is_active=True, is_public=True, valid_from__lte=today)
            .exclude(valid_until__lt=today)
            .select_related("branch", "program")
        )
        page = value.get("program")
        if page:
            page = page.specific
            entries = entries.filter(program__in=page.system_programs.all())
            if page.schedule_match:
                entries = entries.filter(title_en__icontains=page.schedule_match)
        entries = list(entries.order_by("weekday", "start"))
        today = timezone.localdate()
        today_index = (today.weekday() + 2) % 7  # Python Monday=0 -> Kuwait week Saturday=0
        closed = {b.branch.code: b.closed_days for b in BranchPage.objects.live().select_related("branch")}
        open_days = [d for d in range(7) if not all(d in c for c in closed.values())] if closed else list(range(6))
        times = sorted({e.start for e in entries})
        ctx.update(
            entries=entries,
            times=times,
            today_index=today_index,
            selected_day=today_index if today_index in open_days else (open_days[0] if open_days else 0),
            days=[
                {
                    "index": d,
                    "en": DAYS[d][0],
                    "ar": DAYS[d][1],
                    "short_en": DAYS[d][2],
                    "short_ar": DAYS[d][3],
                    "date": (today + datetime.timedelta(days=(d - today_index) % 7)).day,
                    "closed": d not in open_days,
                    "entries": [e for e in entries if e.weekday == d],
                }
                for d in range(7)
            ],
            grid=[
                {"time": t, "cells": [[e for e in entries if e.weekday == d and e.start == t] for d in open_days]}
                for t in times
            ],
            open_days=open_days,
            closed=closed,
            disciplines=sorted({(e.discipline_key, e.discipline_en, e.discipline_ar) for e in entries}),
            block_id=secrets.token_hex(4),  # unique ids for labels when a page holds two schedules
            ages=[
                ("kids", "Kids", "أطفال"),
                ("teens", "Teens", "ناشئين"),
                ("adults", "Adults", "كبار"),
                ("ladies", "Ladies", "سيدات"),
            ],
        )
        return ctx


DAYS = [
    ("Saturday", "السبت", "Sat", "سبت"),
    ("Sunday", "الأحد", "Sun", "أحد"),
    ("Monday", "الاثنين", "Mon", "اثنين"),
    ("Tuesday", "الثلاثاء", "Tue", "ثلاثاء"),
    ("Wednesday", "الأربعاء", "Wed", "أربعاء"),
    ("Thursday", "الخميس", "Thu", "خميس"),
    ("Friday", "الجمعة", "Fri", "جمعة"),
]


class InstructorGridBlock(blocks.StructBlock):
    eyebrow_en, eyebrow_ar = bi("Eyebrow", required=False)
    title_en, title_ar = bi("Title", required=False)
    lead_en, lead_ar = bi("Lead", required=False, kind="text")
    branch = blocks.ChoiceBlock(choices=[("", "All branches"), ("PRM", "Promenade"), ("BED", "Bedaya")], required=False)

    class Meta:
        template = "website/blocks/instructor_grid.html"
        icon = "group"
        label = "Instructors"

    def get_context(self, value, parent_context=None):
        from .models import InstructorPage

        ctx = super().get_context(value, parent_context)
        qs = InstructorPage.objects.live().public().select_related("branch", "photo")
        if value.get("branch"):
            qs = qs.filter(branch__code=value["branch"])
        ctx["instructors"] = list(qs.order_by("path"))
        return ctx


class BeltItem(blocks.StructBlock):
    belt = blocks.ChoiceBlock(choices=BELT_CHOICES)
    name_en, name_ar = bi("Name", required=False, help_text="Defaults to the belt colour's name.")
    note_en, note_ar = bi("Note", required=False)


class BeltProgressionBlock(blocks.StructBlock):
    eyebrow_en, eyebrow_ar = bi("Eyebrow", required=False)
    title_en, title_ar = bi("Title")
    lead_en, lead_ar = bi("Lead", required=False, kind="text")
    belts = blocks.ListBlock(
        BeltItem(), required=False, help_text="Leave empty for the confirmed Kajukenbo path (White → Black)."
    )

    class Meta:
        template = "website/blocks/belt_progression.html"
        icon = "order"
        label = "Belt progression"

    def get_context(self, value, parent_context=None):
        ctx = super().get_context(value, parent_context)
        if value["belts"]:
            ctx["steps"] = [
                {
                    "belt": b["belt"],
                    "name_en": b["name_en"],
                    "name_ar": b["name_ar"],
                    "note_en": b["note_en"],
                    "note_ar": b["note_ar"],
                }
                for b in value["belts"]
            ]
        else:
            notes = {
                0: ("Start here", "البداية"),
                1: ("First test", "أول اختبار"),
                7: ("Years of training", "سنوات من التدريب"),
            }
            ctx["steps"] = [
                {
                    "belt": k,
                    "name_en": "",
                    "name_ar": "",
                    "note_en": notes.get(i, (f"Level {i + 1}", ""))[0],
                    "note_ar": notes.get(i, ("", f"المستوى {i + 1}"))[1],
                }
                for i, k in enumerate(KAJUKENBO_PATH)
            ]
        return ctx


class EventsListBlock(blocks.StructBlock):
    eyebrow_en, eyebrow_ar = bi("Eyebrow", required=False)
    title_en, title_ar = bi("Title", required=False)
    count = blocks.IntegerBlock(default=3, min_value=1, max_value=24)
    layout = blocks.ChoiceBlock(
        choices=[("row", "Rows (date tile)"), ("feature", "Feature cards with photo")], default="row"
    )
    show_filters = blocks.BooleanBlock(required=False, default=False)
    branch = blocks.ChoiceBlock(choices=[("", "All branches"), ("PRM", "Promenade"), ("BED", "Bedaya")], required=False)

    class Meta:
        template = "website/blocks/events_list.html"
        icon = "date"
        label = "Upcoming events"

    def get_context(self, value, parent_context=None):
        from .models import EventIndexPage, EventPage

        ctx = super().get_context(value, parent_context)
        qs = EventPage.objects.live().public().filter(date__gte=timezone.localdate()).select_related("branch")
        if value.get("branch"):
            qs = qs.filter(branch__code=value["branch"])
        ctx["events"] = list(qs.order_by("date", "start_time")[: value["count"]])
        ctx["events_index"] = EventIndexPage.objects.live().first()
        return ctx


class GalleryAlbumsBlock(blocks.StructBlock):
    eyebrow_en, eyebrow_ar = bi("Eyebrow", required=False)
    title_en, title_ar = bi("Title", required=False)
    count = blocks.IntegerBlock(default=3, min_value=1, max_value=24)
    strip = blocks.BooleanBlock(required=False, help_text="Small photo strip (home page) instead of album covers.")

    class Meta:
        template = "website/blocks/gallery_albums.html"
        icon = "image"
        label = "Photo albums"

    def get_context(self, value, parent_context=None):
        from .models import AlbumPage, GalleryIndexPage

        ctx = super().get_context(value, parent_context)
        ctx["albums"] = list(AlbumPage.objects.live().public().order_by("-date")[: value["count"]])
        ctx["gallery_index"] = GalleryIndexPage.objects.live().first()
        return ctx


class LocationBlock(blocks.StructBlock):
    branch = blocks.ChoiceBlock(choices=[("PRM", "Promenade"), ("BED", "Bedaya")])

    class Meta:
        template = "website/blocks/location.html"
        icon = "site"
        label = "Location & opening days"

    def get_context(self, value, parent_context=None):
        from .models import BranchPage

        ctx = super().get_context(value, parent_context)
        page = BranchPage.objects.live().filter(branch__code=value["branch"]).select_related("branch").first()
        ctx["branch_page"] = page
        ctx["today_index"] = (timezone.localdate().weekday() + 2) % 7
        closed = page.closed_days if page else set()
        ctx["week"] = [{"index": d, "en": DAYS[d][0], "ar": DAYS[d][1], "closed": d in closed} for d in range(7)]
        return ctx


def _form_context(ctx, parent_context, kind, defaults):
    """Bound form (after a failed POST) or GET pre-fill values, plus the success flag."""
    parent_context = parent_context or {}
    request = parent_context.get("request")
    form = parent_context.get(f"{kind}_form")
    data = form.data if form is not None else (request.GET if request else {})
    ctx["values"] = {k: (data.get(k) or v) for k, v in defaults.items()}
    ctx["errors"] = (
        {("form" if k == "__all__" else k): v[0] for k, v in form.errors.items()} if form is not None else {}
    )
    ctx["sent"] = bool(request and request.GET.get("sent") == kind and form is None)
    ctx["last"] = request.session.get(f"last_{kind}") if request is not None and ctx["sent"] else None
    return ctx


class TrialFormBlock(blocks.StructBlock):
    title_en, title_ar = bi("Title", required=False)
    lead_en, lead_ar = bi("Lead", required=False)

    class Meta:
        template = "website/blocks/trial_form.html"
        icon = "form"
        label = "Book a trial form"

    def get_context(self, value, parent_context=None):
        from .models import ProgramPage

        ctx = super().get_context(value, parent_context)
        _form_context(
            ctx, parent_context, "trial", {"name": "", "mobile": "", "branch": "PRM", "program": "", "source": ""}
        )
        ctx["programs"] = list(ProgramPage.objects.live().public().select_related("branch").order_by("path"))
        return ctx


class ContactFormBlock(blocks.StructBlock):
    title_en, title_ar = bi("Title", required=False)

    class Meta:
        template = "website/blocks/contact_form.html"
        icon = "mail"
        label = "Contact form"

    def get_context(self, value, parent_context=None):
        ctx = super().get_context(value, parent_context)
        return _form_context(ctx, parent_context, "contact", {"name": "", "mobile": "", "branch": "", "message": ""})


BODY_BLOCKS = [
    ("heading", HeadingBlock()),
    ("text", RichTextBlock()),
    ("image", ImageBlock()),
    ("trial_steps", TrialStepsBlock()),
    ("principles", PrinciplesBlock()),
    ("why_stay", WhyStayBlock()),
    ("programs", ProgramGridBlock()),
    ("branches", BranchComparisonBlock()),
    ("schedule", ScheduleBlock()),
    ("instructors", InstructorGridBlock()),
    ("belt_progression", BeltProgressionBlock()),
    ("events", EventsListBlock()),
    ("albums", GalleryAlbumsBlock()),
    ("testimonials", TestimonialsBlock()),
    ("story", StoryBlock()),
    ("faq", FAQBlock()),
    ("promo", PromoBannerBlock()),
    ("cta", CTAStripBlock()),
    ("location", LocationBlock()),
    ("portal_preview", PortalPreviewBlock()),
    ("trial_form", TrialFormBlock()),
    ("contact_form", ContactFormBlock()),
]


class PathStepBlock(blocks.StructBlock):
    """Home page: one section on the vertical belt spine (direction B · The Path)."""

    belt = blocks.ChoiceBlock(choices=[(k, k.title()) for k in KAJUKENBO_PATH])
    tone = blocks.ChoiceBlock(choices=TONE_CHOICES, required=False)
    eyebrow_en, eyebrow_ar = bi("Section idea", help_text="Shown after the belt name, e.g. 'Where everyone starts'")
    title_en, title_ar = bi("Title")
    content = blocks.StreamBlock(BODY_BLOCKS, required=False)

    class Meta:
        template = "website/blocks/path_step.html"
        icon = "order-down"
        label = "Path section"
