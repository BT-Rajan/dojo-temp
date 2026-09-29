"""Many people using the system at once: no lost updates, no corrupted counters."""

import threading

import pytest
from django.db import close_old_connections, connections, transaction
from django.db.models import F

from apps.members.models import Member


@pytest.mark.django_db
def test_second_editor_with_stale_version_gets_conflict(make_user, client_for, members):
    m = members["prm1"]
    alice = client_for(make_user("operations_manager"))
    bob = client_for(make_user("operations_manager"))
    loaded_version = alice.get(f"/api/v1/members/{m.id}/").json()["version"]

    first = alice.patch(
        f"/api/v1/members/{m.id}/", {"first_name": "Alice-edit", "version": loaded_version}, format="json"
    )
    assert first.status_code == 200 and first.json()["version"] == loaded_version + 1

    second = bob.patch(f"/api/v1/members/{m.id}/", {"first_name": "Bob-edit", "version": loaded_version}, format="json")
    assert second.status_code == 409
    assert Member.objects.get(pk=m.id).first_name == "Alice-edit"


@pytest.mark.django_db
def test_update_without_version_is_refused(make_user, client_for, members):
    client = client_for(make_user("operations_manager"))
    response = client.patch(f"/api/v1/members/{members['prm1'].id}/", {"first_name": "X"}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db(transaction=True, serialized_rollback=True)  # keep Wagtail's migration data
def test_simultaneous_saves_only_one_wins(branches):
    """Ten users press Save on the same record at the same moment against real MySQL: exactly one succeeds."""
    member = Member.objects.create(
        branch=branches["PRM"], first_name="Race", last_name="Test", gender="male", date_of_birth="2015-01-01"
    )
    start = threading.Barrier(10)
    results = []

    def attempt():
        close_old_connections()
        try:
            start.wait()
            with transaction.atomic():
                won = Member.objects.filter(pk=member.pk, version=1).update(version=F("version") + 1)
            results.append(won)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == [0] * 9 + [1]
    assert Member.objects.get(pk=member.pk).version == 2


@pytest.mark.django_db(transaction=True, serialized_rollback=True)  # keep Wagtail's migration data
def test_row_lock_keeps_counters_correct(branches):
    """Pattern used for stock and class places: 20 concurrent increments, none lost."""
    member = Member.objects.create(
        branch=branches["BED"], first_name="Count", last_name="Test", gender="male", date_of_birth="2015-01-01"
    )

    def bump():
        close_old_connections()
        try:
            with transaction.atomic():
                row = Member.objects.select_for_update().get(pk=member.pk)
                row.version = row.version + 1
                row.save(update_fields=["version"])
        finally:
            connections.close_all()

    threads = [threading.Thread(target=bump) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert Member.objects.get(pk=member.pk).version == 21


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_two_desks_booking_the_last_place_and_selling_at_once(branches):
    """Phase 1: one class place, ten people at once — exactly one gets it; receipt numbers never repeat."""
    import datetime
    from decimal import Decimal

    from django.utils import timezone

    from apps.classes.models import Booking, ClassSession
    from apps.classes.services import book
    from apps.organization.models import PricingOption, Program
    from apps.rbac.models import Role, RoleAssignment
    from apps.rbac.sync import sync_rbac
    from apps.sales import services as sales
    from apps.sales.models import Sale

    sync_rbac()
    from django.contrib.auth import get_user_model

    desk = get_user_model().objects.create_user(email="desk@example.test", password="x" * 12, full_name="Desk")
    RoleAssignment.objects.create(
        user=desk, role=Role.objects.get(code="branch_admin"), branch=branches["PRM"], reason="test"
    )
    program = Program.objects.create(branch=branches["PRM"], name="P", name_ar="P")
    tomorrow = timezone.localdate() + datetime.timedelta(days=1)
    session = ClassSession.objects.create(
        branch=branches["PRM"],
        program=program,
        title_en="Class",
        date=tomorrow,
        start=datetime.time(17, 0),
        end=datetime.time(18, 0),
        capacity=1,
    )
    option = PricingOption.objects.create(
        branch=branches["PRM"], name="Trial", kind="trial", price=Decimal("10"), duration_days=1, approval="approved"
    )
    errors = []

    def one_booking(i):
        close_old_connections()
        try:
            book(session, desk, guest_name=f"Guest {i}", guest_mobile=f"5550{i:04d}")
            cart = sales.Cart(items=[sales.Item(pricing_option=option)], payments=[sales.Pay("cash", Decimal("10"))])
            sales.sell(branch=branches["PRM"], user=desk, cart=cart, customer_name=f"Guest {i}")
        except Exception as exc:  # noqa: BLE001 - collected and asserted below
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=one_booking, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert Booking.objects.filter(session=session, status="booked").count() == 1
    assert Booking.objects.filter(session=session, status="waitlisted").count() == 9
    numbers = sorted(Sale.objects.values_list("number", flat=True))
    assert numbers == list(range(1, 11))
