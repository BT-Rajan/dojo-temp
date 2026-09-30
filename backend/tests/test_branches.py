"""Adding and managing branches from the desk (decision P7-12)."""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import Client

from apps.organization import services as org
from apps.organization.models import Branch, Discipline, Program

DETAILS = dict(name="Elite Khaitan", name_ar="إيليت خيطان", area="Khaitan", open_days=["0", "1", "2", "3", "4"])


def client_for(user):
    c = Client()
    c.force_login(user)
    return c


def test_add_branch_rules_and_checklist(branches, make_user):
    ceo, om, admin = (
        make_user("ceo"),
        make_user("operations_manager"),
        make_user("branch_admin", branch=branches["PRM"]),
    )
    with pytest.raises(PermissionDenied):
        org.create_branch(admin, code="KHT", **DETAILS)
    with pytest.raises(ValidationError):
        org.create_branch(om, code="PRM", **DETAILS)  # code already used
    with pytest.raises(ValidationError):
        org.create_branch(om, code="K1", **DETAILS)  # letters only
    with pytest.raises(ValidationError):
        org.create_branch(om, code="KHT", **{**DETAILS, "open_days": []})
    b = org.create_branch(om, code="kht", phone="2222 3333", **DETAILS)
    assert b.code == "KHT" and b.open_days == [0, 1, 2, 3, 4] and b.phone == "22223333" and b.is_active
    checks = {c["key"]: c["done"] for c in org.branch_checklist(b)}
    assert not any(checks.values())
    disc = Discipline.objects.create(code="kajukenbo-t", name="Kajukenbo", name_ar="كاجوكينبو")
    org.save_program(om, b, name="Kids 6-12", name_ar="أطفال", disciplines=[disc], age_min=6, age_max=12)
    with pytest.raises(ValidationError):
        org.save_program(om, b, name="Kids 6-12", name_ar="أطفال", disciplines=[disc])  # duplicate name
    assert {c["key"]: c["done"] for c in org.branch_checklist(b)}["programs"]
    org.update_branch(ceo, b, **{**DETAILS, "address": "Khaitan Mall"})
    b.refresh_from_db()
    assert b.address == "Khaitan Mall"


def test_close_and_reopen(branches, make_user):
    om = make_user("operations_manager")
    b = org.create_branch(om, code="KHT", **DETAILS)
    with pytest.raises(ValidationError):
        org.close_branch(om, b, "")
    org.close_branch(om, b, "Lease ended")
    b.refresh_from_db()
    assert not b.is_active
    org.reopen_branch(om, b)
    b.refresh_from_db()
    assert b.is_active


def test_branch_with_members_cannot_close(db):
    call_command("seed_kuwait", families=2, adults=1, verbosity=0)
    from django.contrib.auth import get_user_model

    om = get_user_model().objects.get(email="ops@test.elite.local")
    prm = Branch.objects.get(code="PRM")
    assert org.closing_blockers(prm)
    with pytest.raises(ValidationError):
        org.close_branch(om, prm, "Test")


def test_branch_pages(branches, make_user):
    om = make_user("operations_manager")
    c = client_for(om)
    for lang in ("en", "ar"):
        assert c.get(f"/{lang}/desk/management/branches/").status_code == 200
        assert c.get(f"/{lang}/desk/management/branches/new/").status_code == 200
    r = c.post(
        "/en/desk/management/branches/new/",
        {"code": "SLM", "name": "Elite Salmiya", "name_ar": "إيليت السالمية", "area": "Salmiya",
         "open_days": ["0", "1", "2"]},
    )  # fmt: skip
    assert r.status_code == 302
    b = Branch.objects.get(code="SLM")
    for lang in ("en", "ar"):
        assert c.get(f"/{lang}/desk/management/branches/{b.pk}/").status_code == 200
    disc = Discipline.objects.create(code="kick-t", name="Kickboxing", name_ar="كيك بوكسينغ")
    c.post(
        f"/en/desk/management/branches/{b.pk}/",
        {"action": "program", "p_name": "Adults", "p_name_ar": "كبار", "disciplines": [disc.pk], "audience": "any"},
    )
    assert Program.objects.filter(branch=b, name="Adults").exists()
    assert client_for(make_user("instructor")).get("/en/desk/management/branches/").status_code == 403
