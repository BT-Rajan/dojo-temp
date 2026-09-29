"""Message log and wording overrides (M17, decisions P6-7 and P6-9)."""

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render

from apps.notifications import services as ns
from apps.notifications.models import Category, MessageLog, MessageTemplate

from ..access import L, can, desk


@desk(any_of=["messages.view", "marketing.approve"])
def message_log(request):
    qs = MessageLog.objects.select_related("member")
    category = request.GET.get("category", "")
    if category:
        qs = qs.filter(category=category)
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(to__icontains=q) | Q(kind__icontains=q))
    return render(
        request,
        "desk/messages/log.html",
        {
            "logs": qs[:200] if can(request, "messages.view") else [],
            "categories": Category.choices,
            "statuses": MessageLog.Status.choices,
            "category": category,
            "status": status,
            "q": q,
            "can_log": can(request, "messages.view"),
        },
    )


@desk(any_of=["marketing.approve", "messages.view"])
def message_templates(request):
    editable = can(request, "marketing.approve")
    if request.method == "POST":
        key = request.POST.get("key", "")
        if request.POST.get("action") == "reset":
            ns.reset_template(request.user, key)
        else:
            ns.save_template(request.user, key, request.POST.get("text_en", ""), request.POST.get("text_ar", ""))
        messages.success(request, L("Wording saved.", "تم حفظ الصياغة."))
        return redirect("desk:message_templates")
    overrides = {t.key: t for t in MessageTemplate.objects.all()}
    rows = []
    for key, (en, ar) in ns.DEFAULTS.items():
        o = overrides.get(key)
        rows.append(
            {
                "key": key,
                "label": ns.LABELS.get(key, key),
                "en": o.text_en if o else en,
                "ar": o.text_ar if o else ar,
                "custom": o is not None,
                "fields": ", ".join("{" + f + "}" for f in sorted(ns._fields(en))),
            }
        )
    return render(request, "desk/messages/templates.html", {"rows": rows, "editable": editable})
