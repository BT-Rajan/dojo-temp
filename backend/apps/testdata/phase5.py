"""
Phase 5 test data (fictional): campaigns, leads at every stage (website, SAQR, walk-in, phone, referral), trials
with feedback, group deals, referral codes, WhatsApp opt-ins, broadcasts, knowledge-base articles and a few
SAQR conversations.

Never loaded in production (seed_kuwait refuses to run there).
"""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.assistant import services as ai
from apps.assistant.models import Article, ArticleVersion, Conversation, Message
from apps.classes.models import ClassSession
from apps.leads import services as ls
from apps.leads.models import (
    Activity,
    Broadcast,
    Campaign,
    GroupDeal,
    Lead,
    MessagingOptIn,
    ReferralCode,
    ReviewRequest,
)
from apps.members.models import Member
from apps.website.models import TrialRequest

TEST_DOMAIN = "test.elite.local"
D = Decimal

NAMES = [
    ("Test Parent Ahmad", "60001101", "Son, 7 — first martial art"),
    ("Test Parent Noura", "60001102", "Daughter, 9 — ladies' class?"),
    ("Test Visitor Faisal", "60001103", "Adult, kickboxing for fitness"),
    ("Test Parent Hessa", "60001104", "Two boys, 6 and 10"),
    ("Test Visitor Yousef", "60001105", "Teen, 14 — Jiu-Jitsu"),
    ("Test Parent Mariam", "60001106", "Daughter, 12 — self-defence"),
    ("Test Visitor Khalid", "60001107", "Adult, returning after a break"),
    ("Test Parent Dana", "60001108", "Son, 8 — confidence"),
    ("Test Visitor Salman", "60001109", "Adult, BJJ blue belt elsewhere"),
    ("Test Parent Lulwa", "60001110", "Son, 5"),
]

ARTICLES = [
    (
        "public",
        "Trials",
        "What happens at a trial class",
        "ماذا يحدث في الحصة التجريبية",
        "Book with your name and mobile only. Arrive 10 minutes early and tell the front desk it's your trial. "
        "Wear comfortable sports clothes and bring water; no equipment is needed for the first class. The "
        "instructor will tell you how it went and which class suits you. The trial price is shown on the prices "
        "page and paid at the branch.",
        "احجز باسمك ورقم جوالك فقط. احضر قبل 10 دقائق وأخبر الاستقبال أنها حصتك التجريبية. البس ملابس رياضية "
        "مريحة وأحضر الماء؛ لا تحتاج معدات في الحصة الأولى. سيخبرك المدرّب بانطباعه وأي صف يناسبك. سعر الحصة "
        "التجريبية موجود في صفحة الأسعار ويُدفع في الفرع.",
        "try, first class, what to wear, bring",
    ),
    (
        "public",
        "Branches",
        "Which branch is right for me?",
        "أي فرع يناسبني؟",
        "Elite Promenade (Hawalli) runs the Complete Fighter Program: Kajukenbo, Kickboxing and Jiu-Jitsu in one "
        "membership. Elite Bedaya (Sabah Al Salem) lets you choose your discipline and has the ladies' class.",
        "إيليت بروميناد (حولي) تقدّم برنامج المقاتل المتكامل: كاجوكينبو وكيك بوكسينغ وجوجيتسو باشتراك واحد. "
        "إيليت بداية (صباح السالم) تتيح لك اختيار رياضتك وفيها صف السيدات.",
        "hawalli, sabah al salem, location, ladies",
    ),
    (
        "public",
        "Belts",
        "How belts and test days work",
        "كيف تعمل الأحزمة وأيام الاختبار",
        "One belt, one stripe, three arts: the belt shows the Kajukenbo rank and kickboxing level, the stripe "
        "shows the Jiu-Jitsu level, and seminars earn the points needed for promotion. Students are evaluated "
        "every 4–6 weeks and invited to a test day when they're ready.",
        "حزام واحد وخط واحد وثلاثة فنون: الحزام يبيّن رتبة الكاجوكينبو ومستوى الكيك بوكسينغ، والخط يبيّن مستوى "
        "الجوجيتسو، والندوات تمنح النقاط المطلوبة للترقية. يُقيَّم الطلاب كل 4–6 أسابيع ويُدعون ليوم الاختبار "
        "عند الجاهزية.",
        "promotion, grading, stripe, seminar",
    ),
    (
        "staff",
        "How to: leads",
        "How to book a trial from a lead",
        "كيف تحجز تجربة من عميل محتمل",
        "Open Leads, pick the lead, log your call or WhatsApp (you become the owner if nobody is), then choose a "
        "class under 'Book a trial'. The instructor gets the trial brief automatically. After the class, record "
        "the feedback on the class list and follow up within 24 hours.",
        "افتح العملاء المحتملين واختر العميل وسجّل اتصالك أو رسالتك (تصبح المسؤول إن لم يكن هناك مسؤول)، ثم اختر "
        "حصة من «حجز تجربة». يصل ملخص التجربة للمدرّب تلقائياً. بعد الحصة سجّل التقييم في قائمة الحصة وتابع خلال 24 ساعة.",
        "trial, book, lead, follow up",
    ),
    (
        "staff",
        "How to: stock",
        "How to transfer stock to Bedaya",
        "كيف تحوّل مخزوناً إلى بداية",
        "Go to Transfers → Send stock, choose the receiving branch and the items. The stock is held while it "
        "travels. Bedaya counts it on arrival and accepts it in the desk; only then does it move. If the count is "
        "short, call the sender and the OM before accepting.",
        "اذهب إلى التحويلات ← إرسال مخزون، واختر الفرع المستلم والأصناف. يُحجز المخزون أثناء النقل. تعدّه بداية عند "
        "الوصول وتستلمه في النظام، وعندها فقط ينتقل. إن كان العدد ناقصاً اتصل بالمرسل ومدير العمليات قبل الاستلام.",
        "transfer, stock, bedaya, send",
    ),
    (
        "staff",
        "How to: training",
        "How to hand over a belt after a promotion",
        "كيف تسلّم الحزام بعد الترقية",
        "Promotions appear under Training → Belts to hand over. Choose the size and press Hand over: the belt is "
        "issued at 0 KD from this branch's stock and printed on a receipt as a grading belt.",
        "تظهر الترقيات في التدريب ← أحزمة للتسليم. اختر المقاس واضغط تسليم: يُصرف الحزام بسعر 0 د.ك من مخزون الفرع "
        "ويظهر في الإيصال كحزام ترقية.",
        "belt, promotion, grading, free issue",
    ),
    (
        "staff",
        "Policies",
        "One Voice: answering a complaint",
        "الصوت الواحد: التعامل مع الشكوى",
        "Listen, thank them, say sorry for how it felt, and log it as a complaint in the desk the same day. Money, "
        "refunds, staff conduct and safety go to the OM. Never promise a refund yourself.",
        "استمع واشكر واعتذر عن شعوره، وسجّلها شكوى في النظام في اليوم نفسه. المال والاسترداد وسلوك الموظفين "
        "والسلامة تذهب لمدير العمليات. لا تعد باسترداد بنفسك.",
        "complaint, refund, one voice",
    ),
]


def reset_phase5():
    for model in (
        Activity,
        Lead,
        GroupDeal,
        Broadcast,
        Campaign,
        ReferralCode,
        ReviewRequest,
        MessagingOptIn,
        Message,
        Conversation,
        ArticleVersion,
        Article,
        TrialRequest,
    ):
        model.objects.all().delete()


class Phase5Data:
    def __init__(self, seed):
        self.rng, self.today, self.branches = seed.rng, seed.today, seed.branches
        self.users = {u.email.split("@")[0]: u for u in get_user_model().objects.filter(email__endswith=TEST_DOMAIN)}

    def load(self):
        for code, branch in self.branches.items():
            branch.google_review_url = f"https://example.test/review/{code.lower()}"
            branch.save(update_fields=["google_review_url"])
        self._campaigns()
        self._leads()
        self._deals()
        self._opt_ins()
        self._broadcasts()
        self._articles()
        self._chats()

    def _campaigns(self):
        mk = self.users["marketing"]
        self.insta = Campaign.objects.create(
            name="Autumn kids intake (test)",
            code="autumn-kids",
            channel="instagram",
            start=self.today - datetime.timedelta(days=30),
            end=self.today + datetime.timedelta(days=30),
            spend=D("120.000"),
            created_by=mk,
        )
        self.flyer = Campaign.objects.create(
            name="Bedaya flyers (test)",
            code="bedaya-flyers",
            channel="flyer",
            branch=self.branches["BED"],
            start=self.today - datetime.timedelta(days=20),
            spend=D("35.000"),
            created_by=mk,
        )

    def _session(self, branch):
        for s in ClassSession.objects.filter(
            branch=branch, date__gte=self.today, date__lte=self.today + datetime.timedelta(days=10), status="scheduled"
        ).order_by("date", "start"):
            if not s.is_over:
                return s
        return None

    def _leads(self):
        prm, bed = self.branches["PRM"], self.branches["BED"]
        desk = {"PRM": self.users["admin.prm"], "BED": self.users["admin.bed"]}
        referrer = Member.objects.filter(branch=prm, is_active=True).order_by("pk").first()
        if referrer is not None:
            ls.referral_code_for(referrer)
        plan = [
            # (branch, source, stage, campaign)
            (prm, "website", "new", self.insta),
            (bed, "saqr", "new", None),
            (prm, "walk_in", "contacted", None),
            (bed, "phone", "contacted", self.flyer),
            (prm, "website", "trial_booked", self.insta),
            (bed, "walk_in", "trial_booked", None),
            (prm, "referral", "trial_done", None),
            (bed, "website", "trial_done", self.flyer),
            (prm, "phone", "lost", None),
            (bed, "walk_in", "lost", None),
        ]
        for (name, mobile, interest), (branch, source, stage, campaign) in zip(NAMES, plan, strict=True):
            user = desk[branch.code]
            if source in ("website", "saqr"):
                tr = TrialRequest.objects.create(
                    name=name, mobile="+965" + mobile, branch=branch, not_sure=True, source=source, language="ar"
                )
                lead = ls.intake(
                    name=name,
                    mobile=mobile,
                    branch=branch,
                    source=source,
                    interest=interest,
                    campaign=campaign,
                    trial_request=tr,
                )
            else:
                lead = ls.intake(
                    name=name,
                    mobile=mobile,
                    branch=branch,
                    source=source,
                    interest=interest,
                    campaign=campaign,
                    referrer=referrer if source == "referral" else None,
                    user=user,
                )
            if stage == "new":
                continue
            due = timezone.now() + datetime.timedelta(hours=self.rng.choice([-3, 5, 20]))
            ls.log_contact(lead, user, "call", "Called; interested in a trial this week (test).", "Book a trial", due)
            if stage in ("trial_booked", "trial_done"):
                session = self._session(branch)
                if session is not None:
                    booking = ls.book_trial(lead, session, user)
                    if stage == "trial_done":
                        ls.record_feedback(booking, user, self.rng.choice([4, 5]), "Keen and listened well (test).")
            if stage == "lost":
                ls.mark_lost(lead, user, self.rng.choice(["timing", "price", "no_answer"]), "Test data")
        # Two older leads that joined (credited to the campaign and owner).
        for i, member in enumerate(Member.objects.filter(branch=prm, is_active=True).order_by("-pk")[:2]):
            lead = Lead.objects.create(
                name=f"{member.first_name} {member.last_name}",
                mobile=member.mobile or f"+96560001{200 + i}",
                branch=prm,
                source="website",
                campaign=self.insta,
                owner=desk["PRM"],
                stage="joined",
                member=member,
                joined_at=timezone.now() - datetime.timedelta(days=10 + i),
                closed_at=timezone.now() - datetime.timedelta(days=10 + i),
            )
            Activity.objects.create(lead=lead, kind="stage", text="Joined — first membership (test).", by=desk["PRM"])

    def _deals(self):
        user, ops = self.users["admin.prm"], self.users["ops"]
        prm = self.branches["PRM"]
        school = ls.create_deal(
            user,
            organisation="Test Bilingual School",
            kind="school",
            contact_name="Test Sports Coordinator",
            mobile="60002001",
            branch=prm,
            details="After-school self-defence, 20 pupils, twice a week (test).",
        )
        ls.move_deal(school, user, "meeting", "Met the coordinator (test).")
        ls.move_deal(school, user, "proposal", "Proposal sent (test).", participants=20)
        company = ls.create_deal(
            user,
            organisation="Test Logistics Co.",
            kind="company",
            contact_name="Test HR Manager",
            mobile="60002002",
            branch=prm,
            details="Staff fitness kickboxing, 12 people, Mondays (test).",
        )
        for stage in ("meeting", "proposal", "agreement"):
            ls.move_deal(company, user, stage, "Test")
        ls.move_deal(company, user, "paid", "Invoice paid (test).", value=D("960"), participants=12)
        ls.confirm_delivery(company, ops)

    def _opt_ins(self):
        desk = self.users["admin.prm"]
        for member in Member.objects.filter(is_active=True).order_by("pk"):
            if self.rng.random() < 0.35:
                MessagingOptIn.objects.create(member=member, opted_in=True, source="rules_form", recorded_by=desk)

    def _broadcasts(self):
        content, mk = self.users["content"], self.users["marketing"]
        sent = ls.save_broadcast(
            content,
            title="Test day reminder (test)",
            message_en="Reminder: our Autumn test day is next week. Ask your instructor if you're invited. (test)",
            message_ar="تذكير: يوم الاختبار الخريفي الأسبوع القادم. اسأل مدربك إن كنت مدعواً. (تجريبي)",
            branch=self.branches["PRM"],
            ages="kids",
        )
        if ls.audience(sent):  # a tiny seed may have nobody opted in; then it stays a draft
            ls.send_broadcast(sent, mk)
        ls.save_broadcast(
            content,
            title="Ladies' class new time (test)",
            message_en="The ladies' class at Bedaya has a new evening slot. Book a trial for a friend! (test)",
            message_ar="صف السيدات في بداية له موعد مسائي جديد. احجزي تجربة لصديقتك! (تجريبي)",
            branch=self.branches["BED"],
            ages="all",
            campaign=self.flyer,
        )

    def _articles(self):
        owners = {"public": self.users["marketing"], "staff": self.users["ops"]}
        for audience, topic, t_en, t_ar, b_en, b_ar, keywords in ARTICLES:
            ai.save_article(
                owners[audience],
                title_en=t_en,
                title_ar=t_ar,
                body_en=b_en,
                body_ar=b_ar,
                audience=audience,
                topic=topic,
                keywords=keywords,
                status="published",
            )

    def _chats(self):
        ai.saqr_message("test-visitor-1", "How much is a month at Promenade?", "en")
        ai.saqr_message("test-visitor-1", "And the class times?", "en")
        ai.saqr_message("test-visitor-2", "أبغى استرجاع المبلغ", "ar")
        ai.saqr_message("test-visitor-3", "Do you have classes for girls?", "en")
        first = Conversation.objects.filter(channel="saqr").order_by("pk").first()
        if first is not None:
            ai.review_conversation(first, self.users["admin.prm"], True)
