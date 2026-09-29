"""Adding staff and giving access from the desk (decision P7-11): who may do it, escalation and branch limits."""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client

from apps.rbac.models import Role, RoleAssignment
from apps.rbac.services import end_role, grant_role, has_perm
from apps.staff import services as ss
from apps.staff.models import StaffProfile


def desk_client(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def people(branches, make_user):
    return {
        "ceo": make_user("ceo"),
        "om": make_user("operations_manager"),
        "it": make_user("it_admin"),
        "admin": make_user("branch_admin", branch=branches["PRM"]),
        "coach": make_user("instructor"),
    }


def test_create_staff_gives_a_one_time_password(people, branches):
    with pytest.raises(PermissionDenied):
        ss.create_staff(people["coach"], email="x@example.test", full_name="X", job_title="Coach",
                        employment_type="hourly")  # fmt: skip
    profile, password = ss.create_staff(
        people["om"],
        email="New.Coach@Example.test",
        full_name="New Coach",
        mobile="55512345",
        job_title="Instructor",
        employment_type="hourly",
        primary_branch=branches["BED"],
    )
    user = profile.user
    assert user.email == "new.coach@example.test" and user.mobile == "+96555512345"
    assert user.must_change_password and user.check_password(password) and len(password) >= 12
    assert not RoleAssignment.objects.filter(user=user).exists()  # no access until a role is given
    with pytest.raises(ValidationError):
        ss.create_staff(people["om"], email="new.coach@example.test", full_name="Dup", job_title="x",
                        employment_type="hourly")  # fmt: skip
    with pytest.raises(ValidationError):
        ss.create_staff(people["om"], email="other@example.test", full_name="Dup", mobile="55512345",
                        job_title="x", employment_type="hourly")  # fmt: skip


def test_grant_and_end_roles_follow_the_rules(people, branches):
    profile, _ = ss.create_staff(people["om"], email="a@example.test", full_name="A", job_title="Desk",
                                 employment_type="full_time")  # fmt: skip
    user = profile.user
    admin_role = Role.objects.get(code="branch_admin")
    with pytest.raises(ValidationError):
        grant_role(people["om"], user, admin_role, branches["BED"], reason="")
    a = grant_role(people["om"], user, admin_role, branches["BED"], reason="New front desk at Bedaya")
    assert has_perm(user, "sales.sell", branches["BED"].pk) and not has_perm(user, "sales.sell", branches["PRM"].pk)
    with pytest.raises(ValidationError):
        grant_role(people["om"], user, admin_role, branches["BED"], reason="again")
    # No escalation: the OM can't hand out the CEO role; a branch admin can't grant at all.
    with pytest.raises(PermissionDenied):
        grant_role(people["om"], user, Role.objects.get(code="ceo"), None, reason="x")
    with pytest.raises(PermissionDenied):
        grant_role(people["admin"], user, admin_role, branches["PRM"], reason="x")
    # The CEO can make someone Operations Manager; nobody changes their own access.
    grant_role(people["ceo"], user, Role.objects.get(code="operations_manager"), None, reason="Promotion")
    with pytest.raises(PermissionDenied):
        grant_role(people["ceo"], people["ceo"], admin_role, None, reason="self")
    with pytest.raises(ValidationError):
        grant_role(people["ceo"], user, Role.objects.get(code="guardian"), None, reason="x")
    stamp = get_user_model().objects.get(pk=user.pk).security_stamp
    end_role(people["om"], a)
    assert not RoleAssignment.objects.current().filter(pk=a.pk).exists()
    assert get_user_model().objects.get(pk=user.pk).security_stamp != stamp  # signed out everywhere
    with pytest.raises(ValidationError):
        end_role(people["om"], RoleAssignment.objects.get(pk=a.pk))


def test_password_reset_cannot_target_someone_with_more_access(people):
    with pytest.raises(PermissionDenied):
        ss.reset_password(people["om"], people["ceo"])
    with pytest.raises(PermissionDenied):
        ss.reset_password(people["om"], people["om"])
    pw = ss.reset_password(people["ceo"], people["admin"])
    admin = get_user_model().objects.get(pk=people["admin"].pk)
    assert admin.check_password(pw) and admin.must_change_password


def test_desk_pages(people, branches):
    om = desk_client(people["om"])
    assert om.get("/en/desk/payroll/staff/new/").status_code == 200
    r = om.post(
        "/en/desk/payroll/staff/new/",
        {"full_name": "Desk Person", "email": "desk.person@example.test", "job_title": "Branch Admin",
         "employment_type": "full_time", "role": "branch_admin", "role_branch": branches["PRM"].pk,
         "reason": "New staff member"},
    )  # fmt: skip
    assert r.status_code == 302
    profile = StaffProfile.objects.get(user__email="desk.person@example.test")
    assert has_perm(profile.user, "sales.sell", branches["PRM"].pk)
    page = om.get(r["Location"]).content.decode()
    assert "One-time password" in page and "Elite-" in page
    assert "Elite-" not in om.get(r["Location"]).content.decode()  # shown only once
    for lang in ("en", "ar"):
        assert om.get(f"/{lang}/desk/payroll/staff/").status_code == 200
        assert om.get(f"/{lang}/desk/payroll/staff/?no_access=1").status_code == 200
        assert om.get(f"/{lang}/desk/payroll/staff/{profile.pk}/").status_code == 200
    a = RoleAssignment.objects.get(user=profile.user)
    om.post(f"/en/desk/payroll/staff/{profile.pk}/", {"action": "end_role", "assignment": a.pk})
    assert RoleAssignment.objects.get(pk=a.pk).ends_on is not None
    om.post(
        f"/en/desk/payroll/staff/{profile.pk}/",
        {"action": "grant", "role": "operations_support", "branch": "", "reason": "Covers both branches"},
    )
    assert RoleAssignment.objects.current().filter(user=profile.user, role__code="operations_support").exists()
    # Systems & IT can manage access; a coach can't open the page.
    it_staff, _ = ss.create_staff(people["om"], email="i@example.test", full_name="I", job_title="x",
                                  employment_type="full_time")  # fmt: skip
    assert desk_client(people["it"]).get(f"/en/desk/payroll/staff/{it_staff.pk}/").status_code == 200
    assert desk_client(people["coach"]).get("/en/desk/payroll/staff/new/").status_code == 403
