"""Role-based access control: deny by default, branch scope, need-to-know fields, no privilege escalation."""

import pytest

from apps.rbac.models import Role, RoleAssignment

pytestmark = pytest.mark.django_db


def ids(response):
    return {row["id"] for row in response.json()["results"]}


def test_anonymous_users_are_refused(anon, members):
    assert anon.get("/api/v1/members/").status_code == 403


def test_logged_in_user_without_roles_gets_nothing(make_user, client_for, members):
    client = client_for(make_user())
    assert client.get("/api/v1/members/").status_code == 403
    assert client.get("/api/v1/branches/").status_code == 403


def test_branch_admin_sees_only_own_branch(make_user, client_for, branches, members):
    client = client_for(make_user("branch_admin", branch=branches["BED"]))
    response = client.get("/api/v1/members/")
    assert response.status_code == 200
    assert ids(response) == {members["bed1"].id, members["bed2"].id}
    # A record from the other branch is invisible, not just read-only.
    assert client.get(f"/api/v1/members/{members['prm1'].id}/").status_code == 404


def test_branch_admin_cannot_register_member_in_other_branch(make_user, client_for, branches):
    client = client_for(make_user("branch_admin", branch=branches["BED"]))
    payload = {
        "branch": branches["PRM"].id,
        "first_name": "New",
        "last_name": "Kid",
        "gender": "male",
        "date_of_birth": "2017-01-01",
    }
    assert client.post("/api/v1/members/", payload, format="json").status_code == 403
    payload["branch"] = branches["BED"].id
    assert client.post("/api/v1/members/", payload, format="json").status_code == 201


def test_branch_admin_cannot_move_member_to_other_branch(make_user, client_for, branches, members):
    client = client_for(make_user("branch_admin", branch=branches["BED"]))
    m = members["bed1"]
    response = client.patch(
        f"/api/v1/members/{m.id}/", {"branch": branches["PRM"].id, "version": m.version}, format="json"
    )
    assert response.status_code == 403


def test_operations_manager_sees_all_branches_and_full_civil_id(make_user, client_for, members):
    client = client_for(make_user("operations_manager"))
    response = client.get("/api/v1/members/")
    assert len(ids(response)) == 4
    detail = client.get(f"/api/v1/members/{members['prm1'].id}/").json()
    assert detail["civil_id"] == members["prm1"].civil_id
    assert detail["medical_notes"] == "Asthma"


def test_marketing_sees_members_without_medical_or_full_civil_id(make_user, client_for, members):
    client = client_for(make_user("marketing_lead"))
    detail = client.get(f"/api/v1/members/{members['prm1'].id}/").json()
    assert "medical_notes" not in detail and "allergies" not in detail
    assert detail["civil_id"].startswith("*")


def test_instructor_sees_medical_but_masked_civil_id(make_user, client_for, branches, members):
    client = client_for(make_user("instructor", branch=branches["PRM"]))
    detail = client.get(f"/api/v1/members/{members['prm1'].id}/").json()
    assert detail["medical_notes"] == "Asthma"
    assert detail["civil_id"].startswith("*")
    # …and cannot change member records.
    assert (
        client.patch(
            f"/api/v1/members/{members['prm1'].id}/", {"first_name": "X", "version": 1}, format="json"
        ).status_code
        == 403
    )


def test_accountant_cannot_see_members(make_user, client_for, members):
    assert client_for(make_user("accountant")).get("/api/v1/members/").status_code == 403


def test_portal_parent_sees_only_own_family(family, client_for, members):
    client = client_for(family)
    response = client.get("/api/v1/portal/my-family/")
    assert response.status_code == 200
    assert [m["id"] for m in response.json()["family"]] == [members["bed1"].id]
    # Parents never reach staff endpoints.
    assert client.get("/api/v1/members/").status_code == 403
    assert client.get(f"/api/v1/members/{members['bed1'].id}/").status_code == 403


def test_me_endpoint_lists_roles_and_permissions(make_user, client_for, branches):
    client = client_for(make_user("branch_admin", branch=branches["PRM"]))
    body = client.get("/api/v1/auth/me/").json()
    assert body["roles"][0]["role"] == "branch_admin" and body["roles"][0]["branch"] == "PRM"
    assert "members.create" in body["permissions"] and "payroll.approve" not in body["permissions"]


# --- granting access ---------------------------------------------------------


def test_no_privilege_escalation_when_granting_roles(make_user, client_for):
    ops = make_user("operations_manager")  # may assign roles, but does not hold every CEO permission
    target = make_user()
    client = client_for(ops)
    response = client.post(
        "/api/v1/rbac/assignments/", {"user": target.id, "role": "ceo", "reason": "test"}, format="json"
    )
    assert response.status_code == 403
    # Instructors can teach; the Operations Manager can't, so can't hand that power out either.
    assert (
        client.post(
            "/api/v1/rbac/assignments/", {"user": target.id, "role": "instructor", "reason": "coach"}, format="json"
        ).status_code
        == 403
    )
    ok = client.post(
        "/api/v1/rbac/assignments/", {"user": target.id, "role": "branch_admin", "reason": "new admin"}, format="json"
    )
    assert ok.status_code == 201
    # Systems & IT (who manage roles) can grant it.
    it = client_for(make_user("it_admin"))
    assert (
        it.post(
            "/api/v1/rbac/assignments/", {"user": target.id, "role": "instructor", "reason": "coach"}, format="json"
        ).status_code
        == 201
    )


def test_cannot_change_own_access(make_user, client_for):
    it = make_user("it_admin")
    response = client_for(it).post(
        "/api/v1/rbac/assignments/", {"user": it.id, "role": "ceo", "reason": "x"}, format="json"
    )
    assert response.status_code == 400


def test_branch_admin_cannot_grant_roles(make_user, client_for, branches):
    client = client_for(make_user("branch_admin", branch=branches["PRM"]))
    target = make_user()
    assert (
        client.post(
            "/api/v1/rbac/assignments/", {"user": target.id, "role": "instructor", "reason": "x"}, format="json"
        ).status_code
        == 403
    )


def test_ending_a_role_takes_effect_immediately(make_user, client_for, branches, members):
    coach = make_user("instructor", branch=branches["PRM"])
    coach_client = client_for(coach)
    assert coach_client.get("/api/v1/members/").status_code == 200
    assignment = RoleAssignment.objects.get(user=coach)
    it_client = client_for(make_user("it_admin"))
    assert it_client.post(f"/api/v1/rbac/assignments/{assignment.id}/end/").status_code == 200
    # The coach's existing session was revoked.
    assert coach_client.get("/api/v1/members/").status_code == 403


def test_deactivated_user_is_logged_out_everywhere(make_user, client_for, members):
    user = make_user("operations_manager")
    client = client_for(user)
    assert client.get("/api/v1/members/").status_code == 200
    user.deactivate()
    assert client.get("/api/v1/members/").status_code == 403
    assert not RoleAssignment.objects.current().filter(user=user).exists()


def test_every_catalogue_role_exists():
    assert Role.objects.filter(code__in=["ceo", "branch_admin", "accountant", "guardian"]).count() == 4
