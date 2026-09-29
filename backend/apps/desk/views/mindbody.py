"""Replacing Mindbody (M18): imports with dry runs, pricing-option mapping, parallel run, cut-over checklist."""

import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.mindbody import services as mb
from apps.mindbody.models import CutoverStep, ImportBatch, OptionMap, ParallelRunCheck
from apps.organization.models import Branch, PricingOption
from apps.reports.models import week_start

from ..access import L, desk
from .ops import _date
from .sales import _money

KIND_HELP = {
    "clients": (
        "Mindbody: Reports › Client Lists (export with ID, name, birth date, gender, mobile, email, home location).",
        "مايندبودي: التقارير › قوائم العملاء.",
    ),
    "relationships": (
        "Mindbody: Client relationships export (client ID, related client ID, relationship).",
        "مايندبودي: تصدير علاقات العملاء.",
    ),
    "inventory": (
        "Mindbody: Retail › Inventory On Hand, one file per location.",
        "مايندبودي: المخزون المتوفر لكل فرع.",
    ),
    "memberships": (
        "Mindbody: Pricing Option Expirations (active options, wide date range) per location.",
        "مايندبودي: انتهاء خيارات الأسعار لكل فرع.",
    ),
    "visits": (
        "Mindbody: Visit History / Attendance with client ID, date, time, class and location.",
        "مايندبودي: سجل الزيارات.",
    ),
    "sales": (
        "Mindbody: Sales report by item with sale ID, date, client ID, item, total and payment method.",
        "مايندبودي: تقرير المبيعات.",
    ),
}


@desk("data.import")
def imports(request):
    if request.method == "POST":
        batch = mb.create_batch(
            request.user,
            request.POST.get("kind", ""),
            request.FILES.get("file"),
            Branch.objects.filter(pk=request.POST.get("branch") or 0).first(),
        )
        messages.info(
            request,
            L(
                "Dry run done — nothing has changed yet. Read the report, then apply.",
                "تم التشغيل التجريبي ولم يتغير شيء. راجع التقرير ثم طبّق.",
            ),
        )
        return redirect("desk:import_batch", pk=batch.pk)
    kinds = [(k, ImportBatch.Kind(k).label, KIND_HELP[k]) for k in ImportBatch.ORDER]
    return render(
        request,
        "desk/mindbody/imports.html",
        {
            "kinds": kinds,
            "branches": Branch.objects.filter(is_active=True),
            "batches": ImportBatch.objects.select_related("branch", "created_by", "applied_by")[:40],
            "unmapped": mb.unmapped_options().count(),
        },
    )


@desk("data.import")
def import_batch(request, pk):
    batch = get_object_or_404(ImportBatch.objects.select_related("branch", "created_by", "applied_by"), pk=pk)
    if request.method == "POST":
        if request.POST.get("action") == "apply":
            batch = mb.run(batch, request.user, apply=True)
            messages.success(request, L("Applied.", "تم التطبيق."))
        else:
            batch = mb.run(batch, request.user, apply=False)
            messages.info(request, L("Checked again — nothing changed.", "تمت إعادة الفحص دون تغيير."))
        return redirect("desk:import_batch", pk=pk)
    counts = (batch.summary or {}).get("counts", {})
    return render(
        request,
        "desk/mindbody/batch.html",
        {
            "b": batch,
            "counts": sorted(counts.items()),
            "blocking": [i for i in batch.issues if i["level"] == "map"],
            "skips": [i for i in batch.issues if i["level"] == "skip"],
            "warnings": [i for i in batch.issues if i["level"] == "warn"],
        },
    )


@desk("data.import")
def option_map(request):
    if request.method == "POST":
        for m in OptionMap.objects.all():
            value = request.POST.get(f"map_{m.pk}")
            if value is None:
                continue
            if value == "skip":
                mb.map_option(m, request.user, skip=True)
            elif value:
                mb.map_option(m, request.user, PricingOption.objects.filter(pk=value).first())
        messages.success(
            request, L("Mapping saved. Run the memberships file again.", "تم حفظ الربط. أعد تشغيل ملف الاشتراكات.")
        )
        return redirect("desk:option_map")
    maps = OptionMap.objects.select_related("branch", "pricing_option").order_by(
        "skip", "pricing_option_id", "branch__code", "mindbody_name"
    )
    options = {}
    for o in PricingOption.objects.filter(is_active=True).order_by("kind", "name"):
        options.setdefault(o.branch_id, []).append(o)
    return render(request, "desk/mindbody/options.html", {"maps": [(m, options.get(m.branch_id, [])) for m in maps]})


@desk("data.import")
def parallel_run(request):
    if request.method == "POST":
        p = request.POST
        branch = get_object_or_404(Branch, pk=p.get("branch") or 0)
        start = week_start(_date(p.get("week"), datetime.date.today()))
        mb.record_check(
            branch,
            start,
            request.user,
            knet=_money(p.get("knet")),
            card=_money(p.get("card")),
            cash=_money(p.get("cash")),
            active=int(p.get("active") or 0),
            explanation=p.get("explanation", ""),
        )
        return redirect("desk:parallel_run")
    checks = [(c, mb.differences(c)) for c in ParallelRunCheck.objects.select_related("branch")[:30]]
    return render(
        request,
        "desk/mindbody/parallel.html",
        {
            "checks": checks,
            "branches": Branch.objects.filter(is_active=True),
            "last_week": week_start(datetime.date.today()) - datetime.timedelta(days=7),
        },
    )


@desk("data.import")
def cutover(request):
    mb.ensure_cutover_steps()
    if request.method == "POST":
        step = get_object_or_404(CutoverStep, pk=request.POST.get("step") or 0)
        mb.tick_step(step, request.user, done=request.POST.get("done") == "1", note=request.POST.get("note", ""))
        return redirect("desk:cutover")
    steps = CutoverStep.objects.select_related("done_by")
    return render(request, "desk/mindbody/cutover.html", {"steps": steps, "done": sum(1 for s in steps if s.done_at)})
