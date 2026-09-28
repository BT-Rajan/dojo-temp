"""Authentication, audit trail and hardening controls (ISO/IEC 27001:2022 Annex A)."""

import pytest
from django.db import connection
from django.test import override_settings
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from apps.audit.chain import seal_pending, verify_chain
from apps.audit.models import AuditEvent

from .conftest import CHILD_CIVIL_ID, OTHER_CIVIL_ID, PASSWORD

pytestmark = pytest.mark.django_db


def login(client, email, password=PASSWORD, **extra):
    return client.post("/api/v1/auth/login/", {"email": email, "password": password, **extra}, format="json")


# --- A.8.5 Secure authentication ---------------------------------------------


def test_login_and_logout(make_user):
    user = make_user("operations_manager")
    client = APIClient()
    response = login(client, user.email)
    assert response.status_code == 200 and response.json()["user"]["email"] == user.email
    assert client.get("/api/v1/members/").status_code == 200
    assert client.post("/api/v1/auth/logout/").status_code == 204
    assert client.get("/api/v1/members/").status_code == 403


def test_wrong_password_is_refused_and_logged(make_user):
    user = make_user("operations_manager")
    assert login(APIClient(), user.email, "wrong-password").status_code == 401
    assert AuditEvent.objects.filter(action="login_failed", object_id=user.email).exists()


def test_account_locks_after_five_failures(make_user):
    user = make_user("operations_manager")
    client = APIClient()
    for _ in range(5):
        login(client, user.email, "wrong-password")
    # Even the right password is refused while locked out.
    assert login(client, user.email).status_code == 429
    assert AuditEvent.objects.filter(action="login_locked_out").exists()


def test_login_requires_csrf_token(make_user):
    user = make_user("operations_manager")
    client = APIClient(enforce_csrf_checks=True)
    assert login(client, user.email).status_code == 403
    token = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
    response = client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json", HTTP_X_CSRFTOKEN=token
    )
    assert response.status_code == 200


def test_weak_passwords_are_rejected(make_user, client_for):
    client = client_for(make_user("instructor"))
    response = client.post(
        "/api/v1/auth/change-password/", {"current_password": PASSWORD, "new_password": "12345678"}, format="json"
    )
    assert response.status_code == 400


@override_settings(ENFORCE_PRIVILEGED_MFA=True)
def test_privileged_roles_must_use_two_factor(make_user, members):
    user = make_user("operations_manager")
    client = APIClient()
    assert login(client, user.email).status_code == 200
    me = client.get("/api/v1/auth/me/").json()
    assert me["mfa_setup_required"] is True
    assert client.get("/api/v1/members/").status_code == 403  # blocked until 2FA is set up

    otpauth = client.post("/api/v1/auth/mfa/setup/").json()["otpauth_url"]
    assert otpauth.startswith("otpauth://totp/")
    device = TOTPDevice.objects.get(user=user)
    code = f"{totp(device.bin_key):06d}"
    assert client.post("/api/v1/auth/mfa/confirm/", {"otp_token": code}, format="json").status_code == 204
    assert client.get("/api/v1/members/").status_code == 200

    # A new login now needs the code.
    fresh = APIClient()
    first = login(fresh, user.email)
    assert first.status_code == 401 and first.json()["otp_required"] is True


@override_settings(ENFORCE_PRIVILEGED_MFA=True)
def test_non_privileged_roles_do_not_need_two_factor(make_user, branches, members):
    user = make_user("branch_admin", branch=branches["PRM"])
    client = APIClient()
    login(client, user.email)
    assert client.get("/api/v1/members/").status_code == 200


# --- A.8.15 Logging -----------------------------------------------------------


def test_changes_are_audited_with_sensitive_values_redacted(make_user, client_for, members):
    user = make_user("operations_manager")
    m = members["prm1"]
    client_for(user).patch(
        f"/api/v1/members/{m.id}/",
        {"first_name": "Changed", "civil_id": OTHER_CIVIL_ID, "version": m.version},
        format="json",
    )
    event = AuditEvent.objects.filter(action="update", object_type="Member", object_id=str(m.id)).first()
    assert event is not None and event.actor_id == user.id
    assert event.changes["first_name"] == ["Fahad", "Changed"]
    assert event.changes["civil_id"] == "[redacted]"
    assert CHILD_CIVIL_ID not in str(event.changes) and OTHER_CIVIL_ID not in str(event.changes)


def test_denied_access_is_audited(make_user, client_for, members):
    client_for(make_user("accountant")).get("/api/v1/members/")
    assert AuditEvent.objects.filter(action="access_denied").exists()


def test_audit_events_cannot_be_edited_or_deleted(make_user):
    event = AuditEvent.objects.create(action="test")
    event.action = "tampered"
    with pytest.raises(PermissionError):
        event.save()
    with pytest.raises(PermissionError):
        event.delete()
    with pytest.raises(PermissionError):
        AuditEvent.objects.all().delete()


def test_audit_chain_detects_tampering(make_user):
    for i in range(5):
        AuditEvent.objects.create(action=f"event-{i}")
    seal_pending()
    assert verify_chain()["ok"] is True
    target = AuditEvent.objects.filter(action="event-2").first()
    with connection.cursor() as cursor:  # simulate someone editing the table directly
        cursor.execute("UPDATE audit_auditevent SET action='innocent' WHERE id=%s", [target.id])
    result = verify_chain()
    assert result["ok"] is False and str(target.id) in result["problem"]


def test_only_authorised_roles_read_the_audit_log(make_user, client_for):
    assert client_for(make_user("branch_admin")).get("/api/v1/audit/events/").status_code == 403
    assert client_for(make_user("it_admin")).get("/api/v1/audit/events/").status_code == 200


# --- A.8.9 / A.8.26 Hardening -------------------------------------------------


def test_api_responses_are_not_cached_and_carry_security_headers(make_user, client_for):
    response = client_for(make_user("operations_manager")).get("/api/v1/auth/me/")
    assert response["Cache-Control"] == "no-store"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "DENY"
    assert "X-Request-ID" in response


def test_health_endpoint_is_public_and_minimal(anon):
    response = anon.get("/healthz")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
