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
