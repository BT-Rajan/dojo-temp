"""
Quarterly Business Report — EA-OPS-RPT-01 (EA-OPS-PROC-01 §6; decisions P7-8 to P7-10).

All 11 sections, each figure for Promenade, Bedaya and Combined, built from the same live data as the weekly reports
(so no figure is new to the OM). The OM writes sections 1 and 2 and a comment per section, submits within 15 days of
quarter end, and the CEO approves. The figures are frozen when submitted.

Rules from the procedure: headline sales and the income statement's trading income must agree or the difference is
explained; the income statement is headed "for the quarter ended"; active members use the business-rule definition.
"""

import calendar
import datetime
from collections import Counter, defaultdict
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, F, Sum
from django.utils import timezone

from apps.audit.services import record_event
from apps.rbac.services import has_perm, users_with_perm

from .models import QuarterlyReport

ZERO = Decimal("0.000")
ALL = "ALL"

SECTIONS = [
    (1, "Management Summary", "ملخص الإدارة"),
    (2, "Next Quarter Strategy", "استراتيجية الربع القادم"),
    (3, "Business Overview (KPIs)", "نظرة عامة على الأعمال (مؤشرات الأداء)"),
    (4, "Sales Analysis", "تحليل المبيعات"),
    (5, "Capacity Analysis", "تحليل الطاقة الاستيعابية"),
    (6, "Footfall", "الزيارات"),
    (7, "New Clients", "العملاء الجدد"),
    (8, "Renewals & Churn", "التجديدات والمغادرة"),
    (9, "Incidents & Complaints", "الحوادث والشكاوى"),
    (10, "Inventory", "المخزون"),
    (11, "Income Statement", "قائمة الدخل"),
]


# ---------------------------------------------------------------------------
# Quarters
# ---------------------------------------------------------------------------
def quarter_start(day) -> datetime.date:
    return datetime.date(day.year, (day.month - 1) // 3 * 3 + 1, 1)


def quarter_end(start) -> datetime.date:
    m = start.month + 2
    return datetime.date(start.year, m, calendar.monthrange(start.year, m)[1])


def previous_quarter(start) -> datetime.date:
    return quarter_start(start - datetime.timedelta(days=1))


def months_of(start) -> list[tuple[datetime.date, datetime.date]]:
    out = []
    for i in range(3):
        m0 = datetime.date(start.year, start.month + i, 1)
        out.append((m0, m0.replace(day=calendar.monthrange(m0.year, m0.month)[1])))
    return out


def last_finished_quarter(today=None) -> datetime.date:
    return previous_quarter(quarter_start(today or timezone.localdate()))


def label(start) -> str:
    return f"Q{(start.month - 1) // 3 + 1} {start.year}"


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def _branches():
    from apps.organization.models import Branch

    return list(Branch.objects.filter(is_active=True).order_by("-code"))  # PRM, BED


def _per(branches, fn):
    out = {b.code: fn(b) for b in branches}
    out[ALL] = fn(None)
    return out


def _pct(a, b):
    return round(a * 100 / b, 1) if b else None


def _change(now, before):
    return {k: (_pct(now[k] - before[k], before[k]) if before.get(k) else None) for k in now}


def build(start) -> dict:
    from apps.classes.models import Attendance, ClassSession
    from apps.finance.services import PRODUCTS, income_statement
    from apps.inventory.models import Receipt, ReceiptLine, StockCountLine, StockMovement
    from apps.operations.models import Complaint, Incident
    from apps.renewals.models import FollowUp
    from apps.reports.services import _range, _week_measures, active_memberships
    from apps.sales.models import Sale, SaleLine

    end = quarter_end(start)
    prev = previous_quarter(start)
    prev_end = quarter_end(prev)
    months = months_of(start)
    prev_months = months_of(prev)
    branches = _branches()
    today = timezone.localdate()

    def f(branch, /, **kw):  # a filter on branch when one is given
        return kw if branch is not None else {}

    def sales(a, z, b, products=None):
        s0, e1 = _range(a, z)
        qs = SaleLine.objects.filter(sale__kind=Sale.Kind.SALE, sale__created_at__gte=s0, sale__created_at__lt=e1)
        if b is not None:
            qs = qs.filter(sale__branch=b)
        if products is True:
            qs = qs.filter(category__in=PRODUCTS)
        elif products is False:
            qs = qs.exclude(category__in=PRODUCTS)
        return qs.aggregate(t=Sum("line_total"))["t"] or ZERO

    def visits(a, z, b):
        return Attendance.objects.filter(session__date__range=(a, z), **f(b, session__branch=b)).count()

    def seats(a, z, b):
        return (
            ClassSession.objects.filter(
                date__range=(a, min(z, today)), status="scheduled", kind="class", **f(b, branch=b)
            ).aggregate(t=Sum("capacity"))["t"]
            or 0
        )

    def active(day, b):
        return active_memberships(day, b).values("member_id").distinct().count()

    def measures(a, z, b):
        if b is not None:
            return _week_measures(b, a, z)
        tot = defaultdict(int)
        for br in branches:
            for k, v in _week_measures(br, a, z).items():
                tot[k] += v
        return dict(tot)

    q_measures = _per(branches, lambda b: measures(start, end, b))
    month_measures = [_per(branches, lambda b, a=a, z=z: measures(a, z, b)) for a, z in months]

    # 3 — KPIs
    q_visits = _per(branches, lambda b: visits(start, end, b))
    q_seats = _per(branches, lambda b: seats(start, end, b))
    kpi = {
        "active": _per(branches, lambda b: active(end, b)),
        "sales": _per(branches, lambda b: sales(start, end, b)),
        "new": {k: v["new"] for k, v in q_measures.items()},
        "visits": q_visits,
        "utilisation": {k: _pct(q_visits[k], q_seats[k]) for k in q_visits},
    }

    # 4 — Sales analysis
    sales_months = [
        {
            "month": a,
            "services": _per(branches, lambda b, a=a, z=z: sales(a, z, b, products=False)),
            "products": _per(branches, lambda b, a=a, z=z: sales(a, z, b, products=True)),
        }
        for a, z in months
    ]
    q_products = _per(branches, lambda b: sales(start, end, b, products=True))
    prev_sales = _per(branches, lambda b: sales(prev, prev_end, b))
    sales_block = {
        "months": sales_months,
        "total": kpi["sales"],
        "products": q_products,
        "product_share": {k: _pct(q_products[k], kpi["sales"][k]) for k in q_products},
        "prev_total": prev_sales,
        "change": _change(kpi["sales"], prev_sales),
    }

    # 5 — Capacity
    weeks = Decimal((min(end, today) - start).days + 1) / 7 if today >= start else Decimal(1)
    capacity = {
        "seats": q_seats,
        "weekly": {k: round(Decimal(v) / max(weeks, Decimal(1))) for k, v in q_seats.items()},
        "active": kpi["active"],
        "utilisation": kpi["utilisation"],
    }

    # 6 — Footfall
    foot_months = [_per(branches, lambda b, a=a, z=z: visits(a, z, b)) for a, z in months]
    foot_prev = [_per(branches, lambda b, a=a, z=z: visits(a, z, b)) for a, z in prev_months]
    prev_visits = _per(branches, lambda b: visits(prev, prev_end, b))
    footfall = {
        "months": [{"month": m[0], "visits": v} for m, v in zip(months, foot_months, strict=True)],
        "prev_months": [{"month": m[0], "visits": v} for m, v in zip(prev_months, foot_prev, strict=True)],
        "total": q_visits,
        "prev_total": prev_visits,
        "change": _change(q_visits, prev_visits),
    }

    # 7 — New clients
    new_clients = {
        "months": [
            {"month": m[0], "new": {k: v["new"] for k, v in mm.items()}}
            for m, mm in zip(months, month_measures, strict=True)
        ],
        "trials_attended": {k: v["trials_attended"] for k, v in q_measures.items()},
        "converted": {k: v["trials_converted"] for k, v in q_measures.items()},
        "rate": {k: _pct(v["trials_converted"], v["trials_attended"]) for k, v in q_measures.items()},
    }

    # 8 — Renewals & churn
    s0, e1 = _range(start, end)
    reasons = Counter(
        (r or "—").strip().capitalize()
        for r in FollowUp.objects.filter(outcome="L", created_at__gte=s0, created_at__lt=e1).values_list(
            "leaving_reason", flat=True
        )
    )
    renewals = {
        "renewals": {k: v["renewals"] for k, v in q_measures.items()},
        "lost": {k: v["lost"] for k, v in q_measures.items()},
        "rate": {k: _pct(v["renewals"], v["renewals"] + v["lost"]) for k, v in q_measures.items()},
        "reasons": reasons.most_common(6),
    }

    # 9 — Incidents & complaints
    incidents = Incident.objects.filter(occurred_at__gte=s0, occurred_at__lt=e1)
    complaints = Complaint.objects.filter(received_at__gte=s0, received_at__lt=e1)

    def by(qs, field, choices, branch_field="branch"):
        return {
            code: _per(branches, lambda b, code=code: qs.filter(**{field: code}, **f(b, **{branch_field: b})).count())
            for code, _ in choices
        }

    repeat_members = (
        incidents.exclude(member__isnull=True).values("member_id").annotate(n=Count("id")).filter(n__gte=2).count()
    )
    repeat_complainants = (
        complaints.exclude(member__isnull=True).values("member_id").annotate(n=Count("id")).filter(n__gte=2).count()
    )
    incidents_block = {
        "incidents": by(incidents, "kind", Incident.Kind.choices),
        "incidents_open": _per(branches, lambda b: incidents.filter(status="open", **f(b, branch=b)).count()),
        "complaints": by(complaints, "category", Complaint.Category.choices),
        "complaints_open": _per(branches, lambda b: complaints.filter(status="open", **f(b, branch=b)).count()),
        "repeat_members": repeat_members,
        "repeat_complainants": repeat_complainants,
    }

    # 10 — Inventory
    count_lines = StockCountLine.objects.filter(
        count__month__range=(start, end), count__status="approved", adjusted_by__isnull=False
    ).exclude(adjusted_by=0)
    moves = StockMovement.objects.filter(kind__in=["count", "adjust"], created_at__gte=s0, created_at__lt=e1)
    receipts = Receipt.objects.filter(received_on__range=(start, end))
    inventory = {
        "count_lines": _per(branches, lambda b: count_lines.filter(**f(b, count__branch=b)).count()),
        "count_units": _per(
            branches,
            lambda b: sum(
                abs(x) for x in count_lines.filter(**f(b, count__branch=b)).values_list("adjusted_by", flat=True)
            ),
        ),
        "adjustments": _per(branches, lambda b: moves.filter(**f(b, branch=b)).count()),
        "receipts": _per(branches, lambda b: receipts.filter(**f(b, branch=b)).count()),
        "receipt_value": _per(
            branches,
            lambda b: (
                ReceiptLine.objects.filter(receipt__in=receipts.filter(**f(b, branch=b))).aggregate(
                    t=Sum(F("received_quantity") * F("unit_cost"))
                )["t"]
                or ZERO
            ),
        ),
    }

    # 11 — Income statement, by month and for the quarter
    lines = (
        "services",
        "products",
        "refunds",
        "trading_income",
        "total_expenses",
        "payroll",
        "purchases",
        "net_income",
    )

    def statement(a, z):
        per = _per(branches, lambda b: income_statement(a, z, b))
        return {line: {k: v[line] for k, v in per.items()} for line in lines}, per[ALL]

    month_statements = []
    for a, z in months:
        rows, _ = statement(a, z)
        month_statements.append({"month": a, "rows": rows})
    q_rows, q_all = statement(start, end)
    income = {
        "months": month_statements,
        "quarter": q_rows,
        "headline": q_all["headline_sales"],
        "trading": q_all["trading_income"],
        "difference": q_all["difference"],
        "unverified": q_all["unverified_weeks"],
    }

    return {
        "start": start,
        "end": end,
        "prev_start": prev,
        "label": label(start),
        "cols": [b.code for b in branches] + [ALL],
        "col_names": {b.code: {"en": b.name, "ar": b.name_ar or b.name} for b in branches}
        | {ALL: {"en": "Combined", "ar": "المجموع"}},
        "kpi": kpi,
        "sales": sales_block,
        "capacity": capacity,
        "footfall": footfall,
        "new_clients": new_clients,
        "renewals": renewals,
        "incidents": incidents_block,
        "inventory": inventory,
        "income": income,
    }


# ---------------------------------------------------------------------------
# Figures → a document (desk page, PDF and Excel use the same blocks)
# ---------------------------------------------------------------------------
INCIDENT_AR = {"injury": "إصابة", "hazard": "خطر سلامة", "conduct": "سلوك", "other": "أخرى"}
COMPLAINT_AR = {
    "money": "مالية أو فواتير",
    "refund": "استرداد",
    "staff": "سلوك موظف",
    "safety": "سلامة",
    "leaving": "تهديد بالمغادرة",
    "classes": "الحصص أو الجدول",
    "facility": "المرفق",
    "other": "أخرى",
}
INCOME_LINES = [
    ("services", "Services", "الخدمات"),
    ("products", "Products (equipment)", "المنتجات (المعدات)"),
    ("refunds", "Refunds", "المبالغ المستردة"),
    ("trading_income", "Trading income", "الإيراد التشغيلي"),
    ("total_expenses", "Branch expenses", "مصروفات الفروع"),
    ("payroll", "Salaries and wages", "الرواتب والأجور"),
    ("purchases", "Purchases", "المشتريات"),
    ("net_income", "Net income", "صافي الدخل"),
]


def _date(v):
    return datetime.date.fromisoformat(v) if isinstance(v, str) else v


def _fmt(v, pct=False):
    if v is None or v == "":
        return "—"
    if pct:
        return f"{v}%"
    return v


def document(data, report=None, lang="en") -> dict:
    """RPT-01 as blocks: ("section", n, title), ("heading", text), ("text", text), ("table", header, rows)."""

    def t(en, ar):
        return ar if lang == "ar" else en

    cols = data["cols"]
    head = [t("Measure", "المؤشر")] + [data["col_names"][c][lang] for c in cols]

    def row(label, values, pct=False):
        return [label] + [_fmt(values.get(c), pct) for c in cols]

    def month_name(v):
        return _date(v).strftime("%b %Y")

    comments = (report.comments if report else {}) or {}
    blocks = []

    def section(n):
        en, ar = SECTIONS[n - 1][1], SECTIONS[n - 1][2]
        blocks.append(("section", n, f"{n}. {t(en, ar)}"))

    def comment(n):
        text = comments.get(str(n), "")
        if text:
            blocks.append(("text", t("OM comment: ", "تعليق مدير العمليات: ") + text))

    section(1)
    blocks.append(("text", (report.summary if report else "") or t("To be written by the OM.", "يكتبه مدير العمليات.")))
    section(2)
    blocks.append(
        (
            "text",
            (report.strategy if report else "") or t("To be written with the function leads.", "يُكتب مع قادة الأقسام."),
        )
    )

    section(3)
    k = data["kpi"]
    blocks.append(
        (
            "table",
            head,
            [
                row(t("Active members at quarter end", "الأعضاء النشطون في نهاية الربع"), k["active"]),
                row(t("Total sales (KD)", "إجمالي المبيعات (د.ك)"), k["sales"]),
                row(t("New members", "أعضاء جدد"), k["new"]),
                row(t("Visits", "الزيارات"), k["visits"]),
                row(t("Average capacity utilisation", "متوسط استخدام الطاقة"), k["utilisation"], pct=True),
            ],
        )
    )
    comment(3)

    section(4)
    s = data["sales"]
    rows = []
    for m in s["months"]:
        rows.append(row(t("Services — ", "الخدمات — ") + month_name(m["month"]), m["services"]))
        rows.append(row(t("Products — ", "المنتجات — ") + month_name(m["month"]), m["products"]))
    rows += [
        row(t("Quarter total", "إجمالي الربع"), s["total"]),
        row(t("Product share of revenue", "حصة المنتجات من الإيراد"), s["product_share"], pct=True),
        row(t("Previous quarter", "الربع السابق"), s["prev_total"]),
        row(t("Change vs previous quarter", "التغير عن الربع السابق"), s["change"], pct=True),
    ]
    blocks.append(("table", head, rows))
    comment(4)

    section(5)
    c = data["capacity"]
    blocks.append(
        (
            "table",
            head,
            [
                row(t("Class places offered in the quarter", "المقاعد المتاحة في الربع"), c["seats"]),
                row(t("Places per week", "المقاعد أسبوعياً"), c["weekly"]),
                row(t("Active members", "الأعضاء النشطون"), c["active"]),
                row(t("Utilisation", "نسبة الاستخدام"), c["utilisation"], pct=True),
            ],
        )
    )
    comment(5)

    section(6)
    f = data["footfall"]
    rows = [row(month_name(m["month"]), m["visits"]) for m in f["months"]]
    rows += [
        row(t("Previous quarter — ", "الربع السابق — ") + month_name(m["month"]), m["visits"]) for m in f["prev_months"]
    ]
    rows += [
        row(t("Quarter total", "إجمالي الربع"), f["total"]),
        row(t("Previous quarter total", "إجمالي الربع السابق"), f["prev_total"]),
        row(t("Change", "التغير"), f["change"], pct=True),
    ]
    blocks.append(("table", head, rows))
    comment(6)

    section(7)
    n = data["new_clients"]
    rows = [row(t("New members — ", "أعضاء جدد — ") + month_name(m["month"]), m["new"]) for m in n["months"]]
    rows += [
        row(t("Trials attended", "تجارب حضرت"), n["trials_attended"]),
        row(t("Joined within 14 days", "اشتركوا خلال 14 يوماً"), n["converted"]),
        row(t("Trial conversion rate", "نسبة تحويل التجارب"), n["rate"], pct=True),
    ]
    blocks.append(("table", head, rows))
    comment(7)

    section(8)
    r = data["renewals"]
    blocks.append(
        (
            "table",
            head,
            [
                row(t("Renewals", "التجديدات"), r["renewals"]),
                row(t("Members lost", "الأعضاء المفقودون"), r["lost"]),
                row(t("Renewal rate", "نسبة التجديد"), r["rate"], pct=True),
            ],
        )
    )
    if r["reasons"]:
        blocks.append(("heading", t("Main reasons for leaving", "أهم أسباب المغادرة")))
        blocks.append(("table", [t("Reason", "السبب"), t("Members", "الأعضاء")], [list(x) for x in r["reasons"]]))
    comment(8)

    section(9)
    i = data["incidents"]
    rows = [
        row(t(label_en, INCIDENT_AR.get(code, label_en)), i["incidents"][code])
        for code, label_en in _choices("incident")
    ]
    rows.append(row(t("Incidents still open", "حوادث ما زالت مفتوحة"), i["incidents_open"]))
    rows += [
        row(t("Complaint: ", "شكوى: ") + t(label_en, COMPLAINT_AR.get(code, label_en)), i["complaints"][code])
        for code, label_en in _choices("complaint")
        if any(i["complaints"][code].values())
    ]
    rows.append(row(t("Complaints still open", "شكاوى ما زالت مفتوحة"), i["complaints_open"]))
    blocks.append(("table", head, rows))
    blocks.append(
        (
            "text",
            t("Repeat issues: ", "مشكلات متكررة: ")
            + t(
                f"{i['repeat_members']} member(s) with 2+ incidents; {i['repeat_complainants']} with 2+ complaints.",
                f"{i['repeat_members']} عضو بحادثتين أو أكثر؛ {i['repeat_complainants']} بشكويين أو أكثر.",
            ),
        )
    )
    comment(9)

    section(10)
    v = data["inventory"]
    blocks.append(
        (
            "table",
            head,
            [
                row(t("Count lines corrected", "بنود جرد مصححة"), v["count_lines"]),
                row(t("Units corrected (±)", "وحدات مصححة (±)"), v["count_units"]),
                row(t("Stock corrections approved", "تصحيحات مخزون معتمدة"), v["adjustments"]),
                row(t("Vendor deliveries received", "توريدات مستلمة"), v["receipts"]),
                row(t("Value received (KD, landed)", "قيمة المستلم (د.ك)"), v["receipt_value"]),
            ],
        )
    )
    comment(10)

    section(11)
    inc = data["income"]
    end = _date(data["end"])
    blocks.append(
        ("heading", t("Income statement for the quarter ended ", "قائمة الدخل للربع المنتهي في ") + f"{end:%d %B %Y}")
    )
    blocks.append(("table", head, [row(t(en, ar), inc["quarter"][key]) for key, en, ar in INCOME_LINES]))
    for m in inc["months"]:
        blocks.append(("heading", month_name(m["month"])))
        blocks.append(("table", head, [row(t(en, ar), m["rows"][key]) for key, en, ar in INCOME_LINES]))
    blocks.append(
        (
            "table",
            [t("Sales check", "مطابقة المبيعات"), t("KD", "د.ك")],
            [
                [
                    t("Headline sales (verified weekly reports)", "المبيعات المعلنة (التقارير الأسبوعية)"),
                    inc["headline"],
                ],
                [t("Trading income", "الإيراد التشغيلي"), inc["trading"]],
                [t("Difference", "الفرق"), inc["difference"]],
            ],
        )
    )
    if inc["unverified"]:
        blocks.append(("text", t("Weeks not verified: ", "أسابيع غير مؤكدة: ") + ", ".join(inc["unverified"])))
    if report and report.difference_note:
        blocks.append(("text", t("Explanation of the difference: ", "تفسير الفرق: ") + report.difference_note))
    comment(11)

    if report is not None:
        sign = [t("Prepared by (Operations Manager)", "أعدّه (مدير العمليات)") + f": {report.prepared_by.full_name}"]
        if report.submitted_at:
            sign[0] += f" · {timezone.localtime(report.submitted_at):%d/%m/%Y}"
        if report.approved_by:
            sign.append(
                t("Approved by (CEO)", "اعتمده (الرئيس التنفيذي)")
                + f": {report.approved_by.full_name} · {timezone.localtime(report.approved_at):%d/%m/%Y}"
            )
        blocks += [("text", x) for x in sign]

    start = _date(data["start"])
    return {
        "title": t("Quarterly Business Report", "تقرير الأعمال الربع سنوي") + f" — {data['label']}",
        "subtitle": (f"{report.reference} · " if report else "")
        + t("Promenade, Bedaya and Combined · ", "بروميناد وبداية والمجموع · ")
        + f"{start:%d/%m/%Y} – {end:%d/%m/%Y}",
        "sheet": "RPT-01",
        "blocks": blocks,
    }


def _choices(which):
    from apps.operations.models import Complaint, Incident

    return Incident.Kind.choices if which == "incident" else Complaint.Category.choices


def export_doc(doc) -> dict:
    """The export writer knows heading/text/table; sections become headings."""
    blocks = [("heading", b[2]) if b[0] == "section" else b for b in doc["blocks"]]
    return {**doc, "blocks": blocks}


# ---------------------------------------------------------------------------
# Prepare → submit → approve
# ---------------------------------------------------------------------------
@transaction.atomic
def open_report(user, start) -> QuarterlyReport:
    if not has_perm(user, "mgmt.qbr"):
        raise PermissionDenied("The Operations Manager prepares the Quarterly Business Report.")
    start = quarter_start(start)
    if quarter_end(start) >= timezone.localdate():
        raise ValidationError("The report is prepared once the quarter has ended.")
    report, created = QuarterlyReport.objects.get_or_create(
        quarter_start=start,
        defaults={
            "reference": f"RPT-01-{start.year}-Q{(start.month - 1) // 3 + 1}",
            "prepared_by": user,
            "created_by": user,
        },
    )
    if created:
        record_event(action="quarterly_report_opened", instance=report)
    return report


def _editable(user, report):
    if not has_perm(user, "mgmt.qbr"):
        raise PermissionDenied("The Operations Manager prepares the Quarterly Business Report.")
    if report.status not in (QuarterlyReport.Status.DRAFT, QuarterlyReport.Status.RETURNED):
        raise ValidationError("The report has been submitted; it can't be changed.")


@transaction.atomic
def save_text(user, report, *, summary, strategy, comments, difference_note="") -> QuarterlyReport:
    report = QuarterlyReport.objects.select_for_update().get(pk=report.pk)
    _editable(user, report)
    report.summary, report.strategy = summary.strip(), strategy.strip()
    report.comments = {str(k): v.strip() for k, v in comments.items() if v and v.strip()}
    report.difference_note = difference_note.strip()
    report.prepared_by, report.updated_by = user, user
    report.save()
    return report


@transaction.atomic
def submit(user, report) -> QuarterlyReport:
    from apps.reports.services import jsonable

    report = QuarterlyReport.objects.select_for_update().get(pk=report.pk)
    _editable(user, report)
    if not report.summary.strip() or not report.strategy.strip():
        raise ValidationError("Write the management summary (1) and the next-quarter strategy (2).")
    data = build(report.quarter_start)
    inc = data["income"]
    if (inc["difference"] != 0 or inc["unverified"]) and not report.difference_note.strip():
        raise ValidationError(
            "Headline sales and trading income differ (or some weeks are not verified): explain the difference."
        )
    report.data = jsonable(data)
    report.status, report.submitted_at, report.return_note = QuarterlyReport.Status.SUBMITTED, timezone.now(), ""
    report.prepared_by, report.updated_by = user, user
    report.save()
    record_event(action="quarterly_report_submitted", instance=report)
    from .services import _tell

    _tell(
        [u for u in users_with_perm("mgmt.approve") if u.pk != user.pk],
        f"The Quarterly Business Report {report.label} ({report.reference}) is waiting for your approval.",
    )
    return report


@transaction.atomic
def approve(user, report) -> QuarterlyReport:
    if not has_perm(user, "mgmt.approve"):
        raise PermissionDenied("The CEO approves the Quarterly Business Report.")
    report = QuarterlyReport.objects.select_for_update().get(pk=report.pk)
    if report.status != QuarterlyReport.Status.SUBMITTED:
        raise ValidationError("The report isn't waiting for approval.")
    if report.prepared_by_id == user.pk:
        raise PermissionDenied("Someone else approves a report you prepared.")
    report.status, report.approved_by, report.approved_at = QuarterlyReport.Status.APPROVED, user, timezone.now()
    report.updated_by = user
    report.save()
    record_event(action="quarterly_report_approved", instance=report)
    from .services import _tell

    _tell([report.prepared_by], f"The Quarterly Business Report {report.label} was approved.")
    return report


@transaction.atomic
def return_report(user, report, note) -> QuarterlyReport:
    if not has_perm(user, "mgmt.approve"):
        raise PermissionDenied("The CEO approves the Quarterly Business Report.")
    report = QuarterlyReport.objects.select_for_update().get(pk=report.pk)
    if report.status != QuarterlyReport.Status.SUBMITTED:
        raise ValidationError("The report isn't waiting for approval.")
    if not (note or "").strip():
        raise ValidationError("Say what needs changing.")
    report.status, report.return_note, report.updated_by = QuarterlyReport.Status.RETURNED, note.strip()[:255], user
    report.save()
    from .services import _tell

    _tell([report.prepared_by], f"The Quarterly Business Report {report.label} was returned: {note.strip()}")
    return report


def figures(report) -> dict:
    """Frozen figures once submitted, live ones while in draft."""
    if report.status in (QuarterlyReport.Status.SUBMITTED, QuarterlyReport.Status.APPROVED) and report.data:
        return report.data
    return build(report.quarter_start)


def remind_quarterly(today=None) -> int:
    """Reminds the OM 1, 10 and 14 days after quarter end, on the due day and every day after it."""
    today = today or timezone.localdate()
    start = last_finished_quarter(today)
    days = (today - quarter_end(start)).days
    report = QuarterlyReport.objects.filter(quarter_start=start).first()
    if report is not None and report.status in (QuarterlyReport.Status.SUBMITTED, QuarterlyReport.Status.APPROVED):
        return 0
    if days not in (1, 10, 14) and days < QuarterlyReport.DUE_DAYS:
        return 0
    due = quarter_end(start) + datetime.timedelta(days=QuarterlyReport.DUE_DAYS)
    from .services import _tell

    people = list(users_with_perm("mgmt.qbr"))
    _tell(people, f"The Quarterly Business Report {label(start)} is due to the CEO by {due:%d/%m/%Y}.")
    return len(people)
