import datetime
import random

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.members.models import Guardian, GuardianLink, Member
from apps.organization.models import Branch
from apps.rbac.models import Role, RoleAssignment
from apps.rbac.sync import sync_rbac
from apps.testdata.kuwait import make_civil_id

PASSWORD = "Correct-Horse-Battery-9"
CHILD_DOB = datetime.date(2016, 5, 10)
CHILD_CIVIL_ID = make_civil_id(random.Random(7), CHILD_DOB, set())
OTHER_CIVIL_ID = make_civil_id(random.Random(8), CHILD_DOB, {CHILD_CIVIL_ID})


@pytest.fixture(autouse=True)
def _rbac(db):
    sync_rbac()


@pytest.fixture
def branches(db):
    prm = Branch.objects.create(code="PRM", name="Elite Promenade", name_ar="إيليت بروميناد", area="Hawalli")
    bed = Branch.objects.create(code="BED", name="Elite Bedaya", name_ar="إيليت بداية", area="Sabah Al Salem")
    return {"PRM": prm, "BED": bed}


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(*roles, branch=None, email=None):
        counter["n"] += 1
        user = get_user_model().objects.create_user(
            email=email or f"user{counter['n']}@example.test", password=PASSWORD, full_name=f"User {counter['n']}"
        )
        for role in roles:
            RoleAssignment.objects.create(user=user, role=Role.objects.get(code=role), branch=branch, reason="test")
        return user

    return _make


@pytest.fixture
def client_for():
    def _client(user):
        client = APIClient()
        client.force_login(user)
        return client

    return _client


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def members(branches):
    """Two members per branch; one Promenade child has medical notes and a Civil ID."""
    common = dict(gender="male", date_of_birth=CHILD_DOB)
    return {
        "prm1": Member.objects.create(
            branch=branches["PRM"],
            first_name="Fahad",
            last_name="Al-Test",
            civil_id=CHILD_CIVIL_ID,
            medical_notes="Asthma",
            **common,
        ),
        "prm2": Member.objects.create(branch=branches["PRM"], first_name="Omar", last_name="Al-Test", **common),
        "bed1": Member.objects.create(branch=branches["BED"], first_name="Ali", last_name="Al-Test", **common),
        "bed2": Member.objects.create(branch=branches["BED"], first_name="Hamad", last_name="Al-Test", **common),
    }


@pytest.fixture
def family(members, make_user):
    parent = make_user("guardian")
    guardian = Guardian.objects.create(full_name="Parent", mobile="+96550000001", user=parent)
    GuardianLink.objects.create(guardian=guardian, member=members["bed1"], relationship="father", is_primary=True)
    return parent
