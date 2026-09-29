"""The staff desk, driven through its screens as each role would use it."""

import base64
import datetime
import io

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from PIL import Image

from apps.classes.models import Attendance, ClassChange, ClassSession, ClassSlot
from apps.classes.services import kuwait_weekday
from apps.members.models import Member, RulesAgreement
from apps.organization.models import PricingOption, Program
from apps.renewals.models import FollowUp
from apps.sales.models import AccountRequest, CashUp, Membership, Sale

PASSWORD = "Elite-Test-2026!"  # fictional test accounts from seed_kuwait
TODAY = timezone.localdate()


@pytest.fixture
def data(db):
    call_command("seed_kuwait", families=4, adults=3, verbosity=0)


def desk_client(who):
    from django.contrib.auth import get_user_model

    client = Client()
    client.force_login(get_user_model().objects.get(email=f"{who}@test.elite.local"))
    return client


def url(path, lang="en"):
    return f"/{lang}/desk/{path}"


def prm_member(**filters):
    return Member.objects.filter(branch__code="PRM", is_active=True, **filters).first()


def test_sign_in_page(data):
    client = Client()
    assert client.get(url("")).status_code == 302  # the desk needs a sign-in
    bad = client.post(url("sign-in/"), {"email": "admin.prm@test.elite.local", "password": "wrong-password"})
    assert "not correct" in bad.content.decode()
    ok = client.post(url("sign-in/"), {"email": "admin.prm@test.elite.local", "password": PASSWORD})
    assert ok.status_code == 302 and client.get(url("")).status_code == 200


def test_privileged_staff_must_set_up_two_factor(data, settings):
    settings.ENFORCE_PRIVILEGED_MFA = True
    response = desk_client("ops").get(url("approvals/"))
    assert response.status_code == 302 and response["Location"].endswith("/desk/two-factor/")


def test_every_screen_renders_in_both_languages(data):
    client = desk_client("ops")
    member = prm_member()
    session = ClassSession.objects.filter(branch__code="PRM").first()
    for lang in ("en", "ar"):
        for path in [
            "",
            "check-in/",
            "members/",
            "members/new/",
            f"members/{member.pk}/",
            "sell/",
            f"sell/?member={member.pk}",
            "sales/",
            "timetable/",
            "classes/",
            f"classes/{session.pk}/",
            "class-changes/",
            "approvals/",
            "cash-up/",
            "renewals/",
            "renewals/?tab=at_risk",
            "pricing/",
            "reports/",
            "leads/",
        ]:
            response = client.get(url(path, lang))
            assert response.status_code == 200, (lang, path)
            assert f'lang="{lang}"' in response.content.decode()


def test_roles_see_only_their_screens(data):
    coach = desk_client("coach.prm")
    assert coach.get(url("sell/")).status_code == 403
    assert coach.get(url("approvals/")).status_code == 403
    assert coach.get(url("classes/mine/")).status_code == 200
    bedaya_admin = desk_client("admin.bed")
    assert bedaya_admin.get(url(f"members/{prm_member().pk}/")).status_code == 404  # other branch's member


def test_register_a_child_with_consent_and_signed_rules(data):
    client = desk_client("admin.prm")
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "PNG")
    signature = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    response = client.post(
        url("members/new/"),
        {
            "m-first_name": "Salem",
            "m-last_name": "Deskregister",
            "m-date_of_birth": "2017-03-01",
            "m-gender": "male",
            "m-source": "walk_in",
            "r-guardian_name": "Test Parent",
            "r-guardian_mobile": "55512345",
            "r-guardian_relationship": "father",
            "r-emergency_name": "Aunt",
            "r-emergency_relationship": "Aunt",
            "r-emergency_mobile": "66612345",
            "r-consent_internal": "on",
            "r-signed_by_name": "Test Parent",
            "r-rules_accepted": "on",
            "r-signature": signature,
        },
    )
    member = Member.objects.get(last_name="Deskregister")
    assert response.status_code == 302 and member.branch.code == "PRM"
    assert member.guardian_links.get().guardian.mobile == "+96555512345"
    assert RulesAgreement.objects.filter(member=member).exists()
    assert member.media_consents.first().internal_records and not member.media_consents.first().website_marketing


def _session_now(branch_code="PRM"):
    """A class at this branch starting in 30 minutes (created for the test)."""
    now = timezone.localtime()
    start = (now + datetime.timedelta(minutes=30)).time().replace(second=0, microsecond=0)
    end = (now + datetime.timedelta(minutes=90)).time().replace(second=0, microsecond=0)
    if end <= start:
        start, end = datetime.time(22, 0), datetime.time(23, 30)
    program = Program.objects.filter(branch__code=branch_code).first()
    slot = ClassSlot.objects.create(
        branch=program.branch,
        program=program,
        title_en="Test class",
        ages_en="All",
        age_group="kids",
        weekday=kuwait_weekday(TODAY),
        start=start,
        end=end,
        valid_from=TODAY,
    )
    program.branch.open_days = list(range(7))
    program.branch.save()
    return ClassSession.objects.create(
        slot=slot,
        branch=program.branch,
        program=program,
        title_en="Test class",
        date=TODAY,
        start=start,
        end=end,
        capacity=10,
    )


def test_front_desk_check_in_with_and_without_membership(data):
    client = desk_client("admin.prm")
    session = _session_now()
    member = Member.objects.create(
        branch=session.branch, first_name="Walk", last_name="In", date_of_birth=datetime.date(2015, 1, 1), gender="male"
    )
    found = client.get(url(f"check-in/?q={member.qr_token}"))
    assert "Walk" in found.content.decode()  # the scanned card finds the member
    response = client.post(url("check-in/do/"), {"member": member.pk, "session": session.pk}, follow=True)
    assert "checked in" in response.content.decode().lower()
    visit = Attendance.objects.get(member=member, session=session)
    assert visit.warning == "no_membership" and visit.walk_in


def test_sell_membership_then_receipt(data):
    client = desk_client("admin.prm")
    member = prm_member()
    option = PricingOption.objects.filter(branch__code="PRM", kind="membership", approval="approved").first()
    response = client.post(
        url("sell/"),
        {
            "member": member.pk,
            "item_0": f"p:{option.pk}",
            "qty_0": "1",
            "pay_method_0": "knet",
            "pay_amount_0": str(option.price),
            "pay_ref_0": "TERM-001",
            "receipt": ["whatsapp"],
        },
    )
    sale = Sale.objects.latest("created_at")
    assert response.status_code == 302 and sale.total == option.price and sale.member == member
    receipt = client.get(url(f"sales/{sale.pk}/"))
    assert sale.reference in receipt.content.decode()
    wrong = client.post(
        url("sell/"),
        {
            "member": member.pk,
            "item_0": f"p:{option.pk}",
            "qty_0": "1",
            "pay_method_0": "cash",
            "pay_amount_0": "1.000",
        },
        follow=True,
    )
    assert "must equal the total" in wrong.content.decode()


def test_freeze_request_then_ops_approval(data):
    membership = (
        Membership.objects.filter(
            branch__code="PRM",
            status="active",
            freeze_used=False,
            end_date__gt=TODAY + datetime.timedelta(days=10),
            pricing_option__kind="membership",
        )
        .exclude(requests__status="pending")
        .first()
    )
    admin = desk_client("admin.prm")
    admin.post(
        url("requests/new/"),
        {
            "membership": membership.pk,
            "kind": "freeze",
            "freeze_start": str(TODAY),
            "freeze_weeks": "2",
            "reason": "Travelling",
        },
    )
    req = AccountRequest.objects.get(membership=membership, reason="Travelling")
    self_approve = desk_client("admin.prm").post(url(f"approvals/requests/{req.pk}/"), {"decision": "approve"})
    assert self_approve.status_code == 403  # admins cannot approve
    desk_client("ops").post(url(f"approvals/requests/{req.pk}/"), {"decision": "approve"})
    req.refresh_from_db()
    assert req.status == "approved"


def test_cash_up_submission(data):
    client = desk_client("admin.prm")
    response = client.post(url("cash-up/"), {"counted_cash": "0", "terminal_knet": "0", "terminal_card": "0"})
    assert response.status_code == 302
    assert CashUp.objects.get(branch__code="PRM", date=TODAY).status == "submitted"


def test_renewal_outcome_recorded(data):
    membership = Membership.objects.filter(branch__code="BED", pricing_option__kind="membership").first()
    desk_client("admin.bed").post(url(f"renewals/{membership.pk}/"), {"outcome": "N", "channel": "call"})
    assert FollowUp.objects.get(membership=membership).outcome == "N"


def test_class_change_request_and_approval(data):
    session = ClassSession.objects.filter(branch__code="PRM", date__gt=TODAY, status="scheduled").first()
    desk_client("coach.prm").post(url(f"classes/{session.pk}/change/"), {"kind": "cancel", "reason": "Unwell"})
    change = ClassChange.objects.get(session=session, reason="Unwell")
    desk_client("training").post(url(f"class-changes/{change.pk}/decide/"), {"decision": "approve"})
    session.refresh_from_db()
    assert session.status == "cancelled"


def test_new_timetable_class_creates_sessions(data):
    client = desk_client("ops")
    program = Program.objects.filter(branch__code="PRM").first()
    client.post(
        url("timetable/new/"),
        {
            "program": program.pk,
            "title_en": "New class",
            "ages_en": "Kids",
            "age_group": "kids",
            "focus": "",
            "weekday": "0",
            "start": "15:00",
            "end": "16:00",
            "capacity": "12",
            "valid_from": str(TODAY),
            "is_public": "on",
            "is_active": "on",
        },
    )
    slot = ClassSlot.objects.get(title_en="New class")
    assert ClassSession.objects.filter(slot=slot).count() >= 3


def test_member_photo_is_private(data):
    member = prm_member()
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, "JPEG")
    buf.name = "photo.jpg"
    client = desk_client("admin.prm")
    from django.core.files.uploadedfile import SimpleUploadedFile

    client.post(
        url(f"members/{member.pk}/photo/"),
        {"photo": SimpleUploadedFile("photo.jpg", buf.getvalue(), content_type="image/jpeg")},
    )
    member.refresh_from_db()
    assert member.photo
    assert client.get(url(f"members/{member.pk}/photo.jpg")).status_code == 200
    assert Client().get(url(f"members/{member.pk}/photo.jpg")).status_code == 302  # signed-out: to sign-in
    assert not member.photo.path.startswith(str(__import__("django.conf").conf.settings.MEDIA_ROOT))
    member.photo.delete(save=False)


def test_website_schedule_follows_the_desk_timetable(data):
    call_command("seed_website", verbosity=0)
    slot = ClassSlot.objects.filter(branch__code="PRM", is_public=True).first()
    slot.title_en = "Desk-edited class"
    slot.save()
    assert "Desk-edited class" in Client().get("/en/schedule/").content.decode()
    slot.is_public = False
    slot.save()
    assert "Desk-edited class" not in Client().get("/en/schedule/").content.decode()
