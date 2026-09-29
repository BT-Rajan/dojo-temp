"""Adding staff and giving them access (decision P7-11): staff records, roles by branch, one-time passwords."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.organization.models import Branch
from apps.rbac import services as rbac
from apps.rbac.models import Role, RoleAssignment
from apps.staff import services as staff_services
from apps.staff.models import StaffProfile

from ..access import L, desk
from .ops import _date

ONE_TIME = "one_time_password"


def remember_password(request, profile, password):
    """Shown once on the next page, then forgotten (never logged)."""
    request.session[ONE_TIME] = {"staff": profile.pk, "password": password}


def pop_password(request, profile):
    data = request.session.get(ONE_TIME)
    if data and data.get("staff") == profile.pk:
        del request.session[ONE_TIME]
        return data["password"]
    return None


def grantable_roles(user):
    return [r for r in Role.objects.exclude(code="guardian").prefetch_related("permissions")]


@desk("staff.manage")
def staff_new(request):
    if request.method == "POST":
        p = request.POST
        profile, password = staff_services.create_staff(
            request.user,
            email=p.get("email", ""),
            full_name=p.get("full_name", ""),
            full_name_ar=p.get("full_name_ar", ""),
            mobile=p.get("mobile", ""),
            job_title=p.get("job_title", ""),
            job_title_ar=p.get("job_title_ar", ""),
            employment_type=p.get("employment_type", ""),
            primary_branch=Branch.objects.filter(pk=p.get("branch") or 0).first(),
            reports_to=StaffProfile.objects.filter(pk=p.get("reports_to") or 0).first(),
            second_lead=StaffProfile.objects.filter(pk=p.get("second_lead") or 0).first(),
            start_date=_date(p.get("start_date")),
        )
        role = Role.objects.filter(code=p.get("role", "")).exclude(code="guardian").first()
        if role is not None:
            try:
                rbac.grant_role(
                    request.user,
                    profile.user,
                    role,
                    Branch.objects.filter(pk=p.get("role_branch") or 0).first(),
                    reason=p.get("reason") or "New staff member",
                )
            except (ValidationError, PermissionDenied) as exc:  # the record is kept; give the role on the next page
                reason = "; ".join(getattr(exc, "messages", None) or [str(exc)])
                messages.error(
                    request,
                    L("Staff member added, but the role was not given: ", "أُضيف الموظف لكن لم يُمنح الدور: ") + reason,
                )
        remember_password(request, profile, password)
        messages.success(request, L("Staff member added.", "تمت إضافة الموظف."))
        return redirect("desk:staff_pay", pk=profile.pk)
    return render(
        request,
        "desk/payroll/staff_new.html",
        {
            "types": StaffProfile.EmploymentType.choices,
            "branches": Branch.objects.filter(is_active=True).order_by("-code"),
            "leads": StaffProfile.objects.filter(user__is_active=True).select_related("user"),
            "roles": grantable_roles(request.user),
            "today": timezone.localdate(),
        },
    )


def access_action(request, staff):
    """Handles the access form actions on a staff page. Returns True when it handled one."""
    p, action = request.POST, request.POST.get("action")
    if action == "grant":
        role = get_object_or_404(Role.objects.exclude(code="guardian"), code=p.get("role", ""))
        rbac.grant_role(
            request.user,
            staff.user,
            role,
            Branch.objects.filter(pk=p.get("branch") or 0).first(),
            reason=p.get("reason", ""),
            starts_on=_date(p.get("starts_on")),
        )
        messages.success(request, L("Access given.", "تم منح الصلاحية."))
    elif action == "end_role":
        assignment = get_object_or_404(RoleAssignment, pk=p.get("assignment"), user=staff.user)
        rbac.end_role(request.user, assignment)
        messages.success(request, L("Access ended; they have been signed out.", "انتهت الصلاحية وتم تسجيل خروجه."))
    elif action == "reset_password":
        remember_password(request, staff, staff_services.reset_password(request.user, staff.user))
        messages.success(request, L("New one-time password created.", "تم إنشاء كلمة مرور مؤقتة جديدة."))
    else:
        return False
    return True


def access_context(request, staff):
    today = timezone.localdate()
    assignments = RoleAssignment.objects.filter(user=staff.user).select_related("role", "branch", "granted_by")
    return {
        "access_current": [a for a in assignments if a.starts_on <= today and (a.ends_on is None or a.ends_on > today)],
        "access_future": [a for a in assignments if a.starts_on > today],
        "access_past": [a for a in assignments if a.ends_on is not None and a.ends_on <= today][:10],
        "can_view_access": rbac.has_perm(request.user, "rbac.view"),
        "can_assign": rbac.has_perm(request.user, "rbac.assign"),
        "can_reset": rbac.has_perm(request.user, "staff.manage") or rbac.has_perm(request.user, "rbac.assign"),
        "is_self": staff.user_id == request.user.pk,
        "roles": grantable_roles(request.user),
        "branches": Branch.objects.filter(is_active=True).order_by("-code"),
        "one_time_password": pop_password(request, staff),
        "today": today,
    }
