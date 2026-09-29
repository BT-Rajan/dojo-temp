"""Menu, branch switcher and waiting counts for every desk page."""

from django.urls import NoReverseMatch, reverse

from .access import allowed_branches, can, current_branch

# (url name, English, Arabic, icon, permission codes — any of them)
MENU = [
    ("desk:home", "Today", "اليوم", "cal", []),
    ("desk:checkin", "Check-in", "تسجيل الحضور", "check", ["classes.checkin"]),
    ("desk:members", "Members", "الأعضاء", "user", ["members.view"]),
    ("desk:sell", "Sell", "بيع", "bag", ["sales.sell"]),
    ("desk:sessions", "Classes", "الحصص", "clock", ["classes.view"]),
    ("desk:my_classes", "My classes", "حصصي", "shield", ["training.teach"]),
    ("desk:timetable", "Timetable", "الجدول الأسبوعي", "cal", ["classes.view"]),
    ("desk:renewals", "Renewals", "التجديدات", "phone", ["renewals.follow_up"]),
    ("desk:trials", "Trial requests", "طلبات التجربة", "plus", ["leads.manage"]),
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
    ("desk:reports", "Reports", "التقارير", "photo", ["reports.branch", "reports.all"]),
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
