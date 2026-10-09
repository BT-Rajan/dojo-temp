"""The review (staging) server: a private test-account password and no search engines."""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.test import Client, override_settings


def test_review_password_replaces_the_published_one(db, monkeypatch):
    User = get_user_model()
    user = User.objects.create_user(email="ops@test.elite.local", password="Elite-Test-2026!", full_name="Ops")
    other = User.objects.create_user(email="real@example.test", password="Someone-Else-2026!", full_name="Real")
    monkeypatch.setenv("REVIEW_PASSWORD", "Rv-Private-Review-77")
    call_command("set_review_password", verbosity=0)
    user.refresh_from_db()
    other.refresh_from_db()
    assert user.check_password("Rv-Private-Review-77") and not user.check_password("Elite-Test-2026!")
    assert other.check_password("Someone-Else-2026!")  # only the fictional test accounts
    monkeypatch.setenv("REVIEW_PASSWORD", "short")
    with pytest.raises(ValidationError):
        call_command("set_review_password", verbosity=0)
    with override_settings(ENVIRONMENT="production"), pytest.raises(CommandError):
        call_command("set_review_password", verbosity=0)


@override_settings(ENVIRONMENT="staging")
def test_review_server_is_hidden_from_search_engines(db):
    assert Client().get("/robots.txt").content.decode() == "User-agent: *\nDisallow: /\n"
