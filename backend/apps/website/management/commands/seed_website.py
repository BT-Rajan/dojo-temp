"""
Builds the elitemaacademy.com page tree with the design's copy in English and Arabic.

    python manage.py seed_website            # create the site if it doesn't exist yet
    python manage.py seed_website --reset    # delete the website pages and build them again

Copy comes from the design system and the canvas "B · The Path: all pages". Arabic is a
draft until a native editor at the academy signs it off (handoff rule 10). Content the
academy still has to supply is NOT invented here:
- instructor profiles are created as unpublished drafts with [bracketed] fields;
- class times are marked "sample" and shop prices "sample price";
- parent quotes are left unapproved, so none is published.
Needs the branches from seed_kuwait (or real ones with codes PRM and BED).
"""

import datetime
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from wagtail.models import Collection, Locale, Page, Site

from apps.inventory.services import set_opening
from apps.members.models import Member
from apps.organization.models import Branch
from apps.shop.models import Product, ProductVariant, ShopSettings, SizeGuide, SizeGuideRow
from apps.website.cms_groups import ensure_cms_groups
from apps.website.models import (
    AlbumPage,
    BranchPage,
    ContentPage,
    EventIndexPage,
    EventPage,
    GalleryIndexPage,
    HomePage,
    InstructorPage,
    MemberProgress,
    PortalPage,
    ProgramPage,
    ShopPage,
    SiteSettings,
)

KAJUKENBO = "white,yellow,purple,blue,green,brown,brownblack,black"

PRINCIPLES = [
    (
        "Safety First",
        "السلامة أولاً",
        "If it's not safe, we don't do it. Safe training, safe places, safe treatment of children.",
        "إن لم يكن آمناً، لا نفعله. تدريب آمن، أماكن آمنة، ومعاملة آمنة للأطفال.",
    ),
    ("Discipline", "الانضباط", "Show up. Repeat. Improve.", "احضر. كرّر. تحسّن."),
    (
        "Accountability",
        "المسؤولية",
        "Own your choices. Get back up. Learn from mistakes.",
        "تحمّل مسؤولية اختياراتك. انهض من جديد. تعلّم من أخطائك.",
    ),
    (
        "Tough Love",
        "الحزم بمحبة",
        "Be the example. Hold the standard. Firm, fair and caring.",
        "كن القدوة. حافظ على المعيار. حازم، عادل، ومهتم.",
    ),
    ("Team First", "الفريق أولاً", "Respect the individual. Protect the group.", "احترم الفرد. احمِ المجموعة."),
]

FAQ_GENERAL = [
    (
        "My child has never trained. Is that okay?",
        "طفلي لم يتدرّب من قبل. هل هذا مناسب؟",
        "Yes. Most of our students started as complete beginners. In the trial class our instructor will assess your "
        "child's level and suggest the right group.",
        "نعم. معظم طلابنا بدأوا من الصفر. في الحصة التجريبية سيقيّم المدرّب مستوى طفلك ويقترح المجموعة المناسبة.",
    ),
    (
        "How do you keep children safe?",
        "كيف تحافظون على سلامة الأطفال؟",
        "Safety First is our first principle: supervised classes, age-matched partners, protective gear for sparring, "
        "and clear rules for how every adult treats children.",
        "السلامة أولاً هي أول مبادئنا: حصص تحت إشراف، شركاء تدريب من نفس العمر، معدات حماية للنزال، وقواعد واضحة "
        "لتعامل الكبار مع الأطفال.",
    ),
    (
        "Is there a class just for women and girls?",
        "هل يوجد صف خاص للسيدات والبنات؟",
        "Yes, at Elite Bedaya in Sabah Al Salem: a dedicated ladies' class for girls 6+ and adult women.",
        "نعم، في إيليت بداية بصباح السالم: صف مخصص للبنات من 6 سنوات والسيدات.",
    ),
    (
        "What should we bring to the trial?",
        "ماذا نحضر للحصة التجريبية؟",
        "Comfortable sportswear and a water bottle. No gear needed for the first class.",
        "ملابس رياضية مريحة وقارورة ماء. لا حاجة لأي معدات في الحصة الأولى.",
    ),
]

# branch, slug, en, ar, ages_en, ages_ar, days_en, days_ar, groups, price, note_en, note_ar, belts, confirmed,
# badge_en, badge_ar, lead_en, lead_ar
PROGRAMS = [
    (
        "PRM",
        "kajukenbo",
        "Kajukenbo",
        "كاجوكينبو",
        "Ages 5–12",
        "من 5 إلى 12 سنة",
        "Sat · Sun · Mon · Tue · Wed",
        "السبت إلى الأربعاء",
        "kids",
        "85",
        "all disciplines",
        "كل الرياضات",
        KAJUKENBO,
        True,
        "",
        "",
        "A complete self-defence art built from karate, judo, jiu-jitsu, kenpo and boxing. Children learn to stay calm, "
        "protect themselves and respect others.",
        "فن دفاع عن النفس متكامل يجمع الكاراتيه والجودو والجوجيتسو والكينبو والملاكمة. يتعلم الأطفال الهدوء وحماية "
        "أنفسهم واحترام الآخرين.",
    ),
    (
        "PRM",
        "kickboxing",
        "Kickboxing",
        "كيك بوكسينغ",
        "Ages 5–12",
        "من 5 إلى 12 سنة",
        "Sun · Tue",
        "الأحد · الثلاثاء",
        "kids",
        "85",
        "all disciplines",
        "كل الرياضات",
        "",
        False,
        "",
        "",
        "Footwork, pad work and conditioning with protective gear. Fitness and focus in every round.",
        "حركة القدمين والعمل على الوسائد واللياقة مع معدات الحماية. لياقة وتركيز في كل جولة.",
    ),
    (
        "PRM",
        "jiu-jitsu",
        "Jiu-Jitsu",
        "جوجيتسو",
        "Ages 13+",
        "13 سنة فما فوق",
        "Sat · Mon · Wed",
        "السبت · الاثنين · الأربعاء",
        "teens,adults",
        "85",
        "all disciplines",
        "كل الرياضات",
        "white,blue,purple,brown,black",
        False,
        "",
        "",
        "Ground technique, leverage and control. Part of the kids program, and the main path from 13.",
        "تقنيات أرضية ورافعة وسيطرة. جزء من برنامج الأطفال، والمسار الرئيسي من عمر 13.",
    ),
    (
        "BED",
        "taekwondo",
        "Taekwondo",
        "تايكوندو",
        "Boys 6–13 · Adults",
        "أولاد 6–13 · كبار",
        "Sat · Mon · Wed",
        "السبت · الاثنين · الأربعاء",
        "kids,teens,adults",
        "65",
        "kids · 55.000 KD adults",
        "أطفال · 55.000 د.ك للكبار",
        "white,yellow,green,blue,red,black",
        False,
        "",
        "",
        "Kicks, forms and focus. Boys 6–13 and adults train on Saturday, Monday and Wednesday.",
        "ركلات وأنماط وتركيز. الأولاد من 6 إلى 13 سنة والكبار يتدربون السبت والاثنين والأربعاء.",
    ),
    (
        "BED",
        "kyokushin-karate",
        "Kyokushin Karate",
        "كيوكوشن كاراتيه",
        "Boys 6–13 · Adults",
        "أولاد 6–13 · كبار",
        "Sat · Mon · Wed",
        "السبت · الاثنين · الأربعاء",
        "kids,teens,adults",
        "65",
        "kids · 55.000 KD adults",
        "أطفال · 55.000 د.ك للكبار",
        "",
        False,
        "",
        "",
        "Full-contact karate that builds strength, spirit and respect.",
        "كاراتيه بالاحتكاك الكامل يبني القوة والروح والاحترام.",
    ),
    (
        "BED",
        "kajukenbo-bedaya",
        "Kajukenbo",
        "كاجوكينبو",
        "Boys 6–13 · Adults",
        "أولاد 6–13 · كبار",
        "Sun · Tue · Thu",
        "الأحد · الثلاثاء · الخميس",
        "kids,teens,adults",
        "65",
        "kids · 55.000 KD adults",
        "أطفال · 55.000 د.ك للكبار",
        KAJUKENBO,
        True,
        "",
        "",
        "Practical self-defence and fitness, Sunday, Tuesday and Thursday.",
        "دفاع عن النفس ولياقة، الأحد والثلاثاء والخميس.",
    ),
    (
        "BED",
        "ladies-class",
        "Ladies' class",
        "صف السيدات",
        "Girls 6+ · Women",
        "بنات 6+ · سيدات",
        "Sun · Tue · Thu",
        "الأحد · الثلاثاء · الخميس",
        "ladies",
        "55",
        "adults · 65.000 KD girls",
        "سيدات · 65.000 د.ك للبنات",
        "white,yellow,orange,green,blue,brown,black",
        False,
        "Rare in Kuwait",
        "نادر في الكويت",
        "A comfortable, respectful class for girls from 6 and adult women, at Elite Bedaya.",
        "صف مريح ومحترم للبنات من 6 سنوات والسيدات، في إيليت بداية.",
    ),
]

# Program page -> timetable programs (from seed_kuwait) and the class titles it covers.
PAGE_PROGRAMS = {
    "kajukenbo": (["Elite Program 5-7", "Elite Program 8-12"], "Kajukenbo"),
    "kickboxing": (["Elite Program 5-7", "Elite Program 8-12"], "Kickboxing"),
    "jiu-jitsu": (["Elite Program 5-7", "Elite Program 8-12", "Jiu-Jitsu 13+"], "Jiu-Jitsu"),
    "taekwondo": (["Taekwondo Boys"], ""),
    "kyokushin-karate": (["Kyokushin Karate", "Shin-Kyokushin Junior"], ""),
    "kajukenbo-bedaya": (["Kajukenbo"], ""),
    "ladies-class": (["Ladies' Class"], ""),
}

# slug, en, ar, sizes [(size, stock)], price, category
PRODUCTS = [
    (
        "boxing-gloves",
        "Boxing gloves",
        "قفازات ملاكمة",
        "gloves",
        "18.500",
        [("8 oz", 0), ("10 oz", 6), ("12 oz", 8), ("14 oz", 4), ("16 oz", 3)],
    ),
    (
        "training-uniform",
        "Training uniform (gi)",
        "زي التدريب",
        "uniforms",
        "22.000",
        [("120 cm", 0), ("130 cm", 5), ("140 cm", 7), ("150 cm", 5), ("160 cm", 4), ("170 cm", 2)],
    ),
    (
        "shin-guards",
        "Shin guards",
        "واقي الساق",
        "shin_guards",
        "12.750",
        [("XS", 4), ("S", 6), ("M", 6), ("L", 3), ("XL", 0)],
    ),
    (
        "head-guard",
        "Head guard",
        "واقي الرأس",
        "head_guards",
        "15.000",
        [("XS", 3), ("S", 5), ("M", 5), ("L", 3), ("XL", 2)],
    ),
    (
        "rash-guard",
        "Rash guard",
        "راش جارد",
        "rash_guards",
        "14.250",
        [("XS", 5), ("S", 6), ("M", 6), ("L", 4), ("XL", 2)],
    ),
    (
        "elite-t-shirt",
        "Elite T-shirt",
        "تيشيرت إيليت",
        "tshirts",
        "7.500",
        [("XS", 10), ("S", 12), ("M", 12), ("L", 8), ("XL", 6)],
    ),
]


def bi(en, ar):
    return {"en": en, "ar": ar}


def heading(eyebrow_en, eyebrow_ar, title_en, title_ar, lead_en="", lead_ar=""):
    return (
        "heading",
        {
            "eyebrow_en": eyebrow_en,
            "eyebrow_ar": eyebrow_ar,
            "title_en": title_en,
            "title_ar": title_ar,
            "lead_en": lead_en,
            "lead_ar": lead_ar,
        },
    )


def text(en, ar):
    return ("text", {"text_en": f"<p>{en}</p>", "text_ar": f"<p>{ar}</p>"})


def cta(headline_en, headline_ar, line_en, line_ar, button_en="", button_ar=""):
    return (
        "cta",
        {
            "headline_en": headline_en,
            "headline_ar": headline_ar,
            "line_en": line_en,
            "line_ar": line_ar,
            "button_en": button_en,
            "button_ar": button_ar,
            "button_page": None,
            "show_whatsapp": True,
        },
    )


def faq(title_en, title_ar, items):
    return (
        "faq",
        {
            "title_en": title_en,
            "title_ar": title_ar,
            "first_open": True,
            "items": [{"question_en": q, "question_ar": qa, "answer_en": a, "answer_ar": aa} for q, qa, a, aa in items],
        },
    )


def principles(style="light", title_en="We build better humans.", title_ar="نبني إنساناً أفضل."):
    return (
        "principles",
        {
            "eyebrow_en": "Our five principles",
            "eyebrow_ar": "مبادئنا الخمسة",
            "title_en": title_en,
            "title_ar": title_ar,
            "lead_en": "Character, discipline and responsibility for ourselves and others.",
            "lead_ar": "الشخصية والانضباط والمسؤولية تجاه أنفسنا والآخرين.",
            "illustration": None,
            "style": style,
            "principles": [
                {"title_en": t, "title_ar": ta, "line_en": line, "line_ar": la} for t, ta, line, la in PRINCIPLES
            ],
        },
    )


class Command(BaseCommand):
    help = "Create the website pages (EN/AR) from the design, with sample timetable and shop data."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete the website pages first.")

    def handle(self, *args, **opts):
        if getattr(settings, "ENVIRONMENT", "") == "production" and opts["reset"]:
            raise CommandError("Refusing to reset the live website.")
        self.branches = {b.code: b for b in Branch.objects.filter(code__in=["PRM", "BED"])}
        if len(self.branches) < 2:
            raise CommandError("Branches PRM and BED are needed. Run `python manage.py seed_kuwait` first.")
        with transaction.atomic():
            if opts["reset"]:
                self._reset()
            elif HomePage.objects.exists():
                self.stdout.write("The website already exists. Use --reset to rebuild it.")
                return
            self._settings()
            self._build()
            self._shop()
            self._progress()
            ensure_cms_groups()
        self.stdout.write(self.style.SUCCESS("Website ready: /en/ and /ar/ (CMS at /cms/)."))

    # ------------------------------------------------------------------
    def _reset(self):
        for home in HomePage.objects.all():
            home.delete()  # removes every page under it too
        ProductVariant.objects.all().delete()
        Product.objects.all().delete()
        SizeGuide.objects.all().delete()

    def _settings(self):
        s = SiteSettings.load()
        s.whatsapp_number = "+96550000001"  # fictional test number (Kuwait mobile format)
        s.instagram_url = "https://www.instagram.com/"
        s.trial_price = Decimal("10.000")
        s.save()
        shop = ShopSettings.load()
        shop.delivery_fee = Decimal("2.000")
        shop.save()

    def add(self, parent, page):
        parent.add_child(instance=page)
        return page

    # ------------------------------------------------------------------
    def _build(self):
        Locale.objects.get_or_create(language_code=settings.LANGUAGE_CODE)
        root = Page.get_first_root_node()
        if root is None:  # a flushed database (e.g. after transactional tests) has no tree root
            root = Page.add_root(instance=Page(title="Root", slug="root", live=True))
        if Collection.get_first_root_node() is None:
            Collection.add_root(name="Root")
        # Wagtail installs a "Welcome" page; the academy's home page replaces it.
        for page in root.get_children().exclude(content_type__model="homepage"):
            if page.slug == "home":
                page.slug = f"old-home-{page.pk}"
                page.save()
        home = HomePage(
            title="Home",
            title_ar="الرئيسية",
            slug="home",
            seo_title="Elite Academy · Kuwait",
            search_description="Martial arts for children, teens, adults and ladies in Hawalli and Sabah "
            "Al Salem. Book a trial class for 10.000 KD.",
            search_description_ar="فنون قتالية للأطفال والناشئين والكبار والسيدات في حولي وصباح السالم. "
            "احجز حصة تجريبية بـ 10.000 د.ك.",
            hero_lead_en="A multi-year path that builds discipline, confidence and character, for "
            "children, teens, adults and ladies. It starts with one trial class.",
            hero_lead_ar="مسار يمتد لسنوات يبني الانضباط والثقة والشخصية، للأطفال والناشئين والكبار "
            "والسيدات. ويبدأ بحصة تجريبية واحدة.",
            hero_image_caption="Photo: belt ceremony, a child receiving a new belt",
        )
        root.add_child(instance=home)
        site = Site.objects.filter(is_default_site=True).first() or Site(
            hostname="localhost", port=80, is_default_site=True
        )
        old_root = site.root_page_id
        site.root_page = home
        site.site_name = "Elite Academy"
        site.save()
        if old_root and old_root != home.pk:
            Page.objects.filter(pk=old_root).exclude(pk=home.pk).delete()

        prm, bed = self.branches["PRM"], self.branches["BED"]

        # --- Programs (index) -------------------------------------------------
        programs = self.add(
            home,
            ContentPage(
                title="Programs",
                title_ar="البرامج",
                slug="programs",
                show_in_menus=True,
                band_belt="purple",
                band_eyebrow_en="Programs",
                band_eyebrow_ar="البرامج",
                band_lead_en="Martial arts for children, teens, adults and ladies at two branches. Every program is a path "
                "your child can follow for years.",
                band_lead_ar="فنون قتالية للأطفال والناشئين والكبار والسيدات في فرعين. كل برنامج مسار يمكن لطفلك أن "
                "يتبعه لسنوات.",
                band_cta=True,
                body=[
                    (
                        "programs",
                        {
                            "eyebrow_en": "",
                            "eyebrow_ar": "",
                            "title_en": "A path for every age",
                            "title_ar": "مسار لكل عمر",
                            "programs": [],
                            "show_filters": True,
                            "compact": False,
                        },
                    ),
                    (
                        "belt_progression",
                        {
                            "eyebrow_en": "Visible progress",
                            "eyebrow_ar": "تقدّم تراه",
                            "title_en": "The Kajukenbo path",
                            "title_ar": "مسار الكاجوكينبو",
                            "lead_en": "Every belt is earned on the mat and tested in front of the class. "
                            "Stripes mark the steps in between.",
                            "lead_ar": "كل حزام يُكتسب على البساط ويُختبر أمام الفريق. والأشرطة تحدد الخطوات بينها.",
                            "belts": [],
                        },
                    ),
                    cta(
                        "Start at white belt.",
                        "ابدأ بالحزام الأبيض.",
                        "Trial class 10.000 KD. Our instructor will confirm your class time.",
                        "حصة تجريبية بـ 10.000 د.ك. سيؤكد المدرّب موعد الحصة.",
                    ),
                ],
            ),
        )
        program_pages = {}
        for (
            code,
            slug,
            en,
            ar,
            ages_en,
            ages_ar,
            days_en,
            days_ar,
            groups,
            price,
            note_en,
            note_ar,
            belts,
            confirmed,
            badge_en,
            badge_ar,
            lead_en,
            lead_ar,
        ) in PROGRAMS:
            branch = self.branches[code]
            body = [
                (
                    "schedule",
                    {
                        "title_en": f"{en} class times",
                        "title_ar": f"مواعيد حصص {ar}",
                        "note_en": "",
                        "note_ar": "",
                        "branch": code,
                        "program": None,
                    },
                ),
            ]
            if belts == KAJUKENBO:
                body.insert(
                    0,
                    (
                        "belt_progression",
                        {
                            "eyebrow_en": "The belt path",
                            "eyebrow_ar": "مسار الأحزمة",
                            "title_en": "White to Black, one stripe at a time",
                            "title_ar": "من الأبيض إلى الأسود، شريطاً بعد شريط",
                            "lead_en": "Every belt is earned on the mat and tested in front of the class.",
                            "lead_ar": "كل حزام يُكتسب على البساط ويُختبر أمام الفريق.",
                            "belts": [],
                        },
                    ),
                )
            body += [
                (
                    "instructors",
                    {
                        "eyebrow_en": "Your coaches",
                        "eyebrow_ar": "مدرّبوك",
                        "title_en": "",
                        "title_ar": "",
                        "lead_en": "",
                        "lead_ar": "",
                        "branch": code,
                    },
                ),
                cta(
                    f"Try {en} for 10.000 KD",
                    f"جرّب {ar} بـ 10.000 د.ك",
                    "Promenade: 85.000 KD a month, all three disciplines included. Bedaya: 65.000 KD kids, "
                    "55.000 KD adults.",
                    "بروميناد: 85.000 د.ك شهرياً تشمل الرياضات الثلاث. بداية: 65.000 د.ك للأطفال و 55.000 د.ك للكبار.",
                ),
            ]
            page = self.add(
                programs,
                ProgramPage(
                    title=en,
                    title_ar=ar,
                    slug=slug,
                    branch=branch,
                    ages_en=ages_en,
                    ages_ar=ages_ar,
                    days_en=days_en,
                    days_ar=days_ar,
                    age_groups=groups,
                    price=Decimal(price),
                    price_note_en=note_en,
                    price_note_ar=note_ar,
                    belt_path=belts,
                    belt_path_confirmed=confirmed,
                    badge_en=badge_en,
                    badge_ar=badge_ar,
                    band_belt="purple",
                    band_lead_en=lead_en,
                    band_lead_ar=lead_ar,
                    band_cta=True,
                    band_image_caption=f"Photo: {en} class, instructor watching",
                    body=body,
                ),
            )
            program_pages[slug] = page
        from apps.organization.models import Program

        for slug, (names, match) in PAGE_PROGRAMS.items():
            page = program_pages[slug]
            page.system_programs.set(Program.objects.filter(branch=page.branch, name__in=names))
            page.schedule_match = match
            page.save()
        for page in program_pages.values():  # the schedule on each program page lists only that program
            page.body[0 if page.belt_path != KAJUKENBO else 1].value["program"] = page
            page.save()

        # --- Branches -------------------------------------------------------------
        branches = self.add(
            home,
            ContentPage(
                title="Branches",
                title_ar="الفروع",
                slug="branches",
                show_in_menus=True,
                band_belt="blue",
                band_eyebrow_en="Two branches, one standard",
                band_eyebrow_ar="فرعان، ومعيار واحد",
                band_lead_en="Let's find the right fit for your child.",
                band_lead_ar="لنجد الخيار الأنسب لطفلك.",
                body=[
                    (
                        "branches",
                        {
                            "eyebrow_en": "",
                            "eyebrow_ar": "",
                            "title_en": "Different skills. Same purpose. Stronger together.",
                            "title_ar": "مهارات مختلفة. هدف واحد. أقوى معاً.",
                            "lead_en": "",
                            "lead_ar": "",
                        },
                    ),
                    faq("Questions parents ask", "أسئلة يطرحها أولياء الأمور", FAQ_GENERAL),
                ],
            ),
        )
        branch_faq = {
            "PRM": FAQ_GENERAL[:1]
            + [
                (
                    "Is one membership really all three disciplines?",
                    "هل الاشتراك الواحد يشمل الرياضات الثلاث فعلاً؟",
                    "Yes. At Promenade one membership covers Kajukenbo, Kickboxing and Jiu-Jitsu.",
                    "نعم. في بروميناد يشمل الاشتراك الواحد الكاجوكينبو والكيك بوكسينغ والجوجيتسو.",
                )
            ]
            + FAQ_GENERAL[3:],
            "BED": FAQ_GENERAL[:1] + FAQ_GENERAL[2:],
        }
        branch_data = {
            "PRM": dict(
                slug="elite-promenade",
                title="Elite Promenade",
                title_ar="إيليت بروميناد",
                promise_en="The Complete Fighter Program",
                promise_ar="برنامج المقاتل المتكامل",
                ticks_en="Kajukenbo · Kickboxing · Jiu-Jitsu\nAges 5–12 train striking and grappling, "
                "alternating through the week\nAges 13+ continue into Jiu-Jitsu\n"
                "A multi-year path, not a single class",
                ticks_ar="كاجوكينبو · كيك بوكسينغ · جوجيتسو\nمن 5 إلى 12 سنة: ضربات ومصارعة بالتناوب خلال "
                "الأسبوع\nمن 13 سنة فما فوق: استمرار في الجوجيتسو\nمسار يمتد لسنوات، لا مجرد حصة",
                price_lines="85|/ month, all disciplines|/ شهرياً، كل الرياضات",
                open_days_en="Open daily except Thu & Fri",
                open_days_ar="مفتوح يومياً عدا الخميس والجمعة",
                closed_weekdays="5,6",
                address_en="Promenade Mall, Hawalli",
                address_ar="بروميناد مول، حولي",
                directions_en="Park in the mall car park and follow the signs to our entrance.",
                directions_ar="اركن في مواقف المول واتبع الإرشادات إلى مدخلنا.",
                whatsapp="+96550000002",
                card_image_caption="Promenade mat, family class",
                band_lead_en="Kajukenbo, Kickboxing and Jiu-Jitsu under one membership. Not a single class: "
                "a path your child can follow for years, right inside Promenade Mall.",
                band_lead_ar="كاجوكينبو وكيك بوكسينغ وجوجيتسو باشتراك واحد. ليست مجرد حصة: مسار يمكن لطفلك "
                "أن يتبعه لسنوات، داخل بروميناد مول.",
                band_image_caption="Photo: parents watching a kids class from the mall side",
            ),
            "BED": dict(
                slug="elite-bedaya",
                title="Elite Bedaya",
                title_ar="إيليت بداية",
                promise_en="Choose Your Discipline",
                promise_ar="اختر رياضتك",
                ticks_en="Taekwondo · Kyokushin Karate (Sat, Mon, Wed)\nKickboxing · Kajukenbo (Sun, Tue, Thu)"
                "\nBoys 6–13 and adults\nLadies' class: girls 6+ and adult women",
                ticks_ar="تايكوندو · كيوكوشن كاراتيه (السبت، الاثنين، الأربعاء)\nكيك بوكسينغ · كاجوكينبو "
                "(الأحد، الثلاثاء، الخميس)\nأولاد من 6 إلى 13 سنة والكبار\nصف السيدات: بنات من 6 "
                "سنوات وسيدات",
                price_lines="65|/ month, kids|/ شهرياً، أطفال\n55|/ month, adults|/ شهرياً، كبار",
                open_days_en="Open daily except Friday",
                open_days_ar="مفتوح يومياً عدا الجمعة",
                closed_weekdays="6",
                address_en="Sabah Al Salem",
                address_ar="صباح السالم",
                directions_en="Street parking outside the building.",
                directions_ar="مواقف أمام المبنى.",
                whatsapp="+96550000003",
                card_image_caption="Bedaya ladies' class",
                band_lead_en="Taekwondo, Kyokushin Karate, Kickboxing and Kajukenbo for boys and adults, "
                "plus a dedicated ladies' class for girls and women.",
                band_lead_ar="تايكوندو وكيوكوشن كاراتيه وكيك بوكسينغ وكاجوكينبو للأولاد والكبار، وصف مخصص "
                "للبنات والسيدات.",
                band_image_caption="Photo: the ladies' class bowing in",
            ),
        }
        for code, data in branch_data.items():
            self.add(
                branches,
                BranchPage(
                    branch=self.branches[code],
                    band_belt="blue",
                    band_cta=True,
                    **data,
                    body=[
                        (
                            "schedule",
                            {
                                "title_en": "This week's classes",
                                "title_ar": "حصص هذا الأسبوع",
                                "note_en": "",
                                "note_ar": "",
                                "branch": code,
                                "program": None,
                            },
                        ),
                        (
                            "instructors",
                            {
                                "eyebrow_en": "Your coaches here",
                                "eyebrow_ar": "مدرّبوك هنا",
                                "title_en": "Specialists, not generalists",
                                "title_ar": "متخصصون في رياضاتهم",
                                "lead_en": "",
                                "lead_ar": "",
                                "branch": code,
                            },
                        ),
                        ("location", {"branch": code}),
                        faq(
                            f"Questions {data['title'].split()[-1]} parents ask",
                            "أسئلة يطرحها أولياء الأمور",
                            branch_faq[code],
                        ),
                        cta(
                            "Start at white belt.",
                            "ابدأ بالحزام الأبيض.",
                            "Trial class 10.000 KD. Our instructor will confirm your class time.",
                            "حصة تجريبية بـ 10.000 د.ك. سيؤكد المدرّب موعد الحصة.",
                        ),
                    ],
                ),
            )

        # --- Schedule -------------------------------------------------------------
        self.add(
            home,
            ContentPage(
                title="Schedule",
                title_ar="الجدول",
                slug="schedule",
                show_in_menus=True,
                band_belt="purple",
                band_eyebrow_en="Class schedule",
                band_eyebrow_ar="جدول الحصص",
                band_lead_en="Filter by branch, age group and discipline. Tap any class to book a trial in it.",
                band_lead_ar="اختر الفرع والفئة والرياضة. اضغط على أي حصة لحجز تجربة فيها.",
                body=[
                    (
                        "schedule",
                        {"title_en": "", "title_ar": "", "note_en": "", "note_ar": "", "branch": "", "program": None},
                    ),
                    cta(
                        "Not sure which class fits?",
                        "لست متأكداً أي حصة تناسبك؟",
                        "Tell SAQR your child's age and branch; it will suggest a class. Or book a trial and our "
                        "instructor will place your child.",
                        "أخبر صقر بعمر طفلك والفرع وسيقترح حصة. أو احجز تجربة وسيضع المدرّب طفلك في مجموعته.",
                    ),
                ],
            ),
        )
        # --- Events ---------------------------------------------------------------
        events = self.add(
            home,
            EventIndexPage(
                title="Events",
                title_ar="الفعاليات",
                slug="events",
                show_in_menus=True,
                band_belt="brown",
                band_eyebrow_en="Life at the academy",
                band_eyebrow_ar="الحياة في الأكاديمية",
                band_lead_en="Everything happening at Promenade and Bedaya. Members get first places.",
                band_lead_ar="كل ما يحدث في بروميناد وبداية. الأولوية للأعضاء.",
            ),
        )
        today = timezone.localdate()
        event_rows = [
            (
                "belt_test",
                "Kajukenbo belt test",
                "اختبار أحزمة الكاجوكينبو",
                prm,
                20,
                None,
                None,
                False,
                False,
                "By instructor invitation. Parents welcome to watch.",
                "بدعوة من المدرّب. أولياء الأمور مرحّب بهم.",
            ),
            (
                "seminar",
                "Jiu-Jitsu seminar with a visiting coach",
                "ندوة جوجيتسو مع مدرّب زائر",
                prm,
                34,
                None,
                None,
                True,
                False,
                "Two hours of ground technique for teens and adults.",
                "ساعتان من التقنيات الأرضية للناشئين والكبار.",
            ),
            (
                "camp",
                "Winter camp for kids 6–12",
                "المعسكر الشتوي للأطفال 6–12",
                bed,
                75,
                79,
                "35.000",
                False,
                True,
                "A week of training, games and new friends, ending with a small showcase for parents.",
                "أسبوع من التدريب والألعاب والأصدقاء الجدد، يُختتم بعرض صغير لأولياء الأمور.",
            ),
            (
                "tournament",
                "Inter-branch kids tournament",
                "بطولة الأطفال بين الفرعين",
                prm,
                110,
                None,
                None,
                False,
                False,
                "Promenade and Bedaya students compete in a friendly tournament.",
                "طلاب بروميناد وبداية يتنافسون في بطولة ودية.",
            ),
            (
                "showcase",
                "End-of-season showcase",
                "عرض نهاية الموسم",
                prm,
                150,
                None,
                None,
                False,
                False,
                "Families watch what every group has learned this season.",
                "تشاهد العائلات ما تعلّمته كل مجموعة هذا الموسم.",
            ),
            (
                "camp",
                "Summer camp 2026",
                "المعسكر الصيفي 2026",
                bed,
                -70,
                -66,
                None,
                False,
                False,
                "Our summer camp for children 6–12.",
                "معسكرنا الصيفي للأطفال من 6 إلى 12 سنة.",
            ),
        ]
        for i, (kind, en, ar, branch, offset, end, price, full, reg, summary_en, summary_ar) in enumerate(event_rows):
            self.add(
                events,
                EventPage(
                    title=en,
                    title_ar=ar,
                    slug=f"{kind.replace('_', '-')}-{i + 1}",
                    event_type=kind,
                    branch=branch,
                    date=today + datetime.timedelta(days=offset),
                    end_date=today + datetime.timedelta(days=end) if end else None,
                    start_time=datetime.time(17, 0),
                    end_time=datetime.time(19, 0),
                    summary_en=summary_en,
                    summary_ar=summary_ar,
                    price=Decimal(price) if price else None,
                    is_full=full,
                    accepts_registrations=reg,
                    capacity=24 if reg else None,
                    band_belt="brown",
                    who_en="Children 6–12 from any branch, members and non-members. Beginners welcome."
                    if kind == "camp"
                    else "",
                    who_ar="الأطفال من 6 إلى 12 سنة من أي فرع، أعضاء وغير أعضاء. المبتدئون مرحّب بهم."
                    if kind == "camp"
                    else "",
                    details="What to bring|Uniform or sportswear, water bottle|ماذا نحضر|الزي أو ملابس رياضية، قارورة ماء\n"
                    "Safety|Supervised all day, groups by age|السلامة|إشراف طوال اليوم، مجموعات حسب العمر"
                    if kind == "camp"
                    else "",
                ),
            )

        # --- Gallery --------------------------------------------------------------
        gallery = self.add(
            home,
            GalleryIndexPage(
                title="Gallery",
                title_ar="الصور",
                slug="gallery",
                show_in_menus=True,
                band_belt="brown",
                band_eyebrow_en="Gallery",
                band_eyebrow_ar="معرض الصور",
                band_lead_en="Life on the mat.",
                band_lead_ar="الحياة على البساط.",
            ),
        )
        for i, (en, ar, days) in enumerate(
            [
                ("Belt ceremony · June 2026", "حفل الأحزمة · يونيو 2026", 110),
                ("Summer camp 2026", "المعسكر الصيفي 2026", 66),
                ("Ladies' class open day", "اليوم المفتوح لصف السيدات", 40),
            ]
        ):
            self.add(
                gallery,
                AlbumPage(
                    title=en,
                    title_ar=ar,
                    slug=f"album-{i + 1}",
                    band_belt="brown",
                    date=today - datetime.timedelta(days=days),
                    branch=prm if i != 2 else bed,
                ),
            )

        # --- Shop -----------------------------------------------------------------
        self.add(
            home,
            ShopPage(
                title="Shop",
                title_ar="المتجر",
                slug="shop",
                show_in_menus=True,
                band_belt="black",
                band_eyebrow_en="Gear",
                band_eyebrow_ar="معدات",
                band_lead_en="Gloves, uniforms and guards in the sizes our students use. Pick up free at either branch.",
                band_lead_ar="قفازات وأزياء ووسائل حماية بالمقاسات التي يستخدمها طلابنا. استلام مجاني من أي فرع.",
            ),
        )

        # --- About ----------------------------------------------------------------
        about = self.add(
            home,
            ContentPage(
                title="About",
                title_ar="من نحن",
                slug="about",
                show_in_menus=True,
                band_belt="yellow",
                band_eyebrow_en="About Elite Academy",
                band_eyebrow_ar="عن أكاديمية إيليت",
                band_lead_en="Since 2015, Elite Academy has contributed to a better society through martial arts: building "
                "character, discipline and responsibility for ourselves and others.",
                band_lead_ar="منذ 2015، تساهم أكاديمية إيليت في مجتمع أفضل من خلال الفنون القتالية: بناء الشخصية "
                "والانضباط والمسؤولية تجاه أنفسنا والآخرين.",
                band_image_caption="Photo: the whole academy lined up, bowing",
                body=[
                    (
                        "story",
                        {
                            "eyebrow_en": "Our story",
                            "eyebrow_ar": "قصتنا",
                            "title_en": "From one mat to two branches",
                            "title_ar": "من بساط واحد إلى فرعين",
                            "intro_en": "",
                            "intro_ar": "",
                            "rows": [
                                {
                                    "year": "2015",
                                    "title_en": "Elite Academy opens",
                                    "title_ar": "افتتاح أكاديمية إيليت",
                                    "line_en": "",
                                    "line_ar": "",
                                },
                                {
                                    "year": "",
                                    "title_en": "Elite Promenade opens in Hawalli",
                                    "title_ar": "افتتاح إيليت بروميناد في حولي",
                                    "line_en": "The Complete Fighter Program brings Kajukenbo, Kickboxing and "
                                    "Jiu-Jitsu under one membership.",
                                    "line_ar": "برنامج المقاتل المتكامل يجمع الكاجوكينبو والكيك بوكسينغ والجوجيتسو "
                                    "باشتراك واحد.",
                                },
                                {
                                    "year": "",
                                    "title_en": "Elite Bedaya opens in Sabah Al Salem",
                                    "title_ar": "افتتاح إيليت بداية في صباح السالم",
                                    "line_en": "Choose Your Discipline, and a dedicated ladies' class for girls "
                                    "and women.",
                                    "line_ar": "اختر رياضتك، وصف مخصص للبنات والسيدات.",
                                },
                            ],
                        },
                    ),
                    principles(
                        title_en="How we train, and how we treat each other", title_ar="كيف نتدرّب، وكيف نعامل بعضنا"
                    ),
                    (
                        "instructors",
                        {
                            "eyebrow_en": "Our instructors",
                            "eyebrow_ar": "مدرّبونا",
                            "title_en": "Six specialists, one standard",
                            "title_ar": "ستة متخصصين، ومعيار واحد",
                            "lead_en": "Each instructor is an expert in their own discipline. Their rank, years "
                            "of training and competition background are here for every parent to "
                            "see.",
                            "lead_ar": "كل مدرّب خبير في رياضته. درجته وسنوات تدريبه ومسيرته في البطولات هنا "
                            "لكل وليّ أمر.",
                            "branch": "",
                        },
                    ),
                    cta(
                        "Build the warrior spirit.",
                        "ابنِ روح المحارب.",
                        "Start at white belt with one trial class, 10.000 KD.",
                        "ابدأ بالحزام الأبيض بحصة تجريبية واحدة، 10.000 د.ك.",
                    ),
                ],
            ),
        )
        # Instructor profiles are the academy's to supply: drafts only, never published by this command.
        for disc, disc_ar, code in [
            ("Kajukenbo", "كاجوكينبو", "PRM"),
            ("Kickboxing", "كيك بوكسينغ", "PRM"),
            ("Jiu-Jitsu", "جوجيتسو", "PRM"),
            ("Taekwondo", "تايكوندو", "BED"),
            ("Kyokushin Karate", "كيوكوشن كاراتيه", "BED"),
            ("[Discipline]", "[الرياضة]", "BED"),
        ]:
            page = InstructorPage(
                title=f"[Instructor name] · {disc}",
                title_ar=f"[اسم المدرّب] · {disc_ar}",
                slug=f"instructor-{disc.lower().strip('[]').replace(' ', '-')}",
                discipline_en=disc,
                discipline_ar=disc_ar,
                rank_en="[Rank]",
                rank_ar="[الدرجة]",
                branch=self.branches[code],
                live=False,
            )
            about.add_child(instance=page)
            page.save_revision()

        # --- Contact, Book a trial, Portal (footer / header links, not in the menu) ---
        self.add(
            home,
            ContentPage(
                title="Contact",
                title_ar="اتصل بنا",
                slug="contact",
                band_belt="blue",
                band_eyebrow_en="Contact",
                band_eyebrow_ar="اتصل بنا",
                band_lead_en="WhatsApp is the fastest way to reach a branch. SAQR answers questions any time.",
                band_lead_ar="واتساب أسرع طريقة للتواصل مع الفرع. وصقر يجيب عن أسئلتك في أي وقت.",
                body=[
                    ("location", {"branch": "PRM"}),
                    ("location", {"branch": "BED"}),
                    ("contact_form", {"title_en": "Send us a message", "title_ar": "أرسل لنا رسالة"}),
                ],
            ),
        )
        self.add(
            home,
            ContentPage(
                title="Book a trial",
                title_ar="احجز حصة تجريبية",
                slug="book-a-trial",
                band_belt="white",
                band_eyebrow_en="White belt · where everyone starts",
                band_eyebrow_ar="الحزام الأبيض · من هنا يبدأ الجميع",
                band_lead_en="One real class for 10.000 KD, paid at the branch. No gear, no commitment. Our instructor "
                "will confirm your class time on WhatsApp.",
                band_lead_ar="حصة حقيقية بـ 10.000 د.ك تُدفع في الفرع. بدون معدات وبدون التزام. سيؤكد المدرّب موعد الحصة "
                "عبر واتساب.",
                mobile_action_en="Book my trial",
                mobile_action_ar="احجز التجربة",
                body=[
                    (
                        "trial_form",
                        {
                            "title_en": "Book a trial class",
                            "title_ar": "احجز حصة تجريبية",
                            "lead_en": "",
                            "lead_ar": "",
                        },
                    ),
                    faq("Questions parents ask", "أسئلة يطرحها أولياء الأمور", FAQ_GENERAL),
                ],
            ),
        )
        self.add(home, PortalPage(title="Member portal", title_ar="بوابة الأعضاء", slug="portal", band_belt="green"))

        # --- Home: the eight-belt path ---------------------------------------------
        home.journey = [
            (
                "step",
                {
                    "belt": "white",
                    "tone": "",
                    "eyebrow_en": "Where everyone starts",
                    "eyebrow_ar": "من هنا يبدأ الجميع",
                    "title_en": "Start with one trial class.",
                    "title_ar": "ابدأ بحصة تجريبية واحدة.",
                    "content": [
                        text(
                            "No experience needed. Let's find the right fit for your child.",
                            "لا حاجة لأي خبرة. لنجد الخيار الأنسب لطفلك.",
                        ),
                        ("trial_steps", {}),
                    ],
                },
            ),
            (
                "step",
                {
                    "belt": "yellow",
                    "tone": "white",
                    "eyebrow_en": "Why families stay",
                    "eyebrow_ar": "لماذا تبقى العائلات معنا",
                    "title_en": "We build better humans.",
                    "title_ar": "نبني إنساناً أفضل.",
                    "content": [
                        (
                            "why_stay",
                            {
                                "image": None,
                                "image_caption_en": "Photo: class lined up, bowing to the instructor",
                                "image_caption_ar": "صورة: تحية بداية الحصة",
                                "lead_en": "Elite Academy contributes to a better society through martial arts: building "
                                "character, discipline and responsibility for ourselves and others.",
                                "lead_ar": "تساهم أكاديمية إيليت في مجتمع أفضل من خلال الفنون القتالية: بناء الشخصية "
                                "والانضباط والمسؤولية تجاه أنفسنا والآخرين.",
                                "chips": [{"label_en": t, "label_ar": ta} for t, ta, _, _ in PRINCIPLES],
                                "reasons": [
                                    {
                                        "title_en": "Complete fighter training",
                                        "title_ar": "تدريب المقاتل المتكامل",
                                        "line_en": "Ages 5–12 train striking and grappling, alternating through the week, so "
                                        "skills grow in balance.",
                                        "line_ar": "من 5 إلى 12 سنة: ضربات ومصارعة بالتناوب خلال الأسبوع، لتنمو المهارات "
                                        "بتوازن.",
                                    },
                                    {
                                        "title_en": "A ladies' class",
                                        "title_ar": "صف السيدات",
                                        "line_en": "For girls from 6 and adult women, at Elite Bedaya. Rare in Kuwait, and "
                                        "taught with care.",
                                        "line_ar": "للبنات من 6 سنوات والسيدات، في إيليت بداية. نادر في الكويت، ويُدرَّس بعناية.",
                                    },
                                    {
                                        "title_en": "Six specialised instructors",
                                        "title_ar": "ستة مدرّبين متخصصين",
                                        "line_en": "Each an expert in their own discipline. See their rank, years of training "
                                        "and competition record.",
                                        "line_ar": "كل مدرّب خبير في رياضته. تعرّف على درجته وسنوات تدريبه ومسيرته.",
                                    },
                                    {
                                        "title_en": "Safety first",
                                        "title_ar": "السلامة أولاً",
                                        "line_en": "If it's not safe, we don't do it. Safe training, safe places, safe "
                                        "treatment of children.",
                                        "line_ar": "إن لم يكن آمناً، لا نفعله. تدريب آمن، أماكن آمنة، ومعاملة آمنة للأطفال.",
                                    },
                                ],
                            },
                        )
                    ],
                },
            ),
            (
                "step",
                {
                    "belt": "purple",
                    "tone": "",
                    "eyebrow_en": "Find your program",
                    "eyebrow_ar": "اختر برنامجك",
                    "title_en": "A path for every age",
                    "title_ar": "مسار لكل عمر",
                    "content": [
                        (
                            "programs",
                            {
                                "eyebrow_en": "",
                                "eyebrow_ar": "",
                                "title_en": "",
                                "title_ar": "",
                                "programs": [
                                    program_pages[s] for s in ("kajukenbo", "jiu-jitsu", "taekwondo", "ladies-class")
                                ],
                                "show_filters": False,
                                "compact": True,
                            },
                        )
                    ],
                },
            ),
            (
                "step",
                {
                    "belt": "blue",
                    "tone": "sunken",
                    "eyebrow_en": "Two branches",
                    "eyebrow_ar": "فرعان",
                    "title_en": "Different skills. Same purpose.",
                    "title_ar": "مهارات مختلفة. هدف واحد.",
                    "content": [
                        (
                            "branches",
                            {
                                "eyebrow_en": "",
                                "eyebrow_ar": "",
                                "title_en": "",
                                "title_ar": "",
                                "lead_en": "",
                                "lead_ar": "",
                            },
                        )
                    ],
                },
            ),
            (
                "step",
                {
                    "belt": "green",
                    "tone": "",
                    "eyebrow_en": "Progress you can see",
                    "eyebrow_ar": "تقدّم تراه",
                    "title_en": "Every stripe, in your pocket.",
                    "title_ar": "كل شريط، في جيبك.",
                    "content": [
                        (
                            "portal_preview",
                            {
                                "lead_en": "The member portal shows each child's belt, stripes toward the next test, their "
                                "next class and membership date. Sign in with your mobile number: no passwords.",
                                "lead_ar": "تعرض بوابة الأعضاء حزام كل طفل وأشرطته نحو الاختبار القادم وحصته القادمة وتاريخ "
                                "اشتراكه. ادخل برقم جوالك: بدون كلمات مرور.",
                            },
                        )
                    ],
                },
            ),
            (
                "step",
                {
                    "belt": "brown",
                    "tone": "white",
                    "eyebrow_en": "Life at the academy",
                    "eyebrow_ar": "الحياة في الأكاديمية",
                    "title_en": "Seminars, camps and belt tests",
                    "title_ar": "ندوات ومعسكرات واختبارات أحزمة",
                    "content": [
                        (
                            "events",
                            {
                                "eyebrow_en": "",
                                "eyebrow_ar": "",
                                "title_en": "",
                                "title_ar": "",
                                "count": 3,
                                "layout": "feature",
                                "show_filters": False,
                                "branch": "",
                            },
                        ),
                        (
                            "albums",
                            {
                                "eyebrow_en": "",
                                "eyebrow_ar": "",
                                "title_en": "",
                                "title_ar": "",
                                "count": 3,
                                "strip": True,
                            },
                        ),
                    ],
                },
            ),
            (
                "step",
                {
                    "belt": "brownblack",
                    "tone": "",
                    "eyebrow_en": "In their words",
                    "eyebrow_ar": "بكلماتهم",
                    "title_en": "What parents tell us",
                    "title_ar": "ماذا يقول أولياء الأمور",
                    "content": [
                        (
                            "testimonials",
                            {
                                "eyebrow_en": "",
                                "eyebrow_ar": "",
                                "title_en": "",
                                "title_ar": "",
                                "items": [
                                    {
                                        "quote_en": "[A real parent's words, with permission: "
                                        "what changed for their child.]",
                                        "quote_ar": "[كلمات وليّ أمر حقيقية، بإذنه.]",
                                        "name_en": "[First name]",
                                        "name_ar": "[الاسم الأول]",
                                        "relation_en": "Parent · Promenade",
                                        "relation_ar": "وليّ أمر · بروميناد",
                                        "branch": "promenade",
                                        "approved": False,
                                    }
                                ],
                            },
                        )
                    ],
                },
            ),
            (
                "step",
                {
                    "belt": "black",
                    "tone": "deep",
                    "eyebrow_en": "The long game",
                    "eyebrow_ar": "الطريق الطويل",
                    "title_en": "Discipline today, brighter tomorrow.",
                    "title_ar": "انضباط اليوم، غدٌ أكثر إشراقاً.",
                    "content": [
                        text(
                            "Every black belt in our academy started with one class. Book yours: our "
                            "instructor will confirm your class time.",
                            "كل حزام أسود في أكاديميتنا بدأ بحصة واحدة. احجز حصتك وسيؤكد المدرّب الموعد.",
                        ),
                        ("trial_form", {"title_en": "", "title_ar": "", "lead_en": "", "lead_ar": ""}),
                    ],
                },
            ),
        ]
        home.save()

    # ------------------------------------------------------------------
    def _shop(self):
        for slug, en, ar, category, price, sizes in PRODUCTS:
            product = Product.objects.create(
                slug=slug, name_en=en, name_ar=ar, category=category, price=Decimal(price), is_sample_price=True
            )
            for i, (size, stock) in enumerate(sizes):
                variant = ProductVariant.objects.create(product=product, size=size, stock=0, sort_order=i)
                for branch in self.branches.values():  # shelves at each branch; online stock is derived (M19)
                    set_opening(variant, branch, max(stock // 2, 0))
        guide = SizeGuide.objects.create(category="gloves")
        for i, (size, measure, en, ar) in enumerate(
            [
                ("8 oz", "< 30 kg", "Kids 5–8", "أطفال 5–8"),
                ("10 oz", "30–45 kg", "Kids 9–12", "أطفال 9–12"),
                ("12 oz", "45–60 kg", "Teens, lighter adults", "ناشئين، كبار بوزن خفيف"),
                ("14–16 oz", "60 kg +", "Adults, sparring", "كبار، للنزال"),
            ]
        ):
            SizeGuideRow.objects.create(guide=guide, size=size, measure=measure, fits_en=en, fits_ar=ar, sort_order=i)

    def _progress(self):
        """Belt progress for a few fictional test members, so the portal has something to show."""
        belts = ["white", "yellow", "purple", "blue"]
        for i, member in enumerate(Member.objects.filter(is_active=True).order_by("pk")[:30]):
            MemberProgress.objects.update_or_create(
                member=member,
                defaults={
                    "belt": belts[i % len(belts)],
                    "stripes": i % 5,
                    "stripes_needed": 4,
                },
            )
