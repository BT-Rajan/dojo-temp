"""Website (elitemaacademy.com): pages in both languages, trial booking, portal sign-in, shop, gallery consent, SAQR."""

import re
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.test import Client
from wagtail.images.models import Image
from wagtail.images.tests.utils import get_test_image_file

from apps.core.messaging import last_message_to
from apps.members.models import MediaConsent
from apps.shop.models import Order, Product
from apps.website.models import AlbumPage, AlbumPhoto, ContactMessage, TrialRequest

PAGES = [
    "/{l}/",
    "/{l}/programs/",
    "/{l}/programs/kajukenbo/",
    "/{l}/branches/",
    "/{l}/branches/elite-promenade/",
    "/{l}/branches/elite-bedaya/",
    "/{l}/schedule/",
    "/{l}/events/",
    "/{l}/events/camp-3/",
    "/{l}/gallery/",
    "/{l}/gallery/album-1/",
    "/{l}/shop/",
    "/{l}/shop/boxing-gloves/",
    "/{l}/shop/cart/",
    "/{l}/about/",
    "/{l}/contact/",
    "/{l}/book-a-trial/",
    "/{l}/portal/",
]


@pytest.fixture
def site(branches):
    call_command("seed_website", verbosity=0)


@pytest.fixture
def web():
    return Client()


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_every_page_renders_in_both_languages(site, web, lang):
    for url in PAGES:
        response = web.get(url.format(l=lang))
        assert response.status_code == 200, url
        html = response.content.decode()
        assert f'<html lang="{lang}" dir="{"rtl" if lang == "ar" else "ltr"}">' in html
        assert "Content-Security-Policy" in response.headers
        assert "[Instructor name]" not in html  # unpublished placeholders never reach the public site


def test_money_is_three_decimals_with_western_digits(site, web):
    html = web.get("/ar/branches/elite-bedaya/").content.decode()
    assert '<span class="ea-num" dir="ltr">65.000</span> د.ك' in html


def test_trial_booking_prefill_error_and_confirmation(site, web):
    page = web.get("/en/book-a-trial/?branch=BED&source=schedule").content.decode()
    assert 'id="tf-b-BED" value="BED" checked' in page

    bad = web.post("/en/book-a-trial/", {"form": "trial", "name": "Sara", "mobile": "5551 23", "branch": "PRM"})
    assert bad.status_code == 200
    assert "Please enter an 8-digit Kuwaiti number." in bad.content.decode()
    assert TrialRequest.objects.count() == 0

    ok = web.post(
        "/ar/book-a-trial/",
        {
            "form": "trial",
            "name": "Sara Test",
            "mobile": "٥٥٥١ ٢٣٤٥",
            "branch": "PRM",
            "program": "unsure",
            "source": "schedule",
        },
    )
    assert ok.status_code == 302 and "sent=trial" in ok["Location"]
    lead = TrialRequest.objects.get()
    assert lead.mobile == "+96555512345" and lead.not_sure and lead.language == "ar" and lead.source == "schedule"
    done = web.get(ok["Location"]).content.decode()
    assert "Sara" in done and "+96555512345" not in done


def test_trial_honeypot_is_silently_dropped(site, web):
    response = web.post(
        "/en/book-a-trial/",
        {"form": "trial", "name": "Bot", "mobile": "55512345", "branch": "PRM", "website": "http://spam.example"},
    )
    assert response.status_code == 302
    assert TrialRequest.objects.count() == 0


def test_contact_form(site, web):
    response = web.post(
        "/en/contact/",
        {"form": "contact", "name": "Noura", "mobile": "99887766", "branch": "BED", "message": "School visit?"},
    )
    assert response.status_code == 302
    assert ContactMessage.objects.get().branch.code == "BED"


def test_portal_sign_in_with_whatsapp_code(site, web, family):
    # Unknown numbers get the same answer and no message (no account discovery).
    unknown = web.post("/en/portal/", {"action": "send", "mobile": "66554433"})
    assert unknown.status_code == 302 and last_message_to("+96566554433") is None

    web.post("/en/portal/", {"action": "send", "mobile": "5000 0001"})
    code = re.search(r"\b(\d{4})\b", last_message_to("+96550000001")["text"]).group(1)
    wrong = "0000" if code != "0000" else "1111"
    bad = web.post("/en/portal/", {"action": "verify", **{f"d{i}": d for i, d in enumerate(wrong)}})
    assert "That code doesn&#x27;t match" in bad.content.decode()

    ok = web.post("/en/portal/", {"action": "verify", **{f"d{i}": d for i, d in enumerate(code)}})
    assert ok.status_code == 302
    family_page = web.get("/en/portal/").content.decode()
    assert "Ali" in family_page and "Fahad" not in family_page  # only this parent's own child


def test_portal_code_is_single_use(site, web, family):
    web.post("/en/portal/", {"action": "send", "mobile": "50000001"})
    code = re.search(r"\b(\d{4})\b", last_message_to("+96550000001")["text"]).group(1)
    web.post("/en/portal/", {"action": "verify", "code": code})
    other = Client()
    other.post("/en/portal/", {"action": "send", "mobile": "50000001"})
    replay = other.post("/en/portal/", {"action": "verify", "code": code})
    assert replay.status_code == 200  # the old code no longer signs anyone in


def _add_to_cart(web, slug="boxing-gloves", size="12 oz", qty=1):
    product = Product.objects.get(slug=slug)
    variant = product.variants.get(size=size)
    web.post(f"/en/shop/{slug}/", {"variant": variant.pk, "qty": qty})
    return variant


def _checkout(web):
    return web.post(
        "/en/shop/checkout/",
        {"name": "Parent Test", "mobile": "55512345", "fulfilment": "pickup", "branch": "BED", "payment": "knet"},
    )


def test_shop_checkout_paid_and_failed(site, web):
    variant = _add_to_cart(web, qty=2)
    stock = variant.stock
    start = _checkout(web)
    assert start.status_code == 302 and "/pay/test/" in start["Location"]
    order = Order.objects.get()
    variant.refresh_from_db()
    assert variant.stock == stock - 2 and order.total == Decimal("37.000")

    # The test gateway's page links back with a signed outcome.
    gateway = web.get(start["Location"]).content.decode()
    decline = re.search(r'href="([^"]*outcome=decline[^"]*)"', gateway).group(1).replace("&amp;", "&")
    failed = web.get(decline)
    assert "you haven't been charged" in failed.content.decode()
    order.refresh_from_db()
    variant.refresh_from_db()
    assert order.status == Order.Status.FAILED and variant.stock == stock  # stock released, cart kept

    again = _checkout(web)
    gateway = web.get(again["Location"]).content.decode()
    approve = re.search(r'href="([^"]*outcome=approve[^"]*)"', gateway).group(1).replace("&amp;", "&")
    paid = web.get(approve)
    assert paid.status_code == 302 and "/order/" in paid["Location"]
    assert Order.objects.filter(status=Order.Status.PAID).count() == 1


def test_shop_forged_payment_return_is_rejected(site, web):
    _add_to_cart(web)
    _checkout(web)
    order = Order.objects.get()
    web.get(f"/en/shop/pay/return/{order.reference}/?outcome=approve&sig=forged")
    order.refresh_from_db()
    assert order.status != Order.Status.PAID


def test_sold_out_size_cannot_be_added(site, web):
    _add_to_cart(web, size="8 oz")
    assert web.get("/en/shop/cart/").context["lines"] == []


def test_other_visitors_cannot_see_an_order(site, web):
    _add_to_cart(web)
    _checkout(web)
    order = Order.objects.get()
    assert Client().get(f"/en/shop/order/{order.reference}/").status_code == 404


def test_gallery_shows_photos_only_with_consent(site, web, members):
    album = AlbumPage.objects.get(slug="album-1")
    image = Image.objects.create(title="test", file=get_test_image_file())
    child = members["prm1"]
    photo = AlbumPhoto.objects.create(album=album, image=image, reviewed=True)
    photo.tagged_members.add(child)
    assert not photo.is_public  # no consent on file
    MediaConsent.objects.create(member=child, signed_by_name="Parent", website_marketing=True)
    assert AlbumPhoto.objects.get(pk=photo.pk).is_public
    unreviewed = AlbumPhoto.objects.create(album=album, image=image, reviewed=False)
    assert not unreviewed.is_public
    assert len(album.public_photos()) == 1


def test_saqr_answers_and_hands_off(site, anon):
    price = anon.post("/api/v1/saqr/", {"message": "How much is it at Bedaya?", "lang": "en"}, format="json")
    assert price.status_code == 200 and "65.000 KD" in price.data["text"]
    refund = anon.post("/api/v1/saqr/", {"message": "أريد استرجاع المبلغ", "lang": "ar"}, format="json")
    assert refund.data["handoff"] is True


def test_cms_needs_the_cms_role(site, make_user):
    coach = Client()
    coach.force_login(make_user("instructor"))
    assert coach.get("/cms/").status_code == 403
    editor_user = make_user("marketing_staff")
    editor = Client()
    editor.force_login(editor_user)
    assert editor.get("/cms/").status_code == 200
    assert editor_user.groups.filter(name="Editors").exists()


def test_leads_api_is_branch_scoped(site, web, make_user, client_for, branches):
    for code in ("PRM", "BED"):
        web.post("/en/book-a-trial/", {"form": "trial", "name": f"Lead {code}", "mobile": "55512345", "branch": code})
    admin_prm = make_user("branch_admin", branch=branches["PRM"])
    rows = client_for(admin_prm).get("/api/v1/website/trial-requests/").data
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert [r["branch_code"] for r in rows] == ["PRM"]
    assert client_for(make_user("instructor")).get("/api/v1/website/trial-requests/").status_code == 403
