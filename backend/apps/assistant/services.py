"""
Knowledge base, SAQR and the Staff Assistant (M16, decisions P5-11 to P5-13).

Both assistants use the same engine: an AI model with tools that read live data and published articles. While
no AI provider is configured (open item O-20), SAQR falls back to the rule-based engine and the Staff Assistant
to keyword routing over the same tools — answers stay correct, just less conversational.
"""

import datetime
import json
import logging
import re

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.validators import day_range, normalize_kuwait_mobile
from apps.organization.models import Branch
from apps.rbac.services import has_perm, notify_perm

from .models import Article, ArticleVersion, Conversation, Message, hash_key

log = logging.getLogger(__name__)
MAX_STEPS = 6
HISTORY = 12
RETENTION_DAYS = 90
HANDOFF = re.compile(
    r"refund|cancel|complain|complaint|injur|hurt|human|real person|staff member|manager|"
    r"استرجاع|استرداد|إلغاء|الغاء|شكوى|اشتكي|إصابة|اصابة|موظف|شخص|إنسان|مدير",
    re.IGNORECASE,
)


def L(lang, en, ar):
    return ar if lang == "ar" else en


# ---------------------------------------------------------------------------
# Knowledge base (P5-11)
# ---------------------------------------------------------------------------
@transaction.atomic
def save_article(user, article=None, **data) -> Article:
    if not has_perm(user, "kb.edit"):
        raise PermissionDenied("Only knowledge-base editors write articles.")
    a = article or Article(owner=user, created_by=user)
    for key, value in data.items():
        setattr(a, key, value)
    if not a.title_en.strip() or not a.body_en.strip():
        raise ValidationError("Write at least the English title and text.")
    if a.audience not in Article.Audience.values or a.status not in Article.Status.values:
        raise ValidationError("Choose who the article is for and whether it is published.")
    a.version, a.updated_by = a.version + 1, user
    a.save()
    ArticleVersion.objects.create(
        article=a,
        version=a.version,
        title_en=a.title_en,
        title_ar=a.title_ar,
        body_en=a.body_en,
        body_ar=a.body_ar,
        status=a.status,
        saved_by=user,
    )
    return a


@transaction.atomic
def restore_version(article, version: ArticleVersion, user) -> Article:
    return save_article(
        user,
        article,
        title_en=version.title_en,
        title_ar=version.title_ar,
        body_en=version.body_en,
        body_ar=version.body_ar,
    )


WORD = re.compile(r"[\w؀-ۿ]{3,}")


def search_articles(query, audiences=("public",), limit=3):
    """Published articles ranked by how many of the question's words they contain."""
    words = {w.lower() for w in WORD.findall(query or "")}
    if not words:
        return []
    q = Q()
    for w in words:
        q |= (
            Q(title_en__icontains=w)
            | Q(title_ar__icontains=w)
            | Q(body_en__icontains=w)
            | Q(body_ar__icontains=w)
            | Q(keywords__icontains=w)
        )
    scored = []
    for a in Article.objects.filter(status="published", audience__in=audiences).filter(q)[:50]:
        text = f"{a.title_en} {a.title_ar} {a.keywords} {a.title_en} {a.body_en} {a.body_ar}".lower()
        scored.append((sum(text.count(w) for w in words), a))
    scored.sort(key=lambda x: -x[0])
    return [a for score, a in scored[:limit] if score]


def _article_text(a, lang):
    return f"{a.title(lang)}\n{a.body(lang)[:1500]}"


# ---------------------------------------------------------------------------
# The AI engine (O-20: needs ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------
def ai_configured() -> bool:
    return bool(getattr(settings, "AI_ENABLED", False) and getattr(settings, "ANTHROPIC_API_KEY", ""))


def _history(conversation, text):
    msgs = []
    for m in list(conversation.messages.order_by("-at", "-id")[:HISTORY])[::-1]:
        role = "user" if m.role == Message.Role.VISITOR else "assistant"
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n" + m.text
        else:
            msgs.append({"role": role, "content": m.text})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    if msgs and msgs[-1]["role"] == "user":
        msgs[-1]["content"] += "\n" + text
    else:
        msgs.append({"role": "user", "content": text})
    return msgs


def run_ai(system, messages, tools, handlers, effort="low"):
    """A manual tool loop. Returns the final text, or None when the model declined or the call failed."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=45.0, max_retries=1)
    for _ in range(MAX_STEPS):
        try:
            response = client.beta.messages.create(
                model=settings.AI_MODEL,
                max_tokens=4000,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                tools=tools,
                messages=messages,
                output_config={"effort": effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIConnectionError:
            log.warning("AI provider unreachable; using the fallback engine")
            return None
        except anthropic.APIStatusError as exc:
            log.warning("AI provider error %s; using the fallback engine", exc.status_code)
            return None
        if response.stop_reason == "refusal":
            return None
        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            return text or None
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            handler = handlers.get(block.name)
            try:
                args = block.input if isinstance(block.input, dict) else json.loads(block.input or "{}")
                output = handler(**args) if handler else "Unknown tool."
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)[:8000]})
            except (TypeError, ValueError, ValidationError, PermissionDenied) as exc:
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": f"Error: {exc}", "is_error": True}
                )
        messages.append({"role": "user", "content": results})
    return None


def _tool(name, description, properties=None, required=()):
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties or {},
            "required": list(required),
            "additionalProperties": False,
        },
    }


BRANCH_PROP = {"type": "string", "enum": ["PRM", "BED", ""], "description": "PRM = Promenade, BED = Bedaya; '' = both"}


# ---------------------------------------------------------------------------
# SAQR (P5-12)
# ---------------------------------------------------------------------------
SAQR_SYSTEM = """You are SAQR, the website assistant of Elite Academy, a martial arts academy in Kuwait with two
branches: Elite Promenade (PRM, Promenade Mall, Hawalli — the Complete Fighter Program: Kajukenbo, Kickboxing and
Jiu-Jitsu in one membership) and Elite Bedaya (BED, Sabah Al Salem — choose your discipline, plus the ladies' class).

Write in the visitor's language (Arabic or English) in the One Voice tone: warm, short (2–4 sentences), confident,
never pushy. Answer only from your tools: programs, class times and prices come live from them, and policies from
the knowledge base. If you don't know, say so and offer to connect them with the team — never guess prices, times
or policies.

When the visitor wants a trial and gives a name and a mobile number, use book_trial (ask for the branch if it's
unclear). Never take payments, give refunds, approve anything, or handle complaints, injuries or cancellations:
use hand_over right away for those, when they ask for a person, or when you could not resolve their question after
two tries."""


class SaqrTools:
    def __init__(self, conversation, lang):
        self.c, self.lang = conversation, lang
        self.handoff = None
        self.trial = None

    def _rules(self):
        from apps.website.saqr import RuleEngine

        return RuleEngine()

    def get_prices(self, branch=""):
        return self._rules()._prices_text(self.lang, branch or None)

    def get_schedule(self, branch=""):
        return self._rules()._schedule_text(self.lang, branch or None)

    def get_branch(self, branch=""):
        return self._rules()._branch_text(self.lang, branch or None)

    def get_programs(self, branch=""):
        from apps.website.models import ProgramPage

        pages = ProgramPage.objects.live().public().select_related("branch")
        if branch:
            pages = pages.filter(branch__code=branch)
        return "\n".join(f"{p.branch.code}: {p.title}" for p in pages[:30]) or "No programs listed."

    def search_knowledge(self, query):
        found = search_articles(query, ("public",))
        return "\n\n".join(_article_text(a, self.lang) for a in found) or "Nothing in the knowledge base."

    def book_trial(self, name, mobile, branch, interest=""):
        from apps.leads.services import intake
        from apps.website.models import TrialRequest

        b = Branch.objects.filter(code=branch).first()
        if b is None:
            raise ValidationError("Ask which branch: Promenade (Hawalli) or Bedaya (Sabah Al Salem).")
        mobile = normalize_kuwait_mobile(mobile)
        tr = TrialRequest.objects.create(
            name=name[:120], mobile=mobile, branch=b, not_sure=True, language=self.lang, source="saqr"
        )
        intake(
            name=name,
            mobile=mobile,
            branch=b,
            source="saqr",
            interest=interest,
            language=self.lang,
            trial_request=tr,
            chat=self.c,
        )
        self.c.visitor_name, self.c.visitor_mobile, self.c.branch = name[:120], mobile, b
        self.trial = tr
        return "Trial request saved. The branch will confirm the class time on WhatsApp."

    def hand_over(self, reason):
        self.handoff = reason[:120] or "Asked for a person"
        return "Handed over to the team."

    def definitions(self):
        return [
            _tool("get_prices", "Membership prices and the trial price.", {"branch": BRANCH_PROP}, ["branch"]),
            _tool("get_schedule", "Class times from the live timetable.", {"branch": BRANCH_PROP}, ["branch"]),
            _tool(
                "get_branch",
                "What a branch offers, where it is and its opening days.",
                {"branch": BRANCH_PROP},
                ["branch"],
            ),
            _tool("get_programs", "Programs offered, per branch.", {"branch": BRANCH_PROP}, ["branch"]),
            _tool(
                "search_knowledge",
                "Search the academy's public articles (policies, trial terms, FAQs).",
                {"query": {"type": "string"}},
                ["query"],
            ),
            _tool(
                "book_trial",
                "Save a trial request once you have the visitor's name, Kuwait mobile number and branch.",
                {
                    "name": {"type": "string"},
                    "mobile": {"type": "string"},
                    "branch": {"type": "string", "enum": ["PRM", "BED"]},
                    "interest": {"type": "string", "description": "Who it's for, age, what they want."},
                },
                ["name", "mobile", "branch", "interest"],
            ),
            _tool(
                "hand_over",
                "Pass the chat to a person (complaints, refunds, injuries, cancellations, asking for a person, "
                "or two unresolved tries).",
                {"reason": {"type": "string"}},
                ["reason"],
            ),
        ]

    def handlers(self):
        return {d["name"]: getattr(self, d["name"]) for d in self.definitions()}


def _conversation_for(session_key, lang):
    key = hash_key(session_key)
    conv = (
        Conversation.objects.filter(
            channel="saqr", session_hash=key, last_at__gte=timezone.now() - datetime.timedelta(hours=6)
        )
        .order_by("-last_at")
        .first()
    )
    return conv or Conversation.objects.create(channel="saqr", session_hash=key, language=lang)


def _hand_off(conv, reason):
    if conv.handed_off_at:
        return
    conv.handed_off_at, conv.handoff_reason = timezone.now(), reason[:120]
    conv.save(update_fields=["handed_off_at", "handoff_reason"])
    text = f"SAQR hand-off waiting in the desk ({reason[:80]})."
    transaction.on_commit(lambda: notify_perm("leads.manage", text, conv.branch_id))


def saqr_message(session_key, text, lang="en") -> dict:
    """One visitor message → the reply the website chat shows (same shape as the rule engine's)."""
    from apps.website.models import SiteSettings
    from apps.website.saqr import RuleEngine

    lang = "ar" if lang == "ar" else "en"
    text = (text or "").strip()[:500]
    conv = _conversation_for(session_key, lang)
    state_key = f"saqr-state:{conv.pk}"
    state = cache.get(state_key, {})
    wa = SiteSettings.load().whatsapp_link
    handoff_reply = {
        "handoff": True,
        "link": wa,
        "link_label": L(lang, "Continue on WhatsApp", "المتابعة عبر واتساب"),
    }
    engine, reply = "rules", None
    if text and HANDOFF.search(text):
        _hand_off(conv, "Asked about a refund, cancellation, complaint or injury, or for a person")
        reply = {
            "text": L(
                lang,
                "I'm really sorry to hear that — let me get this sorted for you personally. A member of our team "
                "will take it from here.",
                "يؤسفني سماع ذلك — سيتابع معك أحد أعضاء فريقنا شخصياً.",
            ),
            **handoff_reply,
        }
    elif text and ai_configured():
        tools = SaqrTools(conv, lang)
        answer = run_ai(SAQR_SYSTEM, _history(conv, text), tools.definitions(), tools.handlers(), effort="low")
        if answer:
            engine, reply = "ai", {"text": answer}
            if tools.handoff:
                _hand_off(conv, tools.handoff)
                reply.update(handoff_reply)
            conv.save()
    if reply is None:
        reply = RuleEngine().reply(text, lang, state)
        if reply.get("handoff"):
            _hand_off(conv, "Two unresolved questions" if state.get("misses", 0) >= 2 else "Asked for a person")
    cache.set(state_key, state, 6 * 3600)
    now = timezone.now()
    if text:
        Message.objects.create(conversation=conv, role=Message.Role.VISITOR, text=text, at=now)
    Message.objects.create(conversation=conv, role=Message.Role.ASSISTANT, text=reply.get("text", ""), engine=engine)
    Conversation.objects.filter(pk=conv.pk).update(last_at=timezone.now(), language=lang)
    return reply


@transaction.atomic
def take_handoff(conv, user) -> Conversation:
    conv = Conversation.objects.select_for_update().get(pk=conv.pk)
    if not has_perm(user, "leads.manage", conv.branch_id):
        raise PermissionDenied("You cannot take SAQR hand-offs.")
    if conv.taken_at:
        raise ValidationError(f"Already taken by {conv.taken_by.full_name}.")
    conv.taken_by, conv.taken_at = user, timezone.now()
    conv.save(update_fields=["taken_by", "taken_at"])
    return conv


@transaction.atomic
def review_conversation(conv, user, ok: bool, note="") -> Conversation:
    """The spot-check (at least 3 per shift): was SAQR right? Wrong answers are fixed in the knowledge base."""
    if not has_perm(user, "leads.manage"):
        raise PermissionDenied("You cannot review SAQR conversations.")
    if not ok and not note.strip():
        raise ValidationError("Say what was wrong, so the knowledge base can be corrected.")
    conv.reviewed_by, conv.reviewed_at, conv.review_ok, conv.review_note = user, timezone.now(), ok, note.strip()[:255]
    conv.save(update_fields=["reviewed_by", "reviewed_at", "review_ok", "review_note"])
    if not ok:
        text = f"SAQR answered wrongly: {conv.review_note} — please correct the knowledge base."
        transaction.on_commit(lambda: notify_perm("kb.edit", text))
    return conv


def reviews_this_shift(user, hours=8) -> int:
    since = timezone.now() - datetime.timedelta(hours=hours)
    return Conversation.objects.filter(reviewed_by=user, reviewed_at__gte=since).count()


def purge_old_conversations(today=None) -> int:
    """SAQR chats are kept 90 days unless they became a lead."""
    cutoff = timezone.now() - datetime.timedelta(days=RETENTION_DAYS)
    old = Conversation.objects.filter(channel="saqr", last_at__lt=cutoff, leads__isnull=True)
    n = old.count()
    old.delete()
    return n


# ---------------------------------------------------------------------------
# Staff Assistant (P5-13)
# ---------------------------------------------------------------------------
STAFF_SYSTEM = """You are the Staff Assistant inside Elite Academy's staff desk (two branches: PRM = Elite Promenade,
BED = Elite Bedaya). Answer "how do I…" questions from the staff articles, and data questions only by calling the
data tools — never estimate numbers. The tools already limit answers to what this staff member may see; if a tool
says access is denied, say so plainly. Keep answers short, in the language of the question, and end with where
the answer came from (the report or article name). You are read-only: you cannot change anything."""


class StaffTools:
    def __init__(self, user, branch, lang):
        self.user, self.branch, self.lang = user, branch, lang
        self.sources = []

    def _branch(self, code):
        b = Branch.objects.filter(code=code).first() if code else self.branch
        if b is None:
            raise ValidationError("Unknown branch.")
        return b

    def _need_any(self, perms, branch):
        if not any(has_perm(self.user, p, branch.pk) for p in perms):
            raise PermissionDenied(f"You can't see this for {branch.name}.")

    def search_articles(self, query):
        found = search_articles(query, ("public", "staff"))
        self.sources += [f"Article: {a.title(self.lang)}" for a in found]
        return "\n\n".join(_article_text(a, self.lang) for a in found) or "No article found."

    def active_members(self, branch=""):
        from apps.reports.services import active_members

        b = self._branch(branch)
        self._need_any(["reports.branch", "reports.all"], b)
        data = active_members(timezone.localdate(), b, self.lang)
        lines = [f"{p['label']}: {p['total']}" for p in data["programs"]]
        self.sources.append(f"Active members report ({b.code})")
        return f"{b.name}: {data['total']} active members today.\n" + "\n".join(lines)

    def expiring_members(self, branch=""):
        from apps.renewals.services import follow_up_list

        b = self._branch(branch)
        self._need_any(["renewals.follow_up", "reports.branch", "reports.all"], b)
        rows = follow_up_list(b)
        expiring = [r for r in rows if r.state == "expiring"]
        names = ", ".join(str(r.member) for r in expiring[:15])
        self.sources.append(f"Renewals list ({b.code})")
        return (
            f"{b.name}: {len(expiring)} expiring within 5 days, "
            f"{len(rows) - len(expiring)} expired or checked in without a valid membership. {names}"
        )

    def sales_summary(self, branch="", period="this_week"):
        from apps.reports.models import week_start
        from apps.sales.models import Payment

        b = self._branch(branch)
        self._need_any(["reports.branch", "reports.all", "finance.manage"], b)
        start = week_start(timezone.localdate())
        if period == "last_week":
            start -= datetime.timedelta(days=7)
        elif period == "today":
            start = timezone.localdate()
        end = timezone.localdate() if period != "last_week" else start + datetime.timedelta(days=6)
        s0, e1 = day_range(start)[0], day_range(end)[1]
        pay = Payment.objects.filter(sale__branch=b, received_at__gte=s0, received_at__lt=e1)
        by = {m: pay.filter(method=m).aggregate(t=Sum("amount"))["t"] or 0 for m in ("knet", "card", "cash")}
        self.sources.append(f"Payments ({b.code}, {start:%d/%m}–{end:%d/%m})")
        return (
            f"{b.name} {start:%d/%m}–{end:%d/%m}: KNET {by['knet']:.3f} KD, card {by['card']:.3f} KD, "
            f"cash {by['cash']:.3f} KD, total {sum(by.values()):.3f} KD."
        )

    def leads_summary(self, branch=""):
        from apps.leads.models import Lead
        from apps.leads.services import funnel

        b = self._branch(branch)
        self._need_any(["leads.manage", "reports.all"], b)
        since = timezone.now() - datetime.timedelta(days=30)
        f = funnel(Lead.objects.filter(branch=b, created_at__gte=since))
        overdue = Lead.objects.filter(branch=b, stage__in=Lead.OPEN, next_due__lt=timezone.now()).count()
        self.sources.append(f"Leads ({b.code}, last 30 days)")
        return (
            f"{b.name}, last 30 days: {f['total']} leads, {f['trial_booked']} trials booked, {f['joined']} joined, "
            f"{f['lost']} lost; {f['open']} open ({overdue} overdue)."
        )

    def definitions(self):
        return [
            _tool(
                "search_articles",
                "Search procedures, system guides and policies.",
                {"query": {"type": "string"}},
                ["query"],
            ),
            _tool("active_members", "Active members today, by program.", {"branch": BRANCH_PROP}, ["branch"]),
            _tool("expiring_members", "Members expiring this week or expired.", {"branch": BRANCH_PROP}, ["branch"]),
            _tool(
                "sales_summary",
                "Payments by method (KNET, card, cash).",
                {"branch": BRANCH_PROP, "period": {"type": "string", "enum": ["today", "this_week", "last_week"]}},
                ["branch", "period"],
            ),
            _tool("leads_summary", "Leads and trials in the last 30 days.", {"branch": BRANCH_PROP}, ["branch"]),
        ]

    def handlers(self):
        return {d["name"]: getattr(self, d["name"]) for d in self.definitions()}


def _route(tools: StaffTools, question):
    """Keyword routing when no AI provider is set up."""
    q = question.lower()
    code = (
        "BED" if re.search(r"bedaya|بداية|\bbed\b", q) else "PRM" if re.search(r"promenade|بروميناد|\bprm\b", q) else ""
    )
    try:
        if re.search(r"active member|نشط", q):
            return tools.active_members(code)
        if re.search(r"expir|renew|ينتهي|تجديد|منتهي", q):
            return tools.expiring_members(code)
        if re.search(r"sales|knet|cash|card|revenue|مبيعات|كي نت|نقد|ايراد|إيراد", q):
            period = "last_week" if re.search(r"last week|الأسبوع الماضي|الاسبوع الماضي", q) else "this_week"
            return tools.sales_summary(code, "today" if re.search(r"today|اليوم", q) else period)
        if re.search(r"lead|trial|تجرب|عملاء محتمل", q):
            return tools.leads_summary(code)
    except (PermissionDenied, ValidationError) as exc:
        return str(exc.messages[0] if hasattr(exc, "messages") else exc)
    found = tools.search_articles(question)
    if found == "No article found.":
        return L(
            tools.lang,
            "I couldn't find that. Try asking about active members, expiring members, sales or leads, or search "
            "with different words.",
            "لم أجد ذلك. جرّب السؤال عن الأعضاء النشطين أو المنتهية اشتراكاتهم أو المبيعات أو العملاء المحتملين.",
        )
    return found


def staff_ask(user, branch, question, lang="en", conversation=None) -> tuple[Conversation, Message]:
    if not has_perm(user, "assistant.use"):
        raise PermissionDenied("You cannot use the Staff Assistant.")
    question = (question or "").strip()[:1000]
    if not question:
        raise ValidationError("Type a question.")
    conv = conversation or Conversation.objects.create(channel="staff", user=user, branch=branch, language=lang)
    tools = StaffTools(user, branch, lang)
    answer, engine = None, "rules"
    if ai_configured():
        answer = run_ai(STAFF_SYSTEM, _history(conv, question), tools.definitions(), tools.handlers(), effort="medium")
        engine = "ai" if answer else "rules"
    if not answer:
        answer = _route(tools, question)
    Message.objects.create(conversation=conv, role=Message.Role.VISITOR, text=question)
    reply = Message.objects.create(
        conversation=conv, role=Message.Role.ASSISTANT, text=answer, engine=engine, sources=sorted(set(tools.sources))
    )
    Conversation.objects.filter(pk=conv.pk).update(last_at=timezone.now())
    record_event(action="assistant_question", instance=conv, changes={"sources": reply.sources})
    return conv, reply
