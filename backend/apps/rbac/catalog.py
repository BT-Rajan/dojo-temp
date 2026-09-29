"""
The permission catalogue and default roles — the single source of truth for RBAC.

Permissions are named "<area>.<action>". Roles are bundles of permissions. A user gets a
role through a RoleAssignment, optionally limited to one branch. Nothing is allowed
unless a role grants it (deny by default).

Default roles follow EA-SYS-SCOPE-01 Section 3 and the Elite org chart. Systems & IT can
adjust roles later; `python manage.py sync_rbac` re-applies this catalogue.
"""

PERMISSIONS: dict[str, str] = {
    # Organisation
    "branches.view": "View branches",
    "branches.manage": "Create and edit branches",
    "programs.view": "View disciplines, programs and pricing options",
    "programs.manage": "Create and edit programs",
    "pricing.manage": "Create and edit pricing options (price changes need approval)",
    "pricing.approve": "Approve price changes",
    # Members
    "members.view": "View members and families",
    "members.create": "Register members",
    "members.update": "Edit member details",
    "members.deactivate": "Deactivate members",
    "members.view_sensitive": "See full Civil IDs",
    "members.view_medical": "See medical notes and allergies",
    "members.manage_consent": "Record media consent",
    # Staff and access
    "staff.view": "View staff directory",
    "staff.manage": "Create and edit staff records",
    "rbac.view": "View roles and assignments",
    "rbac.assign": "Assign and end roles",
    "rbac.manage_roles": "Change what roles can do",
    "audit.view": "Read the audit log",
    "system.admin": "Technical administration",
    # Classes (M4)
    "classes.view": "See the timetable, sessions and class lists",
    "classes.manage": "Edit the weekly timetable, rooms and one-off sessions",
    "classes.book": "Book members and trials into classes",
    "classes.checkin": "Check members in and take attendance",
    "classes.change_request": "Request a class cancellation, time change or substitute coach",
    "classes.change_approve": "Approve class changes (members are notified)",
    # Sales, requests, cash-up and renewals (M5, M6)
    "sales.view": "See sales, receipts and memberships",
    "sales.request": "Log freeze, refund and cancellation requests",
    "sales.cashup": "Prepare and submit the end-of-day cash-up",
    "renewals.follow_up": "Work the renewals follow-up list",
    "sales.sell": "Sell at the front desk",
    "sales.approve_refund": "Approve freezes, refunds and cancellations",
    "reports.branch": "Branch reports",
    "reports.all": "All-branch and quarterly reports",
    "reports.verify": "Verify weekly reports",
    "inventory.view": "See products, stock at each branch and stock history",
    "inventory.manage": "Request purchases, send and accept transfers, take part in stock counts",
    "inventory.purchase": "Place purchase orders with vendors and receive deliveries at Promenade",
    "inventory.approve": "Approve purchase requests and stock corrections; edit the catalogue, costs and prices",
    "data.import": "Import data from Mindbody and run the parallel-run comparison",
    "training.manage": "Curriculum, evaluations and promotions",
    "training.teach": "Take attendance and evaluate own classes",
    "marketing.manage": "Campaigns, leads and media library",
    "cms.edit": "Draft website content",
    "cms.publish": "Publish website content",
    "leads.manage": "Follow up website trial requests and contact messages",
    "finance.manage": "Reconciliation, income statements, vendor invoices and exports",
    "finance.expense": "Record branch expenses with a receipt photo",
    "finance.expense_approve": "Approve branch expenses",
    "payroll.prepare": "Set up staff pay and prepare the monthly payroll run",
    "payroll.view": "See payroll runs, payslips and summaries",
    "payroll.approve": "Approve the monthly payroll run",
    "payroll.self": "See own payslips; request leave and salary advances",
    "leave.approve": "Approve staff leave",
    "incidents.escalate": "Receive safety escalations",
    # Daily operations (M9)
    "ops.shift": "Complete the shift opening checklist",
    "ops.incident": "Report incidents",
    "ops.complaint": "Log and handle complaints",
    "ops.manage": "Follow up incidents and complaints, name cover and handovers",
    # Member / parent portal
    "portal.own_family": "See and manage own family in the portal",
}

ALL = set(PERMISSIONS)
VIEW_ORG = {"branches.view", "programs.view"}

# code: (name, name_ar, description, privileged, permissions)
ROLES: dict[str, tuple[str, str, str, bool, set[str]]] = {
    "ceo": (
        "Chief Executive Officer",
        "الرئيس التنفيذي",
        "Direction and alignment; sees everything.",
        True,
        # Payroll: the OM prepares, the Accountant approves, the CEO sees the summary (decision P2-5).
        ALL - {"system.admin", "portal.own_family", "payroll.prepare", "payroll.approve"},
    ),
    "operations_manager": (
        "Operations Manager (COO)",
        "مدير العمليات",
        "Runs operations across both branches.",
        True,
        VIEW_ORG
        | {
            "programs.manage",
            "pricing.manage",
            "pricing.approve",
            "members.view",
            "members.create",
            "members.update",
            "members.deactivate",
            "members.view_sensitive",
            "members.view_medical",
            "members.manage_consent",
            "staff.view",
            "staff.manage",
            "rbac.view",
            "rbac.assign",
            "audit.view",
            "sales.sell",
            "sales.approve_refund",
            "reports.branch",
            "reports.all",
            "reports.verify",
            "inventory.manage",
            "inventory.approve",
            "finance.manage",
            "incidents.escalate",
        },
    ),
    "training_lead": (
        "Training Lead",
        "مسؤول التدريب",
        "Programs, curriculum and instructors.",
        False,
        VIEW_ORG
        | {
            "programs.manage",
            "members.view",
            "members.view_medical",
            "staff.view",
            "reports.branch",
            "training.manage",
            "training.teach",
            "incidents.escalate",
        },
    ),
    "track_lead": (
        "Track Lead",
        "قائد المسار",
        "Leads the grappling or striking track.",
        False,
        VIEW_ORG | {"members.view", "members.view_medical", "staff.view", "training.manage", "training.teach"},
    ),
    "instructor": (
        "Instructor",
        "مدرب",
        "Teaches classes; sees their students.",
        False,
        VIEW_ORG | {"members.view", "members.view_medical", "training.teach"},
    ),
    "marketing_lead": (
        "Marketing Lead",
        "مسؤولة التسويق",
        "Campaigns, website and brand.",
        False,
        VIEW_ORG | {"members.view", "marketing.manage", "cms.edit", "cms.publish", "reports.branch"},
    ),
    "marketing_staff": (
        "Marketing Implementation",
        "تنفيذ التسويق",
        "Implements campaigns and content.",
        False,
        VIEW_ORG | {"marketing.manage", "cms.edit"},
    ),
    "it_admin": (
        "Systems & IT Lead",
        "مسؤول الأنظمة وتقنية المعلومات",
        "Users, roles and system settings.",
        True,
        VIEW_ORG
        | {
            "branches.manage",
            "staff.view",
            "rbac.view",
            "rbac.assign",
            "rbac.manage_roles",
            "audit.view",
            "system.admin",
        },
    ),
    "branch_admin": (
        "Branch Admin",
        "إداري الفرع",
        "Front desk and daily branch operations.",
        False,
        VIEW_ORG
        | {
            "members.view",
            "members.create",
            "members.update",
            "members.view_sensitive",
            "members.view_medical",
            "members.manage_consent",
            "staff.view",
            "sales.sell",
            "reports.branch",
            "inventory.manage",
        },
    ),
    "operations_support": (
        "Operations Support",
        "دعم العمليات",
        "Front desk support at either branch.",
        False,
        VIEW_ORG
        | {
            "members.view",
            "members.create",
            "members.update",
            "members.manage_consent",
            "members.view_medical",
            "sales.sell",
        },
    ),
    "purchasing_coordinator": (
        "Purchasing / Receiving Coordinator",
        "منسق المشتريات",
        "Orders and deliveries.",
        False,
        VIEW_ORG | {"inventory.manage"},
    ),
    "accountant": (
        "Accountant",
        "المحاسب",
        "Finance, reconciliation and payroll approval.",
        True,
        VIEW_ORG | {"finance.manage", "payroll.view", "payroll.approve", "reports.all", "staff.view"},
    ),
    "guardian": (
        "Parent / Member",
        "ولي الأمر / العضو",
        "Portal access to own family only.",
        False,
        {"portal.own_family"},
    ),
}

_unknown = {p for *_, perms in ROLES.values() for p in perms} - ALL
if _unknown:
    raise ValueError(f"A role references unknown permissions: {sorted(_unknown)}")

# Website trial requests and messages go to whoever sells or markets (Customer Management Procedure).
for _code in ("operations_manager", "branch_admin", "operations_support", "marketing_lead", "marketing_staff"):
    ROLES[_code][4].add("leads.manage")

# Phase 1 (M4–M6) permissions per role, following the scope's role descriptions.
PHASE1 = {
    "operations_manager": {
        "classes.view",
        "classes.manage",
        "classes.book",
        "classes.checkin",
        "classes.change_request",
        "classes.change_approve",
        "sales.view",
        "sales.request",
        "sales.cashup",
        "renewals.follow_up",
    },
    "training_lead": {
        "classes.view",
        "classes.manage",
        "classes.checkin",
        "classes.change_request",
        "classes.change_approve",
    },
    "track_lead": {"classes.view", "classes.checkin", "classes.change_request"},
    "instructor": {"classes.view", "classes.checkin", "classes.change_request"},
    "branch_admin": {
        "classes.view",
        "classes.book",
        "classes.checkin",
        "classes.change_request",
        "sales.view",
        "sales.request",
        "sales.cashup",
        "renewals.follow_up",
    },
    "operations_support": {
        "classes.view",
        "classes.book",
        "classes.checkin",
        "classes.change_request",
        "sales.view",
        "sales.request",
        "sales.cashup",
        "renewals.follow_up",
    },
    "accountant": {"sales.view"},
    "marketing_lead": {"classes.view"},
}
for _code, _perms in PHASE1.items():
    ROLES[_code][4].update(_perms)


# Phase 2 (M9, M10, M11, M20) permissions per role.
PHASE2 = {
    "operations_manager": {
        "ops.shift",
        "ops.incident",
        "ops.complaint",
        "ops.manage",
        "finance.expense",
        "finance.expense_approve",
        "payroll.prepare",
        "payroll.view",
        "leave.approve",
    },
    "training_lead": {"ops.incident", "leave.approve"},
    "track_lead": {"ops.incident"},
    "instructor": {"ops.incident"},
    "branch_admin": {"ops.shift", "ops.incident", "ops.complaint", "finance.expense"},
    "operations_support": {"ops.shift", "ops.incident", "ops.complaint", "finance.expense", "reports.branch"},
    "marketing_lead": {"ops.complaint"},
    "accountant": {"finance.expense_approve"},
}
for _code, _perms in PHASE2.items():
    ROLES[_code][4].update(_perms)

# Everyone who works at Elite sees their own payslips and can ask for leave.
for _code in ROLES:
    if _code != "guardian":
        ROLES[_code][4].add("payroll.self")


# Phase 3 (M8, M18, M19) permissions per role.
PHASE3 = {
    "operations_manager": {"inventory.view", "inventory.purchase", "data.import"},
    "branch_admin": {"inventory.view"},
    "operations_support": {"inventory.view", "inventory.manage"},
    "purchasing_coordinator": {"inventory.view", "inventory.purchase"},
    "accountant": {"inventory.view"},
    "it_admin": {"data.import"},
}
for _code, _perms in PHASE3.items():
    ROLES[_code][4].update(_perms)
