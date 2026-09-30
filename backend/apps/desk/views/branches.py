"""Branches and their programs (decision P7-12): add, edit, close/reopen, and the set-up checklist."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.organization import services as org
from apps.organization.models import Branch, Discipline, Program

from ..access import L, can, desk

DAYS = [
    (0, "Saturday", "السبت"),
    (1, "Sunday", "الأحد"),
    (2, "Monday", "الاثنين"),
    (3, "Tuesday", "الثلاثاء"),
    (4, "Wednesday", "الأربعاء"),
    (5, "Thursday", "الخميس"),
    (6, "Friday", "الجمعة"),
]


def _branch_data(p):
    return {
        "name": p.get("name", ""),
        "name_ar": p.get("name_ar", ""),
        "area": p.get("area", ""),
        "area_ar": p.get("area_ar", ""),
        "address": p.get("address", ""),
        "phone": p.get("phone", ""),
        "open_days": p.getlist("open_days"),
        "positioning": p.get("positioning", ""),
        "google_review_url": p.get("google_review_url", ""),
    }


def _int(value):
    return int(value) if (value or "").strip().isdigit() else None


@desk("branches.manage")
def branches(request):
    rows = []
    for b in Branch.objects.order_by("-is_active", "name"):
        checks = org.branch_checklist(b)
        rows.append({"b": b, "done": sum(c["done"] for c in checks), "total": len(checks)})
    return render(request, "desk/branches/list.html", {"rows": rows})


@desk("branches.manage")
def branch_new(request):
    if request.method == "POST":
        branch = org.create_branch(request.user, code=request.POST.get("code", ""), **_branch_data(request.POST))
        messages.success(
            request,
            L(
                "Branch added. Work through the checklist below before it opens.",
                "أُضيف الفرع. أكمل القائمة أدناه قبل الافتتاح.",
            ),
        )
        return redirect("desk:branch", branch.pk)
    return render(request, "desk/branches/form.html", {"b": None, "days": DAYS, "open_days": [1, 2, 3, 4, 5]})


@desk("branches.manage")
def branch(request, pk):
    b = get_object_or_404(Branch, pk=pk)
    if request.method == "POST":
        p, action = request.POST, request.POST.get("action")
        if action == "edit":
            org.update_branch(request.user, b, **_branch_data(p))
            messages.success(request, L("Saved.", "تم الحفظ."))
        elif action == "close":
            org.close_branch(request.user, b, p.get("reason", ""))
            messages.success(request, L("Branch closed.", "أُغلق الفرع."))
        elif action == "reopen":
            org.reopen_branch(request.user, b)
            messages.success(request, L("Branch reopened.", "أُعيد فتح الفرع."))
        elif action == "program":
            program = Program.objects.filter(pk=p.get("program") or 0, branch=b).first()
            org.save_program(
                request.user,
                b,
                program=program,
                name=p.get("p_name", ""),
                name_ar=p.get("p_name_ar", ""),
                disciplines=list(Discipline.objects.filter(pk__in=p.getlist("disciplines"))),
                audience=p.get("audience", "any"),
                age_min=_int(p.get("age_min")),
                age_max=_int(p.get("age_max")),
                description=p.get("description", ""),
                is_active=p.get("is_active", "1") == "1",
            )
            messages.success(request, L("Program saved.", "تم حفظ البرنامج."))
            return redirect(reverse("desk:branch", args=[b.pk]) + "#programs")
        elif action == "web_page":
            org.create_branch_page(b)
            messages.success(request, L("Draft website page created.", "أُنشئت مسودة صفحة الموقع."))
        return redirect("desk:branch", b.pk)
    page = getattr(b, "web_page", None)
    checks = org.branch_checklist(b)
    for c in checks:
        if c["link"] == "programs":
            c["url"], c["switch"] = "#programs", False
        elif c["link"] == "cms":
            c["url"], c["switch"] = (f"/cms/pages/{page.pk}/edit/" if page else "/cms/"), False
        elif c["link"]:
            c["url"], c["switch"] = reverse(c["link"]), True
        else:
            c["url"], c["switch"] = "#details", False
    return render(
        request,
        "desk/branches/detail.html",
        {
            "b": b,
            "checks": checks,
            "done": sum(c["done"] for c in checks),
            "days": DAYS,
            "open_days": b.open_days,
            "programs": b.programs.prefetch_related("disciplines").order_by("-is_active", "name"),
            "disciplines": Discipline.objects.order_by("name"),
            "audiences": Program.Audience.choices,
            "blockers": org.closing_blockers(b) if b.is_active else [],
            "page": page,
            "can_cms": can(request, "cms.edit"),
        },
    )
