"""
Website page types (Wagtail) for elitemaacademy.com — design direction B · The Path.

One page tree serves both languages: every page and block holds English and Arabic
fields, and URLs are prefixed /en/ or /ar/. Staff build and edit pages in the CMS
(/cms/) from the blocks in blocks.py.
"""

import datetime
import hashlib
import hmac
import secrets

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable, Page
from wagtail.search import index
from wagtail.snippets.models import register_snippet

from apps.core.validators import validate_kuwait_mobile

from .belts import BELT_CHOICES, BELTS, parse_path
from .blocks import BODY_BLOCKS, RICH_FEATURES, PathStepBlock

BELT_FIELD = {"max_length": 12, "choices": BELT_CHOICES}


class BilingualPage(Page):
    """Adds the Arabic title and the night-blue PageBand fields to a page."""

    title_ar = models.CharField("Title (Arabic)", max_length=255, blank=True)
    band_belt = models.CharField(
        "Belt marker",
        default="blue",
        **BELT_FIELD,
        help_text="Trial white · About yellow · Programs/Schedule purple · Branches/Contact "
        "blue · Portal green · Events/Gallery brown · Shop black",
    )
    band_eyebrow_en = models.CharField("Eyebrow (English)", max_length=120, blank=True)
    band_eyebrow_ar = models.CharField("Eyebrow (Arabic)", max_length=120, blank=True)
    band_lead_en = models.TextField("Lead (English)", blank=True)
    band_lead_ar = models.TextField("Lead (Arabic)", blank=True)
    band_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Leave empty on utility pages (schedule, shop, contact).",
    )
    band_image_caption = models.CharField(max_length=160, blank=True, help_text="Shown until a photo is chosen.")
    band_cta = models.BooleanField("Show Book a trial button", default=False)
    search_description_ar = models.TextField("Search description (Arabic)", blank=True)

    band_panels = [
        MultiFieldPanel(
            [
                FieldPanel("band_belt"),
                FieldPanel("band_eyebrow_en"),
                FieldPanel("band_eyebrow_ar"),
                FieldPanel("band_lead_en"),
                FieldPanel("band_lead_ar"),
                FieldPanel("band_image"),
                FieldPanel("band_image_caption"),
                FieldPanel("band_cta"),
            ],
            heading="Page band (night-blue title)",
        ),
    ]
    content_panels = Page.content_panels + [FieldPanel("title_ar")]
    promote_panels = Page.promote_panels + [FieldPanel("search_description_ar")]

    class Meta:
        abstract = True

    @property
    def title_en(self):
        return self.title


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------
class HomePage(BilingualPage):
    hero_eyebrow_en = models.CharField(max_length=120, default="We build better humans")
    hero_eyebrow_ar = models.CharField(max_length=120, blank=True, default="نبني إنساناً أفضل")
    hero_title_en = models.CharField(max_length=120, default="From first bow to black belt.")
    hero_title_ar = models.CharField(max_length=120, blank=True, default="من أول تحية إلى الحزام الأسود.")
    hero_lead_en = models.TextField(blank=True)
    hero_lead_ar = models.TextField(blank=True)
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Bowing, a class line-up or a child tying a belt.",
    )
    hero_image_caption = models.CharField(
        max_length=160, blank=True, default="Photo or video: kids class bowing in on clean mats"
    )
    show_branch_line = models.BooleanField(default=True)
    journey = StreamField([("step", PathStepBlock())], blank=True, use_json_field=True)

    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    content_panels = BilingualPage.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_eyebrow_en"),
                FieldPanel("hero_eyebrow_ar"),
                FieldPanel("hero_title_en"),
                FieldPanel("hero_title_ar"),
                FieldPanel("hero_lead_en"),
                FieldPanel("hero_lead_ar"),
                FieldPanel("hero_image"),
                FieldPanel("hero_image_caption"),
                FieldPanel("show_branch_line"),
            ],
            heading="Hero",
        ),
        FieldPanel("journey"),
    ]
    template = "website/pages/home_page.html"


# ---------------------------------------------------------------------------
# General content page (About, Contact, Schedule, Book a trial, Programs, Branches …)
# ---------------------------------------------------------------------------
class ContentPage(BilingualPage):
    body = StreamField(BODY_BLOCKS, blank=True, use_json_field=True)
    mobile_action_en = models.CharField("Mobile bar button (English)", max_length=60, blank=True)
    mobile_action_ar = models.CharField("Mobile bar button (Arabic)", max_length=60, blank=True)

    content_panels = (
        BilingualPage.content_panels
        + BilingualPage.band_panels
        + [
            FieldPanel("body"),
            FieldPanel("mobile_action_en"),
            FieldPanel("mobile_action_ar"),
        ]
    )
    search_fields = Page.search_fields + [index.SearchField("title_ar")]
    template = "website/pages/content_page.html"

    def serve(self, request, *args, **kwargs):
        from .forms import handle_page_form

        if request.method == "POST":
            response = handle_page_form(self, request)
            if response is not None:
                return response
        return super().serve(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Branches and programs
# ---------------------------------------------------------------------------
class BranchPage(BilingualPage):
    branch = models.OneToOneField("organization.Branch", on_delete=models.PROTECT, related_name="web_page")
    promise_en = models.CharField(max_length=120)
    promise_ar = models.CharField(max_length=120, blank=True)
    ticks_en = models.TextField(help_text="Up to 4 lines, one per line.")
    ticks_ar = models.TextField(blank=True)
    price_lines = models.TextField(
        help_text="One per line: amount|English note|Arabic note, e.g. 85|/ month, all disciplines|/ شهرياً، كل الرياضات"
    )
    open_days_en = models.CharField(max_length=120)
    open_days_ar = models.CharField(max_length=120, blank=True)
    closed_weekdays = models.CharField(
        max_length=20,
        default="6",
        help_text="Closed days, Kuwait week numbers (0 = Saturday … 6 = Friday), comma separated.",
    )
    address_en = models.CharField(max_length=200, blank=True)
    address_ar = models.CharField(max_length=200, blank=True)
    directions_en = models.TextField(blank=True, help_text="Parking and mall directions.")
    directions_ar = models.TextField(blank=True)
    map_url = models.URLField(blank=True, help_text="Google Maps link for 'Get directions'.")
    whatsapp = models.CharField(max_length=16, blank=True, validators=[validate_kuwait_mobile])
    card_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    card_image_caption = models.CharField(max_length=160, blank=True)
    body = StreamField(BODY_BLOCKS, blank=True, use_json_field=True)

    parent_page_types = ["website.ContentPage", "website.HomePage"]
    content_panels = (
        BilingualPage.content_panels
        + BilingualPage.band_panels
        + [
            MultiFieldPanel(
                [
                    FieldPanel("branch"),
                    FieldPanel("promise_en"),
                    FieldPanel("promise_ar"),
                    FieldPanel("ticks_en"),
                    FieldPanel("ticks_ar"),
                    FieldPanel("price_lines"),
                    FieldPanel("open_days_en"),
                    FieldPanel("open_days_ar"),
                    FieldPanel("closed_weekdays"),
                    FieldPanel("card_image"),
                    FieldPanel("card_image_caption"),
                ],
                heading="Branch card",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("address_en"),
                    FieldPanel("address_ar"),
                    FieldPanel("directions_en"),
                    FieldPanel("directions_ar"),
                    FieldPanel("map_url"),
                    FieldPanel("whatsapp"),
                ],
                heading="Location",
            ),
            FieldPanel("body"),
        ]
    )
    template = "website/pages/branch_page.html"

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        ctx["branch_programs"] = (
            ProgramPage.objects.live().public().filter(branch=self.branch_id).select_related("branch").order_by("path")
        )
        return ctx

    @property
    def key(self):
        return "promenade" if self.branch.code == "PRM" else "bedaya"

    @property
    def prices(self):
        rows = []
        for line in self.price_lines.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if parts and parts[0]:
                rows.append(
                    {
                        "amount": parts[0],
                        "note_en": parts[1] if len(parts) > 1 else "",
                        "note_ar": parts[2] if len(parts) > 2 else "",
                    }
                )
        return rows

    @property
    def closed_days(self):
        return {int(d) for d in self.closed_weekdays.split(",") if d.strip().isdigit()}


class ProgramPage(BilingualPage):
    AGE_GROUPS = [("kids", "Kids"), ("teens", "Teens"), ("adults", "Adults"), ("ladies", "Ladies")]

    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="web_programs")
    ages_en = models.CharField(max_length=80)
    ages_ar = models.CharField(max_length=80, blank=True)
    days_en = models.CharField(max_length=80)
    days_ar = models.CharField(max_length=80, blank=True)
    age_groups = models.CharField(
        max_length=40, help_text="Filter groups, comma separated: kids, teens, adults, ladies"
    )
    price = models.DecimalField(max_digits=8, decimal_places=3, validators=[MinValueValidator(0)])
    price_note_en = models.CharField(max_length=80, blank=True, help_text="e.g. all disciplines")
    price_note_ar = models.CharField(max_length=80, blank=True)
    belt_path = models.CharField(
        max_length=160,
        default=",".join(["white", "yellow", "purple", "blue", "green", "brown", "brownblack", "black"]),
        blank=True,
        help_text="Belt keys in order, comma separated. Leave empty until the discipline's "
        "belt order is confirmed (only Kajukenbo is confirmed so far).",
    )
    belt_path_confirmed = models.BooleanField(default=False)
    badge_en = models.CharField(max_length=40, blank=True, help_text="e.g. Rare in Kuwait")
    badge_ar = models.CharField(max_length=40, blank=True)
    card_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    body = StreamField(BODY_BLOCKS, blank=True, use_json_field=True)

    parent_page_types = ["website.ContentPage", "website.BranchPage"]
    content_panels = (
        BilingualPage.content_panels
        + BilingualPage.band_panels
        + [
            MultiFieldPanel(
                [
                    FieldPanel("branch"),
                    FieldPanel("ages_en"),
                    FieldPanel("ages_ar"),
                    FieldPanel("days_en"),
                    FieldPanel("days_ar"),
                    FieldPanel("age_groups"),
                    FieldPanel("price"),
                    FieldPanel("price_note_en"),
                    FieldPanel("price_note_ar"),
                    FieldPanel("belt_path"),
                    FieldPanel("belt_path_confirmed"),
                    FieldPanel("badge_en"),
                    FieldPanel("badge_ar"),
                    FieldPanel("card_image"),
                ],
                heading="Program card",
            ),
            FieldPanel("body"),
        ]
    )
    template = "website/pages/program_page.html"

    @property
    def key(self):
        return "promenade" if self.branch.code == "PRM" else "bedaya"

    @property
    def belts(self):
        return parse_path(self.belt_path)

    @property
    def groups(self):
        return [g.strip() for g in self.age_groups.split(",") if g.strip()]


# ---------------------------------------------------------------------------
# Instructors
# ---------------------------------------------------------------------------
class InstructorPage(BilingualPage):
    staff = models.OneToOneField(
        "staff.StaffProfile", null=True, blank=True, on_delete=models.SET_NULL, related_name="web_profile"
    )
    photo = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Portrait 4:5, in a gi, on the mat. No fighting poses.",
    )
    discipline_en = models.CharField(max_length=60)
    discipline_ar = models.CharField(max_length=60, blank=True)
    role_en = models.CharField(max_length=80, blank=True, help_text="e.g. Head instructor")
    role_ar = models.CharField(max_length=80, blank=True)
    rank_en = models.CharField(max_length=80, blank=True)
    rank_ar = models.CharField(max_length=80, blank=True)
    belt = models.CharField(default="black", **BELT_FIELD)
    years_training = models.PositiveSmallIntegerField(null=True, blank=True)
    competitions = models.PositiveSmallIntegerField(null=True, blank=True)
    years_coaching = models.PositiveSmallIntegerField(null=True, blank=True)
    branch = models.ForeignKey(
        "organization.Branch", null=True, blank=True, on_delete=models.SET_NULL, related_name="web_instructors"
    )
    statement_en = models.TextField(blank=True, help_text="In the instructor's own words.")
    statement_ar = models.TextField(blank=True)
    timeline = models.TextField(blank=True, help_text="One per line, newest first: year|English|Arabic")

    parent_page_types = ["website.ContentPage"]
    content_panels = BilingualPage.content_panels + [
        FieldPanel("staff"),
        FieldPanel("photo"),
        FieldPanel("discipline_en"),
        FieldPanel("discipline_ar"),
        FieldPanel("role_en"),
        FieldPanel("role_ar"),
        FieldPanel("rank_en"),
        FieldPanel("rank_ar"),
        FieldPanel("belt"),
        FieldPanel("years_training"),
        FieldPanel("competitions"),
        FieldPanel("years_coaching"),
        FieldPanel("branch"),
        FieldPanel("statement_en"),
        FieldPanel("statement_ar"),
        FieldPanel("timeline"),
    ]
    template = "website/pages/instructor_page.html"

    @property
    def key(self):
        if not self.branch_id:
            return ""
        return "promenade" if self.branch.code == "PRM" else "bedaya"

    @property
    def timeline_rows(self):
        rows = []
        for line in self.timeline.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if parts and parts[0]:
                rows.append(
                    {
                        "year": parts[0],
                        "text_en": parts[1] if len(parts) > 1 else "",
                        "text_ar": parts[2] if len(parts) > 2 else "",
                    }
                )
        return rows


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
class EventIndexPage(BilingualPage):
    subpage_types = ["website.EventPage"]
    parent_page_types = ["website.HomePage"]
    content_panels = BilingualPage.content_panels + BilingualPage.band_panels
    template = "website/pages/event_index_page.html"

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        events = EventPage.objects.child_of(self).live().public().select_related("branch")
        kind = request.GET.get("type", "")
        if kind in dict(EventPage.TYPES):
            events = events.filter(event_type=kind)
        today = timezone.localdate()
        ctx["event_type"] = kind
        ctx["upcoming"] = list(events.filter(date__gte=today).order_by("date", "start_time"))
        ctx["past"] = list(events.filter(date__lt=today).order_by("-date")[:6])
        ctx["types"] = EventPage.TYPES
        return ctx


class EventPage(RoutablePageMixin, BilingualPage):
    TYPES = [
        ("belt_test", "Belt test"),
        ("seminar", "Seminar"),
        ("camp", "Camp"),
        ("tournament", "Tournament"),
        ("showcase", "Showcase"),
    ]
    TYPE_AR = {
        "belt_test": "اختبار أحزمة",
        "seminar": "ندوة",
        "camp": "معسكر",
        "tournament": "بطولة",
        "showcase": "عرض",
    }
    TYPE_TONE = {"belt_test": "blue", "camp": "orange"}

    event_type = models.CharField(max_length=12, choices=TYPES)
    date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="web_events")
    image = models.ForeignKey("wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    summary_en = models.CharField(max_length=200, blank=True)
    summary_ar = models.CharField(max_length=200, blank=True)
    description_en = RichTextField(blank=True, features=RICH_FEATURES)
    description_ar = RichTextField(blank=True, features=RICH_FEATURES)
    details = models.TextField(
        blank=True,
        help_text="Key facts, one per line: English label|English text|Arabic "
        "label|Arabic text (e.g. What to bring|Sportswear, water|…)",
    )
    programme = models.TextField(
        "Day by day", blank=True, help_text="One per line: English|Arabic|time (e.g. Day 1 · Welcome and team games|…)"
    )
    accepts_registrations = models.BooleanField(default=False, help_text="Show the 'Reserve a place' form.")
    who_en = models.CharField("Who it's for (English)", max_length=120, blank=True)
    who_ar = models.CharField("Who it's for (Arabic)", max_length=120, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    is_full = models.BooleanField("Fully booked", default=False)
    registration_url = models.URLField(blank=True, help_text="Leave empty to register through the front desk.")

    parent_page_types = ["website.EventIndexPage"]
    content_panels = BilingualPage.content_panels + [
        FieldPanel("event_type"),
        FieldPanel("date"),
        FieldPanel("end_date"),
        FieldPanel("start_time"),
        FieldPanel("end_time"),
        FieldPanel("branch"),
        FieldPanel("image"),
        FieldPanel("summary_en"),
        FieldPanel("summary_ar"),
        FieldPanel("description_en"),
        FieldPanel("description_ar"),
        FieldPanel("who_en"),
        FieldPanel("who_ar"),
        FieldPanel("details"),
        FieldPanel("programme"),
        FieldPanel("price"),
        FieldPanel("capacity"),
        FieldPanel("is_full"),
        FieldPanel("accepts_registrations"),
        FieldPanel("registration_url"),
    ]
    template = "website/pages/event_page.html"

    @path("")
    def detail(self, request):
        from .forms import handle_event_registration

        if request.method == "POST":
            response = handle_event_registration(self, request)
            if response is not None:
                return response
        return self.render(request)

    @path("calendar.ics")
    def calendar(self, request):
        """'Add to calendar': a one-event iCalendar file."""
        from django.http import HttpResponse

        start = self.date.strftime("%Y%m%d")
        end = (self.end_date or self.date) + datetime.timedelta(days=1)
        text = "\r\n".join(
            [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Elite Academy//Website//EN",
                "BEGIN:VEVENT",
                f"UID:event-{self.pk}@elitemaacademy.com",
                f"DTSTAMP:{timezone.now():%Y%m%dT%H%M%SZ}",
                f"DTSTART;VALUE=DATE:{start}",
                f"DTEND;VALUE=DATE:{end:%Y%m%d}",
                f"SUMMARY:{self.title}",
                f"LOCATION:{self.branch.name}",
                f"URL:{self.get_full_url(request)}",
                "END:VEVENT",
                "END:VCALENDAR",
                "",
            ]
        )
        response = HttpResponse(text, content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="elite-event-{self.pk}.ics"'
        return response

    @property
    def detail_rows(self):
        rows = []
        for line in self.details.splitlines():
            parts = [p.strip() for p in line.split("|")] + ["", "", ""]
            if parts[0]:
                rows.append({"label_en": parts[0], "text_en": parts[1], "label_ar": parts[2], "text_ar": parts[3]})
        return rows

    @property
    def programme_rows(self):
        rows = []
        for line in self.programme.splitlines():
            parts = [p.strip() for p in line.split("|")] + ["", ""]
            if parts[0]:
                rows.append({"text_en": parts[0], "text_ar": parts[1], "time": parts[2]})
        return rows

    @property
    def places_left(self):
        if self.capacity is None:
            return None
        return max(self.capacity - self.registrations.count(), 0)

    @property
    def key(self):
        return "promenade" if self.branch.code == "PRM" else "bedaya"

    @property
    def is_past(self):
        return (self.end_date or self.date) < timezone.localdate()

    @property
    def type_ar(self):
        return self.TYPE_AR.get(self.event_type, "")

    @property
    def tone(self):
        return self.TYPE_TONE.get(self.event_type, "")


class EventRegistration(models.Model):
    """'Reserve a place' on an event page. Staff confirm and take payment at the branch or by KNET."""

    event = models.ForeignKey(EventPage, on_delete=models.CASCADE, related_name="registrations")
    child_first_name = models.CharField(max_length=60)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    mobile = models.CharField(max_length=16)
    language = models.CharField(max_length=2, default="en")
    confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.child_first_name} · {self.event.title}"

    @property
    def branch_id(self):
        return self.event.branch_id


# ---------------------------------------------------------------------------
# Gallery (with the consent check — EA-SYS-SCOPE-01 M14, rule 17)
# ---------------------------------------------------------------------------
class GalleryIndexPage(BilingualPage):
    subpage_types = ["website.AlbumPage"]
    parent_page_types = ["website.HomePage"]
    content_panels = BilingualPage.content_panels + BilingualPage.band_panels
    template = "website/pages/gallery_index_page.html"

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        ctx["albums"] = AlbumPage.objects.child_of(self).live().public().order_by("-date")
        return ctx


class AlbumPage(BilingualPage):
    date = models.DateField()
    branch = models.ForeignKey(
        "organization.Branch", null=True, blank=True, on_delete=models.SET_NULL, related_name="web_albums"
    )
    cover = models.ForeignKey("wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    parent_page_types = ["website.GalleryIndexPage"]
    content_panels = BilingualPage.content_panels + [
        FieldPanel("date"),
        FieldPanel("branch"),
        FieldPanel("cover"),
        InlinePanel(
            "photos",
            label="Photos",
            help_text="Tag every member who can be identified. A photo appears on the website only when "
            "it is reviewed and every tagged member's consent covers website use.",
        ),
    ]
    template = "website/pages/album_page.html"

    @property
    def key(self):
        if not self.branch_id:
            return ""
        return "promenade" if self.branch.code == "PRM" else "bedaya"

    def public_photos(self):
        photos = self.photos.select_related("image").prefetch_related("tagged_members__media_consents")
        return [p for p in photos if p.is_public]

    @property
    def public_photo_count(self):
        return len(self.public_photos())

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        ctx["photos"] = self.public_photos()
        return ctx


class AlbumPhoto(Orderable):
    album = ParentalKey(AlbumPage, on_delete=models.CASCADE, related_name="photos")
    image = models.ForeignKey("wagtailimages.Image", on_delete=models.CASCADE, related_name="+")
    caption_en = models.CharField(max_length=200, blank=True)
    caption_ar = models.CharField(max_length=200, blank=True)
    tagged_members = ParentalManyToManyField("members.Member", blank=True, related_name="album_photos")
    reviewed = models.BooleanField(
        default=False,
        help_text="I checked this photo: every identifiable member is tagged (or nobody is identifiable).",
    )

    panels = [
        FieldPanel("image"),
        FieldPanel("caption_en"),
        FieldPanel("caption_ar"),
        FieldPanel("tagged_members"),
        FieldPanel("reviewed"),
    ]

    @property
    def is_public(self):
        """Public only when reviewed and every tagged member's latest consent allows website use."""
        if not self.reviewed:
            return False
        for member in self.tagged_members.all():
            consents = list(member.media_consents.all())  # newest first; uses the prefetch when present
            latest = consents[0] if consents else None
            if latest is None or not latest.website_marketing:
                return False
        return True


# ---------------------------------------------------------------------------
# Timetable (read by the Schedule block; the full class module comes in Phase 1)
# ---------------------------------------------------------------------------
@register_snippet
class TimetableEntry(models.Model):
    WEEKDAYS = [
        (0, "Saturday"),
        (1, "Sunday"),
        (2, "Monday"),
        (3, "Tuesday"),
        (4, "Wednesday"),
        (5, "Thursday"),
        (6, "Friday"),
    ]
    AGE_GROUPS = ProgramPage.AGE_GROUPS

    branch = models.ForeignKey("organization.Branch", on_delete=models.CASCADE, related_name="timetable")
    program = models.ForeignKey(ProgramPage, null=True, blank=True, on_delete=models.SET_NULL, related_name="timetable")
    title_en = models.CharField(max_length=80)
    title_ar = models.CharField(max_length=80, blank=True)
    ages_en = models.CharField(max_length=60)
    ages_ar = models.CharField(max_length=60, blank=True)
    age_group = models.CharField(max_length=8, choices=AGE_GROUPS)
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    start = models.TimeField()
    end = models.TimeField()
    is_sample = models.BooleanField(default=True, help_text="Untick once the time is confirmed.")
    is_active = models.BooleanField(default=True)

    panels = [
        FieldPanel("branch"),
        FieldPanel("program"),
        FieldPanel("title_en"),
        FieldPanel("title_ar"),
        FieldPanel("ages_en"),
        FieldPanel("ages_ar"),
        FieldPanel("age_group"),
        FieldPanel("weekday"),
        FieldPanel("start"),
        FieldPanel("end"),
        FieldPanel("is_sample"),
        FieldPanel("is_active"),
    ]

    class Meta:
        ordering = ["weekday", "start"]
        verbose_name_plural = "timetable entries"

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start:%H:%M} · {self.title_en} ({self.branch.code})"

    @property
    def key(self):
        return "promenade" if self.branch.code == "PRM" else "bedaya"

    @property
    def discipline_en(self):
        return self.title_en.split("·")[0].strip()

    @property
    def discipline_ar(self):
        return (self.title_ar or self.title_en).split("·")[0].strip()

    @property
    def discipline_key(self):
        return self.discipline_en.lower().replace(" ", "-").replace("'", "")


# ---------------------------------------------------------------------------
# Site-wide settings
# ---------------------------------------------------------------------------
@register_setting(icon="cog")
class SiteSettings(BaseGenericSetting):
    whatsapp_number = models.CharField(max_length=16, blank=True, validators=[validate_kuwait_mobile])
    instagram_url = models.URLField(blank=True)
    trial_price = models.DecimalField(max_digits=6, decimal_places=3, default=10)
    tagline_en = models.CharField(max_length=120, default="People · Progress · A Stronger You")
    tagline_ar = models.CharField(max_length=120, blank=True, default="ناس · تقدّم · نسخة أقوى منك")
    promo_bar_en = models.CharField(max_length=120, blank=True, help_text="Thin bar above the header (optional).")
    promo_bar_ar = models.CharField(max_length=120, blank=True)
    promo_bar_until = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Site settings"

    @property
    def whatsapp_link(self):
        digits = "".join(ch for ch in self.whatsapp_number if ch.isdigit())
        return f"https://wa.me/{digits}" if digits else ""

    @property
    def show_promo_bar(self):
        return bool(self.promo_bar_en) and (
            self.promo_bar_until is None or self.promo_bar_until >= timezone.localdate()
        )


# ---------------------------------------------------------------------------
# Enquiries captured by the website (become leads in Phase 5, M3)
# ---------------------------------------------------------------------------
class TrialRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        BOOKED = "booked", "Trial booked"
        CLOSED = "closed", "Closed"

    name = models.CharField(max_length=120)
    mobile = models.CharField(max_length=16)
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="trial_requests")
    program = models.ForeignKey(
        ProgramPage, null=True, blank=True, on_delete=models.SET_NULL, related_name="trial_requests"
    )
    not_sure = models.BooleanField(default=False, help_text="Asked for help choosing a program.")
    language = models.CharField(max_length=2, default="en")
    source = models.CharField(max_length=40, default="website", help_text="website, saqr, schedule, program …")
    source_path = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The first person to contact the lead owns it.",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.branch.code}, {self.created_at:%Y-%m-%d})"


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    mobile = models.CharField(max_length=16)
    branch = models.ForeignKey("organization.Branch", null=True, blank=True, on_delete=models.SET_NULL)
    message = models.TextField(max_length=2000)
    language = models.CharField(max_length=2, default="en")
    handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.created_at:%Y-%m-%d})"


# ---------------------------------------------------------------------------
# Member portal
# ---------------------------------------------------------------------------
class PortalPage(BilingualPage):
    max_count = 1
    parent_page_types = ["website.HomePage"]
    content_panels = BilingualPage.content_panels + BilingualPage.band_panels
    template = "website/pages/portal_page.html"

    def serve(self, request, *args, **kwargs):
        from .portal import serve_portal

        return serve_portal(self, request)


class PortalCode(models.Model):
    """A one-time sign-in code sent by WhatsApp. Stored only as a keyed hash."""

    mobile = models.CharField(max_length=16, db_index=True)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Code for …{self.mobile[-4:]} ({self.created_at:%Y-%m-%d %H:%M})"

    @staticmethod
    def hash_code(mobile: str, code: str) -> str:
        return hmac.new(settings.SECRET_KEY.encode(), f"{mobile}:{code}".encode(), hashlib.sha256).hexdigest()

    @classmethod
    def issue(cls, mobile: str) -> tuple["PortalCode", str]:
        code = f"{secrets.randbelow(10000):04d}"
        return cls.objects.create(mobile=mobile, code_hash=cls.hash_code(mobile, code)), code

    @property
    def expired(self):
        return (timezone.now() - self.created_at).total_seconds() > settings.PORTAL_OTP_TTL_SECONDS

    def matches(self, code: str) -> bool:
        return hmac.compare_digest(self.code_hash, self.hash_code(self.mobile, code))


class MemberProgress(models.Model):
    """Current belt and stripes shown in the portal. Replaced by the curriculum module (Phase 4, M7)."""

    member = models.OneToOneField("members.Member", on_delete=models.CASCADE, related_name="progress")
    belt = models.CharField(default="white", **BELT_FIELD)
    stripes = models.PositiveSmallIntegerField(default=0)
    stripes_needed = models.PositiveSmallIntegerField(default=4)
    next_class_en = models.CharField(max_length=80, blank=True)
    next_class_ar = models.CharField(max_length=80, blank=True)
    membership_until = models.DateField(null=True, blank=True)
    renew_price = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.member} · {self.belt}"

    @property
    def next_belt(self):
        keys = list(BELTS)
        path = ["white", "yellow", "purple", "blue", "green", "brown", "brownblack", "black"]
        if self.belt in path and self.belt != "black":
            return path[path.index(self.belt) + 1]
        return keys[-1]

    @property
    def expiring_soon(self):
        return bool(self.membership_until and (self.membership_until - timezone.localdate()).days <= 7)


# ---------------------------------------------------------------------------
# Shop (M19) — product list, product, cart, checkout, payment return
# ---------------------------------------------------------------------------
class ShopPage(RoutablePageMixin, BilingualPage):
    max_count = 1
    parent_page_types = ["website.HomePage"]
    content_panels = BilingualPage.content_panels + BilingualPage.band_panels
    template = "website/pages/shop_index.html"

    @path("")
    def index(self, request):
        from . import shop_views

        return shop_views.product_list(self, request)

    @path("cart/")
    def cart(self, request):
        from . import shop_views

        return shop_views.cart(self, request)

    @path("checkout/")
    def checkout(self, request):
        from . import shop_views

        return shop_views.checkout(self, request)

    @path("pay/return/<str:reference>/")
    def payment_return(self, request, reference):
        from . import shop_views

        return shop_views.payment_return(self, request, reference)

    @path("order/<str:reference>/")
    def order(self, request, reference):
        from . import shop_views

        return shop_views.order_done(self, request, reference)

    @path("<slug:slug>/")
    def product(self, request, slug):
        from . import shop_views

        return shop_views.product_detail(self, request, slug)
