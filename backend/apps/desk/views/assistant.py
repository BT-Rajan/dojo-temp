"""Knowledge base, SAQR conversations (hand-offs and spot-checks) and the Staff Assistant (M16)."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.assistant import services as ai
from apps.assistant.models import Article, ArticleVersion, Conversation
from apps.leads import services as ls

from ..access import L, can, desk, lang


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------
@desk("kb.edit")
def kb(request):
    audience = request.GET.get("audience", "")
    qs = Article.objects.select_related("owner")
    if audience:
        qs = qs.filter(audience=audience)
    q = request.GET.get("q", "").strip()
    found = ai.search_articles(q, ("public", "staff"), limit=20) if q else None
    return render(
        request,
        "desk/assistant/kb.html",
        {"articles": found if found is not None else qs[:200], "audience": audience, "q": q},
    )


@desk("kb.edit")
def kb_edit(request, pk=None):
    article = get_object_or_404(Article, pk=pk) if pk else None
    if request.method == "POST":
        p = request.POST
        if p.get("restore"):
            version = get_object_or_404(ArticleVersion, pk=p["restore"], article=article)
            article = ai.restore_version(article, version, request.user)
            messages.success(
                request, L(f"Version {version.version} restored.", f"تمت استعادة النسخة {version.version}.")
            )
        else:
            article = ai.save_article(
                request.user,
                article,
                title_en=p.get("title_en", "").strip()[:160],
                title_ar=p.get("title_ar", "").strip()[:160],
                body_en=p.get("body_en", ""),
                body_ar=p.get("body_ar", ""),
                audience=p.get("audience", "staff"),
                topic=p.get("topic", "").strip()[:60],
                keywords=p.get("keywords", "").strip()[:255],
                status=p.get("status", "draft"),
            )
            messages.success(request, L("Saved.", "تم الحفظ."))
        return redirect("desk:kb_edit", pk=article.pk)
    return render(
        request,
        "desk/assistant/article.html",
        {
            "a": article,
            "versions": article.versions.select_related("saved_by")[:20] if article else [],
            "audiences": Article.Audience.choices,
        },
    )


# ---------------------------------------------------------------------------
# SAQR conversations
# ---------------------------------------------------------------------------
@desk("leads.manage")
def saqr(request):
    show = request.GET.get("show", "waiting")
    qs = Conversation.objects.filter(channel="saqr").select_related("taken_by", "reviewed_by", "branch")
    if show == "waiting":
        qs = qs.filter(handed_off_at__isnull=False, taken_at__isnull=True)
    elif show == "handoffs":
        qs = qs.filter(handed_off_at__isnull=False)
    elif show == "unreviewed":
        qs = qs.filter(reviewed_at__isnull=True)
    elif show == "wrong":
        qs = qs.filter(review_ok=False)
    return render(
        request,
        "desk/assistant/saqr.html",
        {
            "conversations": qs.prefetch_related("messages")[:80],
            "show": show,
            "reviewed": ai.reviews_this_shift(request.user),
            "ai_on": ai.ai_configured(),
        },
    )


@desk("leads.manage")
def saqr_detail(request, pk):
    conv = get_object_or_404(Conversation, pk=pk, channel="saqr")
    if request.method == "POST":
        p = request.POST
        action = p.get("action")
        if action == "take":
            ai.take_handoff(conv, request.user)
        elif action == "review":
            ai.review_conversation(conv, request.user, p.get("ok") == "1", p.get("note", ""))
            messages.success(request, L("Review saved.", "تم حفظ المراجعة."))
        elif action == "lead":
            lead = ls.intake(
                name=p.get("name") or conv.visitor_name,
                mobile=p.get("mobile") or conv.visitor_mobile,
                branch=request.branch,
                source="saqr",
                interest=p.get("interest", ""),
                language=conv.language,
                chat=conv,
                user=request.user,
                note="From a SAQR hand-off",
            )
            return redirect("desk:lead", pk=lead.pk)
        return redirect("desk:saqr_chat", pk=pk)
    return render(
        request,
        "desk/assistant/saqr_chat.html",
        {"c": conv, "chat": conv.messages.all(), "leads": conv.leads.all()},
    )


# ---------------------------------------------------------------------------
# Staff Assistant
# ---------------------------------------------------------------------------
@desk("assistant.use")
def assistant(request):
    conv_id = request.session.get("assistant_conversation")
    conv = Conversation.objects.filter(pk=conv_id or 0, channel="staff", user=request.user).first()
    if request.method == "POST":
        if request.POST.get("action") == "new":
            request.session.pop("assistant_conversation", None)
            return redirect("desk:assistant")
        conv, _ = ai.staff_ask(request.user, request.branch, request.POST.get("question", ""), lang(), conv)
        request.session["assistant_conversation"] = conv.pk
        return redirect("desk:assistant")
    return render(
        request,
        "desk/assistant/ask.html",
        {"chat": conv.messages.all() if conv else [], "ai_on": ai.ai_configured(), "can_kb": can(request, "kb.edit")},
    )
