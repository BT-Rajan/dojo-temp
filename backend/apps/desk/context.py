"""Menu, branch switcher and waiting counts for every desk page."""

from django.urls import NoReverseMatch, reverse

from .access import allowed_branches, can, current_branch

# (url name, English, Arabic, icon, permission codes — any of them)
MENU = [
    ("desk:home", "Today", "اليوم", "cal", []),
    ("desk:tasks", "My tasks", "مهامي", "check", []),
    ("desk:checkin", "Check-in", "تسجيل الحضور", "check", ["classes.checkin"]),
    ("desk:members", "Members", "الأعضاء", "user", ["members.view"]),
    ("desk:sell", "Sell", "بيع", "bag", ["sales.sell"]),
    ("desk:sessions", "Classes", "الحصص", "clock", ["classes.view"]),
    ("desk:my_classes", "My classes", "حصصي", "shield", ["training.teach"]),
    ("desk:timetable", "Timetable", "الجدول الأسبوعي", "cal", ["classes.view"]),
    ("desk:renewals", "Renewals", "التجديدات", "phone", ["renewals.follow_up"]),
    ("desk:leads", "Leads", "العملاء المحتملون", "plus", ["leads.manage", "marketing.manage"]),
    ("desk:sales", "Sales", "المبيعات", "bag", ["sales.view"]),
    ("desk:cashup", "Cash-up", "الإغلاق اليومي", "check", ["sales.cashup"]),
    (
        "desk:approvals",
        "Approvals",
        "الموافقات",
        "alert",
        ["sales.approve_refund", "pricing.approve", "classes.change_approve", "reports.verify", "finance.manage"],
    ),
    ("desk:changes", "Class changes", "تغييرات الحصص", "alert", ["classes.change_request", "classes.change_approve"]),
    ("desk:pricing", "Prices", "الأسعار", "bag", ["programs.view"]),
    ("desk:shift", "Shift opening", "فتح النوبة", "check", ["ops.shift"]),
    ("desk:incidents", "Incidents", "الحوادث", "alert", ["ops.incident", "ops.manage"]),
    ("desk:complaints", "Complaints", "الشكاوى", "phone", ["ops.complaint", "ops.manage"]),
    ("desk:handovers", "Cover & handover", "التغطية والتسليم", "user", ["ops.manage"]),
    ("desk:expenses", "Expenses", "المصروفات", "bag", ["finance.expense", "finance.expense_approve", "finance.manage"]),
    (
        "desk:weekly_reports",
        "Weekly reports",
        "التقارير الأسبوعية",
        "cal",
        ["reports.branch", "reports.verify", "reports.all"],
    ),
    ("desk:active_members", "Active members", "الأعضاء النشطون", "user", ["reports.branch", "reports.all"]),
    ("desk:dashboards", "Dashboards", "لوحات المتابعة", "photo", ["reports.branch", "reports.all"]),
    ("desk:reports", "Class use", "استخدام الحصص", "clock", ["reports.branch", "reports.all"]),
    ("desk:income_statement", "Finance", "المالية", "bag", ["finance.manage"]),
    ("desk:payroll", "Payroll", "الرواتب", "bag", ["payroll.view", "payroll.prepare", "payroll.approve"]),
    ("desk:staff_list", "Staff", "الموظفون", "user", ["staff.manage", "payroll.view", "payroll.prepare"]),
    ("desk:leave", "Leave", "الإجازات", "cal", ["leave.approve"]),
    ("desk:stock", "Stock", "المخزون", "bag", ["inventory.view"]),
    (
        "desk:purchase_requests",
        "Purchasing",
        "المشتريات",
        "bag",
        ["inventory.manage", "inventory.purchase", "inventory.approve"],
    ),
    ("desk:transfers", "Transfers", "التحويلات", "arrow", ["inventory.manage", "inventory.purchase"]),
    ("desk:stock_counts", "Stock count", "الجرد", "check", ["inventory.manage", "inventory.approve"]),
    ("desk:online_orders", "Online orders", "الطلبات الإلكترونية", "bag", ["inventory.manage"]),
    ("desk:imports", "Mindbody", "مايندبودي", "arrow", ["data.import"]),
    ("desk:training", "Training", "التدريب", "check", ["training.view", "training.teach", "training.manage"]),
    ("desk:campaigns", "Marketing", "التسويق", "photo", ["marketing.manage", "marketing.approve"]),
    ("desk:saqr", "SAQR chats", "محادثات صقر", "phone", ["leads.manage"]),
    ("desk:kb", "Knowledge base", "قاعدة المعرفة", "check", ["kb.edit"]),
    ("desk:assistant", "Ask the assistant", "اسأل المساعد", "user", ["assistant.use"]),
    ("desk:message_log", "Messages", "الرسائل", "phone", ["messages.view", "marketing.approve"]),
    ("desk:my_pay", "My pay", "راتبي", "user", ["payroll.self"]),
]


def desk(request):
    path = request.path
    if "/desk/" not in path or not request.user.is_authenticated or path.endswith("/desk/sign-in/"):
        return {}
    if not hasattr(request, "branch"):
        request.branch = current_branch(request)
    items = []
    for name, en, ar, icon, perms in MENU:
        if perms and not any(can(request, p) for p in perms):
            continue
        try:
            url = reverse(name)
        except NoReverseMatch:
            continue
        active = path == url if name == "desk:home" else path.startswith(url)
        items.append({"url": url, "en": en, "ar": ar, "icon": icon, "active": active, "name": name})
    from .views.home import waiting_counts

    return {
        "desk_menu": items,
        "desk_branches": allowed_branches(request.user).order_by("code").reverse(),
        "desk_branch": request.branch,
        "desk_counts": waiting_counts(request),
    }
