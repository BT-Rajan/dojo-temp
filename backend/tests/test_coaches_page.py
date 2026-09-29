"""The Coaches pages for the CEO and the Operations Manager (fictional seed data)."""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client


@pytest.fixture
def data(db):
    call_command("seed_kuwait", families=2, adults=1, verbosity=0)


def login(who):
    c = Client()
    c.force_login(get_user_model().objects.get(email=f"{who}@test.elite.local"))
    return c


def test_coaches_list_and_profile(data):
    coach = get_user_model().objects.get(email="coach.prm@test.elite.local")
    for who in ("ceo", "ops"):
        client = login(who)
        for lang in ("en", "ar"):
            page = client.get(f"/{lang}/desk/coaches/")
            assert page.status_code == 200
            assert (coach.full_name_ar if lang == "ar" else coach.full_name) in page.content.decode()
            assert client.get(f"/{lang}/desk/coaches/{coach.pk}/").status_code == 200
            assert client.get(f"/{lang}/desk/coaches/?branch=BED&month=2026-01").status_code == 200
    # The CEO is not listed as a coach; staff who don't manage people can't open the page.
    ceo = get_user_model().objects.get(email="ceo@test.elite.local")
    assert login("ops").get(f"/en/desk/coaches/{ceo.pk}/").status_code == 404
    for who in ("coach.prm", "admin.prm", "marketing"):
        assert login(who).get("/en/desk/coaches/").status_code == 403
