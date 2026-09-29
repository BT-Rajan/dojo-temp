"""Report data → exportable documents (see export.py), in English or Arabic."""

import datetime
from decimal import Decimal

from apps.sales.models import SaleLine

CATEGORY_AR = {
    "new": "جديد",
    "renew": "تجديد",
    "trial": "تذكرة تجربة",
    "day_pass": "تذكرة يوم",  # nosec B105 - a sale category label, not a password
    "equipment": "معدات",
    "other": "جلسات وفعاليات",
}


def _t(lang, en, ar):
    return ar if lang == "ar" else en


def _d(value):
    if isinstance(value, str) and len(value) == 10 and value[4] == "-":
        return datetime.date.fromisoformat(value)
    return value


def _n(value):
    return Decimal(str(value)) if value not in (None, "") else None


def category(code, lang):
    return CATEGORY_AR.get(code, code) if lang == "ar" else dict(SaleLine.Category.choices).get(code, code)


def _sign_off(report, lang):
    if report is None:
        return [("text", _t(lang, "Not yet prepared — live figures.", "لم يُعدّ بعد — أرقام مباشرة."))]
    out = [
        (
            "text",
            _t(lang, "Prepared by", "أعدّه") + f" {report.prepared_by.full_name} · {report.prepared_at:%d/%m/%Y %H:%M}",
        )
    ]
    if report.verified_by:
        out.append(
            (
                "text",
                _t(lang, "Verified by (Operations Manager)", "تحقق منه (مدير العمليات)")
                + f" {report.verified_by.full_name} · {report.verified_at:%d/%m/%Y %H:%M}",
            )
        )
    return out


def weekly_sales_doc(data, branch, report=None, lang="en") -> dict:
    start, end = _d(data["start"]), _d(data["end"])
    rows = [
        (
            i,
            _d(r["date"]),
            r["receipt"],
            r.get("member_ar") if lang == "ar" and r.get("member_ar") else r["member"],
            r.get("program_ar") if lang == "ar" and r.get("program_ar") else r["program"],
            category(r["category"], lang),
            r["method"],
            _n(r["amount"]),
        )
        for i, r in enumerate(data["rows"], start=1)
    ]
    from .services import METHODS

    method_names = {c: (ar if lang == "ar" else en) for c, en, ar in METHODS}
    methods = [
        (
            method_names.get(m["code"], m["label"]),
            m["count"],
            _n(m["total"]),
            _n(m["settled"]),
            _t(lang, "Yes", "نعم") if m["matches"] else _t(lang, "No", "لا") + f" ({_n(m['difference']):+.3f})",
        )
        for m in data["by_method"]
    ]
    expenses = [
        (
            i,
            _d(e["date"]),
            e["description"],
            e["paid_to"],
            _n(e["amount"]),
            _t(lang, "Yes", "نعم") if e["receipt"] else _t(lang, "No", "لا"),
        )
        for i, e in enumerate(data["expenses"], start=1)
    ]
    blocks = [
        (
            "table",
            [
                "#",
                _t(lang, "Date", "التاريخ"),
                _t(lang, "Receipt", "الإيصال"),
                _t(lang, "Member", "العضو"),
                _t(lang, "Program", "البرنامج"),
                _t(lang, "Category", "الفئة"),
                _t(lang, "Method", "طريقة الدفع"),
                _t(lang, "Amount (KD)", "المبلغ (د.ك)"),
            ],
            rows,
        ),
        ("heading", _t(lang, "Totals by method", "المجاميع حسب طريقة الدفع")),
        (
            "table",
            [
                _t(lang, "Method", "الطريقة"),
                _t(lang, "No. of transactions", "عدد العمليات"),
                _t(lang, "Total (KD)", "المجموع (د.ك)"),
                _t(lang, "Cash-up / terminal", "الإغلاق / الجهاز"),
                _t(lang, "Matches cash-up and terminal settlement?", "مطابق للإغلاق وتسوية الجهاز؟"),
            ],
            methods,
        ),
    ]
    if data.get("missing_cash_ups"):
        blocks.append(
            (
                "text",
                _t(lang, "Days without a submitted cash-up: ", "أيام بدون إغلاق يومي: ")
                + ", ".join(_d(d).strftime("%d/%m") for d in data["missing_cash_ups"]),
            )
        )
    blocks += [
        ("heading", _t(lang, "Expenses / payments from branch", "المصروفات والمدفوعات من الفرع")),
        (
            "table",
            [
                "#",
                _t(lang, "Date", "التاريخ"),
                _t(lang, "Description", "الوصف"),
                _t(lang, "For", "لـ"),
                _t(lang, "Amount (KD)", "المبلغ (د.ك)"),
                _t(lang, "Receipt attached", "الإيصال مرفق"),
            ],
            expenses,
        ),
        (
            "table",
            [
                _t(lang, "Total sales (KD)", "إجمالي المبيعات (د.ك)"),
                _t(lang, "Total expenses (KD)", "إجمالي المصروفات (د.ك)"),
                _t(lang, "Net weekly income (KD)", "صافي الدخل الأسبوعي (د.ك)"),
            ],
            [(_n(data["total_sales"]), _n(data["total_expenses"]), _n(data["net"]))],
        ),
    ]
    blocks += _sign_off(report, lang)
    return {
        "title": _t(lang, "EA-OPS-FRM-06 — Weekly Sales Report", "EA-OPS-FRM-06 — تقرير المبيعات الأسبوعي"),
        "subtitle": f"{branch.name_ar if lang == 'ar' else branch.name} · "
        + _t(lang, "Week: Sat ", "الأسبوع: السبت ")
        + f"{start:%d/%m/%Y} "
        + _t(lang, "to Fri ", "إلى الجمعة ")
        + f"{end:%d/%m/%Y}"
        + (f" · {report.reference}" if report else ""),
        "sheet": "FRM-06",
        "blocks": blocks,
    }


def weekly_branch_doc(data, branch, report=None, lang="en") -> dict:
    start = _d(data["start"])
    from .services import MEASURES

    labels = {k: (ar if lang == "ar" else en) for k, en, ar in MEASURES}
    rows = [(labels[r["key"]], r["this"], r["last"], f"{r['change']:+d}") for r in data["rows"]]
    blocks = [
        (
            "table",
            [
                _t(lang, "Measure", "المؤشر"),
                _t(lang, "This week", "هذا الأسبوع"),
                _t(lang, "Last week", "الأسبوع الماضي"),
                _t(lang, "Change", "التغيّر"),
            ],
            rows,
        ),
        ("heading", _t(lang, "Members leaving and reasons", "الأعضاء المغادرون والأسباب")),
        ("text", "; ".join(data.get("leaving", [])) or "—"),
    ]
    if report is not None and report.leaving_reasons:
        blocks.append(("text", report.leaving_reasons))
    blocks += [
        (
            "heading",
            _t(lang, "Incidents (FRM-09) and complaints (FRM-10) still open", "الحوادث والشكاوى المفتوحة"),
        ),
        ("text", ", ".join(data.get("open_incidents", []) + data.get("open_complaints", [])) or "—"),
        ("heading", _t(lang, "Facility, stock or system issues", "مشكلات المرافق أو المخزون أو الأنظمة")),
        ("text", "; ".join(data.get("hazards", [])) or "—"),
    ]
    if report is not None and report.facility_issues:
        blocks.append(("text", report.facility_issues))
    blocks += [
        ("heading", _t(lang, "Items needing OM decision", "بنود تحتاج قرار مدير العمليات")),
        ("text", (report.om_decisions if report is not None and report.om_decisions else "—")),
    ]
    blocks += _sign_off(report, lang)
    return {
        "title": _t(lang, "EA-OPS-FRM-07 — Weekly Branch Report", "EA-OPS-FRM-07 — التقرير الأسبوعي للفرع"),
        "subtitle": f"{branch.name_ar if lang == 'ar' else branch.name} · "
        + _t(lang, "Week of ", "أسبوع ")
        + f"{start:%d/%m/%Y}"
        + (f" · {report.reference}" if report else ""),
        "sheet": "FRM-07",
        "blocks": blocks,
    }


def active_members_doc(data, scope_name, change=None, lang="en") -> dict:
    codes = data["codes"]
    programs = [(p["label"], p["total"], *[p["branches"].get(c, 0) for c in codes]) for p in data["programs"]]
    roster = [
        (
            i,
            r["name"],
            r["branch"],
            r["option"],
            r["class_attended"],
            r["last_visit"],
            r["visits"],
            r["expires"],
            _n(r["paid"]),
            r["phone"],
            _t(lang, "Verified — attendance on record", "مؤكد بالحضور")
            if r["verified"]
            else _t(lang, "No visit found", "لا توجد زيارة"),
        )
        for i, r in enumerate(data["roster"], start=1)
    ]
    blocks = [
        (
            "text",
            _t(
                lang,
                "Unique members holding a valid, unexpired paid membership or class package. Trials, day passes, "
                "camps, seminars, private sessions and events are not counted (business rule 1).",
                "أعضاء فريدون لديهم اشتراك مدفوع ساري المفعول. لا تُحتسب التجارب وتذاكر اليوم والمعسكرات والندوات "
                "والحصص الخاصة والفعاليات.",
            ),
        ),
        (
            "table",
            [_t(lang, "Total (unique)", "الإجمالي (فريد)")]
            + codes
            + [_t(lang, "Verified by attendance", "مؤكد بالحضور")],
            [(data["total"], *[data["by_branch"].get(c, 0) for c in codes], data["verified"])],
        ),
    ]
    if change is not None:
        blocks.append(
            (
                "text",
                _t(lang, "Change since ", "التغيّر منذ ")
                + f"{change['since']:%d/%m}: {change['change']:+d} ({change['before']} → {change['now']})",
            )
        )
    blocks += [
        ("heading", _t(lang, "Members by martial art / program", "الأعضاء حسب الفن القتالي / البرنامج")),
        (
            "text",
            _t(
                lang,
                "A member in more than one program is counted once in each, so this total can exceed the unique total.",
                "العضو المشترك في أكثر من برنامج يُحتسب في كل برنامج، لذلك قد يزيد المجموع على العدد الفريد.",
            ),
        ),
        ("table", [_t(lang, "Program", "البرنامج"), _t(lang, "Members", "الأعضاء")] + codes, programs),
        ("heading", _t(lang, "Roster", "القائمة")),
        (
            "table",
            [
                "#",
                _t(lang, "Client name", "الاسم"),
                _t(lang, "Branch", "الفرع"),
                _t(lang, "Membership / pricing option", "الاشتراك"),
                _t(lang, "Class attended", "الحصة"),
                _t(lang, "Last visit", "آخر زيارة"),
                _t(lang, "Total visits", "عدد الزيارات"),
                _t(lang, "Expires", "ينتهي"),
                _t(lang, "Amount paid", "المبلغ المدفوع"),
                _t(lang, "Phone", "الهاتف"),
                _t(lang, "Verification", "التحقق"),
            ],
            roster,
        ),
    ]
    on = _d(data["on"])
    return {
        "title": _t(lang, "Active Members Report", "تقرير الأعضاء النشطين"),
        "subtitle": f"{scope_name} · " + _t(lang, "As of ", "بتاريخ ") + f"{on:%d/%m/%Y}",
        "sheet": "Active members",
        "blocks": blocks,
    }


def daily_doc(data, lang="en") -> dict:
    rows = [
        (
            r["branch"].name_ar if lang == "ar" else r["branch"].name,
            r["classes"],
            r["visits"],
            r["no_shows"],
            f"{r['fill']}%",
            r["sales_count"],
            r["sales_total"],
            r["cash_up"] or _t(lang, "Not started", "لم يبدأ"),
        )
        for r in data["rows"]
    ]
    return {
        "title": _t(lang, "Daily dashboard", "لوحة اليوم"),
        "subtitle": f"{data['day']:%A %d/%m/%Y}",
        "sheet": "Daily",
        "blocks": [
            (
                "table",
                [
                    _t(lang, "Branch", "الفرع"),
                    _t(lang, "Classes", "الحصص"),
                    _t(lang, "Visits", "الزيارات"),
                    _t(lang, "No-shows", "الغياب"),
                    _t(lang, "Class fill", "نسبة الامتلاء"),
                    _t(lang, "Sales", "عمليات البيع"),
                    _t(lang, "Sales (KD)", "المبيعات (د.ك)"),
                    _t(lang, "Cash-up", "الإغلاق"),
                ],
                rows,
            )
        ],
    }


def monthly_doc(data, lang="en") -> dict:
    rows = [
        (
            r["branch"].name_ar if lang == "ar" else r["branch"].name,
            r["sales"],
            r["last_sales"],
            "—" if r["growth"] is None else f"{r['growth']:+}%",
            r["active_start"],
            r["active_end"],
            r["joined"],
            r["left"],
            "—" if r["churn"] is None else f"{r['churn']}%",
            r["visits"],
        )
        for r in data["rows"]
    ]
    return {
        "title": _t(lang, "Monthly dashboard", "اللوحة الشهرية"),
        "subtitle": f"{data['month']:%B %Y}",
        "sheet": "Monthly",
        "blocks": [
            (
                "table",
                [
                    _t(lang, "Branch", "الفرع"),
                    _t(lang, "Sales (KD)", "المبيعات"),
                    _t(lang, "Last month", "الشهر الماضي"),
                    _t(lang, "Growth", "النمو"),
                    _t(lang, "Members at start", "الأعضاء في البداية"),
                    _t(lang, "Members at end", "الأعضاء في النهاية"),
                    _t(lang, "Joined", "انضموا"),
                    _t(lang, "Left", "غادروا"),
                    _t(lang, "Churn", "نسبة المغادرة"),
                    _t(lang, "Visits", "الزيارات"),
                ],
                rows,
            ),
            ("heading", _t(lang, "Instructor hours", "ساعات المدربين")),
            ("table", [_t(lang, "Instructor", "المدرب"), _t(lang, "Hours", "الساعات")], data["instructors"]),
        ],
    }


def income_statement_doc(data, title_kind, lang="en") -> dict:
    start, end = _d(data["start"]), _d(data["end"])
    n = _n
    rows = [
        (
            _t(lang, "Services (memberships, trials, passes, sessions)", "الخدمات (اشتراكات وتجارب وتذاكر وجلسات)"),
            n(data["services"]),
        ),
        (_t(lang, "Products (equipment)", "المنتجات (المعدات)"), n(data["products"])),
        (_t(lang, "Refunds", "المبالغ المستردة"), n(data["refunds"])),
        (_t(lang, "Trading income", "الإيراد التشغيلي"), n(data["trading_income"])),
    ]
    rows += [(label, n(v)) for label, v in data["expenses"]]
    rows += [
        (_t(lang, "Branch expenses", "مصروفات الفروع"), n(data["total_expenses"])),
        (_t(lang, "Salaries and wages (incl. PIFSS)", "الرواتب والأجور (مع التأمينات)"), n(data["payroll"])),
        (_t(lang, "Purchases (vendor invoices)", "المشتريات (فواتير الموردين)"), n(data["purchases"])),
        (_t(lang, "Total costs", "إجمالي التكاليف"), n(data["total_costs"])),
        (_t(lang, "Net income", "صافي الدخل"), n(data["net_income"])),
    ]
    check = [
        (
            _t(lang, "Headline sales (verified weekly reports)", "المبيعات المعلنة (التقارير الأسبوعية)"),
            n(data["headline_sales"]),
        ),
        (_t(lang, "Trading income", "الإيراد التشغيلي"), n(data["trading_income"])),
        (_t(lang, "Difference", "الفرق"), n(data["difference"])),
    ]
    return {
        "title": _t(lang, "Income statement", "قائمة الدخل"),
        "subtitle": f"{data['branch']} · "
        + (
            _t(lang, "for the quarter ended ", "للربع المنتهي في ")
            if title_kind == "quarter"
            else _t(lang, "for the month ended ", "للشهر المنتهي في ")
        )
        + f"{end:%d %B %Y}"
        + f" ({start:%d/%m} – {end:%d/%m})",
        "sheet": "Income statement",
        "blocks": [
            ("table", [_t(lang, "Line", "البند"), _t(lang, "KD", "د.ك")], rows),
            ("heading", _t(lang, "Sales check", "مطابقة المبيعات")),
            ("table", [_t(lang, "Line", "البند"), _t(lang, "KD", "د.ك")], check),
            (
                "text",
                _t(lang, "Weeks not verified: ", "أسابيع غير مؤكدة: ") + (", ".join(data["unverified_weeks"]) or "—"),
            ),
        ],
    }


def payslip_doc(slip, lang="en") -> dict:
    run = slip.run
    rows = []
    for line in slip.lines.all():
        label = line.label_ar if lang == "ar" and line.label_ar else line.label
        qty = "" if line.quantity is None else f"{line.quantity}"
        rate = "" if line.rate is None else f"{line.rate:.3f}"
        kind = {
            "earning": _t(lang, "Earning", "استحقاق"),
            "deduction": _t(lang, "Deduction", "استقطاع"),
            "employer": _t(lang, "Paid by Elite", "تدفعه إيليت"),
        }[line.kind]
        rows.append((kind, label, qty, rate, line.amount))
    return {
        "title": _t(lang, "Payslip", "قسيمة الراتب") + f" · {run.month:%m/%Y}",
        "subtitle": f"{slip.full_name_ar if lang == 'ar' and slip.full_name_ar else slip.full_name} · "
        f"{slip.job_title_ar if lang == 'ar' and slip.job_title_ar else slip.job_title} · {run.reference}",
        "sheet": "Payslip",
        "blocks": [
            (
                "table",
                [
                    _t(lang, "Type", "النوع"),
                    _t(lang, "Item", "البند"),
                    _t(lang, "Qty", "الكمية"),
                    _t(lang, "Rate", "السعر"),
                    _t(lang, "KD", "د.ك"),
                ],
                rows,
            ),
            (
                "table",
                [
                    _t(lang, "Gross", "الإجمالي"),
                    _t(lang, "Deductions", "الاستقطاعات"),
                    _t(lang, "Net pay", "صافي الراتب"),
                ],
                [(slip.gross, slip.deductions, slip.net)],
            ),
            (
                "text",
                _t(lang, "Paid on ", "يُدفع في ")
                + f"{run.pay_date:%d/%m/%Y}"
                + (f" · IBAN ****{slip.iban_last4}" if slip.iban_last4 else "")
                + _t(lang, " · Classes and sales counted ", " · الحصص والمبيعات من ")
                + f"{run.period_start:%d/%m} – {run.period_end:%d/%m}",
            ),
        ],
    }


def payroll_summary_doc(run, totals, summary, lang="en") -> dict:
    def table(bucket):
        return [(k, v["people"], v["gross"], v["net"], v["cost"]) for k, v in bucket.items()]

    header = [
        "",
        _t(lang, "People", "العدد"),
        _t(lang, "Gross (KD)", "الإجمالي"),
        _t(lang, "Net (KD)", "الصافي"),
        _t(lang, "Cost to Elite (KD)", "التكلفة على إيليت"),
    ]
    slips = [
        (
            s.full_name,
            s.job_title,
            s.branch.code if s.branch_id else "—",
            s.gross,
            s.deductions,
            s.net,
            s.employer_pifss,
        )
        for s in run.payslips.select_related("branch")
    ]
    return {
        "title": _t(lang, "Payroll summary", "ملخص الرواتب") + f" · {run.month:%m/%Y}",
        "subtitle": f"{run.reference} · {run.get_status_display()}",
        "sheet": "Payroll",
        "blocks": [
            (
                "table",
                [
                    _t(lang, "People", "العدد"),
                    _t(lang, "Gross", "الإجمالي"),
                    _t(lang, "Deductions", "الاستقطاعات"),
                    _t(lang, "Net", "الصافي"),
                    _t(lang, "PIFSS (Elite)", "التأمينات (إيليت)"),
                    _t(lang, "End-of-service provision", "مخصص نهاية الخدمة"),
                ],
                [
                    (
                        totals["people"],
                        totals["gross"],
                        totals["deductions"],
                        totals["net"],
                        totals["pifss"],
                        totals["eos"],
                    )
                ],
            ),
            ("heading", _t(lang, "By branch", "حسب الفرع")),
            ("table", header, table(summary["branch"])),
            ("heading", _t(lang, "By function", "حسب الوظيفة")),
            ("table", header, table(summary["function"])),
            ("heading", _t(lang, "People", "الموظفون")),
            (
                "table",
                [
                    _t(lang, "Name", "الاسم"),
                    _t(lang, "Job", "الوظيفة"),
                    _t(lang, "Branch", "الفرع"),
                    _t(lang, "Gross", "الإجمالي"),
                    _t(lang, "Deductions", "الاستقطاعات"),
                    _t(lang, "Net", "الصافي"),
                    _t(lang, "PIFSS (Elite)", "التأمينات (إيليت)"),
                ],
                slips,
            ),
        ],
    }


def bank_file_doc(run, rows) -> dict:
    return {
        "title": f"Salary transfer {run.reference}",
        "subtitle": f"Pay date {run.pay_date:%d/%m/%Y}",
        "sheet": "Transfers",
        "blocks": [
            (
                "table",
                ["Beneficiary name", "IBAN", "Bank", "Amount", "Currency", "Reference"],
                [(r["name"], r["iban"], r["bank"], r["amount"], r["currency"], r["reference"]) for r in rows],
            )
        ],
    }
