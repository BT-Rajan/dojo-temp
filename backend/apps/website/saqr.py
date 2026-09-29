"""
SAQR — the website chat assistant (EA-SYS-SCOPE-01 M16).

This first engine is rule-based: it answers from live data (branches, prices, timetable)
in the One Voice tone and applies the Customer Management Procedure's hand-off rules.
The Claude-powered engine (knowledge base + live data) replaces `RuleEngine` behind the
same `reply()` interface in Phase 5; nothing in the page changes.

Hand-off rule (Customer Management Procedure): refund, cancel, complaint, injury, asking
for a person, or two unresolved exchanges → hand over to a human on WhatsApp.
"""

import re
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.classes.models import ClassSlot

from .models import BranchPage, ProgramPage, SiteSettings

HANDOFF = re.compile(
    r"refund|cancel|complain|complaint|injur|hurt|person|human|staff|manager|"
    r"استرجاع|استرداد|إلغاء|الغاء|شكوى|اشتكي|إصابة|اصابة|موظف|شخص|إنسان|مدير",
    re.IGNORECASE,
)
TOPICS = {
    "price": r"price|cost|fee|how much|kd|سعر|اسعار|أسعار|كم|رسوم|تكلفة",
    "trial": r"trial|try|book|تجرب|تجربة|تجريبي|احجز|حجز",
    "schedule": r"schedule|time|when|day|class times|جدول|موعد|مواعيد|وقت|أيام|متى",
    "ladies": r"lad(y|ies)|women|girl|daughter|سيدات|بنات|بنت|ابنتي|نساء",
    "branch": r"where|location|address|branch|hawalli|promenade|bedaya|sabah|وين|موقع|عنوان|فرع|حولي|صباح|بداية|بروميناد",  # noqa: E501
    "kids": r"kid|child|son|age|years old|طفل|اطفال|أطفال|ابني|عمر|سنوات",
}

GREETING = (
    "Hi! Thanks for reaching out to Elite Academy. Happy to help. Are you asking about our Hawalli or Sabah Al "
    "Salem branch?",
    "أهلاً وسهلاً! شكراً لتواصلك مع أكاديمية إيليت. يسعدني مساعدتك. هل تسأل عن فرع حولي أم فرع صباح السالم؟",
)


def kd_text(amount, lang):
    """Plain-text KD amount for chat replies: three decimals, Western digits."""
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError):
        return ""
    return f"{value:.3f} " + ("د.ك" if lang == "ar" else "KD")


def L(lang, en, ar):
    return ar if lang == "ar" else en


class RuleEngine:
    def reply(self, text: str, lang: str, state: dict) -> dict:
        text = (text or "").strip()
        settings_ = SiteSettings.load()
        wa = settings_.whatsapp_link
        if not text:
            return {"text": L(lang, *GREETING), "chips": self._branch_chips(lang)}

        if HANDOFF.search(text):
            return {
                "text": L(
                    lang,
                    "I'm really sorry to hear that — let me get this sorted for you personally. Our team will "
                    "take it from here on WhatsApp.",
                    "يؤسفني سماع ذلك — دعني أتأكد أن يتابعها معك أحد من فريقنا شخصياً عبر واتساب.",
                ),
                "handoff": True,
                "link": wa,
                "link_label": L(lang, "Continue on WhatsApp", "المتابعة عبر واتساب"),
            }

        topics = [name for name, pattern in TOPICS.items() if re.search(pattern, text, re.IGNORECASE)]
        branch = self._branch_in(text) or state.get("branch")
        if branch:
            state["branch"] = branch

        if "ladies" in topics:
            return {
                "text": L(
                    lang,
                    "Yes! Our ladies' class at Elite Bedaya (Sabah Al Salem) welcomes girls from 6 and adult "
                    f"women. It's {self._price('BED', 0, lang)} a month for girls and "
                    f"{self._price('BED', 1, lang)} for women, and a trial class is "
                    f"{kd_text(settings_.trial_price, lang)}. Shall I book a trial?",
                    "نعم! صف السيدات في إيليت بداية (صباح السالم) يستقبل البنات من عمر 6 سنوات والسيدات. "
                    f"الاشتراك {self._price('BED', 0, lang)} شهرياً للبنات و{self._price('BED', 1, lang)} "
                    f"للسيدات، والحصة التجريبية {kd_text(settings_.trial_price, lang)}. هل أحجز لك تجربة؟",
                ),
                "chips": self._trial_chips(lang, "BED"),
            }
        if "trial" in topics:
            return {
                "text": L(
                    lang,
                    f"Great choice! A trial class is {kd_text(settings_.trial_price, lang)}, paid at the "
                    "branch. Just four things: your name, mobile, branch and program — our instructor will "
                    "confirm your class time on WhatsApp.",
                    f"اختيار رائع! الحصة التجريبية بـ {kd_text(settings_.trial_price, lang)} تُدفع في الفرع. "
                    "نحتاج أربعة أشياء فقط: الاسم والجوال والفرع والبرنامج، وسيؤكد المدرّب الموعد عبر واتساب.",
                ),
                "action": "trial",
                "branch": branch or "",
            }
        if "price" in topics:
            return {"text": self._prices_text(lang, branch), "chips": self._trial_chips(lang, branch)}
        if "schedule" in topics:
            return {"text": self._schedule_text(lang, branch), "chips": self._trial_chips(lang, branch)}
        if branch or "branch" in topics:
            return {"text": self._branch_text(lang, branch), "chips": self._trial_chips(lang, branch)}
        if "kids" in topics:
            return {
                "text": L(
                    lang,
                    "Let's find the right fit for your child. At Promenade, ages 5–12 train both striking "
                    "and grappling; at Bedaya they choose one discipline. Which branch is closer to you?",
                    "لنجد الخيار الأنسب لطفلك. في بروميناد يتدرّب الأطفال من 5 إلى 12 سنة على الضربات "
                    "والمصارعة معاً، وفي بداية يختارون رياضة واحدة. أي فرع أقرب إليك؟",
                ),
                "chips": self._branch_chips(lang),
            }

        state["misses"] = state.get("misses", 0) + 1
        if state["misses"] >= 2:
            return {
                "text": L(
                    lang,
                    "Good question — let me hand you to the team so you get the right answer. They'll reply "
                    "on WhatsApp.",
                    "سؤال جيد — سأحوّلك إلى الفريق ليجيبك بدقة عبر واتساب.",
                ),
                "handoff": True,
                "link": wa,
                "link_label": L(lang, "Continue on WhatsApp", "المتابعة عبر واتساب"),
            }
        return {
            "text": L(
                lang,
                "I can help with programs, class times, prices and booking a trial. What would you like to know?",
                "أستطيع مساعدتك في البرامج ومواعيد الحصص والأسعار وحجز حصة تجريبية. ماذا تود أن تعرف؟",
            ),
            "chips": [
                L(lang, "Prices", "الأسعار"),
                L(lang, "Class times", "مواعيد الحصص"),
                L(lang, "Book a trial", "احجز تجربة"),
            ],
        }

    # -- helpers ---------------------------------------------------------------
    @staticmethod
    def _branch_in(text):
        if re.search(r"hawalli|promenade|حولي|بروميناد", text, re.IGNORECASE):
            return "PRM"
        if re.search(r"bedaya|sabah|salem|بداية|صباح", text, re.IGNORECASE):
            return "BED"
        return None

    @staticmethod
    def _branch_chips(lang):
        return [
            L(lang, "Hawalli (Promenade)", "حولي (بروميناد)"),
            L(lang, "Sabah Al Salem (Bedaya)", "صباح السالم (بداية)"),
            L(lang, "Not sure yet", "لست متأكداً"),
        ]

    @staticmethod
    def _trial_chips(lang, branch):
        return [L(lang, "Book a trial", "احجز تجربة"), L(lang, "See class days", "أيام الحصص")]

    @staticmethod
    def _page(branch):
        return BranchPage.objects.live().filter(branch__code=branch).select_related("branch").first()

    def _price(self, branch, index, lang):
        page = self._page(branch)
        rows = page.prices if page else []
        return kd_text(rows[index]["amount"], lang) if len(rows) > index else ""

    def _prices_text(self, lang, branch):
        parts = []
        for code in [branch] if branch else ["PRM", "BED"]:
            page = self._page(code)
            if not page:
                continue
            rows = " · ".join(
                f"{kd_text(r['amount'], lang)} {r['note_ar'] if lang == 'ar' else r['note_en']}" for r in page.prices
            )
            name = page.title_ar if lang == "ar" and page.title_ar else page.title
            parts.append(f"{name}: {rows}")
        trial = kd_text(SiteSettings.load().trial_price, lang)
        return "\n".join(parts) + "\n" + L(lang, f"A trial class is {trial}.", f"الحصة التجريبية بـ {trial}.")

    def _schedule_text(self, lang, branch):
        days_en = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
        days_ar = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
        entries = ClassSlot.objects.filter(is_active=True, is_public=True).select_related("branch")
        if branch:
            entries = entries.filter(branch__code=branch)
        lines = []
        for e in entries.order_by("weekday", "start")[:6]:
            day = days_ar[e.weekday] if lang == "ar" else days_en[e.weekday]
            title = e.title_ar if lang == "ar" and e.title_ar else e.title_en
            lines.append(f"{day} {e.start:%-I:%M} · {title}")
        intro = L(
            lang,
            "Here are some class times (samples until confirmed):",
            "هذه بعض مواعيد الحصص (للتوضيح حتى يتم تأكيدها):",
        )
        return intro + "\n" + "\n".join(lines)

    def _branch_text(self, lang, branch):
        if branch == "BED":
            return L(
                lang,
                "Elite Bedaya in Sabah Al Salem: choose your discipline — Taekwondo and Kyokushin on Sat, "
                "Mon, Wed; Kickboxing and Kajukenbo on Sun, Tue, Thu — plus the ladies' class. Open every "
                "day except Friday.",
                "إيليت بداية في صباح السالم: اختر رياضتك — تايكوندو وكيوكوشن السبت والاثنين والأربعاء، وكيك "
                "بوكسينغ وكاجوكينبو الأحد والثلاثاء والخميس — بالإضافة إلى صف السيدات. مفتوح يومياً عدا الجمعة.",
            )
        if branch == "PRM":
            return L(
                lang,
                "Elite Promenade in Promenade Mall, Hawalli: the Complete Fighter Program — Kajukenbo, "
                "Kickboxing and Jiu-Jitsu in one membership. Open daily except Thursday and Friday.",
                "إيليت بروميناد في بروميناد مول، حولي: برنامج المقاتل المتكامل — كاجوكينبو وكيك بوكسينغ "
                "وجوجيتسو باشتراك واحد. مفتوح يومياً عدا الخميس والجمعة.",
            )
        return L(lang, *GREETING)


class SaqrSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=500, allow_blank=True)
    lang = serializers.ChoiceField(choices=["en", "ar"], default="en")


class SaqrThrottle(AnonRateThrottle):
    rate = "30/min"


class SaqrView(APIView):
    """Public chat endpoint. Conversation state is kept per browser session only."""

    public = True
    throttle_classes = [SaqrThrottle]

    def post(self, request):
        data = SaqrSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if not request.session.session_key:
            request.session.save()  # each visitor gets their own conversation state
        session_key = request.session.session_key
        state_key = f"saqr:{session_key}"
        state = cache.get(state_key, {})
        answer = RuleEngine().reply(data.validated_data["message"], data.validated_data["lang"], state)
        cache.set(state_key, state, 3600)
        return Response(answer)


def programs_for_prefill():
    return ProgramPage.objects.live().public().select_related("branch")
